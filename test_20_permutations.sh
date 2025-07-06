#!/bin/bash

# VoxVibe Bluetooth 20 Permutations Test
# This script tries 20 different switching strategies to find the working one

set -e

CARD_NAME="bluez_card.20_18_5B_1E_72_6C"
SOURCE_NAME="bluez_input.20_18_5B_1E_72_6C.0"
SINK_NAME="bluez_output.20_18_5B_1E_72_6C.1"
TEST_DURATION=3

echo "🔵 VoxVibe Bluetooth 20 Permutations Test"
echo "🔵 Target: $SOURCE_NAME"
echo "🔵 Card: $CARD_NAME"
echo ""

# Function to reset to high quality mode
reset_to_high_quality() {
    echo "🔄 Resetting to high quality A2DP mode..."
    pactl set-card-profile "$CARD_NAME" a2dp-sink 2>/dev/null || true
    pactl set-sink-port "$SINK_NAME" headphone-output 2>/dev/null || true
    sleep 1
    echo "✅ Reset to A2DP mode complete"
}

# Function to test if Bluetooth microphone is working
test_bluetooth_mic() {
    local attempt_name="$1"
    echo "🔵 Testing $attempt_name with 3-second recording..."
    
    # Try to record 3 seconds of audio
    timeout 3s parec --device="$SOURCE_NAME" --rate=16000 --channels=1 --format=s16le --raw > /tmp/bt_test.raw 2>/dev/null || true
    
    # Check file size
    if [ -f /tmp/bt_test.raw ]; then
        local size=$(stat -c%s /tmp/bt_test.raw 2>/dev/null || echo 0)
        echo "📊 Recorded $size bytes"
        
        if [ "$size" -gt 32000 ]; then  # At least 1 second of 16kHz mono
            echo "🎉 SUCCESS! $attempt_name works! ($size bytes)"
            return 0
        else
            echo "❌ FAILED: $attempt_name ($size bytes)"
            rm -f /tmp/bt_test.raw
            return 1
        fi
    else
        echo "❌ FAILED: $attempt_name (no file created)"
        return 1
    fi
}

# Function to get current profile
get_current_profile() {
    pactl list cards | grep -A 20 "$CARD_NAME" | grep "Active Profile:" | awk '{print $3}' || echo "unknown"
}

echo "🚀 Starting 20 permutation test..."
echo ""

# PERMUTATION 1: Direct switch to headset when already in headset
reset_to_high_quality
echo "1️⃣ PERMUTATION 1: Direct headset switch when already in headset"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc  # Double switch
sleep 0.5
if test_bluetooth_mic "Permutation 1"; then exit 0; fi

# PERMUTATION 2: A2DP -> headset with port switch
reset_to_high_quality
echo "2️⃣ PERMUTATION 2: A2DP -> headset + port switch"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
pactl set-sink-port "$SINK_NAME" headphone-hf-output 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 2"; then exit 0; fi

# PERMUTATION 3: A2DP -> off -> headset
reset_to_high_quality
echo "3️⃣ PERMUTATION 3: A2DP -> off -> headset"
pactl set-card-profile "$CARD_NAME" off
sleep 1
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
if test_bluetooth_mic "Permutation 3"; then exit 0; fi

# PERMUTATION 4: A2DP -> headset -> off -> headset
reset_to_high_quality
echo "4️⃣ PERMUTATION 4: A2DP -> headset -> off -> headset"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-card-profile "$CARD_NAME" off
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
if test_bluetooth_mic "Permutation 4"; then exit 0; fi

# PERMUTATION 5: A2DP -> headset + activate source
reset_to_high_quality
echo "5️⃣ PERMUTATION 5: A2DP -> headset + activate source"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-default-source "$SOURCE_NAME" 2>/dev/null || true
pactl suspend-source "$SOURCE_NAME" false 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 5"; then exit 0; fi

# PERMUTATION 6: A2DP -> headset + port switch + activate
reset_to_high_quality
echo "6️⃣ PERMUTATION 6: A2DP -> headset + port switch + activate"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
pactl set-sink-port "$SINK_NAME" headphone-hf-output 2>/dev/null || true
pactl set-default-source "$SOURCE_NAME" 2>/dev/null || true
pactl suspend-source "$SOURCE_NAME" false 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 6"; then exit 0; fi

# PERMUTATION 7: A2DP -> CVSD -> mSBC
reset_to_high_quality
echo "7️⃣ PERMUTATION 7: A2DP -> CVSD -> mSBC"
pactl set-card-profile "$CARD_NAME" headset-head-unit-cvsd
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
if test_bluetooth_mic "Permutation 7"; then exit 0; fi

# PERMUTATION 8: A2DP -> basic headset -> mSBC
reset_to_high_quality
echo "8️⃣ PERMUTATION 8: A2DP -> basic headset -> mSBC"
pactl set-card-profile "$CARD_NAME" headset-head-unit
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
if test_bluetooth_mic "Permutation 8"; then exit 0; fi

# PERMUTATION 9: A2DP -> headset with longer delay
reset_to_high_quality
echo "9️⃣ PERMUTATION 9: A2DP -> headset with 2s delay"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 2
if test_bluetooth_mic "Permutation 9"; then exit 0; fi

# PERMUTATION 10: A2DP -> headset -> double port switch
reset_to_high_quality
echo "🔟 PERMUTATION 10: A2DP -> headset -> double port switch"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
pactl set-sink-port "$SINK_NAME" headphone-output 2>/dev/null || true
sleep 0.2
pactl set-sink-port "$SINK_NAME" headphone-hf-output 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 10"; then exit 0; fi

