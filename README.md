# Whisper Key v0.3.3 🎤

**Fast, reliable voice transcription with global hotkeys for Linux**

Whisper Key is a unified Python application that provides instant speech-to-text transcription with global hotkeys. Simply hold **Win+Alt** and speak - Whisper Key will transcribe your speech and paste it directly where you need it.

## ✨ Features

- **🚀 Ultra-fast pasting** (0.25s response time)
- **🎯 Global hotkeys** - Works anywhere in the system
- **📚 Transcription history** - Access recent transcriptions via tray menu  
- **🔄 Auto-startup** - Runs automatically when you log in
- **🖥️ Native Wayland & X11 support** - Works on any Linux desktop
- **🎨 Clean system tray integration** - Unobtrusive background operation

## 🎯 Quick Start

1. **Clone and install:**
   ```bash
   git clone <repository-url>
   cd whisperkey
   make all
   ```

2. **Start using immediately:**
   - Whisper Key will auto-start and appear in your system tray
   - Hold **Win+Alt** and speak to transcribe
   - Text appears instantly where your cursor is

## 📋 Prerequisites

### Required Dependencies

1. **Python 3.11+** - Check with `python3 --version`
2. **uv** - Fast Python package manager
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **PortAudio** - For audio recording
   ```bash
   # Ubuntu/Debian
   sudo apt install -y portaudio19-dev
   
   # Fedora
   sudo dnf install portaudio portaudio-devel
   
   # Arch Linux
   sudo pacman -S portaudio
   ```

### Wayland Support (Recommended)

For optimal Wayland compatibility, install **ydotool**:
```bash
# Ubuntu/Debian  
sudo apt install ydotool

# Fedora
sudo dnf install ydotool

# Arch Linux
sudo pacman -S ydotool
```

**Note:** ydotool requires setup - see [Wayland Setup](#wayland-setup) section below.

## 🔧 Installation

### Debian/Ubuntu Package (Recommended) 🆕

**For Ubuntu/Debian users**, the easiest way to install with all prerequisites:

```bash
# Clone the repository
git clone <repository-url>
cd whisperkey

# Build and install .deb package (handles ALL dependencies)
make deb-install
```

This will:
- ✅ Install ALL system prerequisites automatically
- ✅ Set up Python environment with `uv`
- ✅ Install Whisper Key system-wide
- ✅ Configure auto-startup 
- ✅ Set up system tray integration
- ✅ Enable Wayland support (ydotool)

**See**: `QUICK-INSTALL-UBUNTU.md` for one-line installation, or `INSTALL-DEBIAN.md` for detailed guide.

### Automatic Installation (Other Distributions)

For non-Debian/Ubuntu systems:

```bash
# Clone the repository
git clone <repository-url>
cd whisperkey

# Install everything (requires manual prerequisite installation)
make all
```

This will:
- ✅ Set up Python environment with `uv`
- ✅ Install Whisper Key system-wide
- ✅ Configure auto-startup 
- ✅ Set up system tray integration

### Manual Installation

If you prefer manual control:

```bash
# 1. Setup Python environment
cd app
uv sync

# 2. Build the application  
uv build

# 3. Install globally (choose one option)

# Option A: Using pipx (recommended for system-wide installation)
pipx install dist/whisperkey-*.whl

# Option B: Development mode (runs from source)
# No additional installation needed

# 4. Set up autostart

# For pipx installation:
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/whisperkey.desktop << EOF
[Desktop Entry]
Type=Application
Name=Whisper Key
Comment=Voice transcription with global hotkeys
Exec=whisperkey
Icon=microphone
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Categories=AudioVideo;Audio;
EOF
chmod +x ~/.config/autostart/whisperkey.desktop

# For development mode:
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/whisperkey.desktop << EOF
[Desktop Entry]
Type=Application
Name=Whisper Key
Comment=Voice transcription with global hotkeys
Exec=bash -c "cd /path/to/your/whisperkey/app && uv run python -m whisperkey"
Path=/path/to/your/whisperkey/app
Icon=microphone
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
Categories=AudioVideo;Audio;
EOF
chmod +x ~/.config/autostart/whisperkey.desktop
```

**Note:** Replace `/path/to/your/whisperkey/app` with your actual installation path.

## ⚙️ System Setup

### Wayland Setup

For Wayland systems, configure ydotool:

```bash
# Enable ydotool service
sudo systemctl enable --now ydotool

# Add yourself to input group (may require logout)
sudo usermod -a -G input $USER

# Test ydotool works
ydotool key ctrl+c
```

### Verify Installation

Check that everything is working:

```bash
# Check Whisper Key is installed
whisperkey --version

# Check dependencies
~/check-whisperkey-conflicts.sh  # (created during installation)
```

## 🎮 Usage

### Basic Operation

1. **Start Whisper Key** - It starts automatically on login, or run `whisperkey`
2. **Look for tray icon** - Whisper Key appears in your system tray
3. **Hold Win+Alt and speak** - Release when done speaking
4. **Text appears instantly** - Transcribed text is pasted where your cursor is

### Hotkeys

| Hotkey | Action |
|--------|--------|
| **Win+Alt** (hold) | Record and transcribe speech |
| **Alt+Space** (hold) | Alternative recording hotkey |
| **Win+Alt+Space** | Toggle hands-free mode |
| **Space** | Exit hands-free mode |

### Tray Menu Features

- **📚 Paste from History** - Access your last 15 transcriptions
- **⭐ Last Transcription** - Quickly re-paste the most recent text
- **ℹ️ About** - View version and hotkey information
- **❌ Quit** - Exit Whisper Key

### History Access

- **Recent transcriptions** appear in the tray menu
- **Double-click tray icon** to paste the last transcription
- **Right-click** for full history menu with timestamps

## 🔧 Management

### Start/Stop Whisper Key

```bash
# Manual start
whisperkey

# Stop (from tray menu or)
pkill whisperkey

# Check if running
ps aux | grep whisperkey
```

### Disable Auto-start

```bash
# Disable auto-start
rm ~/.config/autostart/whisperkey.desktop

# Re-enable auto-start
make all  # (re-run installation)
```

### Check for Conflicts

If you experience issues:

```bash
# Run conflict checker (created during installation)
~/check-whisperkey-conflicts.sh

# This will show:
# - Running Whisper Key processes
# - Old extension conflicts  
# - Installation status
```

## 🛠️ Troubleshooting

### Common Issues

**Whisper Key doesn't start on login:**
```bash
# Check autostart file exists
ls -la ~/.config/autostart/whisperkey.desktop

# Recreate if missing
make all
```

**No audio recording:**
```bash
# Check PortAudio installation
python3 -c "import sounddevice; print('PortAudio OK')"

# Install if needed (see Prerequisites)
```

**Pasting doesn't work on Wayland:**
```bash
# Check ydotool is running
systemctl status ydotool

# Enable if needed
sudo systemctl enable --now ydotool
```

**Multiple tray icons or conflicts:**
```bash
# Check for conflicts
~/check-whisperkey-conflicts.sh

# Kill old processes
pkill whisperkey
whisperkey  # Start fresh
```

### Getting Help

If you encounter issues:
1. **Check the conflict detector:** `~/check-whisperkey-conflicts.sh`
2. **View logs:** Whisper Key shows detailed logs when run from terminal
3. **Check audio permissions** - ensure microphone access is enabled

## 🏗️ Development

### Project Structure
```