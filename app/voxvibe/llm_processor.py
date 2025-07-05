#!/usr/bin/env python3
"""LLM post-processor for cleaning up dictated text using OpenAI GPT-4.1-nano."""

import os
import re
import time
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not available, LLM processing disabled")


class LLMProcessor(QObject):
    """
    Post-processes transcribed text using OpenAI GPT-4o-nano to clean up dictated content.
    """
    
    # Signals for async processing
    processing_started = pyqtSignal()
    processing_finished = pyqtSignal(str)  # cleaned_text
    processing_finished_with_context = pyqtSignal(str, str)  # cleaned_text, context_type
    processing_failed = pyqtSignal(str)    # error_message
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4.1-nano", settings=None):
        super().__init__()
        self.model = model
        self.client = None
        self.enabled = False
        self._active_threads = []
        self._active_workers = []
        self.settings = settings
        
        # Initialize OpenAI client
        if OPENAI_AVAILABLE and (api_key or os.getenv("OPENAI_API_KEY")):
            try:
                self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
                self.enabled = True
                print(f"✅ LLM processor initialized with model: {self.model}")
            except Exception as e:
                print(f"⚠️ Failed to initialize OpenAI client: {e}")
                self.enabled = False
        else:
            print("⚠️ LLM processing disabled - missing OpenAI API key")
    
    def cleanup(self):
        """Clean up any running threads"""
        print("🧹 Cleaning up LLM processor threads...")
        for thread in self._active_threads[:]:  # Copy list to avoid modification during iteration
            if thread.isRunning():
                thread.quit()
                if not thread.wait(3000):  # Wait up to 3 seconds
                    print("⚠️ LLM thread did not finish gracefully")
                    thread.terminate()
        
        for worker in self._active_workers[:]:
            worker.deleteLater()
        
        self._active_threads.clear()
        self._active_workers.clear()
    
    def is_enabled(self) -> bool:
        """Check if LLM processing is available"""
        return self.enabled and self.client is not None
    
    def process_text_async(self, raw_text: str):
        """Process text asynchronously in a separate thread"""
        if not self.is_enabled():
            # If LLM processing is disabled, just return original text
            self.processing_finished.emit(raw_text)
            return
        
        # Store thread reference to prevent premature destruction
        thread = QThread(self)  # Pass parent to prevent early destruction
        worker = LLMWorker(self.client, self.model, raw_text, self.settings)
        worker.moveToThread(thread)
        
        # Store references to prevent garbage collection
        if not hasattr(self, '_active_threads'):
            self._active_threads = []
        if not hasattr(self, '_active_workers'):
            self._active_workers = []
        
        self._active_threads.append(thread)
        self._active_workers.append(worker)
        
        # Connect signals with proper cleanup
        thread.started.connect(worker.process)
        worker.finished.connect(self._on_regular_finished)
        worker.failed.connect(self._on_regular_failed)
        
        # Cleanup handlers
        def cleanup():
            if thread in self._active_threads:
                self._active_threads.remove(thread)
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            thread.quit()
            thread.wait(2000)  # Wait up to 2 seconds for thread to finish
            worker.deleteLater()
            thread.deleteLater()
        
        worker.finished.connect(lambda: cleanup())
        worker.failed.connect(lambda: cleanup())
        
        self.processing_started.emit()
        thread.start()
    
    def _on_regular_finished(self, cleaned_text: str):
        """Handle finished processing"""
        self.processing_finished.emit(cleaned_text)
    
    def _on_regular_failed(self, error_msg: str):
        """Handle failed processing"""
        self.processing_failed.emit(error_msg)
    
    def process_text_async_with_context(self, raw_text: str):
        """Process text asynchronously and return both cleaned text and context"""
        if not self.is_enabled():
            # If LLM processing is disabled, just return original text with unknown context
            self.processing_finished_with_context.emit(raw_text, "unknown")
            return
        
        # Store thread reference to prevent premature destruction
        thread = QThread(self)  # Pass parent to prevent early destruction
        worker = LLMWorkerWithContext(self.client, self.model, raw_text, self.settings)
        worker.moveToThread(thread)
        
        # Store references to prevent garbage collection
        if not hasattr(self, '_active_threads'):
            self._active_threads = []
        if not hasattr(self, '_active_workers'):
            self._active_workers = []
        
        self._active_threads.append(thread)
        self._active_workers.append(worker)
        
        # Connect signals with proper cleanup
        thread.started.connect(worker.process)
        worker.finished_with_context.connect(self._on_context_finished)
        worker.failed.connect(self._on_context_failed)
        
        # Cleanup handlers
        def cleanup():
            if thread in self._active_threads:
                self._active_threads.remove(thread)
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            thread.quit()
            thread.wait(2000)  # Wait up to 2 seconds for thread to finish
            worker.deleteLater()
            thread.deleteLater()
        
        worker.finished_with_context.connect(lambda: cleanup())
        worker.failed.connect(lambda: cleanup())
        
        self.processing_started.emit()
        thread.start()
    
    def _on_context_finished(self, cleaned_text: str, context_type: str):
        """Handle finished processing with context"""
        self.processing_finished_with_context.emit(cleaned_text, context_type)
    
    def _on_context_failed(self, error_msg: str):
        """Handle failed processing"""
        self.processing_failed.emit(error_msg)
    
    def process_text_sync(self, raw_text: str) -> str:
        """Process text synchronously (blocking)"""
        if not self.is_enabled():
            return raw_text
        
        try:
            return self._clean_dictated_text(raw_text)
        except Exception as e:
            print(f"❌ LLM processing failed: {e}")
            return raw_text  # Return original text on failure
    
    def _extract_explicit_context(self, text: str) -> tuple[str, Optional[str]]:
        """Look for explicit context instruction inside the dictated text.
        Returns a tuple of (cleaned_text_without_instruction, detected_context_or_None).
        Supported patterns:
          • "this is a <context> message"
          • "send (this )?as a <context> (message|email)"
          • "context: <context>"
        <context> can be: code, coding, slack, whatsapp, formal email, casual email, casual message
        The search is case-insensitive.
        The matched instruction phrase is removed from the returned text.
        """
        context_patterns = {
            'code_window': [r"this is (a )?(code|coding|text) (window|editor|message)",
                            r"send (this )?as (a )?(code|coding) (window|message)",
                            r"context:\s*code"],
            'coding_agent': [r"this is (a )?coding agent (request|message)",
                             r"send (this )?to (the )?coding agent", r"context:\s*coding agent"],
            'slack': [r"this is (a )?slack message", r"send (this )?as (a )?slack message", r"context:\s*slack"],
            'whatsapp': [r"this is (a )?whatsapp message", r"send (this )?as (a )?whatsapp message", r"context:\s*whatsapp"],
            'formal_email': [r"this is (a )?formal email", r"send (this )?as (a )?formal email", r"context:\s*formal email"],
            'casual_email': [r"this is (a )?casual email", r"send (this )?as (a )?casual email", r"context:\s*casual email"],
            'casual_message': [r"this is (a )?casual message", r"send (this )?as (a )?casual message", r"context:\s*casual message"],
        }

        lowered = text.lower()
        for ctx, patterns in context_patterns.items():
            for pat in patterns:
                m = re.search(pat, lowered, flags=re.IGNORECASE)
                if m:
                    # Remove the matched instruction phrase from the original text (case-insensitive)
                    start, end = m.span()
                    cleaned = text[:start] + text[end:]  # keep original casing outside match
                    return cleaned.strip(), ctx
        return text, None

    def _clean_dictated_text(self, raw_text: str) -> str:
        """Send text to GPT for context-aware cleaning of dictated content"""
        # First, check for explicit context instruction and strip it
        cleaned_raw, explicit_ctx = self._extract_explicit_context(raw_text)
        base_text = cleaned_raw or raw_text  # fallback if stripping empties text

        # Detect context if not explicitly specified
        context_type = explicit_ctx or self._detect_communication_context(base_text)
        print(f"🎯 Detected context: {context_type} (explicit: {bool(explicit_ctx)})")
        
        # Build prompt
        prompt = self._get_context_prompt(base_text, context_type)

        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt(context_type)
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent, conservative edits
                timeout=15  # Increased timeout for context analysis
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            cleaned_text = response.choices[0].message.content.strip()
            
            print(f"🤖 LLM cleanup completed in {processing_time}ms ({context_type})")
            print(f"📝 Original: '{raw_text}'")
            print(f"✨ Cleaned:  '{cleaned_text}'")
            
            return cleaned_text
            
        except Exception as e:
            print(f"❌ LLM processing error: {e}")
            raise
    
    def _clean_dictated_text_with_context(self, raw_text: str) -> tuple[str, str]:
        """Clean text and return both cleaned text and context type"""
        cleaned_raw, explicit_ctx = self._extract_explicit_context(raw_text)
        base_text = cleaned_raw or raw_text
        context_type = explicit_ctx or self._detect_communication_context(base_text)
        print(f"🎯 Detected context: {context_type} (explicit: {bool(explicit_ctx)})")
        prompt = self._get_context_prompt(base_text, context_type)

        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt(context_type)
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent, conservative edits
                timeout=15  # Increased timeout for context analysis
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            cleaned_text = response.choices[0].message.content.strip()
            
            print(f"🤖 LLM cleanup completed in {processing_time}ms ({context_type})")
            print(f"📝 Original: '{raw_text}'")
            print(f"✨ Cleaned:  '{cleaned_text}'")
            
            return cleaned_text, context_type
            
        except Exception as e:
            print(f"❌ LLM processing error: {e}")
            raise
    
    def _detect_communication_context(self, text: str) -> str:
        """Detect the type of communication from the content"""
        text_lower = text.lower()
        
        # Check for explicit context indicators first
        # Code window context - user wants simple Ctrl+V paste
        if any(phrase in text_lower for phrase in [
            'code window', 'coding window', 'in a code', 'in code', 'im in a code', "i'm in a code",
            # New phrases to capture common wording
            'text editor', 'in a text editor', "i'm in a text editor", 'editor window', 'code editor'
        ]):
            return 'code_window'
        elif any(word in text_lower for word in ['cursor', 'code', 'coding', 'agent', 'programming', 'debug', 'function', 'variable']):
            return 'coding_agent'
        elif any(word in text_lower for word in ['slack', 'channel', 'thread']):
            return 'slack'
        elif any(word in text_lower for word in ['whatsapp', 'chat', 'message']):
            return 'whatsapp'
        elif any(phrase in text_lower for phrase in ['dear sir', 'dear madam', 'to whom it may concern', 'yours faithfully', 'yours sincerely']):
            return 'formal_email'
        elif any(word in text_lower for word in ['email', 'mail']) and any(word in text_lower for word in ['meeting', 'proposal', 'contract', 'business']):
            return 'formal_email'
        elif any(word in text_lower for word in ['hi', 'hello', 'hey', 'cheers', 'thanks']):
            return 'casual_email'
        
        # Default based on length and formality indicators
        if len(text.split()) > 50:  # Longer texts tend to be emails
            if any(word in text_lower for word in ['please', 'kindly', 'regarding', 'furthermore', 'however']):
                return 'formal_email'
            else:
                return 'casual_email'
        else:
            return 'casual_message'  # Short texts default to casual
    
    def _get_system_prompt(self, context_type: str) -> str:
        """Get the appropriate system prompt for the context"""
        # Try to get custom prompt from settings first
        if self.settings:
            custom_prompt = self.settings.get_prompt(context_type, "system_prompt")
            if custom_prompt:
                return custom_prompt
        
        # Fallback to default prompts using custom base prompts if available
        if self.settings:
            base_prompt = self.settings.get_base_prompt()
        else:
            base_prompt = "You are an expert editor who specialises in cleaning up dictated text using British English conventions."
        
        context_prompts = {
            'code_window': f"{base_prompt} You format text for direct insertion into code editors or IDEs, keeping it concise and code-appropriate.",
            'coding_agent': f"{base_prompt} You focus on technical communication with coding assistants, maintaining technical accuracy whilst improving clarity.",
            'slack': f"{base_prompt} You format text for Slack messages, keeping them concise and team-friendly.",
            'whatsapp': f"{base_prompt} You format text for WhatsApp messages, keeping them casual and conversational.",
            'formal_email': f"{base_prompt} You format text for formal business emails using proper British English etiquette.",
            'casual_email': f"{base_prompt} You format text for casual emails, maintaining a friendly but professional tone.",
            'casual_message': f"{base_prompt} You format text for casual messages, keeping them natural and conversational."
        }
        
        return context_prompts.get(context_type, context_prompts['casual_message'])
    
    def _get_recent_history_snippet(self, max_entries: int = 10, minutes: int = 5) -> str:
        """Fetch recent history entries within the specified number of minutes.
        Returns a newline-joined snippet or an empty string if none.
        """
        try:
            from datetime import datetime, timedelta

            from .history import TranscriptionHistory
            history = TranscriptionHistory()  # Uses the same default DB path
            entries = history.get_recent(limit=max_entries)
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            recent_entries = [e.text for e in entries if e.timestamp >= cutoff]
            if recent_entries:
                # Reverse chronological order (oldest first) for natural flow
                recent_entries.reverse()
                snippet_lines = [f"{i+1}. {t}" for i, t in enumerate(recent_entries)]
                return "\n".join(snippet_lines)
            return ""
        except Exception as e:
            print(f"⚠️ Could not fetch recent history for context: {e}")
            return ""

    def _get_context_prompt(self, raw_text: str, context_type: str) -> str:
        """Get the appropriate cleaning prompt based on context, including recent history for extra context"""
        
        # Try to get custom instructions from settings first
        if self.settings:
            custom_instructions = self.settings.get_prompt(context_type, "instructions")
            if custom_instructions:
                instructions_block = custom_instructions
            else:
                instructions_block = None
        else:
            instructions_block = None
        
        # Fallback to default instructions using base instructions if needed
        if instructions_block is None:
            if self.settings:
                base_instructions = self.settings.get_base_instructions()
            else:
                base_instructions = """- Use British English spelling and conventions
- Fix punctuation and capitalisation
- Remove filler words (um, uh, you know, etc.)
- Improve sentence structure and flow
- Maintain the original meaning and intent
- Don't add content that wasn't implied in the original"""
            # Build context-specific instructions from earlier dict (existing logic)
            context_instructions = {
                'code_window': f"""{base_instructions}
- Keep text concise and editor-appropriate
- Remove all dictation-specific phrases
- Focus on content that belongs in code editors
- Maintain technical accuracy if applicable
- Remove context indicators like 'I'm in a code window'""",
                'coding_agent': f"""{base_instructions}
- Keep technical terms precise and accurate
- Maintain clarity for coding-related requests
- Use proper technical vocabulary
- Structure requests logically for AI assistants""",
                'slack': f"""{base_instructions}
- Keep it concise and team-friendly
- Use appropriate Slack conventions
- Maintain casual but clear communication
- Remove excessive formality""",
                'whatsapp': f"""{base_instructions}
- Keep it casual and conversational
- Use natural, friendly language
- Remove excessive formality
- Maintain personal tone""",
                'formal_email': f"""{base_instructions}
- Use formal British English conventions
- Structure with proper email etiquette
- Maintain professional tone throughout
- Use appropriate formal vocabulary""",
                'casual_email': f"""{base_instructions}
- Use friendly but professional tone
- Structure clearly but not overly formal
- Maintain approachable language
- Balance casualness with clarity""",
                'casual_message': f"""{base_instructions}
- Keep natural and conversational
- Maintain friendly tone
- Remove excessive formality
- Focus on clear communication"""
            }
            instructions_block = context_instructions.get(context_type, context_instructions['casual_message'])
        
        # Fetch recent history context
        recent_snippet = self._get_recent_history_snippet()
        recent_block = f"Recent conversation snippets (last 5 minutes):\n{recent_snippet}\n\n" if recent_snippet else ""
        
        return f"""Please clean up the dictated text for {context_type.replace('_', ' ')} context.

{recent_block}Instructions:
{instructions_block}

Raw dictated text:
"{raw_text}"

Cleaned text:"""


