"""Deepgram streaming transcription using raw WebSocket client."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass

import numpy as np
import websockets


@dataclass
class StreamingTranscriptionResult:
    text: str
    confidence: float
    latency_ms: int


class DeepgramStreamingError(Exception):
    """Raised when Deepgram streaming API returns an error."""


class DeepgramStreamingTranscriber:
    """Minimal Deepgram streaming client using the WebSocket protocol."""

    WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, *, model: str = "nova-2"):
        if not api_key:
            raise ValueError("DeepgramStreamingTranscriber requires a non-empty API key")
        self.api_key = api_key
        self.model = model

    def transcribe(self, pcm_bytes: bytes, language: str = "en") -> StreamingTranscriptionResult:
        if not pcm_bytes:
            raise ValueError("No audio supplied for streaming")

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._stream(pcm_bytes, language))
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    async def _stream(self, pcm_bytes: bytes, language: str) -> StreamingTranscriptionResult:
        headers = [("Authorization", f"Token {self.api_key}")]

        # Build query parameters for WebSocket URL (Deepgram doesn't use JSON start messages)
        params = {
            "model": self.model,
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
            "smart_format": "true",
            "interim_results": "true",  # Get interim results to know when processing is done
            "endpointing": "false",  # Don't auto-detect end of speech
        }
        if language and language != "auto":
            params["language"] = language

        # Encode params into URL
        import urllib.parse
        query_string = urllib.parse.urlencode(params)
        ws_url = f"{self.WS_URL}?{query_string}"

        start_time = time.perf_counter()

        async with websockets.connect(ws_url, additional_headers=headers, max_size=None) as ws:
            print(f"🔌 WebSocket connected to {ws_url[:80]}...")
            print(f"📤 Streaming {len(pcm_bytes)} bytes of PCM16 audio...")

            # Send audio at ~2x real-time speed (Deepgram needs pacing, not instant burst)
            # At 16kHz, 16-bit PCM: 32000 bytes/sec, so 8192 bytes = ~256ms of audio
            chunk_size = 8192  # 256ms of audio per chunk
            chunk_duration_ms = (chunk_size / 2) / 16  # bytes to samples to ms
            chunks_sent = 0
            for offset in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[offset : offset + chunk_size]
                await ws.send(chunk)
                chunks_sent += 1
                # Pace delivery at 2x real-time (send 256ms of audio every 128ms)
                await asyncio.sleep(chunk_duration_ms / 2000)  # Half the chunk duration

            print(f"📤 Sent {chunks_sent} audio chunks, sending Finalize and collecting results...")

            # Send Finalize message to tell Deepgram we're done sending audio
            await ws.send(json.dumps({"type": "Finalize"}))

            latest_transcript = ""
            confidence = 0.0

            # Read responses - collect ALL results until speech_final
            try:
                while True:
                    message = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    data = json.loads(message)
                    m_type = data.get("type")
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)
                    data.get("duration", 0)
                    print(f"📡 Message: {m_type}, final={is_final}, speech_final={speech_final}")  # noqa: E501
                    if m_type == "Results":
                        print(f"   Full data: {json.dumps(data, indent=2)[:500]}")

                    if m_type == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [])
                        if alternatives:
                            alt = alternatives[0]
                            new_transcript = alt.get("transcript", "").strip()

                            # Update latest transcript (Deepgram sends cumulative transcripts)
                            if new_transcript:
                                latest_transcript = new_transcript
                                confidence = alt.get("confidence", 0.0)
                                print(f"📝 Transcript: '{latest_transcript[:60]}...' (conf={confidence:.2f})")

                        # speech_final=True means ALL audio has been processed
                        if speech_final:
                            print("✅ Got speech_final, all audio processed!")
                            break
                    elif m_type == "Error":
                        raise DeepgramStreamingError(data.get("description", "Deepgram error"))
                    elif m_type == "close":
                        break
            except asyncio.TimeoutError:
                print("⏳ Timeout waiting for speech_final (using last transcript)")

            # Close the stream
            await ws.send(json.dumps({"type": "CloseStream"}))

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        # Use latest_transcript which contains the cumulative result from Deepgram
        return StreamingTranscriptionResult(text=latest_transcript, confidence=confidence, latency_ms=latency_ms)


def ensure_16k_pcm(audio: np.ndarray, sample_rate: int, channels: int) -> bytes:
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio = audio / peak

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    if sample_rate != 16000:
        length = int(len(audio) * 16000 / sample_rate)
        audio = np.interp(
            np.linspace(0, 1, length, endpoint=False),
            np.linspace(0, 1, len(audio), endpoint=False),
            audio,
        )

    pcm16 = np.clip(audio * 32767.0, -32767, 32767).astype(np.int16)
    return pcm16.tobytes()

