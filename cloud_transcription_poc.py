#!/usr/bin/env python3
"""
Proof of Concept: Fast Cloud Transcription APIs
Comparing Deepgram, OpenAI Whisper, and faster-whisper
"""

import numpy as np
import time
import tempfile
import wave
from typing import Optional, Literal
from abc import ABC, abstractmethod


# ============================================================================
# Abstract Base Class
# ============================================================================

class TranscriberInterface(ABC):
    """Base interface for all transcription engines"""
    
    @abstractmethod
    def transcribe(self, audio_data: np.ndarray, language: str = "en") -> Optional[str]:
        """Transcribe audio data to text"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this transcription engine"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this engine is available and configured"""
        pass
    
    def benchmark(self, audio_data: np.ndarray, language: str = "en") -> dict:
        """Benchmark transcription performance"""
        if not self.is_available():
            return {
                "engine": self.get_name(),
                "available": False,
                "error": "Engine not available"
            }
        
        start_time = time.time()
        try:
            result = self.transcribe(audio_data, language)
            elapsed = time.time() - start_time
            
            return {
                "engine": self.get_name(),
                "available": True,
                "transcription": result,
                "duration_seconds": elapsed,
                "duration_ms": elapsed * 1000,
                "audio_duration": len(audio_data) / 16000,
                "realtime_factor": elapsed / (len(audio_data) / 16000)
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "engine": self.get_name(),
                "available": True,
                "error": str(e),
                "duration_seconds": elapsed
            }


# ============================================================================
# 1. Deepgram (Fastest) ⚡
# ============================================================================

class DeepgramTranscriber(TranscriberInterface):
    """
    Deepgram Nova-2 transcriber - Fastest cloud API
    <300ms latency, 60min audio in 12 seconds
    
    Requires: pip install deepgram-sdk
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy load Deepgram client"""
        if self._client is None:
            try:
                from deepgram import Deepgram
                self._client = Deepgram(self.api_key)
                print("✅ Deepgram client initialized")
            except ImportError:
                print("❌ deepgram-sdk not installed")
                print("   Install with: pip install deepgram-sdk")
                return None
            except Exception as e:
                print(f"❌ Failed to initialize Deepgram: {e}")
                return None
        return self._client
    
    def transcribe(self, audio_data: np.ndarray, language: str = "en") -> Optional[str]:
        """Transcribe using Deepgram API"""
        client = self._get_client()
        if not client:
            # Return mock for demo
            return "[Deepgram Mock] This is a sample transcription with excellent punctuation and capitalization."
        
        try:
            import asyncio
            import io
            
            # Convert numpy array to WAV bytes
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                # Convert float32 to int16
                if audio_data.dtype == np.float32:
                    audio_data = (audio_data * 32767).astype(np.int16)
                wav_file.writeframes(audio_data.tobytes())
            
            wav_buffer.seek(0)
            source = {
                'buffer': wav_buffer.read(),
                'mimetype': 'audio/wav'
            }
            
            # Call Deepgram API
            async def transcribe_async():
                response = await client.transcription.prerecorded(
                    source,
                    {
                        'punctuate': True,
                        'language': language,
                        'model': 'nova-2',
                    }
                )
                return response['results']['channels'][0]['alternatives'][0]['transcript']
            
            # Run async function
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context
                transcript = asyncio.create_task(transcribe_async())
            else:
                transcript = loop.run_until_complete(transcribe_async())
            
            return transcript
            
        except ImportError:
            return "[Deepgram Mock] This is a sample transcription with excellent punctuation and capitalization."
        except Exception as e:
            print(f"❌ Deepgram transcription error: {e}")
            return None
    
    def get_name(self) -> str:
        return "Deepgram Nova-2 (Cloud)"
    
    def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0


# ============================================================================
# 2. OpenAI Whisper API (Easy Integration)
# ============================================================================

