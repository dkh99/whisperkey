import os
import time
from typing import Optional, Tuple

import numpy as np
from faster_whisper import WhisperModel

try:
    from .cloud_transcriber_streaming import (
        DeepgramStreamingTranscriber,
        StreamingTranscriptionResult,
    )
    STREAMING_AVAILABLE = True
    print("🚀 Deepgram streaming support available")
except Exception as exc:
    print(f"⚠️ Deepgram streaming unavailable: {exc}")
    import traceback
    traceback.print_exc()
    DeepgramStreamingTranscriber = None
    StreamingTranscriptionResult = None
    STREAMING_AVAILABLE = False

from .cloud_transcriber import (
    DeepgramError,
    DeepgramTranscriber,
    DeepgramTranscription,
)
from .settings_dialog import WhisperKeySettings


class Transcriber:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        settings: Optional[WhisperKeySettings] = None,
    ):
        """
        Initialize the Whisper transcriber.
        
        Args:
            model_size: Size of the Whisper model ("tiny", "base", "small", "medium", "large-v2", "large-v3")
            device: Device to run on ("cpu", "cuda", "auto")
            compute_type: Compute type ("int8", "int16", "float16", "float32", "auto")
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self.settings = settings or WhisperKeySettings()
        self.deepgram_client: Optional[DeepgramTranscriber] = None
        self.deepgram_streaming: Optional[DeepgramStreamingTranscriber] = None
        self.last_engine: str = "Whisper"
        self.last_latency_ms: int = 0
        
        # Initialize model lazily to avoid long startup times
        self._load_model()
        self._initialize_deepgram()

    def _initialize_deepgram(self):
        api_key = self.settings.get("transcription.deepgram_api_key", "")
        print(f"🔍 DEBUG: Deepgram API key from settings: {api_key[:20] if api_key else '(empty)'}...")
        if api_key:
            try:
                if STREAMING_AVAILABLE:
                    print("🔌 Initializing Deepgram streaming client...")
                    self.deepgram_streaming = DeepgramStreamingTranscriber(api_key)
                    print("✅ Deepgram STREAMING client ready")
                else:
                    print("⚠️ Streaming not available, using REST only")
                    self.deepgram_streaming = None
                
                print("🔌 Initializing Deepgram REST client...")
                self.deepgram_client = DeepgramTranscriber(api_key=api_key)
                print("✅ Deepgram REST client ready")
            except Exception as exc:
                print(f"⚠️ Failed to initialize Deepgram: {exc}")
                import traceback
                traceback.print_exc()
                self.deepgram_client = None
                self.deepgram_streaming = None
        else:
            print("⚠️ No Deepgram API key found, using Whisper only")
            self.deepgram_client = None
            self.deepgram_streaming = None

    def refresh_from_settings(self):
        """Reload provider selection after settings change."""
        self._initialize_deepgram()
    
    def _load_model(self):
        """Load the Whisper model"""
        try:
            print(f"Loading Whisper model: {self.model_size}")
            
            # Use CPU for better compatibility
            if self.device == "auto":
                device = "cpu"
            else:
                device = self.device
            
            if self.compute_type == "auto":
                compute_type = "int8" if device == "cpu" else "float16"
            else:
                compute_type = self.compute_type
            
            self.model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
                download_root=os.path.expanduser("~/.cache/whisper"),
                local_files_only=True  # Use only cached files, don't access internet
            )
            print(f"Model loaded successfully on {device} with {compute_type}")
            
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            raise
    
    def transcribe(self, audio_data: np.ndarray, language="en") -> Optional[str]:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Numpy array of audio data (float32, mono, 16kHz)
            language: Language code ("en", "es", "fr", etc.) or None for auto-detection
            
        Returns:
            Transcribed text or None if transcription failed
        """
        if audio_data is None or len(audio_data) == 0:
            print("No audio data provided")
            return None
        
        try:
            audio_data = self._prepare_audio(audio_data)
            if audio_data is None:
                return None

            text, engine_name, latency_ms = self._transcribe_with_best_engine(audio_data, language)
            self.last_engine = engine_name
            self.last_latency_ms = latency_ms

            if text:
                print(f"Transcribed with {engine_name}: {text}")
                return text

            print("Empty transcription result")
            return None
        
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    def _prepare_audio(self, audio_data: np.ndarray) -> Optional[np.ndarray]:
        if audio_data is None or len(audio_data) == 0:
            print("No audio data provided")
            return None

        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        peak = np.max(np.abs(audio_data))
        if peak > 1.0:
            audio_data = audio_data / peak

        current_sr = getattr(self, "sample_rate", 16000)
        target_sr = 16000

        if current_sr != target_sr:
            length = int(len(audio_data) * target_sr / current_sr)
            audio_data = np.interp(
                np.linspace(0, 1, length, endpoint=False),
                np.linspace(0, 1, len(audio_data), endpoint=False),
                audio_data,
            )

        min_samples = int(0.1 * 16000)
        if len(audio_data) < min_samples:
            print("Audio too short for transcription")
            return None

        return audio_data

    def _ensure_16k_mono_pcm(self, audio_data: np.ndarray) -> bytes:
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        peak = np.max(np.abs(audio_data))
        
        # Check if audio actually has voice-like characteristics
        # Voice typically has energy in 300-3000 Hz range
        rms = np.sqrt(np.mean(audio_data ** 2))
        
        # Normalize audio to use full dynamic range for better Deepgram detection
        # Target 70% of full scale to avoid clipping but ensure strong signal
        if peak > 0.001:  # Avoid division by zero for silence
            target_level = 0.7
            audio_data = audio_data * (target_level / peak)
            print(f"🔊 Audio stats: peak={peak:.4f}, rms={rms:.4f}, samples={len(audio_data)}")
            print(f"🔊 Normalized: {peak:.4f} → {target_level} (boosted {target_level/peak:.1f}x)")
        else:
            print(f"⚠️ Audio too quiet (peak={peak:.6f}), may not transcribe well")

        target_sr = 16000
        current_sr = 16000
        if hasattr(self, "fallback_transcriber") and getattr(self.fallback_transcriber, "sample_rate", None):
            current_sr = self.fallback_transcriber.sample_rate

        if current_sr != target_sr:
            length = int(len(audio_data) * target_sr / current_sr)
            audio_data = np.interp(
                np.linspace(0, 1, length, endpoint=False),
                np.linspace(0, 1, len(audio_data), endpoint=False),
                audio_data,
            )

        pcm16 = np.clip(audio_data * 32767.0, -32767, 32767).astype(np.int16)
        return pcm16.tobytes()

    def _transcribe_with_best_engine(self, audio_data: np.ndarray, language: str) -> Tuple[Optional[str], str, int]:
        start_time = time.perf_counter()
        if self.deepgram_streaming:
            try:
                streamed_bytes = self._ensure_16k_mono_pcm(audio_data)
                streamed_result: StreamingTranscriptionResult = self.deepgram_streaming.transcribe(
                    streamed_bytes, language
                )
                print(
                    f"⚡ Deepgram STREAMING response time: {streamed_result.latency_ms}ms, confidence {streamed_result.confidence:.2f}"
                )
                self.last_engine = "Deepgram-Streaming"
                self.last_latency_ms = streamed_result.latency_ms
                self._record_latency("deepgram-streaming", streamed_result.latency_ms, success=True)
                return streamed_result.text, "Deepgram-Streaming", streamed_result.latency_ms
            except Exception as err:
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                print(f"⚠️ Deepgram streaming error ({elapsed_ms}ms): {err}")
                self._record_latency("deepgram-streaming", elapsed_ms, success=False)

        if self.deepgram_client:
            try:
                result: DeepgramTranscription = self.deepgram_client.transcribe(audio_data, language)
                elapsed_ms = int(result.latency_s * 1000)
                print(f"⚡ Deepgram REST response time: {elapsed_ms}ms, confidence {result.confidence:.2f}")
                self._record_latency("deepgram-rest", elapsed_ms, success=True)
                return result.text, "Deepgram-REST", elapsed_ms
            except (DeepgramError, Exception) as err:
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                print(f"⚠️ Deepgram REST error ({elapsed_ms}ms): {err}")
                self._record_latency("deepgram-rest", elapsed_ms, success=False)

        if self.model is None:
            print("Model not loaded")
            return None, "Whisper", 0

        segments, info = self.model.transcribe(
            audio_data,
            language=language if language != "auto" else None,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                max_speech_duration_s=30,
            ),
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        if not text_parts:
            print("No speech detected in audio")
            return None, "Whisper", 0

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        self._record_latency("whisper", elapsed_ms, success=True)

        full_text = " ".join(text_parts).strip()
        print(
            f"Transcribed ({info.language}, {info.language_probability:.2f}) with Whisper in {elapsed_ms}ms"
        )
        return full_text, "Whisper", elapsed_ms

    def _record_latency(self, engine: str, latency_ms: int, success: bool) -> None:
        """Best-effort latency logging."""
        log_message = f"engine={engine} latency_ms={latency_ms} success={'1' if success else '0'}"
        print(f"📈 Latency: {log_message}")
    
    def get_available_models(self):
        """Get list of available Whisper model sizes"""
        return [
            "tiny",      # ~39 MB
            "base",      # ~74 MB  
            "small",     # ~244 MB
            "medium",    # ~769 MB
            "large-v2",  # ~1550 MB
            "large-v3"   # ~1550 MB
        ]
    
    def get_supported_languages(self):
        """Get list of supported language codes"""
        return [
            "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", 
            "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", 
            "el", "ms", "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", 
            "bg", "lt", "la", "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", 
            "sr", "az", "sl", "kn", "et", "mk", "br", "eu", "is", "hy", "ne", 
            "mn", "bs", "kk", "sq", "sw", "gl", "mr", "pa", "si", "km", "sn", 
            "yo", "so", "af", "oc", "ka", "be", "tg", "sd", "gu", "am", "yi", 
            "lo", "uz", "fo", "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", 
            "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"
        ]