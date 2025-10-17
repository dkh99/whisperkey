"""Cloud transcription providers (Deepgram)."""

from __future__ import annotations

import io
import json
import time
import wave
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

try:
    from deepgram import DeepgramClient
    DEEPGRAM_SDK_AVAILABLE = True
except ImportError:
    DEEPGRAM_SDK_AVAILABLE = False
    DeepgramClient = None


class DeepgramError(Exception):
    """Base class for Deepgram-specific errors."""


class DeepgramAuthenticationError(DeepgramError):
    """Raised when Deepgram rejects the API key."""


class DeepgramRateLimitError(DeepgramError):
    """Raised when Deepgram responds with a rate limit or throttling error."""


class DeepgramTransientError(DeepgramError):
    """Raised for transient errors that may succeed on retry."""


@dataclass
class DeepgramTranscription:
    """Container for Deepgram transcription results."""

    text: str
    confidence: float
    latency_s: float


class DeepgramTranscriber:
    """Deepgram transcriber using official SDK for optimal performance."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "nova-2",
        timeout: float = 15.0,
        enable_smart_format: bool = True,
    ) -> None:
        if not api_key:
            raise ValueError("DeepgramTranscriber requires a non-empty API key")

        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.enable_smart_format = enable_smart_format
        
        # Use SDK if available, otherwise fall back to urllib
        if DEEPGRAM_SDK_AVAILABLE:
            self.client = DeepgramClient(api_key=api_key)
            self.use_sdk = True
            print("🚀 Using Deepgram SDK for optimized performance")
        else:
            self.client = None
            self.use_sdk = False
            print("⚠️ Using fallback HTTP client (install deepgram-sdk for better performance)")

    def transcribe(self, audio_data: np.ndarray, language: str = "en") -> DeepgramTranscription:
        """Transcribe audio using Deepgram.

        Returns:
            DeepgramTranscription: Transcribed text, confidence, and latency.
        """

        if audio_data is None or len(audio_data) == 0:
            raise ValueError("Audio data is empty; cannot transcribe")

        wav_bytes = self._encode_wav(audio_data)
        
        if self.use_sdk and self.client:
            return self._transcribe_with_sdk(wav_bytes, language)
        else:
            return self._transcribe_with_urllib(wav_bytes, language)
    
    def _transcribe_with_sdk(self, wav_bytes: bytes, language: str) -> DeepgramTranscription:
        """Use Deepgram SDK (faster, better connection pooling)."""
        start_time = time.perf_counter()
        
        try:
            options = {
                "model": self.model,
                "smart_format": self.enable_smart_format,
            }
            
            if language and language != "auto":
                options["language"] = language
            else:
                options["detect_language"] = True
            
            # Use the SDK's media API with bytes
            response = self.client.listen.v1.media.transcribe_file(
                request=wav_bytes,
                **options
            )
            
            latency_s = time.perf_counter() - start_time
            
            # Parse SDK response
            channel = response.results.channels[0]
            alternative = channel.alternatives[0]
            text = alternative.transcript.strip()
            confidence = float(alternative.confidence)
            
            return DeepgramTranscription(text=text, confidence=confidence, latency_s=latency_s)
            
        except Exception as exc:
            print(f"❌ Deepgram SDK error: {exc}")
            raise DeepgramError(f"Deepgram SDK failed: {exc}") from exc
    
    def _transcribe_with_urllib(self, wav_bytes: bytes, language: str) -> DeepgramTranscription:
        """Fallback urllib implementation."""
        import urllib.error
        import urllib.parse
        import urllib.request
        
        params = self._build_query(language)
        url = f"https://api.deepgram.com/v1/listen?{params}"
        request = urllib.request.Request(url, data=wav_bytes)
        request.add_header("Authorization", f"Token {self.api_key}")
        request.add_header("Content-Type", "audio/wav")

        attempts = 2
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            start_time = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = response.read()
                latency_s = time.perf_counter() - start_time
                data = json.loads(payload.decode("utf-8"))
                text, confidence = self._parse_response(data)
                return DeepgramTranscription(text=text, confidence=confidence, latency_s=latency_s)
            except urllib.error.HTTPError as exc:
                last_error = exc
                status = exc.code
                body = exc.read().decode("utf-8", errors="ignore")

                if status == 401:
                    raise DeepgramAuthenticationError("Deepgram rejected the API key") from exc
                if status == 429:
                    if attempt == attempts:
                        raise DeepgramRateLimitError("Deepgram rate limit exceeded") from exc
                    time.sleep(1.0)
                    continue
                if status >= 500:
                    if attempt == attempts:
                        raise DeepgramTransientError(f"Deepgram server error ({status})") from exc
                    time.sleep(0.75)
                    continue
                raise DeepgramError(f"Deepgram HTTP error {status}: {body}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt == attempts:
                    raise DeepgramTransientError("Deepgram request failed: network error") from exc
                time.sleep(0.75)
                continue

        raise DeepgramError(f"Deepgram request failed after retries: {last_error}")

    def _build_query(self, language: str) -> str:
        params = {
            "model": self.model,
            "smart_format": str(self.enable_smart_format).lower(),
        }
        if language and language != "auto":
            params["language"] = language
        else:
            params["detect_language"] = "true"

        return urllib.parse.urlencode(params)

    def _encode_wav(self, audio_data: np.ndarray) -> bytes:
        """Encode float32 mono PCM data to WAV bytes with minimal overhead."""

        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        clipped = np.clip(audio_data, -1.0, 1.0)
        int_data = (clipped * 32767).astype(np.int16)

        # Minimal WAV header + data for fastest encoding
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(int_data.tobytes())

        return buffer.getvalue()

    def _parse_response(self, data: dict) -> Tuple[str, float]:
        try:
            channel = data["results"]["channels"][0]
            alternative = channel["alternatives"][0]
            text = alternative.get("transcript", "").strip()
            confidence = float(alternative.get("confidence", 0.0))
            return text, confidence
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepgramError("Unexpected Deepgram response format") from exc