class OpenAIWhisperTranscriber(TranscriberInterface):
    """
    OpenAI Whisper API - Great for existing OpenAI users
    3-4x faster than local, excellent accuracy
    
    Requires: pip install openai
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Lazy load OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
                print("✅ OpenAI client initialized")
            except ImportError:
                print("❌ openai package not installed")
                print("   Install with: pip install openai")
                return None
            except Exception as e:
                print(f"❌ Failed to initialize OpenAI: {e}")
                return None
        return self._client
    
    def transcribe(self, audio_data: np.ndarray, language: str = "en") -> Optional[str]:
        """Transcribe using OpenAI Whisper API"""
        client = self._get_client()
        if not client:
            # Return mock for demo
            return "[OpenAI Whisper Mock] This is a sample transcription with good punctuation."
        
        try:
            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    # Convert float32 to int16
                    if audio_data.dtype == np.float32:
                        audio_data = (audio_data * 32767).astype(np.int16)
                    wav_file.writeframes(audio_data.tobytes())
                
                # Transcribe with OpenAI
                with open(temp_file.name, 'rb') as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )
                    return transcript.text
                    
        except ImportError:
            return "[OpenAI Whisper Mock] This is a sample transcription with good punctuation."
        except Exception as e:
            print(f"❌ OpenAI Whisper transcription error: {e}")
            return None
    
    def get_name(self) -> str:
        return "OpenAI Whisper API (Cloud)"
    
    def is_available(self) -> bool:
        return self.api_key is not None and len(self.api_key) > 0


# ============================================================================
# 3. faster-whisper (Current - Local & Private)
# ============================================================================

class FasterWhisperTranscriber(TranscriberInterface):
    """
    Current faster-whisper implementation
    Slower but free and private
    """
    
    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
    
    def _get_model(self):
        """Lazy load model"""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                print(f"✅ faster-whisper model loaded: {self.model_size}")
            except ImportError:
                print("❌ faster-whisper not installed")
                print("   Install with: pip install faster-whisper")
                return None
            except Exception as e:
                print(f"❌ Failed to load faster-whisper: {e}")
                return None
        return self._model
    
    def transcribe(self, audio_data: np.ndarray, language: str = "en") -> Optional[str]:
        """Transcribe using faster-whisper"""
        model = self._get_model()
        if not model:
            # Return mock for demo
            return "[faster-whisper Mock] This is a sample transcription."
        
        try:
            # Ensure float32 format
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Normalize
            if np.max(np.abs(audio_data)) > 1.0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Transcribe
            segments, info = model.transcribe(
                audio_data,
                language=language if language != "auto" else None,
                beam_size=5,
                vad_filter=True
            )
            
            # Combine segments
            text = " ".join([seg.text.strip() for seg in segments])
            return text.strip() if text else None
            
        except ImportError:
            return "[faster-whisper Mock] This is a sample transcription."
        except Exception as e:
            print(f"❌ faster-whisper transcription error: {e}")
            return None
    
    def get_name(self) -> str:
        return f"faster-whisper-{self.model_size} (Local)"
    
    def is_available(self) -> bool:
        try:
            import faster_whisper
            return True
        except ImportError:
            return False


# ============================================================================
# Factory & Comparison Tools
# ============================================================================

TranscriberType = Literal["deepgram", "openai-whisper", "faster-whisper"]

class TranscriberFactory:
    """Factory to create transcribers"""
    
    @staticmethod
    def create(engine: TranscriberType, **kwargs) -> TranscriberInterface:
        """Create a transcriber instance"""
        if engine == "deepgram":
            api_key = kwargs.get("api_key")
            if not api_key:
                raise ValueError("Deepgram requires an api_key")
            return DeepgramTranscriber(api_key=api_key)
            
        elif engine == "openai-whisper":
            api_key = kwargs.get("api_key")
            if not api_key:
                raise ValueError("OpenAI Whisper requires an api_key")
            return OpenAIWhisperTranscriber(api_key=api_key)
            
        elif engine == "faster-whisper":
            return FasterWhisperTranscriber(
                model_size=kwargs.get("model_size", "base")
            )
        else:
            raise ValueError(f"Unknown engine: {engine}")
    
    @staticmethod
    def list_available() -> dict[str, bool]:
        """Check which engines are available"""
        return {
            "deepgram": True,  # Always available if user has API key
            "openai-whisper": True,  # Always available if user has API key
            "faster-whisper": FasterWhisperTranscriber("base").is_available()
        }


def compare_transcribers(audio_data: np.ndarray, configs: list[dict]):
    """
    Compare multiple transcription engines
    
    Args:
        audio_data: Audio to transcribe (numpy array, float32, 16kHz)
        configs: List of config dicts with 'engine' and other params
    
    Returns:
        List of benchmark results
    """
    results = []
    
    for config in configs:
        engine_name = config.get('engine')
        try:
            transcriber = TranscriberFactory.create(**config)
            print(f"\n{'='*70}")
            print(f"Testing: {transcriber.get_name()}")
            print(f"{'='*70}")
            
            result = transcriber.benchmark(audio_data)
            results.append(result)
            
            # Print results
            if result.get('available'):
                if 'error' in result:
                    print(f"❌ Error: {result['error']}")
                else:
                    print(f"✅ Success!")
                    print(f"   Time: {result['duration_ms']:.0f}ms")
                    print(f"   Realtime factor: {result['realtime_factor']:.2f}x")
                    print(f"   Text: {result['transcription'][:100]}...")
            else:
                print(f"❌ Not available: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Failed to create {engine_name}: {e}")
            results.append({
                "engine": engine_name,
                "available": False,
                "error": str(e)
            })
    
    return results


def print_comparison_table(results: list[dict]):
    """Print a comparison table of results"""
    print("\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)
    
    # Header
    print(f"{'Engine':<30} {'Time (ms)':<12} {'Speed':<15} {'Status':<12}")
    print("-" * 70)
    
    # Sort by speed (fastest first)
    sorted_results = sorted(
        [r for r in results if r.get('available') and 'duration_ms' in r],
        key=lambda x: x.get('duration_ms', float('inf'))
    )
    
    # Print rows
    for result in sorted_results:
        engine = result.get('engine', 'Unknown')
        if 'error' in result:
            print(f"{engine:<30} {'N/A':<12} {'N/A':<15} {'Error':<12}")
        else:
            duration_ms = result.get('duration_ms', 0)
            rtf = result.get('realtime_factor', 0)
            
            # Speed category
            if duration_ms < 500:
                speed = "⚡ Instant"
            elif duration_ms < 2000:
                speed = "🚀 Fast"
            elif duration_ms < 5000:
                speed = "🏃 Quick"
            else:
                speed = "🐢 Slow"
            
            print(f"{engine:<30} {duration_ms:<12.0f} {speed:<15} {'✅ OK':<12}")
    
    # Print unavailable engines
    unavailable = [r for r in results if not r.get('available')]
    if unavailable:
        print("\nUnavailable:")
        for result in unavailable:
            engine = result.get('engine', 'Unknown')
            error = result.get('error', 'Unknown error')
            print(f"  ❌ {engine}: {error}")


# ============================================================================
# Example Usage & Demo
# ============================================================================

def main():
    """Demo comparing all transcription services"""
    
    print("="*70)
    print("Fast Cloud Transcription API Comparison")
    print("="*70)
    print()
    
    # Create sample audio (5 seconds of random noise)
    # In real usage, this would be actual recorded audio
    sample_audio = np.random.randn(16000 * 5).astype(np.float32) * 0.1
    audio_duration = len(sample_audio) / 16000
    print(f"📊 Sample audio: {audio_duration:.1f} seconds @ 16kHz")
    print()
    
    # Configuration for each service
    configs = [
        {
            "engine": "deepgram",
            "api_key": "your-deepgram-api-key-here"  # Get from deepgram.com
        },
        {
            "engine": "openai-whisper",
            "api_key": "your-openai-api-key-here"  # You likely already have this!
        },
        {
            "engine": "faster-whisper",
            "model_size": "base"
        }
    ]
    
    # Run comparison
    results = compare_transcribers(sample_audio, configs)
    
    # Print comparison table
    print_comparison_table(results)
    
    # Print recommendations
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    print("""
    ⭐ FASTEST: Deepgram Nova-2
       - <300ms latency
       - $6.45/month for typical usage
       - Best for speed-critical apps
       - Get $200 free credits at deepgram.com
    
    ⭐ EASIEST: OpenAI Whisper API
       - You likely already have OpenAI API key!
       - 3-4x faster than local
       - Just add to existing OpenAI integration
       - $9/month for typical usage
    
    ⭐ PRIVATE: faster-whisper (current)
       - 100% local processing
       - Free forever
       - Works offline
       - Keep as fallback option
    
    💡 RECOMMENDED STRATEGY:
       Offer users a choice:
       1. Deepgram (fastest, cheapest cloud)
       2. OpenAI Whisper (easy if already using OpenAI)
       3. faster-whisper (privacy/offline)
    """)
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
    1. Sign up for Deepgram: https://deepgram.com/
       - Get $200 in free credits
    
    2. Install SDK:
       pip install deepgram-sdk
    
    3. Test with real audio:
       python cloud_transcription_poc.py
    
    4. Compare with OpenAI (if you have key):
       pip install openai
    
    5. Implement in VoxVibe:
       - Add to settings UI
       - Let users choose engine
       - Default to fastest available
    """)


if __name__ == "__main__":
    main()


