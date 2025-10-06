#!/usr/bin/env python3
"""Whisper Key main application with enhanced hotkey service and persistent UI."""

import logging
import signal
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from .audio_device_manager import AudioDeviceManager
from .audio_recorder import AudioRecorder
from .dbus_window_manager import DBusWindowManager
from .dbus_hotkey_manager import DBusHotkeyManager, RecordingMode
from .hotkey_service import HotkeyService as PynputHotkeyService
from .history import TranscriptionHistory
from .llm_processor import LLMProcessor
from .mic_bar import MicBar
from .settings_dialog import SettingsDialog
from .sound_fx import SoundFX
from .streaming_transcriber import StreamingTranscriber
from .theme import apply_theme
from .transcriber import Transcriber
from .tray_icon import WhisperKeyTrayIcon
from .window_manager import WindowManager


class RecordingThread(QThread):
    """Worker thread for audio recording using the improved timeout approach"""
    recording_finished = pyqtSignal(object, float)  # audio_data, start_time
    transcription_ready = pyqtSignal(str, int)  # text, duration_ms
    transcription_progress = pyqtSignal(str)  # partial_text
    
    def __init__(self, transcriber: StreamingTranscriber):
        super().__init__()
        self.transcriber = transcriber
        self.recorder = AudioRecorder()
        self.should_stop = False
        self.start_time = 0
        
        # Connect to streaming transcriber signals
        self.transcriber.partial_result.connect(self.on_partial_result)
        self.transcriber.final_result.connect(self.on_final_result)
        self.transcriber.transcription_started.connect(self.on_transcription_started)
        self.transcriber.transcription_finished.connect(self.on_transcription_finished)
        self.transcriber.llm_processing_started.connect(self.on_llm_processing_started)
        self.transcriber.llm_processing_finished.connect(self.on_llm_processing_finished)
    
    def run(self):
        """Record audio until stopped - using the improved pattern"""
        print(f"🎯 RecordingThread: Starting recording session... [{time.strftime('%H:%M:%S.%f')[:-3]}]")
        print(f"🔍 DEBUG: should_stop = {self.should_stop} at start of run()")
        self.start_time = time.time()
        
        # Reset should_stop flag for new recording
        self.should_stop = False
        print(f"🔍 DEBUG: Reset should_stop = {self.should_stop}")
        
        # Start the audio recorder (this will create its own thread)
        self.recorder.start_recording()
        
        # Wait until stop is requested (but don't block the audio recording)
        # Add minimum recording duration to avoid race conditions
        min_recording_time = 0.5  # 500ms minimum to ensure audio capture
        
        while self.recorder.is_recording and (not self.should_stop or (time.time() - self.start_time) < min_recording_time):
            self.msleep(50)  # Check every 50ms
            
            # If stop was requested but we haven't reached minimum time, keep recording
            if self.should_stop and (time.time() - self.start_time) < min_recording_time:
                elapsed_time = time.time() - self.start_time
                remaining_time = min_recording_time - elapsed_time
                print(f"🎯 RecordingThread: Stop requested early, continuing for {remaining_time:.2f}s more... [{time.strftime('%H:%M:%S.%f')[:-3]}]")
                # Keep the AudioRecorder running - don't stop it yet
        
        print("🎯 RecordingThread: Stop requested, collecting audio...")
        
        # Stop recording and get audio data
        audio_data = self.recorder.stop_recording()
        
        print(f"🎯 RecordingThread: Finished, emitting results...")
        self.recording_finished.emit(audio_data, self.start_time)
    
    def stop_recording(self):
        """Signal the recording thread to stop"""
        import traceback
        print(f"🛑 RecordingThread: stop_recording called [{time.strftime('%H:%M:%S.%f')[:-3]}]")
        print("🔍 STACK TRACE - WHO CALLED stop_recording:")
        for line in traceback.format_stack()[:-1]:  # Exclude current frame
            print(f"    {line.strip()}")
        self.should_stop = True
        
        # Don't directly set is_recording=False here - let the run() method handle it
        # This prevents race conditions where we stop before audio chunks are collected
    
    def on_partial_result(self, text: str, confidence: float):
        """Handle partial transcription results"""
        print(f"📝 Partial result: {text} (confidence: {confidence:.2f})")
        self.transcription_progress.emit(text)
    
    def on_final_result(self, text: str, confidence: float):
        """Handle final transcription results"""
        print(f"✅ Final result: {text} (confidence: {confidence:.2f})")
        duration_ms = int((time.time() - self.start_time) * 1000)
        self.transcription_ready.emit(text, duration_ms)
    
    def on_transcription_started(self):
        """Handle transcription started"""
        print("🎯 Transcription started")
    
    def on_transcription_finished(self):
        """Handle transcription finished"""
        print("🎯 Transcription finished")
    
    def on_llm_processing_started(self):
        """Handle LLM processing started"""
        print("🤖 LLM processing started")
        # Note: tray_icon updates handled by main app, not recording thread
    
    def on_llm_processing_finished(self, cleaned_text: str):
        """Handle LLM processing finished"""
        print(f"🤖 LLM processing finished: '{cleaned_text}'")
        # Note: tray_icon updates handled by main app, not recording thread