# PERMUTATION 11: Multiple rapid switches
reset_to_high_quality
echo "1️⃣1️⃣ PERMUTATION 11: Multiple rapid switches"
for i in {1..3}; do
    pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
    sleep 0.1
done
sleep 0.5
if test_bluetooth_mic "Permutation 11"; then exit 0; fi

# PERMUTATION 12: A2DP -> headset with source port manipulation
reset_to_high_quality
echo "1️⃣2️⃣ PERMUTATION 12: A2DP -> headset + source port"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
# Try to set source port if it exists
pactl set-source-port "$SOURCE_NAME" headphone-hf-input 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 12"; then exit 0; fi

# PERMUTATION 13: A2DP -> off -> long delay -> headset
reset_to_high_quality
echo "1️⃣3️⃣ PERMUTATION 13: A2DP -> off -> 3s delay -> headset"
pactl set-card-profile "$CARD_NAME" off
sleep 3
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
if test_bluetooth_mic "Permutation 13"; then exit 0; fi

# PERMUTATION 14: A2DP -> headset -> restart pulseaudio source
reset_to_high_quality
echo "1️⃣4️⃣ PERMUTATION 14: A2DP -> headset -> restart pulse source"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl suspend-source "$SOURCE_NAME" true 2>/dev/null || true
sleep 0.2
pactl suspend-source "$SOURCE_NAME" false 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 14"; then exit 0; fi

# PERMUTATION 15: A2DP -> SBC-XQ -> headset
reset_to_high_quality
echo "1️⃣5️⃣ PERMUTATION 15: A2DP -> SBC-XQ -> headset"
pactl set-card-profile "$CARD_NAME" a2dp-sink-sbc_xq
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
if test_bluetooth_mic "Permutation 15"; then exit 0; fi

# PERMUTATION 16: A2DP -> headset -> force sink switch
reset_to_high_quality
echo "1️⃣6️⃣ PERMUTATION 16: A2DP -> headset -> force sink"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-default-sink "$SINK_NAME" 2>/dev/null || true
pactl set-default-source "$SOURCE_NAME" 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 16"; then exit 0; fi

# PERMUTATION 17: A2DP -> headset -> move all streams
reset_to_high_quality
echo "1️⃣7️⃣ PERMUTATION 17: A2DP -> headset -> move streams"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
# Move all sink inputs to the Bluetooth sink
pactl list short sink-inputs | while read stream; do
    stream_id=$(echo $stream | cut -d$'\t' -f1)
    pactl move-sink-input "$stream_id" "$SINK_NAME" 2>/dev/null || true
done
sleep 0.5
if test_bluetooth_mic "Permutation 17"; then exit 0; fi

# PERMUTATION 18: A2DP -> headset -> cycle through all ports
reset_to_high_quality
echo "1️⃣8️⃣ PERMUTATION 18: A2DP -> headset -> cycle ports"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-sink-port "$SINK_NAME" headphone-output 2>/dev/null || true
sleep 0.2
pactl set-sink-port "$SINK_NAME" headphone-hf-output 2>/dev/null || true
sleep 0.2
pactl set-source-port "$SOURCE_NAME" headphone-hf-input 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 18"; then exit 0; fi

# PERMUTATION 19: A2DP -> headset -> volume manipulation
reset_to_high_quality
echo "1️⃣9️⃣ PERMUTATION 19: A2DP -> headset -> volume manipulation"
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-source-volume "$SOURCE_NAME" 65536 2>/dev/null || true  # 100%
pactl set-source-mute "$SOURCE_NAME" false 2>/dev/null || true
sleep 0.5
if test_bluetooth_mic "Permutation 19"; then exit 0; fi

# PERMUTATION 20: The kitchen sink - everything together
reset_to_high_quality
echo "2️⃣0️⃣ PERMUTATION 20: Kitchen sink - everything!"
pactl set-card-profile "$CARD_NAME" off
sleep 1
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc
sleep 0.5
pactl set-card-profile "$CARD_NAME" headset-head-unit-msbc  # Double switch
sleep 0.2
pactl set-sink-port "$SINK_NAME" headphone-hf-output 2>/dev/null || true
pactl set-source-port "$SOURCE_NAME" headphone-hf-input 2>/dev/null || true
pactl set-default-source "$SOURCE_NAME" 2>/dev/null || true
pactl set-default-sink "$SINK_NAME" 2>/dev/null || true
pactl suspend-source "$SOURCE_NAME" false 2>/dev/null || true
pactl set-source-volume "$SOURCE_NAME" 65536 2>/dev/null || true
pactl set-source-mute "$SOURCE_NAME" false 2>/dev/null || true
sleep 1
if test_bluetooth_mic "Permutation 20"; then exit 0; fi

echo ""
echo "❌ ALL 20 PERMUTATIONS FAILED!"
echo "🔍 The Bluetooth microphone is not working with any of these approaches."
echo ""
echo "📊 Summary:"
echo "- Tested 20 different switching strategies"
echo "- Always reset to A2DP high quality mode between tests"
echo "- None produced working audio data"
echo ""
echo "🔧 Possible issues:"
echo "1. Hardware/driver problem with Bluetooth microphone"
echo "2. PipeWire/PulseAudio configuration issue"
echo "3. Bluetooth codec negotiation failure"
echo "4. SCO transport not establishing properly"

# Clean up
reset_to_high_quality
rm -f /tmp/bt_test.raw

exit 1 