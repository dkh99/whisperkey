#!/bin/bash

# VoxVibe Bluetooth Test - Start from A2DP and get switching working
# This script ensures we start in high quality mode and can switch to working microphone

set -e

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
SOURCE_NAME="bluez_input.20_18_5B_1E_72_6C.0"
SINK_NAME="bluez_output.20_18_5B_1E_72_6C.1"
TEST_DURATION=3

echo "🔵 VoxVibe Bluetooth Test - Starting from High Quality Mode"
echo "🔵 Target: $SOURCE_NAME"
echo "🔵 Card: $CARD_NAME"
echo ""

# Function to get current profile
get_current_profile() {
    pactl list cards | grep -A 20 "$CARD_NAME" | grep "Active Profile:" | awk '{print $3}'
}

# Function to test if Bluetooth microphone is working
test_bluetooth_mic() {
    echo "🔵 Testing Bluetooth microphone with 3-second recording..."
    
    # Try to record 3 seconds of audio
    timeout 3s parec --device="$SOURCE_NAME" --rate=16000 --channels=1 --format=s16le --raw > /tmp/bt_test.raw 2>/dev/null || true
    
    # Check file size
    if [ -f /tmp/bt_test.raw ]; then
        size=$(stat -c%s /tmp/bt_test.raw)
        echo "🔵 Recorded $size bytes"
        rm -f /tmp/bt_test.raw
        
        if [ "$size" -gt 32000 ]; then  # At least 1 second of 16kHz mono
            return 0  # Success
        fi
    fi
    
    return 1  # Failed
}

# 1. ENSURE WE START IN HIGH QUALITY A2DP MODE
echo "🔵 Step 1: Ensuring high quality A2DP mode..."
current_profile=$(get_current_profile)
echo "🔵 Current profile: $current_profile"

if [ "$current_profile" != "a2dp-sink" ]; then
    echo "🔵 Switching to A2DP high quality mode..."
    pactl set-card-profile "$CARD_NAME" a2dp-sink
    sleep 1
    
    # Also ensure we're on the high quality headphone port
    pactl set-sink-port "$SINK_NAME" headphone-output 2>/dev/null || echo "⚠️ Could not set headphone port"
    sleep 0.5
    
    echo "✅ Now in A2DP high quality mode"
else
    echo "✅ Already in A2DP high quality mode"
fi

# 2. IMPLEMENT THE WORKING SEQUENCE FROM OUR MANUAL TESTS
echo ""
echo "🔵 Step 2: Implementing the working sequence..."

# Switch to headset mode
echo "🔵 Switching to headset-head-unit-msbc..."
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1

# Do the "magic" double switch (switch to headset when already in headset)
echo "🔵 Performing the magic double switch..."
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5

# Switch the sink port to handsfree output (critical step!)
echo "🔵 Switching sink port to handsfree output..."
pactl set-sink-port "$SINK_NAME" headphone-hf-output
sleep 1

# Activate the Bluetooth source
echo "🔵 Activating Bluetooth source..."
pactl set-default-source "$SOURCE_NAME"
pactl suspend-source "$SOURCE_NAME" false 2>/dev/null || true
sleep 1

# 3. TEST THE MICROPHONE
echo ""
echo "🔵 Step 3: Testing the microphone..."
if test_bluetooth_mic; then
    echo "🎉 SUCCESS! Bluetooth microphone is working!"
    working=true
else
    echo "❌ FAILED: Bluetooth microphone is not working"
    working=false
fi

# 4. SWITCH BACK TO HIGH QUALITY MODE
echo ""
echo "🔵 Step 4: Switching back to high quality mode..."
pactl set-card-profile "$CARD_NAME" a2dp-sink
sleep 0.5
pactl set-sink-port "$SINK_NAME" headphone-output 2>/dev/null || true
sleep 0.5

current_profile=$(get_current_profile)
echo "✅ Back to profile: $current_profile"

# 5. SUMMARY
echo ""
echo "🔵 === SUMMARY ==="
if [ "$working" = true ]; then
    echo "✅ SUCCESS: The Bluetooth microphone switching sequence works!"
    echo "📋 Working sequence:"
    echo "   1. Start in A2DP mode (high quality)"
    echo "   2. Switch to headset-head-unit-msbc"
    echo "   3. Double switch (switch to headset when already in headset)"
    echo "   4. Switch sink port to headphone-hf-output"
    echo "   5. Activate Bluetooth source"
    echo "   6. Record audio successfully"
    echo "   7. Switch back to A2DP mode"
    exit 0
else
    echo "❌ FAILED: The sequence did not work"
    exit 1
fi 