class WhisperKeyApp:
    """Main Whisper Key application with all components integrated"""
    
    def __init__(self, openai_api_key=None, settings=None):
        # Core components
        self.app = None
        self.transcriber = StreamingTranscriber(openai_api_key=openai_api_key, settings=settings)
        self.history = TranscriptionHistory()
        
        # UI components
        # mic_bar removed - using tray icon for status
        self.tray_icon: WhisperKeyTrayIcon = None
        self.sound_fx: SoundFX = None
        
        # Services
        self.hotkey_service: DBusHotkeyManager = None
        self.window_manager: WindowManager = None
        self.audio_device_manager: AudioDeviceManager = None
        
        # State
        self.current_mode = RecordingMode.IDLE
        
        # Recording thread (using improved timeout approach)
        self.recording_thread: RecordingThread = None
    
    def initialize(self):
        """Initialize all components"""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        
        # Create Qt application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # Keep running in tray
        self.app.setApplicationName("Whisper Key")
        
        # Apply theme
        apply_theme(self.app)
        
        # Initialize window manager
        try:
            self.window_manager = WindowManager()
            print("✅ Native window manager initialized")
            
            # Check dependencies
            deps = self.window_manager.check_dependencies()
            print(f"📋 Display server: {deps['display_server']}")
            print(f"📋 Available tools: {deps.get('tools', {})}")
        except Exception as e:
            print(f"⚠️ Window manager failed: {e}")
            self.window_manager = None
        
        # Initialize sound effects
        self.sound_fx = SoundFX()
        
        # Initialize audio device manager
        self.audio_device_manager = AudioDeviceManager()
        self._configure_audio_device_manager()
        
        # Initialize system tray
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = WhisperKeyTrayIcon(self.history, self.window_manager)
            self.setup_tray_connections()
            # Pass settings to tray icon so it can create the settings dialog
            self.tray_icon.settings = self.transcriber.settings
        else:
            print("⚠️ System tray not available")
        
        # Initialize recording thread
        self.recording_thread = RecordingThread(self.transcriber)
        self.recording_thread.recording_finished.connect(self.on_recording_finished)
        # Note: Removed transcription_ready connection - using context-aware signal instead
        self.recording_thread.transcription_progress.connect(self.on_transcription_progress)
        
        # Connect ONLY to context-aware transcription signal (this handles both LLM and non-LLM cases)
        self.transcriber.final_result_with_context.connect(self.on_transcription_complete_with_context)
        
        # Connect LLM processing signals to main app for UI updates only
        self.transcriber.llm_processing_started.connect(self.on_llm_processing_started_main)
        self.transcriber.llm_processing_finished.connect(self.on_llm_processing_finished_main)
        
        # Initialize hotkey service, preferring GNOME extension (DBus) with fallback to pynput
        # Prefer DBus; only fall back to pynput if DBus is unavailable or the extension is not ACTIVE
        self.hotkey_service = None
        
        try:
            print("🎯 Attempting to use GNOME extension DBus hotkeys")
            # Ensure extension is ACTIVE
            if self._gnome_extension_is_active():
                self.hotkey_service = DBusHotkeyManager()
            else:
                raise RuntimeError("GNOME extension not ACTIVE")
        except Exception as e:
            print(f"⚠️ DBus hotkeys unavailable or inactive ({e}); using Python (pynput)")
            self.hotkey_service = PynputHotkeyService()

        # Wire callbacks and start
        self.setup_hotkey_callbacks()
        self.hotkey_service.start()
        
        print("🚀 Whisper Key initialized successfully")

    def _gnome_extension_in_error_state(self) -> bool:
        """Best-effort check of GNOME extension state via gnome-extensions CLI."""
        import subprocess
        try:
            result = subprocess.run(
                ['gnome-extensions', 'info', 'whisperkey@whisperkey.app'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.splitlines():
                    if line.strip().startswith('State:') and 'ERROR' in line:
                        return True
        except Exception:
            # If we cannot determine, do not force fallback
            pass
        return False

    def _gnome_extension_is_active(self) -> bool:
        """Check if GNOME extension state is ACTIVE via gnome-extensions CLI."""
        import subprocess
        try:
            result = subprocess.run(
                ['gnome-extensions', 'info', 'whisperkey@whisperkey.app'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.splitlines():
                    if line.strip().startswith('State:') and 'ACTIVE' in line:
                        return True
        except Exception:
            pass
        return False
    
    def setup_hotkey_callbacks(self):
        """Setup hotkey service callbacks"""
        self.hotkey_service.on_start_recording = self.start_recording
        self.hotkey_service.on_stop_recording = self.stop_recording
        self.hotkey_service.on_mode_change = self.on_mode_change
    
    def setup_tray_connections(self):
        """Setup tray icon signal connections"""
        if self.tray_icon:
            self.tray_icon.quit_requested.connect(self.quit_application)
            self.tray_icon.settings_changed.connect(self._configure_audio_device_manager)
    
    def _configure_audio_device_manager(self):
        """Configure audio device manager with user preferences"""
        if not self.audio_device_manager:
            return
            
        # Get settings from the transcriber's settings object
        settings = self.transcriber.settings
        if not settings:
            return
        
        # Check if device switching is enabled
        device_switching_enabled = settings.get("audio.device_switching_enabled", False)
        dictating_mic = settings.get("audio.dictating_mic", "")
        dictating_output = settings.get("audio.dictating_output", "")
        normal_mic = settings.get("audio.normal_mic", "")
        normal_output = settings.get("audio.normal_output", "")
        
        print(f"🔧 Configuring audio device manager:")
        print(f"  Device switching enabled: {device_switching_enabled}")
        print(f"  Dictating mic: {dictating_mic}")
        print(f"  Dictating output: {dictating_output}")
        print(f"  Normal mic: {normal_mic}")
        print(f"  Normal output: {normal_output}")
        
        if device_switching_enabled:
            self.audio_device_manager.configure_four_device_switching(
                dictating_mic=dictating_mic,
                dictating_output=dictating_output,
                normal_mic=normal_mic,
                normal_output=normal_output
            )
            # Enable Bluetooth profile switching for seamless microphone/speaker switching
            self.audio_device_manager.enable_bluetooth_switching()
            print(f"🔊 Four-device audio switching configured with Bluetooth profile switching")
        else:
            self.audio_device_manager.disable_switching()
            self.audio_device_manager.disable_bluetooth_switching()
            print(f"🔊 Audio device switching disabled")
    
    def start_recording(self):
        """Start audio recording"""
        if self.recording_thread.isRunning():
            print("⚠️ Recording already in progress, but playing start sound for feedback")
            # Still play the start sound for user feedback even if recording is already active
            if self.sound_fx:
                self.sound_fx.play_start()
            return
        
        print("🎤 Starting recording...")
        
        # Switch to dictating audio devices
        if self.audio_device_manager:
            self.audio_device_manager.start_recording_audio_switch()
        
        # Store current window for pasting later
        if self.window_manager:
            try:
                self.window_manager.store_current_window()
                print("📋 Current window stored for pasting")
            except Exception as e:
                print(f"⚠️ Failed to store current window: {e}")
        
        self.recording_thread.start()
        
        # Play start sound
        if self.sound_fx:
            self.sound_fx.play_start()
        
        # Update UI (mic bar removed - using tray icon for status)
        
        if self.tray_icon:
            mode_name = self.hotkey_service.current_mode.value
            self.tray_icon.update_status(True, mode_name)
    
    def stop_recording(self):
        """Stop audio recording and process transcription"""
        if not self.recording_thread.isRunning():
            print("⚠️ Stop called but not currently recording")
            return
        
        import traceback
        print("🛑 Stopping recording...")
        print("🔍 STACK TRACE - WHO CALLED WhisperKeyApp.stop_recording:")
        for line in traceback.format_stack()[:-1]:  # Exclude current frame
            print(f"    {line.strip()}")
        
        # Stop recording thread and WAIT for it to finish
        self.recording_thread.stop_recording()
        
        # Wait for thread to finish properly (with timeout)
        if self.recording_thread.wait(2000):  # Wait up to 2 seconds
            print("✅ Recording thread finished cleanly")
        else:
            print("⚠️ Recording thread didn't finish in time, forcing cleanup")
            # FORCE CLEANUP: Only if thread hangs
            if hasattr(self.recording_thread, 'recorder'):
                self.recording_thread.recorder.force_cleanup()
        
        # Play stop sound
        if self.sound_fx:
            self.sound_fx.play_stop()
        
        # Switch back to normal audio devices after recording
        if self.audio_device_manager:
            self.audio_device_manager.stop_recording_audio_switch()
        
        # Update UI state
        self.current_mode = RecordingMode.IDLE
        if self.tray_icon:
            self.tray_icon.update_status(False, "Ready")
    
    def on_recording_finished(self, audio_data, start_time: float):
        """Handle completed recording - start streaming transcription"""
        if audio_data is not None and len(audio_data) > 0:
            print("🔄 Starting streaming transcription...")
            
            # Update tray icon to show transcription is starting
            if self.tray_icon:
                self.tray_icon.update_transcription_status(True)
            
            # Start streaming transcription (this will emit partial/final results via signals)
            self.transcriber.transcribe_streaming(audio_data)
        else:
            print("❌ No audio data recorded - check microphone permissions")
    
    def on_transcription_progress(self, partial_text: str):
        """Handle partial transcription results"""
        print(f"📝 Transcription progress: '{partial_text}'")
        
        # Update tray icon with partial results
        if self.tray_icon:
            self.tray_icon.update_transcription_status(True, partial_text)
    
    def on_transcription_complete(self, text: str, duration_ms: int):
        """Handle completed transcription"""
        print(f"✅ Transcription complete ({duration_ms}ms): '{text}'")
        
        # Update tray icon to show transcription is complete
        if self.tray_icon:
            self.tray_icon.update_transcription_status(False)
        
        # Add to history
        mode_name = self.current_mode.value
        entry_id = self.history.add_entry(text, duration_ms, mode_name)
        print(f"📚 Added to history as entry #{entry_id}")
        
        # Paste text with default method
        self._paste_text_with_method(text, "ctrl+shift+v")
        
        # Notify tray icon
        if self.tray_icon:
            self.tray_icon.notify_transcription_complete(text)
    
    def on_transcription_complete_with_context(self, text: str, confidence: float, context_type: str):
        """Handle completed transcription with context awareness"""
        print(f"✅ Transcription complete with context '{context_type}': '{text}'")

        # Append disclaimer if LLM is disabled
        if not self.transcriber.is_llm_enabled():
            disclaimer = "\n\n(This was dictated. If some words look odd, it might be because they sound like something else you know the sound of.)"
            text = text.rstrip() + disclaimer

        # Update tray icon to show transcription is complete
        if self.tray_icon:
            self.tray_icon.update_transcription_status(False)
        
        # Add to history
        mode_name = self.current_mode.value
        duration_ms = int(time.time() * 1000)  # Approximate duration
        entry_id = self.history.add_entry(text, duration_ms, mode_name)
        print(f"📚 Added to history as entry #{entry_id}")
        
        # Determine paste method based on context
        paste_method = self._get_paste_method_for_context(context_type)
        print(f"🎯 Using paste method: {paste_method} for context: {context_type}")
        
        # Paste text with context-appropriate method
        self._paste_text_with_method(text, paste_method)
        
        # Notify tray icon
        if self.tray_icon:
            self.tray_icon.notify_transcription_complete(text)
    
    def _get_paste_method_for_context(self, context_type: str) -> str:
        """Get the appropriate paste method based on detected context"""
        if context_type == "code_window":
            return "ctrl+v"  # Simple paste for code windows
        else:
            return "ctrl+shift+v"  # Default paste for most contexts
    
    def _paste_text_with_method(self, text: str, paste_method: str):
        """Paste text using the specified method"""
        if self.window_manager:
            try:
                print(f"📋 Attempting to paste text with {paste_method}...")
                # Set text to clipboard for other apps with fallback
                print(f"📋 Setting clipboard to: '{text[:50]}{'...' if len(text) > 50 else ''}'")
                
                # First try Qt clipboard
                qt_success = False
                try:
                    from PyQt6.QtWidgets import QApplication
                    clipboard = QApplication.clipboard()
                    clipboard.setText(text)
                    print("📋 Qt clipboard set")
                    qt_success = True
                except Exception as e:
                    print(f"📋 Qt clipboard failed: {e}")
                
                # Use xclip as backup with shorter timeout for reliability
                if not qt_success:
                    print("📋 Qt clipboard failed, using xclip fallback...")
                    self._set_clipboard_with_xclip(text)
                else:
                    # Even if Qt worked, try xclip as backup for reliability (with short timeout)
                    print("📋 Using xclip as backup for reliability...")
                    self._set_clipboard_with_xclip(text)
                
                # Show eye icon briefly as notification
                if self.tray_icon:
                    self.tray_icon.show_paste_ready()
                
                # Brief delay to show the eye icon, then reset before pasting
                from datetime import datetime
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"⏱️ [{timestamp}] Starting 500ms timer before paste")
                QTimer.singleShot(500, lambda: self._do_paste(paste_method, text))
            except Exception as e:
                print(f"❌ Error preparing to paste: {e}")
                if self.tray_icon:
                    self.tray_icon.reset_to_ready()
        else:
            print("❌ No window manager available for pasting")
    
    def _do_paste(self, paste_method: str, text: str):
        """Execute the paste operation after showing the eye icon"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"⏱️ [{timestamp}] Timer fired! _do_paste called, about to reset icon")
        try:
            # Reset icon before starting paste
            if self.tray_icon:
                self.tray_icon.reset_to_ready()
            
            # Focus previous window and paste with specified method
            if self.window_manager:
                success = self.window_manager.paste_to_previous_window(paste_method=paste_method)
                if success:
                    timestamp_end = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    print(f"✅ [{timestamp_end}] Text pasted successfully with {paste_method}")
                else:
                    paste_display = paste_method.replace('+', '+').upper()
                    print(f"❌ Auto-paste failed - please press {paste_display}")
                    if self.tray_icon:
                        # Use warning to ensure the popup is still visible when paste fails
                        from PyQt6.QtWidgets import QMessageBox
                        self.tray_icon.show_message(
                            "Whisper Key - Paste Ready",
                            f"Text copied to clipboard.\nPress {paste_display} to paste.",
                            icon=QMessageBox.Icon.Warning,
                            timeout=5000
                        )
            else:
                print("❌ No window manager available for pasting")
        except Exception as e:
            print(f"❌ Error pasting text: {e}")
            if self.tray_icon:
                self.tray_icon.reset_to_ready()
    
    def _set_clipboard_with_xclip(self, text: str):
        """Set clipboard using xclip as fallback/backup"""
        import subprocess
        
        try:
            result = subprocess.run(['xclip', '-selection', 'clipboard'], 
                                  input=text, text=True, capture_output=True, timeout=0.25)
            if result.returncode == 0:
                print("📋 xclip clipboard set successfully")
            else:
                print(f"📋 xclip failed with return code: {result.returncode}")
                if result.stderr:
                    print(f"📋 xclip stderr: {result.stderr.decode()}")
        except subprocess.TimeoutExpired:
            print("📋 xclip timed out after 0.25 seconds")
        except FileNotFoundError:
            print("📋 xclip not found, skipping")
        except Exception as e:
            print(f"📋 xclip error: {e}")
    
    def on_mode_change(self, mode: RecordingMode):
        """Handle recording mode change"""
        self.current_mode = mode
        print(f"🔄 Mode changed to: {mode.value}")
        
        # UI updates handled by tray icon
    
    def on_llm_processing_started_main(self):
        """Handle LLM processing started in main app"""
        print("🤖 LLM processing started (main app)")
        # Update tray icon to show LLM processing
        if self.tray_icon:
            self.tray_icon.update_transcription_status(True, "Cleaning up text...")
    
    def on_llm_processing_finished_main(self, cleaned_text: str):
        """Handle LLM processing finished in main app"""
        print(f"🤖 LLM processing finished (main app): '{cleaned_text}'")
        # Update tray icon back to ready state
        if self.tray_icon:
            self.tray_icon.update_transcription_status(False)
    
    def quit_application(self):
        """Quit the application"""
        print("👋 Shutting down Whisper Key...")
        
        # Stop services
        if self.hotkey_service:
            self.hotkey_service.stop()
        
        if self.recording_thread.isRunning():
            self.recording_thread.stop_recording()
        
        # Close UI components
        if self.tray_icon:
            self.tray_icon.hide()
        
        # Quit application
        if self.app:
            self.app.quit()
    
    def run(self):
        """Run the application"""
        if not self.app:
            raise RuntimeError("Application not initialized")
        
        print("🎯 Whisper Key is running...")
        print("Hotkeys:")
        print("  • Win+Alt: Hold to talk")
        
        return self.app.exec()

    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up...")
        
        # Clean up LLM processor threads first
        if hasattr(self.transcriber, 'llm_processor') and self.transcriber.llm_processor:
            self.transcriber.llm_processor.cleanup()
        
        if self.hotkey_service:
            self.hotkey_service.stop()
        
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.stop_recording()
            self.recording_thread.wait()  # Ensure thread finishes before cleanup
        
        # Close UI components
        if self.tray_icon:
            self.tray_icon.hide()
        
        if self.app:
            self.app.quit()


def main():
    """Main entry point"""
    try:
        # Load settings
        from .settings_dialog import WhisperKeySettings
        settings = WhisperKeySettings()
        
        # Get OpenAI API key from settings (which checks environment as fallback)
        openai_api_key = settings.get_openai_api_key()
        
        if openai_api_key:
            if settings.is_llm_enabled():
                print("🤖 OpenAI API key found and LLM enabled - post-processing active")
            else:
                print("⚠️ OpenAI API key found but LLM disabled in settings - post-processing disabled")
                openai_api_key = None  # Disable LLM processing
        else:
            print("⚠️ No OpenAI API key found - LLM post-processing disabled")
            print("   Use 'Settings' in the tray menu to configure your API key")
        
        app = WhisperKeyApp(openai_api_key=openai_api_key, settings=settings)
        app.initialize()
        return app.run()
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
