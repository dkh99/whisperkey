# WhisperKey Debian/Ubuntu Installation Guide

This guide explains how to install WhisperKey on Ubuntu or Debian systems using the native `.deb` package format.

## 📦 About the Debian Package

The WhisperKey `.deb` package provides a complete, production-ready installation that:

- ✅ **Automatically installs all system dependencies** via `apt`
- ✅ **Sets up Python environment** with `uv` and `pipx`
- ✅ **Installs GNOME extension** with proper permissions
- ✅ **Configures Wayland support** via `ydotool`
- ✅ **Creates autostart entry** for automatic startup
- ✅ **Sets up global hotkeys** (Alt+Space and Super+Alt+G)
- ✅ **Handles clean uninstallation** with purge support

This is the **recommended installation method** for Ubuntu/Debian systems.

---

## 🚀 Quick Installation

### Option 1: Build and Install (Recommended)

If you have the source code:

```bash
# Clone the repository
git clone https://github.com/yourusername/voxvibe.git
cd voxvibe

# Build and install the package
make deb-install
```

This single command will:
1. Build the `.deb` package
2. Install it with all dependencies
3. Configure everything automatically

### Option 2: Install Pre-built Package

If you downloaded a pre-built `.deb` file:

```bash
# Install the package
sudo dpkg -i whisperkey_0.2.1_all.deb

# Fix any missing dependencies
sudo apt-get install -f
```

---

## 📋 System Requirements

### Minimum Requirements

- **OS**: Ubuntu 22.04+ or Debian 12+
- **Desktop**: GNOME Shell 42+
- **Python**: 3.11 or higher
- **Architecture**: Any (package is architecture-independent)

### Supported Environments

- ✅ Ubuntu 22.04 LTS (Jammy Jellyfish)
- ✅ Ubuntu 24.04 LTS (Noble Numbat)
- ✅ Debian 12 (Bookworm)
- ✅ Debian 13 (Trixie)
- ✅ Other GNOME-based distributions

---

## 🔧 Manual Build Process

If you want to build the package manually:

### 1. Install Build Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    dpkg-dev \
    libglib2.0-dev \
    python3-dev \
    portaudio19-dev
```

### 2. Install `uv` Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env  # or restart your terminal
```

### 3. Build the Package

```bash
# From the repository root
./build-deb.sh
```

This will create: `dist/whisperkey_0.2.1_all.deb`

### 4. Install the Package

```bash
sudo dpkg -i dist/whisperkey_0.2.1_all.deb
sudo apt-get install -f  # Install any missing dependencies
```

---

## 🎯 Post-Installation Steps

### 1. Log Out and Back In

**This is required** to activate:
- GNOME extension
- ydotool permissions (Wayland)
- Autostart configuration

```bash
# Log out
gnome-session-quit --logout
```

### 2. Enable GNOME Extension

After logging back in, enable the extension:

```bash
gnome-extensions enable whisperkey@whisperkey.app
```

Or use the GNOME Extensions app (GUI).

### 3. Verify Installation

Check that everything is working:

```bash
# Check WhisperKey is installed
whisperkey --version

# Check if running
ps aux | grep whisperkey

# Test hotkey configuration
gsettings get org.gnome.shell.extensions.whisperkey toggle-recording
```

Expected output: `['<Alt>space', '<Super><Alt>g']`

### 4. Start Using WhisperKey

WhisperKey will auto-start on next login, or start it manually:

```bash
whisperkey &
```

Look for the microphone icon in your system tray.

---

## 🎮 Using WhisperKey

### Hotkeys

| Hotkey | Action |
|--------|--------|
| **Alt+Space** | Hold to record, release to transcribe and paste |
| **Super+Alt+G** | Alternative recording hotkey |

### System Tray

Right-click the microphone icon to:
- View transcription history
- Paste previous transcriptions
- Access settings
- Quit the application

---

## 🛠️ Package Management

### Check Installation Status

```bash
# Check if installed
dpkg -l | grep whisperkey

# Show package details
dpkg -s whisperkey

# List installed files
dpkg -L whisperkey
```

### Reinstall or Upgrade

```bash
# Build new package
make deb

# Upgrade (overwrites old version)
sudo dpkg -i dist/whisperkey_0.2.1_all.deb
```

### Uninstall

```bash
# Remove package but keep configuration
sudo apt-get remove whisperkey

# Remove package AND all configuration (purge)
sudo apt-get purge whisperkey
```

