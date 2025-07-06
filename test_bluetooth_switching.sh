#!/bin/bash

# VoxVibe Bluetooth Switching Test - Loop until working
# Start with Bluetooth disconnect/reconnect, then loop: HF -> off -> HF until working

set -e

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
SOURCE_NAME="bluez_input.20_18_5B_1E_72_6C.0"
BT_DEVICE="20:18:5B:1E:72:6C"
MAX_ATTEMPTS=50

echo "🔵 VoxVibe Bluetooth Switching Test - Disconnect/Reconnect + Loop until working"
echo "🔵 Target: $SOURCE_NAME"
echo "🔵 Card: $CARD_NAME"
echo "🔵 Bluetooth Device: $BT_DEVICE"
echo "🔵 Max attempts: $MAX_ATTEMPTS"
echo ""

# Function to test if Bluetooth microphone is working
test_bluetooth_mic() {
    echo "  🔵 Testing Bluetooth microphone with 2-second recording..."
    
    # Try to record 2 seconds of audio
    timeout 2s parec --device="$SOURCE_NAME" --rate=16000 --channels=1 --format=s16le --raw > /tmp/test_bt.raw 2>/dev/null || true
    
    # Check file size
    if [ -f /tmp/test_bt.raw ]; then
        size=$(stat -c%s /tmp/test_bt.raw)
        echo "  📊 Recorded $size bytes"
        rm -f /tmp/test_bt.raw
        
        if [ $size -gt 1000 ]; then
            echo "  ✅ SUCCESS: Bluetooth microphone is working!"
            return 0
        else
            echo "  ❌ FAILED: No audio data (source suspended)"
            return 1
        fi
    else
        echo "  ❌ FAILED: No recording file created"
        return 1
    fi
}

# Step 0: Bluetooth disconnect and reconnect (testing the theory)
echo "🔵 Step 0: Bluetooth disconnect/reconnect sequence..."
echo "  🔵 Disconnecting Bluetooth device..."
bluetoothctl disconnect "$BT_DEVICE" || echo "  ⚠️ Disconnect may have failed (device might already be disconnected)"
sleep 2.0

echo "  🔵 Reconnecting Bluetooth device..."
bluetoothctl connect "$BT_DEVICE" || echo "  ⚠️ Connect may have failed"
sleep 3.0

echo "  🔵 Waiting for audio profiles to establish..."
sleep 2.0
echo "✅ Bluetooth disconnect/reconnect completed"
echo ""

# Step 1: Switch to A2DP mode (high quality starting point)
echo "🔵 Step 1: Setting to A2DP mode (high quality start)..."

# Check current profile first
current_profile=$(pactl list cards | grep -A 20 "bluez_card.20_18_5B_1E_72_6C" | grep "Active Profile:" | awk '{print $3}')
echo "  🔵 Current profile: $current_profile"

if [ "$current_profile" = "headset-head-unit-msbc" ]; then
    echo "  🔵 Already in headset mode, switching to A2DP first..."
    pactl set-card-profile "$CARD_NAME" a2dp-sink || echo "  ⚠️ A2DP switch failed, continuing anyway..."
    sleep 1.0
    echo "✅ Switched to A2DP mode"
elif [ "$current_profile" = "off" ]; then
    echo "  🔵 Device is off, switching to A2DP..."
    pactl set-card-profile "$CARD_NAME" a2dp-sink || echo "  ⚠️ A2DP switch failed, continuing anyway..."
    sleep 1.0
    echo "✅ Switched to A2DP mode"
else
    echo "  🔵 Already in A2DP-like mode ($current_profile)"
    echo "✅ Starting from current profile"
fi
echo ""

# Step 2: Loop the switching sequence until it works
echo "🔵 Step 2: Starting switching loop..."
for attempt in $(seq 1 $MAX_ATTEMPTS); do
    echo "🔄 ATTEMPT $attempt/$MAX_ATTEMPTS:"
    
    # Switch to HF mode
    echo "  🔵 Switching to headset mode..."
    pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
    sleep 0.5
    
    # Switch to OFF (disconnect)
    echo "  🔵 Switching to OFF..."
    pactl set-card-profile "$CARD_NAME" off
    sleep 0.5
    
    # Switch back to HF mode (activation)
    echo "  🔵 Switching back to headset mode..."
    pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
    sleep 1.0
    
    # Test if it's working
    if test_bluetooth_mic; then
        echo ""
        echo "🎉 SUCCESS on attempt $attempt!"
        echo "🎉 Working sequence: BT disconnect/reconnect -> A2DP -> (HF -> off -> HF) x$attempt"
        exit 0
    else
        echo "  ⚠️ Attempt $attempt failed, trying again..."
        echo ""
    fi
done

echo ""
echo "❌ FAILED: All $MAX_ATTEMPTS attempts failed"
echo "❌ Bluetooth microphone could not be activated even with disconnect/reconnect"
exit 1 