#!/bin/bash

# VoxVibe Bluetooth Working Sequence Test
# This replicates the exact sequence that worked in our manual testing

set -e

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
SOURCE_NAME="bluez_input.20_18_5B_1E_72_6C.0"
SINK_NAME="bluez_output.20_18_5B_1E_72_6C.1"

echo "🔵 Testing the exact working sequence from manual testing..."
echo "🔵 Target: $SOURCE_NAME"
echo ""

# Function to test if Bluetooth microphone is working
test_bluetooth_mic() {
    echo "🔵 Testing Bluetooth microphone with 3-second recording..."
    
    # Try to record 3 seconds of audio
    timeout 3s parec --device="$SOURCE_NAME" --rate=16000 --channels=1 --format=s16le --raw > /tmp/test_bt_audio.raw 2>/dev/null || true
    
    # Check file size
    if [ -f /tmp/test_bt_audio.raw ]; then
        size=$(stat -c%s /tmp/test_bt_audio.raw)
        echo "📊 Recorded $size bytes"
        rm -f /tmp/test_bt_audio.raw
        
        if [ $size -gt 1000 ]; then
            return 0  # Success
        fi
    fi
    
    return 1  # Failed
}

# Reset to A2DP mode first
echo "🔄 Starting from A2DP mode..."
pactl set-card-profile "$CARD_NAME" a2dp-sink 2>/dev/null || true
sleep 1

# PERMUTATION 4 - The one that worked!
echo ""
echo "🎯 TESTING PERMUTATION 4 (the working one):"
echo "   A2DP → headset → off → headset"

# Step 1: A2DP to headset
echo "🔵 Step 1: A2DP → headset"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5

# Step 2: headset to off
echo "🔵 Step 2: headset → off"
pactl set-card-profile "$CARD_NAME" off
sleep 0.5

# Step 3: off to headset (activation)
echo "🔵 Step 3: off → headset (ACTIVATION)"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1

# Test the microphone
if test_bluetooth_mic; then
    echo "🎉 SUCCESS! Bluetooth microphone is working!"
    echo "✅ This is the exact sequence VoxVibe needs to implement"
else
    echo "❌ Failed - microphone not working"
fi

# Reset back to A2DP
echo ""
echo "🔄 Resetting back to A2DP mode..."
pactl set-card-profile "$CARD_NAME" a2dp-sink 2>/dev/null || true
echo "✅ Reset complete" 