**Note**: Purging will remove:
- Autostart configuration
- GNOME extension
- pipx installation
- User data in `~/.cache/whisperkey` (preserved, but notified)

---

## 🐛 Troubleshooting

### Installation Fails with Dependency Errors

```bash
# Fix missing dependencies
sudo apt-get update
sudo apt-get install -f
```

### Package Won't Install (Held Packages)

```bash
# Check for held packages
dpkg --get-selections | grep hold

# Unhold if needed
sudo apt-mark unhold package-name
```

### GNOME Extension Not Loading

```bash
# Check extension status
gnome-extensions list
gnome-extensions info whisperkey@whisperkey.app

# Reinstall extension manually
sudo dpkg-reconfigure whisperkey
```

### Hotkeys Not Working

```bash
# Reset and reconfigure hotkeys
gsettings reset org.gnome.shell.extensions.whisperkey toggle-recording
gsettings set org.gnome.shell.extensions.whisperkey toggle-recording "['<Alt>space', '<Super><Alt>g']"

# Restart GNOME Shell (X11 only)
Alt+F2, type 'r', press Enter

# On Wayland, log out and back in
gnome-session-quit --logout
```

### ydotool Permission Denied (Wayland)

```bash
# Check ydotool service
systemctl status ydotool

# Restart service
sudo systemctl restart ydotool

# Check user groups
groups $USER

# Add to input group (requires logout)
sudo usermod -a -G input $USER
```

### WhisperKey Not Auto-starting

```bash
# Check autostart file
ls -la ~/.config/autostart/whisperkey.desktop

# Recreate if missing
sudo dpkg-reconfigure whisperkey
```

---

## 📁 Package Contents

The `.deb` package installs files to:

```
/usr/share/whisperkey/           # Application files
├── whisperkey-0.2.1-py3-none-any.whl  # Python wheel
└── extension/                          # GNOME extension
    ├── extension.js
    ├── metadata.json
    └── schemas/

/usr/share/doc/whisperkey/       # Documentation
├── README.md
├── LICENSE
├── copyright
└── CHANGELOG.md

~/.local/share/gnome-shell/extensions/whisperkey@whisperkey.app/
                                  # User-installed extension

~/.config/autostart/whisperkey.desktop
                                  # Autostart entry

~/.local/pipx/venvs/whisperkey/  # Python virtual environment
```

---

## 🔍 Advanced Configuration

### Change Installation User

The package installs for the user who ran `sudo`. To install for a different user:

```bash
sudo -u targetuser dpkg -i whisperkey_0.2.1_all.deb
```

### Custom Hotkeys

After installation, customize hotkeys:

```bash
# Set custom hotkeys
gsettings set org.gnome.shell.extensions.whisperkey toggle-recording "['<Primary><Alt>v', '<Super>v']"
```

### Disable Autostart

```bash
# Disable autostart
rm ~/.config/autostart/whisperkey.desktop

# Or modify the file
sed -i 's/X-GNOME-Autostart-enabled=true/X-GNOME-Autostart-enabled=false/' ~/.config/autostart/whisperkey.desktop
```

---

## 🏗️ Development Installation

For developers who want to modify WhisperKey:

```bash
# Don't use the .deb package for development
# Instead, use the manual installation:

cd voxvibe/app
uv sync
uv run python -m whisperkey
```

See the main `README.md` for development setup.

---

## 📚 Additional Resources

- **Main README**: `README.md` - General usage guide
- **Build Script**: `build-deb.sh` - Package building details
- **Control Files**: `debian-package/DEBIAN/` - Package metadata
- **Changelog**: `CHANGELOG.md` - Version history

---

## ❓ Getting Help

### Check Logs

```bash
# Run WhisperKey in terminal to see logs
whisperkey

# Check system logs
journalctl -xe | grep whisperkey
```

### Report Issues

If you encounter problems:

1. **Collect diagnostic info**:
   ```bash
   dpkg -s whisperkey
   gnome-shell --version
   uv --version
   systemctl status ydotool
   ```

2. **Check for known issues** in the repository

3. **Submit a bug report** with:
   - Ubuntu/Debian version
   - Installation method
   - Error messages
   - Logs from terminal

---

## 🎉 Success!

Once installed, WhisperKey provides:

- 🎤 **Voice transcription** anywhere in the system
- ⚡ **Instant text pasting** with global hotkeys
- 📚 **Transcription history** in the system tray
- 🚀 **Auto-start** on every login
- 🖥️ **Native Wayland & X11 support**

Enjoy using WhisperKey! 🎉


