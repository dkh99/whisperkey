#!/bin/bash

# Test script for Bluetooth microphone switching - COMPREHENSIVE PERMUTATION TESTING
# Based on our successful manual testing sequence

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
OUTPUT_SINK="bluez_output.20_18_5B_1E_72_6C.1"
INPUT_SOURCE="bluez_input.20_18_5B_1E_72_6C.0"

echo "🔵 COMPREHENSIVE Bluetooth microphone switching test..."

# Function to check current state
check_state() {
    echo "📊 Current state:"
    echo "  Card profile: $(pactl list cards | grep -A 20 "$CARD_NAME" | grep "Active Profile" | cut -d: -f2 | xargs)"
    echo "  Sink status: $(pactl list sinks short | grep bluez || echo "No Bluetooth sink")"
    echo "  Source status: $(pactl list sources short | grep bluez || echo "No Bluetooth source")"
    echo "  Available ports:"
    pactl list cards | grep -A 30 "$CARD_NAME" | grep -E "(headphone|handsfree)" | head -4
    echo ""
}

# Function to test recording
test_recording() {
    local test_name="$1"
    echo "🎤 Testing recording for: $test_name"
    timeout 3s parec --device "$INPUT_SOURCE" --rate 16000 --channels 1 --format s16le --raw /tmp/test_bt_${test_name}.raw 2>/dev/null
    local bytes=$(wc -c < /tmp/test_bt_${test_name}.raw 2>/dev/null || echo 0)
    echo "  📊 Recorded: $bytes bytes"
    if [ "$bytes" -gt 1000 ]; then
        echo "  ✅ SUCCESS: Recording worked!"
        return 0
    else
        echo "  ❌ FAILED: No audio data"
        return 1
    fi
}

echo "🔵 Starting from current state..."
check_state

echo "🔵 PERMUTATION 1: Direct profile + port switch"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1
pactl set-sink-port "$OUTPUT_SINK" headphone-hf-output 2>/dev/null || echo "  ⚠️ Port switch failed"
sleep 1
check_state
test_recording "perm1"

echo "🔵 PERMUTATION 2: Reset + profile + port + source activation"
pactl set-card-profile "$CARD_NAME" off
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1
pactl set-sink-port "$OUTPUT_SINK" headphone-hf-output 2>/dev/null || echo "  ⚠️ Port switch failed"
sleep 0.5
pactl set-default-source "$INPUT_SOURCE" 2>/dev/null || echo "  ⚠️ Set default source failed"
pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null || echo "  ⚠️ Unsuspend failed"
sleep 1
check_state
test_recording "perm2"

echo "🔵 PERMUTATION 3: Profile + wait + force source activation"
pactl set-card-profile "$CARD_NAME" off
sleep 0.3
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 2
pactl set-default-source "$INPUT_SOURCE" 2>/dev/null
pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null
# Try multiple times
for i in {1..3}; do
    pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null
    sleep 0.2
done
sleep 1
check_state
test_recording "perm3"

echo "🔵 PERMUTATION 4: Try different profile first"
pactl set-card-profile "$CARD_NAME" headset-head-unit-cvsd
sleep 1
pactl set-sink-port "$OUTPUT_SINK" headphone-hf-output 2>/dev/null || echo "  ⚠️ Port switch failed"
sleep 1
check_state
test_recording "perm4"

echo "🔵 PERMUTATION 5: Manual sink port detection and switching"
echo "  🔍 Available sink ports:"
pactl list sinks | grep -A 10 "$OUTPUT_SINK" | grep -E "(Port|Active)"
echo "  🔄 Trying to switch to handsfree port..."
pactl set-sink-port "$OUTPUT_SINK" handsfree 2>/dev/null || echo "  ⚠️ 'handsfree' port failed"
pactl set-sink-port "$OUTPUT_SINK" headphone-hf-output 2>/dev/null || echo "  ⚠️ 'headphone-hf-output' port failed"
sleep 1
check_state
test_recording "perm5"

echo "🔵 PERMUTATION 6: Force sink to running state"
pactl set-card-profile "$CARD_NAME" off
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1
pactl set-default-sink "$OUTPUT_SINK" 2>/dev/null || echo "  ⚠️ Set default sink failed"
pactl suspend-sink "$OUTPUT_SINK" false 2>/dev/null || echo "  ⚠️ Unsuspend sink failed"
sleep 0.5
pactl set-default-source "$INPUT_SOURCE" 2>/dev/null
pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null
sleep 1
check_state
test_recording "perm6"

echo "🔵 PERMUTATION 7: Try with audio playing to activate bidirectional"
pactl set-card-profile "$CARD_NAME" off
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1
echo "  🔊 Playing test audio to activate bidirectional flow..."
paplay /usr/share/sounds/alsa/Front_Left.wav &
PLAY_PID=$!
sleep 0.5
pactl set-default-source "$INPUT_SOURCE" 2>/dev/null
pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null
sleep 1
kill $PLAY_PID 2>/dev/null || true
check_state
test_recording "perm7"

echo "🔵 PERMUTATION 8: Try headset-head-unit (basic) profile"
pactl set-card-profile "$CARD_NAME" off
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit
sleep 1
pactl set-sink-port "$OUTPUT_SINK" headphone-hf-output 2>/dev/null || echo "  ⚠️ Port switch failed"
sleep 1
check_state
test_recording "perm8"

echo "🔵 PERMUTATION 9: Longer waits + multiple activation attempts"
pactl set-card-profile "$CARD_NAME" off
sleep 1
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 3
for i in {1..5}; do
    echo "  🔄 Activation attempt $i..."
    pactl set-default-source "$INPUT_SOURCE" 2>/dev/null
    pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null
    sleep 0.5
done
check_state
test_recording "perm9"

echo "🔵 PERMUTATION 10: Test with concurrent parec to force activation"
pactl set-card-profile "$CARD_NAME" off
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 1
echo "  🎤 Starting background parec to force source activation..."
timeout 5s parec --device "$INPUT_SOURCE" --rate 16000 --channels 1 --format s16le --raw /tmp/test_concurrent.raw &
PAREC_PID=$!
sleep 1
pactl suspend-source "$INPUT_SOURCE" false 2>/dev/null
sleep 2
kill $PAREC_PID 2>/dev/null || true
check_state
test_recording "perm10"

echo "🔵 FINAL STATE CHECK:"
check_state

echo "🔵 SUMMARY: Checking which tests produced audio data..."
for i in {1..10}; do
    if [ -f "/tmp/test_bt_perm$i.raw" ]; then
        bytes=$(wc -c < "/tmp/test_bt_perm$i.raw" 2>/dev/null || echo 0)
        if [ "$bytes" -gt 1000 ]; then
            echo "  ✅ PERMUTATION $i: SUCCESS ($bytes bytes)"
        else
            echo "  ❌ PERMUTATION $i: FAILED ($bytes bytes)"
        fi
    else
        echo "  ❌ PERMUTATION $i: NO FILE"
    fi
done

echo "🔵 Restoring to high quality mode..."
pactl set-card-profile "$CARD_NAME" a2dp-sink
pactl set-sink-port "$OUTPUT_SINK" headphone-output 2>/dev/null || echo "  ⚠️ Failed to restore headphone port"
echo "✅ Test complete!" 