#!/usr/bin/env python3
"""Test Deepgram SDK streaming to find the correct API usage."""

import asyncio
import sys
import time
import numpy as np

# Add pipx venv to path
sys.path.insert(0, '/home/david-hathiramani/.local/share/pipx/venvs/whisperkey/lib/python3.12/site-packages')

from deepgram import DeepgramClient

# Read the API key from settings
import json
from pathlib import Path
config_file = Path.home() / ".config" / "whisperkey" / "settings.json"
with open(config_file) as f:
    settings = json.load(f)
    api_key = settings.get("transcription", {}).get("deepgram_api_key", "")

if not api_key:
    print("❌ No API key found in settings")
    sys.exit(1)

print(f"🔑 Using API key: {api_key[:20]}...")

# Create client
client = DeepgramClient(api_key=api_key)
print("✅ Client created")

# Test 1: Try the synchronous listen API (pre-recorded)
print("\n📡 Testing pre-recorded (REST) API...")
test_audio = np.random.randn(16000).astype(np.float32) * 0.1  # 1 second of noise
audio_bytes = (np.clip(test_audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

# Create minimal WAV
import io
import wave
buffer = io.BytesIO()
with wave.open(buffer, "wb") as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)
    wav_file.writeframes(audio_bytes)
wav_data = buffer.getvalue()

print(f"📦 Audio size: {len(wav_data)} bytes")

try:
    start = time.time()
    
    # Try using the media (prerecorded) API with correct SDK 5.x syntax
    response = client.listen.v1.media.transcribe_file(
        request=wav_data,
        model="nova-2",
        smart_format=True,
    )
    
    elapsed = int((time.time() - start) * 1000)
    print(f"✅ SDK API works! Response time: {elapsed}ms")
    print(f"Response type: {type(response)}")
    
    # Parse response
    channel = response.results.channels[0]
    alternative = channel.alternatives[0]
    text = alternative.transcript
    confidence = alternative.confidence
    print(f"📝 Transcript: '{text}'")
    print(f"📊 Confidence: {confidence}")
    
except Exception as e:
    print(f"❌ SDK API failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check WebSocket structure
print("\n🔌 Checking WebSocket API structure...")
print(f"listen.v1 type: {type(client.listen.v1)}")
print(f"listen.v1 methods: {[m for m in dir(client.listen.v1) if not m.startswith('_')]}")

print("\n✅ Test complete")