class LLMWorker(QObject):
    """Worker for processing text in background thread"""
    
    finished = pyqtSignal(str)  # cleaned_text
    failed = pyqtSignal(str)    # error_message
    
    def __init__(self, client, model: str, raw_text: str, settings=None):
        super().__init__()
        self.client = client
        self.model = model
        self.raw_text = raw_text
        self.settings = settings
    
    def process(self):
        """Process the text"""
        try:
            processor = LLMProcessor(settings=self.settings)
            processor.client = self.client
            processor.model = self.model
            processor.enabled = True
            
            cleaned_text = processor._clean_dictated_text(self.raw_text)
            self.finished.emit(cleaned_text)
            
        except Exception as e:
            error_msg = f"LLM processing failed: {e}"
            print(f"❌ {error_msg}")
            self.failed.emit(error_msg)


class LLMWorkerWithContext(QObject):
    """Worker for processing text in background thread with context detection"""
    
    finished_with_context = pyqtSignal(str, str)  # cleaned_text, context_type
    failed = pyqtSignal(str)    # error_message
    
    def __init__(self, client, model: str, raw_text: str, settings=None):
        super().__init__()
        self.client = client
        self.model = model
        self.raw_text = raw_text
        self.settings = settings
    
    def process(self):
        """Process the text with context detection"""
        try:
            processor = LLMProcessor(settings=self.settings)
            processor.client = self.client
            processor.model = self.model
            processor.enabled = True
            
            cleaned_text, context_type = processor._clean_dictated_text_with_context(self.raw_text)
            self.finished_with_context.emit(cleaned_text, context_type)
            
        except Exception as e:
            error_msg = f"LLM processing failed: {e}"
            print(f"❌ {error_msg}")
            self.failed.emit(error_msg) 