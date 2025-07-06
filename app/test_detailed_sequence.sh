#!/bin/bash

# Detailed test with more diagnostics and different approaches

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
SOURCE_NAME="bluez_input.20_18_5B_1E_72_6C.0"

echo "🔵 DETAILED BLUETOOTH MICROPHONE TEST"
echo "🔵 Testing multiple approaches to activate Bluetooth microphone"
echo ""

# Function to check source state
check_source() {
    if pactl list sources | grep -q "$SOURCE_NAME"; then
        state=$(pactl list sources | grep -A 10 "$SOURCE_NAME" | grep "State:" | awk '{print $2}')
        echo "  📱 Source exists, state: $state"
        return 0
    else
        echo "  ❌ Source does not exist"
        return 1
    fi
}

# Function to test recording
test_recording() {
    echo "  🔵 Testing 2-second recording..."
    timeout 2s parec --device="$SOURCE_NAME" --rate=16000 --channels=1 --format=s16le --raw > /tmp/test_bt.raw 2>/dev/null || true
    
    if [ -f /tmp/test_bt.raw ]; then
        size=$(stat -c%s /tmp/test_bt.raw)
        echo "  📊 Recorded $size bytes"
        rm -f /tmp/test_bt.raw
        if [ $size -gt 1000 ]; then
            return 0
        fi
    fi
    return 1
}

echo "🔵 APPROACH 1: Our working sequence"
pactl set-card-profile "$CARD_NAME" a2dp-sink
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-card-profile "$CARD_NAME" off
sleep 1.0
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1.0

check_source
if test_recording; then
    echo "🎉 APPROACH 1 SUCCESS!"
    exit 0
else
    echo "❌ Approach 1 failed"
fi

echo ""
echo "🔵 APPROACH 2: Activate source manually"
pactl set-default-source "$SOURCE_NAME" 2>/dev/null || true
pactl suspend-source "$SOURCE_NAME" false 2>/dev/null || true
sleep 1.0

check_source
if test_recording; then
    echo "🎉 APPROACH 2 SUCCESS!"
    exit 0
else
    echo "❌ Approach 2 failed"
fi

echo ""
echo "🔵 APPROACH 3: Restart PulseAudio"
echo "  🔵 Restarting PulseAudio..."
pulseaudio -k
sleep 2.0
pulseaudio --start
sleep 2.0

# Redo the sequence after restart
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1.0

check_source
if test_recording; then
    echo "🎉 APPROACH 3 SUCCESS!"
    exit 0
else
    echo "❌ Approach 3 failed"
fi

echo ""
echo "🔵 APPROACH 4: Try different codec"
pactl set-card-profile "$CARD_NAME" headset-head-unit-cvsd
sleep 1.0

check_source
if test_recording; then
    echo "🎉 APPROACH 4 SUCCESS!"
    exit 0
else
    echo "❌ Approach 4 failed"
fi

echo ""
echo "❌ All approaches failed"

# Reset to A2DP
pactl set-card-profile "$CARD_NAME" a2dp-sink

