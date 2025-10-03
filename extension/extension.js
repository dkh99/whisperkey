// extension.js - GNOME Extension for Dictation App Window Management
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import Clutter from 'gi://Clutter';
import St from 'gi://St';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

const HOTKEY_SCHEMA = 'org.gnome.shell.extensions.whisperkey';
const HOTKEY_BINDING = 'toggle-recording';

/**
 * @class DictationWindowExtension
 * @extends Extension
 * @property {Meta.Window|null} _lastFocusedWindow - The last focused GNOME window (Meta.Window or null)
 * @property {Gio.DBusExportedObject|null} _dbusImpl - The exported DBus object for this extension (Gio.DBusExportedObject or null)
 * @property {number|undefined} _focusSignal - Signal handler ID returned by global.display.connect (number or undefined)
 * @property {Set} _pressedKeys - Set of currently pressed key codes
 * @property {boolean} _isRecording - Whether recording is currently active
 */
export default class DictationWindowExtension extends Extension {
    enable() {
        this._lastFocusedWindow = null;
        this._dbusImpl = null;
        this._pressedKeys = new Set();
        this._isRecording = false;
        this._altDown = false;
        this._spaceDown = false;
        this._pendingStopId = 0;
        this._stageFallbackEnabled = false;
        this._lastToggleTs = 0;
        this._keyPressSignal = null;
        this._keyReleaseSignal = null;
        this._setupDBusService();
        this._connectSignals();
        this._setupHotkeys();

        // Add panel indicator with microphone icon (native, no tooltip)
        this._trayButton = new PanelMenu.Button(0.0, 'Whisper Key Indicator', false);
        const icon = new St.Icon({
            icon_name: 'audio-input-microphone-symbolic',
            style_class: 'system-status-icon',
        });
        this._trayButton.add_child(icon);
        // Add menu item showing app name and version (non-interactive)
        const appInfoItem = new PopupMenu.PopupMenuItem('Whisper Key v0.2.0');
        appInfoItem.setSensitive(false);
        this._trayButton.menu.addMenuItem(appInfoItem);
        Main.panel.addToStatusArea('whisperkey-indicator', this._trayButton);
    }

