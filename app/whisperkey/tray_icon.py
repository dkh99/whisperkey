"""System tray icon for Whisper Key with history access and quick actions."""

from datetime import datetime, timezone
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .history import TranscriptionHistory
from .window_manager import WindowManager


class WhisperKeyTrayIcon(QSystemTrayIcon):
    # Signals
    paste_requested = pyqtSignal(str)  # text to paste
    quit_requested = pyqtSignal()
    settings_changed = pyqtSignal()  # emitted when settings are changed

    def __init__(self, history: TranscriptionHistory, window_manager: Optional[WindowManager] = None):
        super().__init__()

        self.history = history
        self.window_manager = window_manager

        # Create different icon states
        self.icons = {
            'ready': self.create_microphone_icon(),
            'recording': self.create_recording_icon(),
            'transcribing': self.create_rocket_icon(),
            'pasting': self.create_eye_icon()
        }

        # Set initial icon
        self.setIcon(self.icons['ready'])
        self.setToolTip("Whisper Key - Voice Transcription")
        self.last_engine_label = "Whisper"
        self.last_latency_ms = 0

        # Setup context menu
        self.setup_menu()

        # Connect signals
        self.activated.connect(self.on_tray_activated)

        # Show the tray icon
        self.show()

        print("🎯 System tray icon initialized")

    def create_microphone_icon(self) -> QIcon:
        """Create a simple microphone icon"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw microphone shape
        painter.setBrush(QColor(0, 213, 255))  # Cyan color
        painter.setPen(QColor(255, 255, 255, 200))

        # Mic body
        painter.drawRoundedRect(12, 8, 8, 12, 3, 3)

        # Mic stand
        painter.drawLine(16, 20, 16, 26)
        painter.drawLine(12, 26, 20, 26)

        # Sound waves
        painter.setPen(QColor(0, 213, 255, 150))
        painter.drawArc(6, 10, 8, 8, 0, 180 * 16)
        painter.drawArc(4, 8, 12, 12, 0, 180 * 16)

        painter.end()
        return QIcon(pixmap)

    def create_recording_icon(self) -> QIcon:
        """Create a recording microphone icon with red dot"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw microphone shape
        painter.setBrush(QColor(255, 80, 80))  # Red color for recording
        painter.setPen(QColor(255, 255, 255, 200))

        # Mic body
        painter.drawRoundedRect(12, 8, 8, 12, 3, 3)

        # Mic stand
        painter.drawLine(16, 20, 16, 26)
        painter.drawLine(12, 26, 20, 26)

        # Recording indicator (red circle)
        painter.setBrush(QColor(255, 0, 0))
        painter.setPen(QColor(255, 0, 0))
        painter.drawEllipse(22, 6, 6, 6)

        painter.end()
        return QIcon(pixmap)

    def create_rocket_icon(self) -> QIcon:
        """Create a clear emoji-style rocket icon for transcription"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        from PyQt6.QtCore import QPointF

        # Main rocket body (larger and more prominent)
        painter.setBrush(QColor(220, 220, 220))  # Light gray body
        painter.setPen(QColor(100, 100, 100, 200))
        painter.drawRoundedRect(12, 12, 8, 14, 3, 3)

        # Rocket nose cone (more prominent)
        painter.setBrush(QColor(255, 80, 80))  # Red nose
        rocket_tip = [
            QPointF(16, 8),    # Top point
            QPointF(12, 12),   # Left base
            QPointF(20, 12)    # Right base
        ]
        painter.drawPolygon(rocket_tip)

        # Window/porthole in the middle
        painter.setBrush(QColor(100, 150, 255))  # Blue window
        painter.setPen(QColor(50, 50, 50))
        painter.drawEllipse(14, 16, 4, 3)

        # Rocket fins (more emoji-like)
        painter.setBrush(QColor(180, 180, 180))  # Darker gray fins
        painter.setPen(QColor(100, 100, 100))
        # Left fin
        left_fin = [QPointF(12, 22), QPointF(8, 26), QPointF(12, 26)]
        painter.drawPolygon(left_fin)
        # Right fin
        right_fin = [QPointF(20, 22), QPointF(24, 26), QPointF(20, 26)]
        painter.drawPolygon(right_fin)

        # Flame/exhaust (more vibrant and emoji-like)
        # Orange flame
        painter.setBrush(QColor(255, 165, 0))  # Orange
        painter.setPen(QColor(255, 140, 0))
        flame_orange = [QPointF(13, 26), QPointF(16, 30), QPointF(19, 26)]
        painter.drawPolygon(flame_orange)

        # Yellow inner flame
        painter.setBrush(QColor(255, 255, 0))  # Bright yellow
        painter.setPen(QColor(255, 200, 0))
        flame_yellow = [QPointF(14, 26), QPointF(16, 29), QPointF(18, 26)]
        painter.drawPolygon(flame_yellow)

        painter.end()
        return QIcon(pixmap)

    def create_eye_icon(self) -> QIcon:
        """Create an eye icon for paste ready"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw eye outline
        painter.setBrush(QColor(100, 200, 100))  # Green eye
        painter.setPen(QColor(255, 255, 255, 200))

        # Eye shape (ellipse)
        painter.drawEllipse(8, 12, 16, 8)

        # Pupil
        painter.setBrush(QColor(50, 50, 50))  # Dark pupil
        painter.drawEllipse(14, 14, 4, 4)

        # Eye highlight
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(15, 15, 1, 1)

        painter.end()
        return QIcon(pixmap)

    def setup_menu(self):
        """Setup the context menu"""
        self.menu = QMenu()

        # Add label for history section (no separate paste last action)
        history_label = QAction("📚 Paste from History:", self)
        history_label.setEnabled(False)
        self.menu.addAction(history_label)

        # History items will be added here dynamically
        self.history_actions = []
        self.next_10_submenu = None

        self.menu.addSeparator()

        # Settings
        settings_action = QAction("⚙️ Settings", self)
        settings_action.triggered.connect(self.show_settings)
        self.menu.addAction(settings_action)

        # Restart Extension
        restart_action = QAction("🔄 Restart Extension", self)
        restart_action.triggered.connect(self.restart_extension)
        self.menu.addAction(restart_action)

        # About
        about_action = QAction("ℹ️ About Whisper Key", self)
        about_action.triggered.connect(self.show_about)
        self.menu.addAction(about_action)

        # Quit
        quit_action = QAction("❌ Quit", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        self.menu.addAction(quit_action)

        self.setContextMenu(self.menu)

        # Update history menu initially
        self.update_history_menu()

    def update_history_menu(self):
        """Update the recent history items in main menu with Next 10 submenu"""
        # Remove existing history actions
        for action in self.history_actions:
            self.menu.removeAction(action)
        self.history_actions.clear()

        # Remove existing submenu if it exists
        if self.next_10_submenu:
            self.menu.removeAction(self.next_10_submenu.menuAction())
            self.next_10_submenu = None

        # Get recent entries (get 15 total: 5 in main menu + 10 in submenu)
        recent_entries = self.history.get_recent(limit=15)

        if not recent_entries:
            no_history_action = QAction("  (No recent history)", self)
            no_history_action.setEnabled(False)
            self.menu.insertAction(self.menu.actions()[-2], no_history_action)  # Insert before separator
            self.history_actions.append(no_history_action)
        else:
            # Add first 5 entries directly to main menu
            first_5 = recent_entries[:5]
            for i, entry in enumerate(first_5):
                # Create preview text
                preview = entry.text[:40] + "..." if len(entry.text) > 40 else entry.text
                # Convert UTC timestamp to local time (BST/GMT) for display
                local_time = self._convert_to_local_time(entry.timestamp)
                timestamp = local_time.strftime("%H:%M")

                if i == 0:
                    # First item is marked as "Last" and styled differently
                    action_text = f"  ★ Last - {timestamp}: {preview}"
                    action = QAction(action_text, self)
                    # Make it bold to stand out
                    font = action.font()
                    font.setBold(True)
                    action.setFont(font)
                else:
                    # Regular formatting for other items
                    action_text = f"  [{timestamp}] {preview}"
                    action = QAction(action_text, self)

                # Fix the clicking issue by creating a proper slot function
                def create_paste_slot(text):
                    return lambda: self.paste_text(text)

                action.triggered.connect(create_paste_slot(entry.text))
                self.menu.insertAction(self.menu.actions()[-2], action)  # Insert before separator
                self.history_actions.append(action)

            # Add "Next 10" submenu if there are more than 5 items
            if len(recent_entries) > 5:
                self.next_10_submenu = QMenu("📂 Next 10", self.menu)

                # Add entries 6-15 to submenu
                next_10 = recent_entries[5:]
                for entry in next_10:
                    # Create preview text
                    preview = entry.text[:40] + "..." if len(entry.text) > 40 else entry.text
                    # Convert UTC timestamp to local time (BST/GMT) for display
                    local_time = self._convert_to_local_time(entry.timestamp)
                    timestamp = local_time.strftime("%H:%M")

                    action_text = f"[{timestamp}] {preview}"
                    action = QAction(action_text, self.next_10_submenu)

                    # Fix the clicking issue by creating a proper slot function
                    def create_paste_slot(text):
                        return lambda: self.paste_text(text)

                    action.triggered.connect(create_paste_slot(entry.text))
                    self.next_10_submenu.addAction(action)

                # Add submenu to main menu
                self.menu.insertMenu(self.menu.actions()[-2], self.next_10_submenu)

    def paste_text(self, text: str):
        """Paste text using the window manager"""
        print(f"🖱️ TRAY PASTE DEBUG: Starting paste operation for text: '{text[:30]}...'")

        if self.window_manager:
            try:
                print("🖱️ TRAY PASTE DEBUG: Window manager available, proceeding...")

                # Store current window before pasting
                print("🖱️ TRAY PASTE DEBUG: Storing current window...")
                self.window_manager.store_current_window()

                # Set text to clipboard with multiple fallback methods
                print("🖱️ TRAY PASTE DEBUG: Setting text to clipboard with fallbacks...")
                clipboard_success = self._set_clipboard_with_fallbacks(text)

                if clipboard_success:
                    print(f"🖱️ TRAY PASTE DEBUG: Clipboard successfully set to: '{text[:30]}...'")
                else:
                    print("🖱️ TRAY PASTE DEBUG: ⚠️ Clipboard setting failed!")

                # Focus previous window and paste
                print("🖱️ TRAY PASTE DEBUG: Attempting to focus previous window and paste...")
                success = self.window_manager.paste_to_previous_window()

                if success:
                    print(f"✅ TRAY PASTE DEBUG: SUCCESS - Pasted from history: {text[:50]}...")
                    self.show_message("Pasted", "Text pasted successfully!",
                                    QMessageBox.Icon.Information, timeout=2000)
                else:
                    print("❌ TRAY PASTE DEBUG: FAILED - Failed to paste from history")
                    self.show_message("Paste Failed", "Could not paste text. Try again.",
                                    QMessageBox.Icon.Warning)

            except Exception as e:
                print(f"❌ TRAY PASTE DEBUG: EXCEPTION - Error pasting from history: {e}")
                print(f"🖱️ TRAY PASTE DEBUG: Exception type: {type(e).__name__}")
                import traceback
                print(f"🖱️ TRAY PASTE DEBUG: Full traceback: {traceback.format_exc()}")
                self.show_message("Error", f"Paste error: {e}", QMessageBox.Icon.Critical)
        else:
            # Fallback: emit signal for manual handling
            print("🖱️ TRAY PASTE DEBUG: No window manager available, emitting paste signal")
            self.paste_requested.emit(text)

    def _set_clipboard_with_fallbacks(self, text: str) -> bool:
        """Set clipboard using multiple fallback methods like in main app"""
        success = False

        # Method 1: Try Qt clipboard
        try:
            print("🖱️ CLIPBOARD: Trying Qt clipboard...")
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            print("🖱️ CLIPBOARD: Qt clipboard set successfully")
            success = True
        except Exception as e:
            print(f"🖱️ CLIPBOARD: Qt clipboard failed: {e}")

        # Method 2: Try xclip as backup (with short timeout)
        try:
            print("🖱️ CLIPBOARD: Trying xclip as backup...")
            import subprocess
            result = subprocess.run(['xclip', '-selection', 'clipboard'],
                                  input=text, text=True, capture_output=True, timeout=0.5)
            if result.returncode == 0:
                print("🖱️ CLIPBOARD: xclip set successfully")
                success = True
            else:
                print(f"🖱️ CLIPBOARD: xclip failed with return code: {result.returncode}")
        except subprocess.TimeoutExpired:
            print("🖱️ CLIPBOARD: xclip timed out")
        except FileNotFoundError:
            print("🖱️ CLIPBOARD: xclip not found")
        except Exception as e:
            print(f"🖱️ CLIPBOARD: xclip error: {e}")

        # Method 3: Try wl-copy for Wayland
        try:
            print("🖱️ CLIPBOARD: Trying wl-copy for Wayland...")
            import subprocess
            result = subprocess.run(['wl-copy'],
                                  input=text, text=True, capture_output=True, timeout=0.5)
            if result.returncode == 0:
                print("🖱️ CLIPBOARD: wl-copy set successfully")
                success = True
            else:
                print(f"🖱️ CLIPBOARD: wl-copy failed with return code: {result.returncode}")
        except subprocess.TimeoutExpired:
            print("🖱️ CLIPBOARD: wl-copy timed out")
        except FileNotFoundError:
            print("🖱️ CLIPBOARD: wl-copy not found")
        except Exception as e:
            print(f"🖱️ CLIPBOARD: wl-copy error: {e}")

        if success:
            print(f"🖱️ CLIPBOARD: ✅ Successfully set clipboard to: '{text[:30]}...'")
        else:
            print("🖱️ CLIPBOARD: ❌ All clipboard methods failed!")

        return success

    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double-click to paste last transcription
            last_entry = self.history.get_last_entry()
            if last_entry:
                self.paste_text(last_entry.text)
            else:
                self.show_message("No History", "No recent transcriptions found.", QMessageBox.Icon.Information)

    def restart_extension(self):
        """Restart the GNOME extension to fix hotkey detection"""
        import subprocess
        try:
            # Disable extension
            subprocess.run(['gnome-extensions', 'disable', 'whisperkey@whisperkey.app'],
                         check=False,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         timeout=5)

            # Wait a bit
            import time
            time.sleep(1)

            # Enable extension
            subprocess.run(['gnome-extensions', 'enable', 'whisperkey@whisperkey.app'],
                         check=False,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         timeout=5)

            print("🔄 Extension restarted")
            self.showMessage("Extension Restarted",
                           "GNOME extension has been reloaded. Hotkeys should work now.",
                           QSystemTrayIcon.MessageIcon.Information,
                           2000)
        except Exception as e:
            print(f"⚠️ Failed to restart extension: {e}")
            self.showMessage("Restart Failed",
                           "Failed to restart extension. Try manually: gnome-extensions disable/enable whisperkey",
                           QSystemTrayIcon.MessageIcon.Warning,
                           3000)

    def show_about(self):
        """Show about dialog centered on screen"""
        # Create message box
        msg_box = QMessageBox()
        msg_box.setWindowTitle("About Whisper Key")
        msg_box.setText("Whisper Key v0.3.2\n\n"
                       "Voice transcription with global hotkeys.\n"
                       "Fast, reliable speech-to-text for Linux.\n\n"
                       "Hotkeys:\n"
                       "• Alt+Space or Super+Alt+G: Toggle recording\n\n"
                       "Features:\n"
                       "• Ultra-fast pasting (0.25s)\n"
                       "• History access via tray menu\n"
                       "• Native Wayland support")
        msg_box.setIcon(QMessageBox.Icon.Information)

        # Center the dialog on screen
        try:
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                screen_center_x = screen_geometry.width() // 2
                screen_center_y = screen_geometry.height() // 2

                # Position dialog at screen center (dialog will auto-size, so we just set position)
                dialog_x = screen_center_x - 200  # Rough estimate for half dialog width
                dialog_y = screen_center_y - 150  # Rough estimate for half dialog height

                msg_box.move(dialog_x, dialog_y)
                print(f"📱 About dialog centered on screen at ({dialog_x}, {dialog_y})")
            else:
                print("📱 No screen found, using default dialog position")
        except Exception as e:
            print(f"📱 Could not center dialog: {e}")
            # Will use default positioning as fallback

        msg_box.exec()

    def show_settings(self):
        """Show settings dialog"""
        try:
            from .settings_dialog import SettingsDialog, WhisperKeySettings

            # Create settings if needed
            if not hasattr(self, 'settings'):
                self.settings = WhisperKeySettings()

            # Create and show dialog (use None as parent since tray icon isn't a QWidget)
            dialog = SettingsDialog(self.settings, None)

            # Connect to settings changed signal
            dialog.settings_changed.connect(self.on_settings_changed)

            # Center dialog on screen
            try:
                screen = QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.availableGeometry()
                    dialog_size = dialog.sizeHint()
                    dialog_x = (screen_geometry.width() - dialog_size.width()) // 2
                    dialog_y = (screen_geometry.height() - dialog_size.height()) // 2
                    dialog.move(dialog_x, dialog_y)
            except Exception:
                pass  # Use default position if centering fails

            # Show dialog
            dialog.exec()

        except Exception as e:
            print(f"❌ Error showing settings dialog: {e}")
            QMessageBox.critical(None, "Settings Error", f"Failed to open settings:\n{str(e)}")

    def on_settings_changed(self):
        """Handle settings changes"""
        print("⚙️ Settings changed - application restart may be required for some changes")
        self.show_message("Settings Saved",
                         "Settings have been saved!\nSome changes may require a restart to take effect.",
                         timeout=3000)
        # Emit signal to notify main app
        self.settings_changed.emit()

    def show_message(self, title: str, message: str, icon=QMessageBox.Icon.Information, timeout: int = 5000):
        """Show a system tray message. Suppress Information-level ("i") popups."""
        # Suppress informational popups entirely to avoid the "i" icon bubble
        if icon == QMessageBox.Icon.Information:
            print(f"🔕 Info popup suppressed: {title} - {message}")
            return

        # Map QMessageBox icon to QSystemTrayIcon message icon
        qt_tray_icon = QSystemTrayIcon.MessageIcon.NoIcon
        if icon == QMessageBox.Icon.Warning:
            qt_tray_icon = QSystemTrayIcon.MessageIcon.Warning
        elif icon == QMessageBox.Icon.Critical:
            qt_tray_icon = QSystemTrayIcon.MessageIcon.Critical

        if self.supportsMessages():
            self.showMessage(title, message, qt_tray_icon, timeout)
        else:
            # Fallback to message box for non-information messages only
            msg_box = QMessageBox()
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec()

    def update_status(self, recording: bool, mode: str = "", transcribing: bool = False):
        """Update tray icon status based on recording and transcription state"""
        engine = getattr(self, "last_engine_label", "")
        latency = getattr(self, "last_latency_ms", 0)
        if recording:
            self.setIcon(self.icons['recording'])
            tooltip = self._build_tooltip("Recording", mode, engine, latency)
        elif transcribing:
            self.setIcon(self.icons['transcribing'])
            tooltip = self._build_tooltip("Transcribing", engine=engine, latency=latency)
        else:
            self.setIcon(self.icons['ready'])
            tooltip = self._build_tooltip("Ready", engine=engine, latency=latency)

        self.setToolTip(tooltip)

        # Update history menu when not recording and not transcribing (new entry might be available)
        if not recording and not transcribing:
            self.update_history_menu()

    def update_transcription_status(self, transcribing: bool, partial_text: str = ""):
        """Update tray icon to show transcription progress with rocket icon"""
        from datetime import datetime
        engine = getattr(self, "last_engine_label", "")
        latency = getattr(self, "last_latency_ms", 0)
        if transcribing:
            self.setIcon(self.icons['transcribing'])  # Show rocket icon
            if partial_text:
                # Show partial results in tooltip
                preview = partial_text[:30] + "..." if len(partial_text) > 30 else partial_text
                tooltip = self._build_tooltip(f"🚀 Transcribing: \"{preview}\"", engine=engine, latency=latency)
            else:
                tooltip = self._build_tooltip("🚀 Transcribing...", engine=engine, latency=latency)
        else:
            self.setIcon(self.icons['ready'])  # Back to microphone
            tooltip = self._build_tooltip("Ready", engine=engine, latency=latency)

        self.setToolTip(tooltip)
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"🎯 [{timestamp}] Icon updated: {'rocket' if transcribing else 'microphone'} - {tooltip}")

        # Update history menu when transcription is complete
        if not transcribing:
            self.update_history_menu()

    def show_paste_ready(self):
        """Show eye icon when ready to paste"""
        from datetime import datetime

        from PyQt6.QtWidgets import QApplication
        self.setIcon(self.icons['pasting'])
        self.setToolTip("Whisper Key - 👁️ Ready to paste!")
        # Force immediate visual update
        QApplication.processEvents()
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"🎯 [{timestamp}] Icon updated: eye - Ready to paste! (visual update forced)")

    def reset_to_ready(self):
        """Reset icon to ready state"""
        from datetime import datetime

        from PyQt6.QtWidgets import QApplication
        self.setIcon(self.icons['ready'])
        engine = getattr(self, "last_engine_label", "")
        latency = getattr(self, "last_latency_ms", 0)
        self.setToolTip(self._build_tooltip("Ready", engine=engine, latency=latency))
        # Force immediate visual update
        QApplication.processEvents()
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"🎯 [{timestamp}] Icon updated: microphone - Ready (visual update forced)")

    def record_last_transcription_stats(self, engine: str, latency_ms: int):
        self.last_engine_label = engine
        self.last_latency_ms = latency_ms

    def _build_tooltip(self, primary_status: str, mode: str = "", engine: str = "", latency: int = 0) -> str:
        parts = ["Whisper Key"]
        if primary_status:
            parts.append(primary_status)
        tooltip = " - ".join(parts)
        detail_parts = []
        if mode:
            detail_parts.append(f"Mode: {mode}")
        if engine:
            detail_parts.append(f"Engine: {engine}")
        if latency:
            detail_parts.append(f"Latency: {latency}ms")
        if detail_parts:
            tooltip = f"{tooltip}\n" + " • ".join(detail_parts)
        return tooltip

    def _convert_to_local_time(self, utc_datetime: datetime) -> datetime:
        """Convert UTC datetime to local system time (handles BST/GMT automatically)"""
        # If the datetime is naive (no timezone info), assume it's UTC
        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)

        # Convert to local timezone
        local_datetime = utc_datetime.astimezone()
        return local_datetime

    def notify_transcription_complete(self, text: str):
        """Notify that a new transcription is complete (suppress info popup)."""
        # No info popup to avoid the "i" bubble; just refresh history
        self.update_history_menu()
