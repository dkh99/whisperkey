# WhisperKey - Quick Ubuntu Installation

**For Fresh Ubuntu Installations** 🚀

This is the fastest way to get WhisperKey running on a fresh Ubuntu install.

---

## One-Command Installation

```bash
# Clone, build, and install
git clone https://github.com/yourusername/voxvibe.git && cd voxvibe && make deb-install
```

That's it! ✨

---

## What This Does

1. ✅ Installs all system dependencies (Python, PortAudio, ydotool, etc.)
2. ✅ Builds the `.deb` package with all prerequisites
3. ✅ Installs WhisperKey system-wide
4. ✅ Sets up GNOME extension and hotkeys
5. ✅ Configures autostart
6. ✅ Enables Wayland support

---

## After Installation

### 1. Log Out and Back In

```bash
gnome-session-quit --logout
```

This activates:
- GNOME extension
- Wayland permissions
- Autostart

### 2. Enable Extension (First Time)

```bash
gnome-extensions enable whisperkey@whisperkey.app
```

### 3. Start Using!

- Look for the microphone 🎤 icon in your system tray
- Press **Alt+Space** and speak
- Release to transcribe and paste

---

## Requirements

- Ubuntu 22.04 LTS or newer
- GNOME desktop environment
- Internet connection (for dependency downloads)

---

## Manual Step-by-Step (If Needed)

If the one-command installation doesn't work:

### 1. Install Git (if not present)

```bash
sudo apt-get update
sudo apt-get install -y git
```

### 2. Clone Repository

```bash
git clone https://github.com/yourusername/voxvibe.git
cd voxvibe
```

### 3. Build Package

```bash
make deb
```

### 4. Install Package

```bash
sudo apt install ./dist/whisperkey_0.3.3_all.deb
```

### 5. Log Out and Back In

```bash
gnome-session-quit --logout
```

---

## Troubleshooting

### "make: command not found"

```bash
sudo apt-get install -y build-essential
```

### "git: command not found"

```bash
sudo apt-get install -y git
```

### "dpkg-deb: command not found"

```bash
sudo apt-get install -y dpkg-dev
```

### Dependencies Won't Install

```bash
sudo apt-get update
sudo apt-get install -f
```

---

## Verify Installation

```bash
# Check WhisperKey is installed
whisperkey --version

# Check extension is enabled
gnome-extensions list | grep whisperkey

# Test hotkey configuration
gsettings get org.gnome.shell.extensions.whisperkey toggle-recording
```

Should show: `['<Alt>space', '<Super><Alt>g']`

---

## Uninstall

```bash
# Remove WhisperKey
sudo apt-get remove whisperkey

# Remove all configuration (complete purge)
sudo apt-get purge whisperkey
```

---

## Full Documentation

For detailed information, see:
- `INSTALL-DEBIAN.md` - Complete Debian/Ubuntu installation guide
- `README.md` - General usage and features
- `make help` - All available build commands

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `make deb` | Build .deb package |
| `make deb-install` | Build and install |
| `make deb-clean` | Clean build artifacts |
| `whisperkey` | Start WhisperKey manually |
| `Alt+Space` | Record and transcribe (hold) |
| `Super+Alt+G` | Alternative hotkey |

---

**Need help?** Check `INSTALL-DEBIAN.md` for troubleshooting and advanced configuration.

Happy transcribing! 🎉


