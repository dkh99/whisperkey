#!/bin/bash

# Create autostart file for WhisperKey

AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/whisperkey.desktop"

# Create autostart directory if it doesn't exist
mkdir -p "$AUTOSTART_DIR"

# Create desktop file
cat > "$AUTOSTART_FILE" << 'EOF'
[Desktop Entry]
Type=Application
Name=WhisperKey
Comment=Voice dictation application for Linux
Exec=whisperkey
Icon=audio-input-microphone
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF

# Make the script executable
chmod +x "$AUTOSTART_FILE"

echo "✅ Autostart file created at $AUTOSTART_FILE"
echo "   WhisperKey will start automatically on login" 