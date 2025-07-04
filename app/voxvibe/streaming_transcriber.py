#!/usr/bin/env python3
"""Streaming transcriber using WhisperFlow for real-time transcription with partial results."""

import asyncio
import time
import threading
from typing import Optional, Callable, Any
from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# Note: WhisperFlow has Python version compatibility issues with 3.12
# Using our own streaming implementation based on faster-whisper
WHISPERFLOW_AVAILABLE = False

from .transcriber import Transcriber  # Fallback to original transcriber
from .llm_processor import LLMProcessor


@dataclass
class TranscriptionResult:
    """Result from streaming transcription"""
    text: str
    is_partial: bool
    end_time: float
    confidence: float = 0.0


class StreamingTranscriber(QObject):
    """
    Streaming transcriber that provides real-time partial results using WhisperFlow.
    Falls back to batch transcription if WhisperFlow is not available.
    """
    
    # Signals for real-time updates
    partial_result = pyqtSignal(str, float)  # text, confidence
    final_result = pyqtSignal(str, float)    # text, confidence
    final_result_with_context = pyqtSignal(str, float, str)  # text, confidence, context_type
    transcription_started = pyqtSignal()
    transcription_finished = pyqtSignal()
    llm_processing_started = pyqtSignal()
    llm_processing_finished = pyqtSignal(str)  # cleaned_text
    error_occurred = pyqtSignal(str)
    
    def __init__(self, model_size="base", prefer_streaming=True, openai_api_key=None):
        super().__init__()
        self.model_size = model_size
        self.prefer_streaming = prefer_streaming and WHISPERFLOW_AVAILABLE
        
        # Initialize models
        self.whisper_model = None
        self.fallback_transcriber = None
        self.llm_processor = None
        
        # State
        self.is_transcribing = False
        self.current_session = None
        
        # Initialize the appropriate transcriber
        self._initialize_transcriber()
        
        # Initialize LLM processor
        self._initialize_llm_processor(openai_api_key)
    
    def _initialize_transcriber(self):
        """Initialize the appropriate transcriber based on availability"""
        # Always use our custom streaming implementation
        self.fallback_transcriber = Transcriber(model_size=self.model_size)
        print("✅ Custom streaming transcriber initialized")
    
    def _initialize_llm_processor(self, api_key=None):
        """Initialize the LLM processor for text cleanup"""
        try:
            self.llm_processor = LLMProcessor(api_key=api_key, model="gpt-4.1-nano")
            
            # Connect LLM processor signals
            self.llm_processor.processing_started.connect(self.llm_processing_started.emit)
            self.llm_processor.processing_finished.connect(self._on_llm_finished)
            self.llm_processor.processing_finished_with_context.connect(self._on_llm_finished_with_context)
            self.llm_processor.processing_failed.connect(self._on_llm_failed)
            
            if self.llm_processor.is_enabled():
                print("✅ LLM post-processor initialized")
            else:
                print("⚠️ LLM post-processor disabled")
        except Exception as e:
            print(f"⚠️ Failed to initialize LLM processor: {e}")
            self.llm_processor = None
    
    def transcribe_streaming(self, audio_data: np.ndarray, language="en") -> None:
        """
        Start streaming transcription with real-time partial results.
        Results are emitted via signals.
        """
        if self.is_transcribing:
            print("⚠️ Already transcribing, ignoring new request")
            return
        
        self.is_transcribing = True
        self.transcription_started.emit()
        
        if self.prefer_streaming and self.whisper_model:
            # Use streaming transcription in a separate thread
            thread = threading.Thread(
                target=self._stream_transcribe_worker,
                args=(audio_data, language),
                daemon=True
            )
            thread.start()
        else:
            # Use batch transcription as fallback
            thread = threading.Thread(
                target=self._batch_transcribe_worker,
                args=(audio_data, language),
                daemon=True
            )
            thread.start()
    
    def _stream_transcribe_worker(self, audio_data: np.ndarray, language: str):
        """Worker thread for streaming transcription"""
        try:
            print("🎯 Starting streaming transcription...")
            
            # Convert numpy array to the format expected by WhisperFlow
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Normalize audio if needed
            if np.max(np.abs(audio_data)) > 1.0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Convert to PCM chunks for streaming
            chunk_size = 1024  # 1024 samples per chunk
            chunks = []
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                # Convert to bytes (16-bit PCM)
                chunk_bytes = (chunk * 32767).astype(np.int16).tobytes()
                chunks.append(chunk_bytes)
            
            # Create async session for streaming
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._async_transcribe_chunks(chunks, language))
            finally:
                loop.close()
                
        except Exception as e:
            print(f"❌ Streaming transcription error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.is_transcribing = False
            self.transcription_finished.emit()
    
    async def _async_transcribe_chunks(self, chunks: list, language: str):
        """Custom async transcription with simulated streaming"""
        try:
            # Simulate streaming by processing in chunks with partial results
            chunk_texts = []
            accumulated_text = ""
            
            # Process audio in smaller chunks to simulate streaming
            for i, chunk in enumerate(chunks):
                if i % 5 == 0:  # Every 5th chunk, emit partial result
                    # Emit partial result as we process
                    partial_text = f"Processing... {i//5 + 1}/{len(chunks)//5 + 1}"
                    self.partial_result.emit(partial_text, 0.3)
                    await asyncio.sleep(0.05)  # Small delay to simulate processing
            
            # Now do the actual transcription on the full audio
            # Reconstruct audio from chunks
            full_audio = b''.join(chunks)
            audio_array = np.frombuffer(full_audio, dtype=np.int16).astype(np.float32) / 32767.0
            
            # Use the fallback transcriber for actual processing
            if self.fallback_transcriber:
                print("🎯 Processing with faster-whisper...")
                text = self.fallback_transcriber.transcribe(audio_array, language)
                
                if text and text.strip():
                    # Emit final result
                    self.final_result.emit(text.strip(), 0.9)
                    print(f"✅ Final streaming result: {text}")
                else:
                    self.error_occurred.emit("No speech detected")
            else:
                self.error_occurred.emit("Transcriber not initialized")
                
        except Exception as e:
            print(f"❌ Custom streaming error: {e}")
            self.error_occurred.emit(str(e))
    
    def _batch_transcribe_worker(self, audio_data: np.ndarray, language: str):
        """Worker thread for batch transcription (fallback)"""
        try:
            print("🎯 Starting batch transcription (fallback)...")
            
            # Emit a working indicator
            self.partial_result.emit("Processing...", 0.0)
            
            # Use fallback transcriber
            if self.fallback_transcriber is not None:
                text = self.fallback_transcriber.transcribe(audio_data, language)
                
                if text and text.strip():
                    print(f"✅ Batch transcription complete: {text}")
                    # Store the raw text for LLM processing
                    self.raw_transcription = text.strip()
                    
                    # Start LLM processing if available
                    if self.llm_processor and self.llm_processor.is_enabled():
                        print("🤖 Starting LLM post-processing with context detection...")
                        self.llm_processor.process_text_async_with_context(self.raw_transcription)
                        # Note: Final result will be emitted after LLM processing via _on_llm_finished_with_context
                    else:
                        # No LLM processing, emit final result directly with unknown context
                        self.final_result_with_context.emit(self.raw_transcription, 0.9, "unknown")
                else:
                    self.error_occurred.emit("No speech detected")
            else:
                self.error_occurred.emit("Transcriber not initialized")
                
        except Exception as e:
            print(f"❌ Batch transcription error: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.is_transcribing = False
            self.transcription_finished.emit()
    
    def _on_llm_finished(self, cleaned_text: str):
        """Handle completed LLM processing (legacy - should use context version)"""
        print(f"🤖 LLM processing complete: '{cleaned_text}'")
        # For compatibility - emit with unknown context
        self.final_result_with_context.emit(cleaned_text, 0.95, "unknown")
        self.llm_processing_finished.emit(cleaned_text)
    
    def _on_llm_finished_with_context(self, cleaned_text: str, context_type: str):
        """Handle completed LLM processing with context"""
        print(f"🤖 LLM processing complete with context '{context_type}': '{cleaned_text}'")
        # Emit ONLY the context-aware result to avoid double processing
        self.final_result_with_context.emit(cleaned_text, 0.95, context_type)
        self.llm_processing_finished.emit(cleaned_text)
    
    def _on_llm_failed(self, error_message: str):
        """Handle failed LLM processing"""
        print(f"❌ LLM processing failed: {error_message}")
        # Fall back to raw transcription with unknown context
        if hasattr(self, 'raw_transcription'):
            self.final_result_with_context.emit(self.raw_transcription, 0.9, "unknown")
        else:
            self.error_occurred.emit("Both transcription and LLM processing failed")
    
    def is_streaming_available(self) -> bool:
        """Check if streaming transcription is available"""
        return self.prefer_streaming and WHISPERFLOW_AVAILABLE
    
    def is_llm_enabled(self) -> bool:
        """Check if LLM processing is enabled"""
        return self.llm_processor and self.llm_processor.is_enabled()
    
    def get_status(self) -> str:
        """Get current transcriber status"""
        if self.is_transcribing:
            return "Transcribing"
        elif self.prefer_streaming:
            return "Streaming Ready"
        else:
            return "Batch Ready" 