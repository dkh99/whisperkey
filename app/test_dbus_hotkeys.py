That means we're coding.

(This was dictated. If some words look odd, it might be because they sound like something else you know the sound of.)#!/usr/bin/env python3
"""Test script to verify GNOME extension hotkey detection via DBus."""

import sys
import signal
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtDBus import QDBusConnection

# Add the app directory to path
sys.path.insert(0, '.')

from whisperkey.dbus_hotkey_manager import DBusHotkeyManager, RecordingMode


def on_toggle():
    print("🔥 HOTKEY TOGGLED signal received!")


def main():
    # Create Qt application (needed for DBus)
    app = QCoreApplication(sys.argv)
    
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    print("🚀 Starting DBus hotkey test...")
    print("Press Super+Alt+G to test hotkey detection from GNOME extension")
    print("Press Ctrl+C to quit\n")
    
    try:
        # Create DBus hotkey manager
        manager = DBusHotkeyManager()
        
        # This is a bit of a hack for the test script.
        # In the real app, we'd have separate start/stop callbacks.
        # Here, we'll just use the start callback to signal a toggle.
        manager.on_start_recording = on_toggle
        manager.on_stop_recording = on_toggle

        print("✅ DBus hotkey manager initialized")
        print("Waiting for hotkey signals from GNOME extension...\n")
        
        # Run the event loop
        return app.exec()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 