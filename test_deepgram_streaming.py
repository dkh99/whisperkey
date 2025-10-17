#!/usr/bin/env python3
"""Manual Deepgram streaming test that mirrors the app's workflow."""

import argparse
import asyncio
import io
import json
import os
import sys
import time
import wave
from pathlib import Path
from typing import Tuple

import numpy as np
import websockets


PIPX_VENV = Path.home() / ".local" / "share" / "pipx" / "venvs" / "whisperkey"
if PIPX_VENV.exists():
    sys.path.insert(0, str(PIPX_VENV / "lib" / "python3.12" / "site-packages"))


def load_api_key() -> str:
    settings_path = Path.home() / ".config" / "whisperkey" / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
            api_key = data.get("transcription", {}).get("deepgram_api_key", "")
            if api_key:
                return api_key
        except json.JSONDecodeError:
            pass

    env_key = os.getenv("DEEPGRAM_API_KEY", "")
    if env_key:
        return env_key

    raise RuntimeError("Deepgram API key not found in settings.json or DEEPGRAM_API_KEY env var")


def ensure_16k_pcm(wav_path: Path) -> Tuple[bytes, int]:
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sample_width not in (1, 2):
        raise ValueError("WAV must be 8-bit or 16-bit PCM")

    # Convert to float32 mono in range [-1, 1]
    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
        audio /= 32767.0
    else:
        audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    if sample_rate != 16000:
        target_len = int(len(audio) * 16000 / sample_rate)
        x_old = np.linspace(0, 1, len(audio), endpoint=False)
        x_new = np.linspace(0, 1, target_len, endpoint=False)
        audio = np.interp(x_new, x_old, audio)

    pcm16 = np.clip(audio * 32767.0, -32767, 32767).astype(np.int16)
    return pcm16.tobytes(), 16000


def float_audio_to_pcm16(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    return pcm16.tobytes()


async def deepgram_stream(pcm_bytes: bytes, api_key: str, *, model: str = "nova-2", language: str = "en") -> Tuple[str, float, int]:
    headers = {"Authorization": f"Token {api_key}"}
    start_message = {
        "type": "start",
        "model": model,
        "encoding": "linear16",
        "sample_rate": 16000,
        "channels": 1,
        "smart_format": True,
        "interim_results": False,
    }
    if language and language != "auto":
        start_message["language"] = language

    print("🔌 Connecting to Deepgram WebSocket…")
    start_time = time.perf_counter()

    header_items = [("Authorization", f"Token {api_key}")]

    ws = await websockets.connect(
        "wss://api.deepgram.com/v1/listen",
        additional_headers=header_items,
        max_size=None,
    )

    try:
        await ws.send(json.dumps(start_message))

        # Wait for acknowledgement before sending audio
        while True:
            ack = await asyncio.wait_for(ws.recv(), timeout=5.0)
            ack_data = json.loads(ack)
            if ack_data.get("type") == "message" and "listening" in ack_data.get("message", "").lower():
                print("✅ Deepgram acknowledged start message")
                break
            elif ack_data.get("type") == "error":
                raise RuntimeError(f"Deepgram error: {ack_data.get('message')}")

        chunk_size = 8192
        for idx in range(0, len(pcm_bytes), chunk_size):
            chunk = pcm_bytes[idx : idx + chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.002)

        await ws.send(json.dumps({"type": "stop"}))

        transcript = ""
        confidence = 0.0

        while True:
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=15.0)
            except asyncio.TimeoutError:
                print("⏳ Timeout waiting for final transcript")
                break

            data = json.loads(message)
            m_type = data.get("type")

            if m_type == "transcript":
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if alternatives:
                    alt = alternatives[0]
                    transcript = alt.get("transcript", transcript).strip()
                    confidence = alt.get("confidence", confidence)
                    print(f"📝 Partial: '{transcript}' (conf={confidence:.2f})")
                if channel.get("is_final") or data.get("speech_final"):
                    break
            elif m_type == "error":
                raise RuntimeError(f"Deepgram error: {data.get('message')}")
            elif m_type == "close" or m_type == "session":
                break

    finally:
        await ws.close()

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    return transcript, confidence, latency_ms


def synthetic_speech(duration_s: float = 2.0, sample_rate: int = 16000) -> bytes:
    t = np.linspace(0, duration_s, int(duration_s * sample_rate), endpoint=False)
    freq = 220.0
    waveform = 0.4 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    return float_audio_to_pcm16(waveform, sample_rate=sample_rate)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deepgram streaming smoke test")
    parser.add_argument("--file", type=Path, help="Path to WAV file (16kHz mono). If omitted, generate synthetic audio.")
    parser.add_argument("--language", default="en")
    parser.add_argument("--model", default="nova-2")
    args = parser.parse_args()

    api_key = load_api_key()
    print(f"🔑 Using API key: {api_key[:6]}********")

    if args.file:
        print(f"🎧 Loading audio from {args.file}")
        if not args.file.exists():
            raise FileNotFoundError(args.file)
        pcm_bytes, _ = ensure_16k_pcm(args.file)
    else:
        print("🎛️ No file provided; generating synthetic test tone")
        pcm_bytes = synthetic_speech()

    transcript, confidence, latency_ms = asyncio.run(
        deepgram_stream(pcm_bytes, api_key, model=args.model, language=args.language)
    )

    print("\n✅ Streaming complete")
    print(f"⏱️ Latency: {latency_ms} ms")
    print(f"📝 Transcript: {transcript!r}")
    print(f"📊 Confidence: {confidence:.2f}")


if __name__ == "__main__":
    main()