    disable() {
        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }
        if (this._focusSignal) {
            global.display.disconnect(this._focusSignal);
        }
        this._removeHotkeys();
        // Disconnect key event listeners if connected
        try {
            if (this._keyPressSignal) {
                global.stage.disconnect(this._keyPressSignal);
                this._keyPressSignal = null;
            }
            if (this._keyReleaseSignal) {
                global.stage.disconnect(this._keyReleaseSignal);
                this._keyReleaseSignal = null;
            }
            if (this._pendingStopId) {
                try { GLib.Source.remove(this._pendingStopId); } catch (e) {}
                this._pendingStopId = 0;
            }
        } catch (e) {
            globalThis.log?.(`[Whisper Key] Error disconnecting key listeners: ${e}`);
        }
        // Remove panel indicator
        if (this._trayButton) {
            this._trayButton.destroy();
            this._trayButton = null;
        }
    }

    _setupDBusService() {
        const WhisperKeyInterface = `
        <node>
            <interface name="org.gnome.Shell.Extensions.WhisperKey">
                <method name="GetFocusedWindow">
                    <arg type="s" direction="out" name="windowId"/>
                </method>
                <method name="FocusAndPaste">
                    <arg type="s" direction="in" name="windowId"/>
                    <arg type="s" direction="in" name="text"/>
                    <arg type="b" direction="out" name="success"/>
                </method>
                <signal name="WindowFocused">
                    <arg type="s" name="windowId"/>
                </signal>
                <signal name="ToggleRecording">
                </signal>
            </interface>
        </node>`;

        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(WhisperKeyInterface, this);
        this._dbusImpl.export(Gio.DBus.session, '/org/gnome/Shell/Extensions/WhisperKey');
    }

    _connectSignals() {
        // Track window focus changes
        this._focusSignal = global.display.connect('notify::focus-window', () => {
            const focusedWindow = global.display.focus_window;
            if (focusedWindow) {
                this._lastFocusedWindow = focusedWindow;
                // Emit signal to notify dictation app
                this._dbusImpl.emit_signal('WindowFocused', 
                    GLib.Variant.new('(s)', [this._getWindowId(focusedWindow)]));
            }
        });
    }

    _setupHotkeys() {
        try {
            Main.wm.addKeybinding(
                HOTKEY_BINDING,
                this.getSettings(HOTKEY_SCHEMA),
                Meta.KeyBindingFlags.NONE,
                Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW,
                () => {
                    // Toggle recording on each keybinding activation
                    globalThis.log?.('[Whisper Key] Hotkey activated (Alt+Space), toggling');
                    this._dbusImpl.emit_signal('ToggleRecording', GLib.Variant.new('()', []));
                }
            );
            globalThis.log?.('[Whisper Key] Hotkey registered.');
            this._stageFallbackEnabled = false;
        } catch (e) {
            globalThis.log?.(`[Whisper Key] addKeybinding failed: ${e}`);
            // Fallback: stage-level listeners
            try {
                this._keyPressSignal = global.stage.connect('key-press-event', this._onKeyPressed.bind(this));
                globalThis.log?.('[Whisper Key] Stage key listeners connected (fallback).');
                this._stageFallbackEnabled = true;
            } catch (e2) {
                globalThis.log?.(`[Whisper Key] Could not connect stage key listeners: ${e2}`);
            }
        }
    }

    _removeHotkeys() {
        Main.wm.removeKeybinding(HOTKEY_BINDING);
        globalThis.log?.('[Whisper Key] Hotkey removed.');
    }

    _onKeyPressed(actor, event) {
        if (!this._stageFallbackEnabled) return Clutter.EVENT_PROPAGATE;

        const keycode = event.get_key_code();
        const state = event.get_state();
        const symbol = event.get_key_symbol();

        // Fallback: emit toggle on Alt+Space press (debounced)
        const hasAlt = (state & Clutter.ModifierType.MOD1_MASK) !== 0;
        const isSpace = (symbol === Clutter.KEY_space);
        if (hasAlt && isSpace) {
            const now = Date.now();
            if (now - this._lastToggleTs > 300) {
                this._lastToggleTs = now;
                globalThis.log?.('[Whisper Key] Fallback Alt+Space press -> toggling');
                this._dbusImpl.emit_signal('ToggleRecording', GLib.Variant.new('()', []));
            }
        }
        return Clutter.EVENT_PROPAGATE;
    }

    _onKeyReleased(actor, event) {
        // In toggle mode, ignore releases in fallback path
        return Clutter.EVENT_PROPAGATE;
    }

    _getWindowId(window) {
        globalThis.log?.(`[Whisper Key] Window ID: ${window.get_pid()}-${window.get_id()}`);
        // Create a unique identifier for the window
        return `${window.get_pid()}-${window.get_id()}`;
    }

    // D-Bus method implementations
    GetFocusedWindow() {
        let result = '';
        if (this._lastFocusedWindow && !this._lastFocusedWindow.destroyed) {
            result = this._getWindowId(this._lastFocusedWindow);
        }
        globalThis.log?.(`[Whisper Key] GetFocusedWindow called, returning: ${result}`);
        return result;
    }

    _setClipboardText(text) {
        globalThis.log?.(`[Whisper Key] _setClipboardText: Setting clipboard and primary to: ${text.slice(0, 40)}...`);
        const clipboard = St.Clipboard.get_default();
        clipboard.set_text(St.ClipboardType.CLIPBOARD, text);
        clipboard.set_text(St.ClipboardType.PRIMARY, text);
    }

    _triggerPasteHack() {
        globalThis.log?.(`[Whisper Key] _triggerPasteHack: Will simulate Ctrl+V after delay`);
        // Use a 100ms delay to ensure clipboard is set
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            try {
                const seat = Clutter.get_default_backend().get_default_seat();
                const virtualDevice = seat.create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
                // Press Ctrl
                virtualDevice.notify_keyval(global.get_current_time(), Clutter.KEY_Control_L, Clutter.KeyState.PRESSED);
                // Press V
                virtualDevice.notify_keyval(global.get_current_time(), Clutter.KEY_v, Clutter.KeyState.PRESSED);
                // Release V
                virtualDevice.notify_keyval(global.get_current_time(), Clutter.KEY_v, Clutter.KeyState.RELEASED);
                // Release Ctrl
                virtualDevice.notify_keyval(global.get_current_time(), Clutter.KEY_Control_L, Clutter.KeyState.RELEASED);
                globalThis.log?.(`[Whisper Key] _triggerPasteHack: Ctrl+V simulated successfully`);
            } catch (pasteErr) {
                globalThis.log?.(`[Whisper Key] ERROR during _triggerPasteHack: ${pasteErr}`);
            }
            // Return false to remove the timeout (run only once)
            return false;
        });
    }

    FocusAndPaste(windowId, text) {
        globalThis.log?.(`[Whisper Key] FocusAndPaste called with windowId: ${windowId}, text: ${text.slice(0, 40)}...`);
        try {
            // 1. Find and focus the window
            globalThis.log?.(`[Whisper Key] Step 1: Searching for window with ID ${windowId}`);
            const windows = global.get_window_actors();
            let found = false;
            for (let windowActor of windows) {
                const window = windowActor.get_meta_window();
                if (this._getWindowId(window) === windowId) {
                    globalThis.log?.(`[Whisper Key] Step 1: Focusing window ${windowId}`);
                    window.activate(global.get_current_time());
                    found = true;
                    break;
                }
            }
            if (!found) {
                globalThis.log?.(`[Whisper Key] FocusAndPaste: window not found for ID ${windowId}`);
                return false;
            }
            // 2. Set clipboard content (both CLIPBOARD and PRIMARY)
            this._setClipboardText(text);
            // 3. Trigger paste after a short delay
            this._triggerPasteHack();
            return true;
        } catch (e) {
            globalThis.log?.(`[Whisper Key] Error in FocusAndPaste: ${e}`);
            console.error('Error in FocusAndPaste:', e);
            return false;
        }
    }
}
