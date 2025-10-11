# WhisperKey - Voice Transcription for Linux

**Quick: Install voice dictation on your Ubuntu/Debian system!**

## What is this?

WhisperKey gives you voice-to-text transcription anywhere on your Linux desktop. Just press a hotkey, speak, and your words appear as text - in any application.

## Installation (Super Simple!)

```bash
# 1. Install the package
sudo dpkg -i whisperkey_0.2.1_all.deb
sudo apt-get install -f

# 2. Log out and back in

# 3. Enable the extension
gnome-extensions enable whisperkey@whisperkey.app

# 4. Done!
```

## Usage

| Action | How |
|--------|-----|
| **Quick dictation** | Press **Alt+Space**, speak, release |
| **Alternative** | Press **Super+Alt+G**, speak, release |
| **View history** | Right-click microphone icon |
| **Repeat last** | Double-click microphone icon |

## What You Get

- ✅ **Global hotkeys** - Works in any application
- ✅ **Instant transcription** - 0.25s response time
- ✅ **Transcription history** - Access recent text via tray menu
- ✅ **Auto-start** - Launches on login
- ✅ **Local processing** - All transcription happens on your machine (private!)
- ✅ **Wayland & X11** - Works on both display servers

## Requirements

- Ubuntu 22.04+ or Debian 12+
- GNOME desktop environment
- Microphone
- ~2GB disk space (for AI models)

## First Run

When you first use WhisperKey, it will:
1. Download speech recognition models (~1.5GB)
2. This takes 2-5 minutes depending on your connection
3. After that, everything runs instantly offline

## Troubleshooting

### "Dependency problems"
```bash
sudo apt-get install -f
```

### Hotkeys don't work
1. Log out and back in
2. Run: `gnome-extensions enable whisperkey@whisperkey.app`

### No microphone icon
```bash
whisperkey &
```

### Permission errors (Wayland)
Log out and back in (group membership needs refresh)

## Testing

After installation:

```bash
# Check it's installed
whisperkey --version

# Check extension is enabled  
gnome-extensions list | grep whisperkey

# Test hotkeys
gsettings get org.gnome.shell.extensions.whisperkey toggle-recording
# Should show: ['<Alt>space', '<Super><Alt>g']
```

## Uninstall

```bash
# Remove application
sudo apt-get remove whisperkey

# Remove everything including settings
sudo apt-get purge whisperkey
```

## Privacy

**100% Local Processing**
- All transcription happens on YOUR computer
- No internet required after initial setup
- No data sent to cloud services
- Your voice never leaves your machine

## Technical Details

- **Engine**: Whisper AI (OpenAI's speech recognition)
- **Python**: 3.11+ required (auto-installed)
- **GNOME**: Version 42+ required
- **Audio**: PortAudio for recording
- **Clipboard**: ydotool (Wayland) or xdotool (X11)

## Package Info

- **Package**: `whisperkey_0.2.1_all.deb`
- **Size**: 100KB (models downloaded separately)
- **Type**: Debian binary package
- **Format**: .deb (standard Ubuntu/Debian format)

## Getting Help

1. Check the full documentation:
   ```bash
   cat /usr/share/doc/whisperkey/README.md
   ```

2. View logs:
   ```bash
   # Run in terminal to see debug output
   whisperkey
   ```

3. Check if running:
   ```bash
   ps aux | grep whisperkey
   ```

## What Happens During Installation?

The installer:
1. ✅ Installs Python 3.11+ (if needed)
2. ✅ Installs system libraries (PortAudio, etc.)
3. ✅ Sets up Python package manager (uv, pipx)
4. ✅ Installs WhisperKey application
5. ✅ Installs GNOME extension for hotkeys
6. ✅ Configures Wayland support (ydotool)
7. ✅ Sets up auto-start
8. ✅ Configures default hotkeys (Alt+Space)

All automatic - just approve the prompts!

## Examples

**Writing an email:**
1. Click in email body
2. Press Alt+Space
3. Say: "Hi team, just wanted to follow up on our meeting yesterday..."
4. Release Alt+Space
5. Text appears in your email!

**Coding comments:**
1. Click in your code editor
2. Press Alt+Space  
3. Say: "This function calculates the fibonacci sequence recursively..."
4. Release
5. Comment appears in your code!

**Quick notes:**
1. Open any text editor
2. Press Alt+Space
3. Speak your thoughts
4. Release
5. Keep pressing Alt+Space for more notes!

## Cool Features

- **History**: Right-click tray icon to see and re-use previous transcriptions
- **Fast**: 0.25s from release to text appearing
- **Smart**: Automatically capitalizes and punctuates
- **Reliable**: Uses state-of-the-art Whisper AI model
- **Background**: Runs quietly, uses minimal resources

## System Requirements Check

Before installing, check:

```bash
# Check Ubuntu version (need 22.04+)
lsb_release -a

# Check GNOME version (need 42+)
gnome-shell --version

# Check Python (need 3.11+, but will be installed)
python3 --version

# Check microphone
arecord -l
```

## Ready to Install?

Just run:
```bash
sudo dpkg -i whisperkey_0.2.1_all.deb && sudo apt-get install -f
```

Then log out and back in!

---

**Enjoy WhisperKey!** 🎤✨

*Built on October 9, 2025*


