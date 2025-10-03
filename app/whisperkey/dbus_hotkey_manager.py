"""DBus hotkey manager that receives hotkey signals from the GNOME extension.

This replaces the pynput-based hotkey detection with DBus signals from GNOME.
"""
from __future__ import annotations

from typing import Callable, Optional
from enum import Enum

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage


class RecordingMode(Enum):
    IDLE = "idle"
    HOLD_TO_TALK = "hold_to_talk"
    HANDS_FREE = "hands_free"


class DBusHotkeyManager(QObject):
    """Receives hotkey signals from the GNOME extension via DBus."""
    
    # Qt signals
    toggle_recording_signal = pyqtSignal()
    
    def __init__(self) -> None:
        super().__init__()
        
        self._bus = QDBusConnection.sessionBus()
        if not self._bus.isConnected():
            raise RuntimeError("Cannot connect to the session DBus bus")

        # Ensure the GNOME extension DBus object/interface is available
        self._interface = QDBusInterface(
            "org.gnome.Shell",
            "/org/gnome/Shell/Extensions/WhisperKey",
            "org.gnome.Shell.Extensions.WhisperKey",
            self._bus
        )
        if not self._interface.isValid():
            raise RuntimeError("Whisper Key GNOME extension DBus interface not available. Is the extension enabled?")
        
        # Callbacks
        self.on_start_recording: Optional[Callable] = None
        self.on_stop_recording: Optional[Callable] = None
        self.on_mode_change: Optional[Callable[[RecordingMode], None]] = None
        
        self.mode = RecordingMode.IDLE
        self._recording = False
        
        # Connect to DBus signals
        self._connect_signals()
        
    def _connect_signals(self):
        """Connect to DBus signals from the GNOME extension."""
        success = self._bus.connect(
            "org.gnome.Shell",  # service
            "/org/gnome/Shell/Extensions/WhisperKey",  # path
            "org.gnome.Shell.Extensions.WhisperKey",  # interface
            "ToggleRecording",  # signal name
            self._on_dbus_toggle_recording  # slot method
        )
        
        if success:
            print("🎯 DBus hotkey manager connected to GNOME extension for ToggleRecording")
        else:
            raise RuntimeError("DBus connection for ToggleRecording failed. Is the Whisper Key GNOME extension enabled?")
        
        # Connect internal signals to callbacks
        self.toggle_recording_signal.connect(self._handle_toggle_recording)
    
    @pyqtSlot()
    def _on_dbus_toggle_recording(self):
        """Handle ToggleRecording signal from DBus."""
        print("📡 Received ToggleRecording signal from GNOME")
        self.toggle_recording_signal.emit()
    
    def _handle_toggle_recording(self):
        """Handle toggle recording request (press once to start/stop)."""
        self._recording = not self._recording
        
        if self._recording:
            self.mode = RecordingMode.HANDS_FREE
            print(f"🎤 Starting recording in {self.mode.value} mode (toggle)")
            if self.on_start_recording:
                self.on_start_recording()
        else:
            prev_mode = self.mode
            self.mode = RecordingMode.IDLE
            print(f"🛑 Stopping recording (was in {prev_mode.value} mode)")
            if self.on_stop_recording:
                self.on_stop_recording()
        
        if self.on_mode_change:
            self.on_mode_change(self.mode)
    
    def start(self):
        """Start the hotkey manager (for compatibility)."""
        # Already started in __init__
        pass
    
    def stop(self):
        """Stop the hotkey manager."""
        # Nothing to stop, signals are automatically disconnected
        pass
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording
    
    @property
    def current_mode(self) -> RecordingMode:
        """Get current recording mode."""
        return self.mode 