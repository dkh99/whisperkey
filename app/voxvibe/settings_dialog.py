#!/usr/bin/env python3
"""Settings dialog for VoxVibe configuration."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QCheckBox, QComboBox, QPushButton, 
    QLabel, QGroupBox, QMessageBox, QTabWidget, QWidget,
    QTextEdit, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal


class VoxVibeSettings:
    """Configuration manager for VoxVibe settings."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "voxvibe"
        self.config_file = self.config_dir / "settings.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Error loading settings: {e}")
        
        # Default settings
        return {
            "llm": {
                "enabled": False,
                "api_key": "",
                "model": "gpt-4.1-nano",
                "temperature": 0.1,
                "max_tokens": 500
            },
            "audio": {
                "model": "base",
                "language": "auto"
            },
            "ui": {
                "show_notifications": True,
                "minimize_to_tray": True
            },
            "prompts": self._get_default_prompts()
        }
    
    def _get_default_prompts(self) -> Dict[str, Dict[str, str]]:
        """Get default prompts for each context type."""
        base_prompt = "You are an expert editor who specialises in cleaning up dictated text using British English conventions."
        base_instructions = """- Use British English spelling and conventions
- Fix punctuation and capitalisation
- Remove filler words (um, uh, you know, etc.)
- Improve sentence structure and flow
- Maintain the original meaning and intent
- Don't add content that wasn't implied in the original"""
        
        return {
            "code_window": {
                "system_prompt": f"{base_prompt} You format text for direct insertion into code editors or IDEs, keeping it concise and code-appropriate.",
                "instructions": f"""{base_instructions}
- Keep text concise and editor-appropriate
- Remove all dictation-specific phrases
- Focus on content that belongs in code editors
- Maintain technical accuracy if applicable
- Remove context indicators like 'I'm in a code window'"""
            },
            "coding_agent": {
                "system_prompt": f"{base_prompt} You focus on technical communication with coding assistants, maintaining technical accuracy whilst improving clarity.",
                "instructions": f"""{base_instructions}
- Keep technical terms precise and accurate
- Maintain clarity for coding-related requests
- Use proper technical vocabulary
- Structure requests logically for AI assistants"""
            },
            "slack": {
                "system_prompt": f"{base_prompt} You format text for Slack messages, keeping them concise and team-friendly.",
                "instructions": f"""{base_instructions}
- Keep it concise and team-friendly
- Use appropriate Slack conventions
- Maintain casual but clear communication
- Remove excessive formality"""
            },
            "whatsapp": {
                "system_prompt": f"{base_prompt} You format text for WhatsApp messages, keeping them casual and conversational.",
                "instructions": f"""{base_instructions}
- Keep it casual and conversational
- Use natural, friendly language
- Remove excessive formality
- Maintain personal tone"""
            },
            "formal_email": {
                "system_prompt": f"{base_prompt} You format text for formal business emails using proper British English etiquette.",
                "instructions": f"""{base_instructions}
- Use formal British English conventions
- Structure with proper email etiquette
- Maintain professional tone throughout
- Use appropriate formal vocabulary"""
            },
            "casual_email": {
                "system_prompt": f"{base_prompt} You format text for casual emails, maintaining a friendly but professional tone.",
                "instructions": f"""{base_instructions}
- Use friendly but professional tone
- Structure clearly but not overly formal
- Maintain approachable language
- Balance casualness with clarity"""
            },
            "casual_message": {
                "system_prompt": f"{base_prompt} You format text for casual messages, keeping them natural and conversational.",
                "instructions": f"""{base_instructions}
- Keep natural and conversational
- Maintain friendly tone
- Remove excessive formality
- Focus on clear communication"""
            }
        }
    
    def save_settings(self) -> bool:
        """Save settings to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Error saving settings: {e}")
            return False
    
    def get(self, key: str, default=None):
        """Get a setting value using dot notation (e.g., 'llm.api_key')."""
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set a setting value using dot notation."""
        keys = key.split('.')
        current = self._settings
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from settings or environment."""
        # First check settings
        api_key = str(self.get("llm.api_key", "")).strip()
        if api_key:
            return api_key
        
        # Fallback to environment variable
        return os.getenv("OPENAI_API_KEY")
    
    def is_llm_enabled(self) -> bool:
        """Check if LLM processing is enabled."""
        enabled = self.get("llm.enabled", False)
        api_key = self.get_openai_api_key()
        return bool(enabled) and bool(api_key)
    
    def get_prompt(self, context_type: str, prompt_type: str) -> str:
        """Get a custom prompt for a context type."""
        result = self.get(f"prompts.{context_type}.{prompt_type}", "")
        return str(result) if result is not None else ""
    
    def set_prompt(self, context_type: str, prompt_type: str, value: str):
        """Set a custom prompt for a context type."""
        self.set(f"prompts.{context_type}.{prompt_type}", value)


class SettingsDialog(QDialog):
    """Settings dialog for VoxVibe."""
    
    settings_changed = pyqtSignal()  # Emitted when settings are saved
    
    def __init__(self, settings: VoxVibeSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("VoxVibe Settings")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        
        # Create tab widget
        self.tabs = QTabWidget()
        
        # LLM Settings Tab
        llm_tab = self.create_llm_tab()
        self.tabs.addTab(llm_tab, "🤖 LLM Settings")
        
        # Audio Settings Tab
        audio_tab = self.create_audio_tab()
        self.tabs.addTab(audio_tab, "🎤 Audio Settings")
        
        # Prompts Settings Tab
        prompts_tab = self.create_prompts_tab()
        self.tabs.addTab(prompts_tab, "📝 Custom Prompts")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_llm_connection)
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_settings)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.test_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def create_llm_tab(self) -> QWidget:
        """Create the LLM settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # LLM Group
        llm_group = QGroupBox("AI Text Processing")
        llm_layout = QFormLayout()
        
        # Enable LLM checkbox
        self.llm_enabled_cb = QCheckBox("Enable AI text cleanup")
        self.llm_enabled_cb.setToolTip("Use AI to clean up dictated text (remove filler words, fix grammar)")
        self.llm_enabled_cb.stateChanged.connect(self.on_llm_enabled_changed)
        llm_layout.addRow("", self.llm_enabled_cb)
        
        # API Key input
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Enter your OpenAI API key...")
        self.api_key_edit.setToolTip("Get your API key from https://platform.openai.com/api-keys")
        llm_layout.addRow("OpenAI API Key:", self.api_key_edit)
        
        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "gpt-4.1-nano",
            "gpt-4o-mini", 
            "gpt-3.5-turbo"
        ])
        self.model_combo.setToolTip("Choose the AI model for text processing")
        llm_layout.addRow("Model:", self.model_combo)
        
        llm_group.setLayout(llm_layout)
        layout.addWidget(llm_group)
        
        # Instructions
        instructions = QLabel(
            "💡 AI text cleanup helps make your dictated text more professional by:\n"
            "• Removing filler words (um, uh, you know, etc.)\n"
            "• Fixing punctuation and capitalization\n"
            "• Improving sentence structure\n"
            "• Maintaining your original meaning"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; font-size: 12px; margin: 10px;")
        layout.addWidget(instructions)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_prompts_tab(self) -> QWidget:
        """Create the prompts customization tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(
            "🎯 Customize the AI prompts for different contexts. Each context has:\n"
            "• System Prompt: Defines the AI's role and behaviour\n"
            "• Instructions: Specific guidelines for text cleanup"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; font-size: 12px; margin: 10px;")
        layout.addWidget(instructions)
        
        # Create scroll area for all the prompt editors
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Store prompt editors for later access
        self.prompt_editors = {}
        
        # Context types with user-friendly names
        contexts = [
            ("code_window", "🖥️ Code Window", "Direct insertion into code editors/IDEs"),
            ("coding_agent", "🤖 Coding Agent", "Technical communication with AI assistants"),
            ("slack", "💬 Slack", "Team messaging on Slack"),
            ("whatsapp", "📱 WhatsApp", "Casual messaging"),
            ("formal_email", "📧 Formal Email", "Business correspondence"),
            ("casual_email", "✉️ Casual Email", "Friendly emails"),
            ("casual_message", "💭 Casual Message", "General conversational text")
        ]
        
        for context_id, context_name, context_desc in contexts:
            # Create group for this context
            group = QGroupBox(f"{context_name} - {context_desc}")
            group_layout = QVBoxLayout()
            
            # System prompt editor
            sys_label = QLabel("System Prompt (defines AI's role):")
            sys_label.setStyleSheet("font-weight: bold;")
            group_layout.addWidget(sys_label)
            
            sys_edit = QTextEdit()
            sys_edit.setMaximumHeight(100)
            sys_edit.setPlaceholderText("Enter the system prompt that defines how the AI should behave for this context...")
            group_layout.addWidget(sys_edit)
            
            # Instructions editor
            inst_label = QLabel("Instructions (specific cleanup guidelines):")
            inst_label.setStyleSheet("font-weight: bold;")
            group_layout.addWidget(inst_label)
            
            inst_edit = QTextEdit()
            inst_edit.setMaximumHeight(120)
            inst_edit.setPlaceholderText("Enter specific instructions for cleaning up text in this context...")
            group_layout.addWidget(inst_edit)
            
            # Reset button for this context
            reset_btn = QPushButton("Reset to Default")
            reset_btn.clicked.connect(lambda checked, ctx=context_id: self.reset_context_prompts(ctx))
            group_layout.addWidget(reset_btn)
            
            group.setLayout(group_layout)
            scroll_layout.addWidget(group)
            
            # Store references
            self.prompt_editors[context_id] = {
                'system_prompt': sys_edit,
                'instructions': inst_edit
            }
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # Reset all button
        reset_all_btn = QPushButton("Reset All Prompts to Default")
        reset_all_btn.clicked.connect(self.reset_all_prompts)
        layout.addWidget(reset_all_btn)
        
        widget.setLayout(layout)
        return widget
    
    def create_audio_tab(self) -> QWidget:
        """Create the audio settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        audio_group = QGroupBox("Speech Recognition")
        audio_layout = QFormLayout()
        
        # Whisper model selection
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems([
            "tiny", "base", "small", "medium", "large"
        ])
        self.whisper_model_combo.setToolTip("Larger models are more accurate but slower")
        audio_layout.addRow("Whisper Model:", self.whisper_model_combo)
        
        # Language selection
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "auto", "en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"
        ])
        self.language_combo.setToolTip("Set to 'auto' for automatic language detection")
        audio_layout.addRow("Language:", self.language_combo)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def on_llm_enabled_changed(self, state):
        """Handle LLM enabled state change."""
        enabled = state == Qt.CheckState.Checked.value
        self.api_key_edit.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.test_button.setEnabled(enabled)
    
    def load_current_settings(self):
        """Load current settings into the dialog."""
        # LLM settings
        self.llm_enabled_cb.setChecked(self.settings.get("llm.enabled", False))
        self.api_key_edit.setText(self.settings.get("llm.api_key", ""))
        self.model_combo.setCurrentText(self.settings.get("llm.model", "gpt-4.1-nano"))
        
        # Audio settings
        self.whisper_model_combo.setCurrentText(self.settings.get("audio.model", "base"))
        self.language_combo.setCurrentText(self.settings.get("audio.language", "auto"))
        
        # Load prompts
        if hasattr(self, 'prompt_editors'):
            defaults = self.settings._get_default_prompts()
            for context_id, editors in self.prompt_editors.items():
                # Get custom prompts or fall back to defaults
                system_prompt = self.settings.get_prompt(context_id, "system_prompt")
                instructions = self.settings.get_prompt(context_id, "instructions")
                
                # If no custom prompts exist, use defaults
                if not system_prompt and context_id in defaults:
                    system_prompt = defaults[context_id]["system_prompt"]
                if not instructions and context_id in defaults:
                    instructions = defaults[context_id]["instructions"]
                
                editors['system_prompt'].setPlainText(system_prompt)
                editors['instructions'].setPlainText(instructions)
        
        # Update UI state
        self.on_llm_enabled_changed(self.llm_enabled_cb.checkState())
    
    def test_llm_connection(self):
        """Test the LLM connection."""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your OpenAI API key first.")
            return
        
        # Test with a simple request
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            # Simple test request
            response = client.chat.completions.create(
                model=self.model_combo.currentText(),
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            QMessageBox.information(self, "Success", "✅ Connection successful! LLM processing is working.")
            
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency", 
                              "OpenAI library not installed. Please install it with:\npip install openai")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"❌ Failed to connect to OpenAI:\n{str(e)}")
    
    def save_settings(self):
        """Save the current settings."""
        try:
            # Save LLM settings
            self.settings.set("llm.enabled", self.llm_enabled_cb.isChecked())
            self.settings.set("llm.api_key", self.api_key_edit.text().strip())
            self.settings.set("llm.model", self.model_combo.currentText())
            
            # Save audio settings
            self.settings.set("audio.model", self.whisper_model_combo.currentText())
            self.settings.set("audio.language", self.language_combo.currentText())
            
            # Save prompts
            if hasattr(self, 'prompt_editors'):
                for context_id, editors in self.prompt_editors.items():
                    system_prompt = editors['system_prompt'].toPlainText()
                    instructions = editors['instructions'].toPlainText()
                    
                    self.settings.set_prompt(context_id, "system_prompt", system_prompt)
                    self.settings.set_prompt(context_id, "instructions", instructions)
            
            # Save to file
            if self.settings.save_settings():
                self.settings_changed.emit()
                QMessageBox.information(self, "Settings Saved", "✅ Settings saved successfully!")
                self.accept()
            else:
                QMessageBox.critical(self, "Save Failed", "❌ Failed to save settings.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"❌ Error saving settings:\n{str(e)}")
    
    def reset_context_prompts(self, context_id: str):
        """Reset prompts for a specific context to defaults."""
        if not hasattr(self, 'prompt_editors'):
            return
        
        # Get default prompts
        defaults = self.settings._get_default_prompts()
        
        if context_id in defaults and context_id in self.prompt_editors:
            default_system = defaults[context_id]["system_prompt"]
            default_instructions = defaults[context_id]["instructions"]
            
            self.prompt_editors[context_id]['system_prompt'].setPlainText(default_system)
            self.prompt_editors[context_id]['instructions'].setPlainText(default_instructions)
            
            QMessageBox.information(self, "Reset Complete", f"✅ {context_id.replace('_', ' ').title()} prompts reset to defaults!")
    
    def reset_all_prompts(self):
        """Reset all prompts to defaults."""
        reply = QMessageBox.question(
            self, "Reset All Prompts", 
            "Are you sure you want to reset ALL prompts to their defaults?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self, 'prompt_editors'):
                defaults = self.settings._get_default_prompts()
                
                for context_id, editors in self.prompt_editors.items():
                    if context_id in defaults:
                        default_system = defaults[context_id]["system_prompt"]
                        default_instructions = defaults[context_id]["instructions"]
                        
                        editors['system_prompt'].setPlainText(default_system)
                        editors['instructions'].setPlainText(default_instructions)
                
                QMessageBox.information(self, "Reset Complete", "✅ All prompts reset to defaults!")
