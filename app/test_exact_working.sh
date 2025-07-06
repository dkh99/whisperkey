#!/bin/bash

# Test the exact working sequence from our manual testing
# This reproduces the SUCCESSFUL 64,000 bytes result

set -e

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
SOURCE_NAME="bluez_input.20_18_5B_1E_72_6C.0"

echo "🔵 Testing EXACT working sequence that produced 64,000 bytes..."
echo "🔵 Current profile: $(pactl list cards | grep -A 20 "$CARD_NAME" | grep "Active Profile:" | awk '{print $3}')"

# Step 1: Switch to A2DP (high quality)
echo "�� Step 1: Setting to A2DP mode..."
pactl set-card-profile "$CARD_NAME" a2dp-sink
sleep 0.5

# Step 2: Switch to headset mode
echo "🔵 Step 2: Switching to headset mode..."
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5

# Step 3: Reset with OFF profile
echo "🔵 Step 3: Resetting connection..."
pactl set-card-profile "$CARD_NAME" off
sleep 1.0

# Step 4: Switch back to headset mode (ACTIVATION)
echo "🔵 Step 4: Activating headset mode..."
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1.0

# Check if source exists
if pactl list sources | grep -q "$SOURCE_NAME"; then
    echo "✅ Bluetooth source exists: $SOURCE_NAME"
    
    # Check source state
    state=$(pactl list sources | grep -A 10 "$SOURCE_NAME" | grep "State:" | awk '{print $2}')
    echo "🔵 Source state: $state"
    
    # Test recording
    echo "🔵 Testing 3-second recording..."
    timeout 3s parec --device="$SOURCE_NAME" --rate=16000 --channels=1 --format=s16le --raw > /tmp/test_exact.raw 2>/dev/null || true
    
    if [ -f /tmp/test_exact.raw ]; then
        size=$(stat -c%s /tmp/test_exact.raw)
        echo "📊 Recorded $size bytes"
        if [ $size -gt 0 ]; then
            echo "🎉 SUCCESS! Bluetooth microphone is working!"
        else
            echo "❌ FAILED: No audio data recorded"
        fi
        rm -f /tmp/test_exact.raw
    else
        echo "❌ FAILED: No output file created"
    fi
else
    echo "❌ FAILED: Bluetooth source does not exist"
fi

# Reset to high quality mode
echo "🔵 Resetting to A2DP mode..."
pactl set-card-profile "$CARD_NAME" a2dp-sink

echo "🔵 Test complete!"
