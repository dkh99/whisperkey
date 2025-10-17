#!/usr/bin/env python3
"""Test Deepgram streaming with the exact code from cloud_transcriber_streaming.py"""

import asyncio
import json
import sys
import time
from pathlib import Path

import numpy as np
import websockets

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from whisperkey.cloud_transcriber_streaming import DeepgramStreamingTranscriber


def load_api_key() -> str:
    """Load API key from settings."""
    settings_path = Path.home() / ".config" / "whisperkey" / "settings.json"
    if settings_path.exists():
        data = json.loads(settings_path.read_text())
        api_key = data.get("transcription", {}).get("deepgram_api_key", "")
        if api_key:
            return api_key
    raise RuntimeError("No Deepgram API key found")


def create_test_audio() -> np.ndarray:
    """Create 2 seconds of test audio (sine wave at 440Hz)."""
    sample_rate = 16000
    duration = 2.0
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    # Create a simple tone
    frequency = 440.0
    audio = (0.3 * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
    return audio


def main():
    print("🧪 Testing Deepgram streaming with exact production code")
    print("=" * 60)
    
    api_key = load_api_key()
    print(f"✅ API key loaded: {api_key[:6]}...")
    
    # Create test audio
    audio_data = create_test_audio()
    print(f"🎵 Generated {len(audio_data)} samples of test audio (2 seconds)")
    
    # Initialize streaming transcriber (same as production)
    print("\n🔌 Creating DeepgramStreamingTranscriber...")
    transcriber = DeepgramStreamingTranscriber(api_key)
    print("✅ Transcriber created")
    
    # Convert to PCM16 bytes (same as app does)
    print("🔄 Converting to PCM16 bytes...")
    pcm16 = np.clip(audio_data * 32767.0, -32767, 32767).astype(np.int16)
    pcm_bytes = pcm16.tobytes()
    print(f"✅ Converted to {len(pcm_bytes)} bytes of PCM16 data")
    
    # Transcribe (this uses the exact same code path as the app)
    print("\n📡 Starting transcription...")
    start = time.time()
    
    try:
        result = transcriber.transcribe(pcm_bytes, language="en")
        elapsed = time.time() - start
        
        print(f"\n{'='*60}")
        print(f"✅ Transcription complete in {elapsed:.2f}s")
        print(f"⏱️  Latency: {result.latency_ms}ms")
        print(f"📝 Transcript: '{result.text}'")
        print(f"📊 Confidence: {result.confidence:.2f}")
        print(f"{'='*60}")
        
        if not result.text:
            print("\n⚠️  WARNING: Empty transcript received!")
            print("This suggests Deepgram didn't detect any speech in the audio.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

