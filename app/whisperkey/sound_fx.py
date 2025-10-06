"""Sound effects module for Whisper Key audio feedback.

Provides non-blocking ping sounds for recording start/stop events.
"""
import os
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect


class SoundFX:
    def __init__(self):
        self.start_sound: Optional[QSoundEffect] = None
        self.stop_sound: Optional[QSoundEffect] = None
        
        # Sound debouncing to prevent double playback
        self._last_sound_time = 0
        self._sound_debounce_delay = 0.3  # 300ms debounce delay
        
        self._setup_sounds()
    
    def _setup_sounds(self):
        """Initialize sound effects"""
        try:
            # Create sound effects
            self.start_sound = QSoundEffect()
            self.stop_sound = QSoundEffect()
            
            # Get sound file paths
            sounds_dir = Path(__file__).parent / "sounds"
            start_file = sounds_dir / "start.wav"
            stop_file = sounds_dir / "stop.wav"
            
            # Create sounds directory if it doesn't exist
            sounds_dir.mkdir(exist_ok=True)
            
            # Generate default sounds if files don't exist
            if not start_file.exists():
                self._create_default_start_sound(start_file)
            if not stop_file.exists():
                self._create_default_stop_sound(stop_file)
            
            # Load sound files
            self.start_sound.setSource(QUrl.fromLocalFile(str(start_file)))
            self.stop_sound.setSource(QUrl.fromLocalFile(str(stop_file)))
            
            # Set volume (0.0 to 1.0) - increased for better audibility
            self.start_sound.setVolume(1.0)
            self.stop_sound.setVolume(1.0)
            
            print("🔊 Sound effects initialized")
            print(f"🔊 Start sound loaded: {self.start_sound.isLoaded()}")
            print(f"🔊 Stop sound loaded: {self.stop_sound.isLoaded()}")
            print(f"🔊 Start sound source: {self.start_sound.source()}")
            print(f"🔊 Stop sound source: {self.stop_sound.source()}")
            
        except Exception as e:
            print(f"⚠️ Failed to initialize sound effects: {e}")
            self.start_sound = None
            self.stop_sound = None
    
    def _create_default_start_sound(self, filepath: Path):
        """Create a default start sound using system beep or synthesized tone"""
        try:
            # Try to create a simple WAV file with a pleasant start tone
            import wave

            import numpy as np
            
            # Generate a pleasant "ping" sound (ascending tone)
            sample_rate = 44100
            duration = 0.15  # 150ms
            
            t = np.linspace(0, duration, int(sample_rate * duration))
            # Start at 800Hz, rise to 1200Hz
            frequency = 800 + 400 * t / duration
            
            # Create sine wave with envelope
            envelope = np.exp(-t * 8)  # Decay envelope
            wave_data = envelope * np.sin(2 * np.pi * frequency * t)
            
            # Convert to 16-bit PCM
            wave_data = (wave_data * 32767).astype(np.int16)
            
            # Write WAV file
            with wave.open(str(filepath), 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 2 bytes per sample
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(wave_data.tobytes())
                
            print(f"✅ Created default start sound: {filepath}")
            
        except Exception as e:
            print(f"⚠️ Failed to create start sound: {e}")
            # Fallback: create empty file
            filepath.touch()
    
    def _create_default_stop_sound(self, filepath: Path):
        """Create a default stop sound"""
        try:
            import wave

            import numpy as np
            
            # Generate a pleasant "done" sound (descending tone)
            sample_rate = 44100
            duration = 0.12  # 120ms
            
            t = np.linspace(0, duration, int(sample_rate * duration))
            # Start at 1000Hz, drop to 600Hz
            frequency = 1000 - 400 * t / duration
            
            # Create sine wave with envelope
            envelope = np.exp(-t * 6)  # Decay envelope
            wave_data = envelope * np.sin(2 * np.pi * frequency * t)
            
            # Convert to 16-bit PCM
            wave_data = (wave_data * 32767).astype(np.int16)
            
            # Write WAV file
            with wave.open(str(filepath), 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 2 bytes per sample
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(wave_data.tobytes())
                
            print(f"✅ Created default stop sound: {filepath}")
            
        except Exception as e:
            print(f"⚠️ Failed to create stop sound: {e}")
            # Fallback: create empty file
            filepath.touch()
    
    def play_start(self):
        """Play recording start sound (non-blocking)"""
        if self.start_sound:
            threading.Thread(target=self._play_sound_with_debounce, args=(self.start_sound,), daemon=True).start()
        else:
            print("🔊 Start sound not available")
    
    def play_stop(self):
        """Play recording stop sound (non-blocking)"""
        if self.stop_sound:
            threading.Thread(target=self._play_sound_with_debounce, args=(self.stop_sound,), daemon=True).start()
        else:
            print("🔊 Stop sound not available")
    
    def _play_sound_with_debounce(self, sound_effect: QSoundEffect):
        """Play sound with debouncing to prevent double playback"""
        import time
        current_time = time.time()
        
        # Check if we've played a sound recently
        if current_time - self._last_sound_time < self._sound_debounce_delay:
            print(f"🔊 Sound debounced - too soon after last sound ({current_time - self._last_sound_time:.3f}s ago)")
            return
        
        # Update last sound time and play
        self._last_sound_time = current_time
        self._play_sound(sound_effect)
    
    def _play_sound(self, sound_effect: QSoundEffect):
        """Internal method to play a sound effect"""
        try:
            # Check if Qt sound is loaded, if not use system fallback immediately
            if not sound_effect.isLoaded():
                print(f"🔊 Qt sound not loaded, using system fallback")
                self._play_system_sound(sound_effect)
                return
            
            # Try Qt sound first
            print(f"🔊 Attempting to play sound: {sound_effect.source()}")
            sound_effect.play()
            print(f"🔊 Qt sound play() called")
            
            # Use system audio as fallback if Qt sound fails
            import time
            time.sleep(0.1)  # Wait 100ms to see if Qt sound starts
            
            # Check if Qt sound actually played by trying system fallback as backup
            self._play_system_sound(sound_effect)
                        
        except Exception as e:
            print(f"⚠️ Error playing sound: {e}")
            # Fallback to system sound on any error
            self._play_system_sound(sound_effect)
    
    def _play_system_sound(self, sound_effect: QSoundEffect):
        """Play sound using system audio tools as fallback"""
        try:
            import subprocess
            import urllib.parse
            
            # Extract file path from QUrl
            url_string = str(sound_effect.source().toString())
            if url_string.startswith('file://'):
                file_path = urllib.parse.unquote(url_string[7:])  # Remove 'file://' prefix
                
                # Try paplay (PulseAudio) first
                try:
                    subprocess.run(['paplay', file_path], 
                                 check=False, 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL,
                                 timeout=2)
                    print(f"🔊 System audio (paplay) played")
                    return
                except:
                    pass
                
                # If paplay fails, try aplay
                try:
                    subprocess.run(['aplay', file_path], 
                                 check=False, 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL,
                                 timeout=2)
                    print(f"🔊 System audio (aplay) played")
                    return
                except:
                    pass
                    
                print(f"⚠️ Both paplay and aplay failed for {file_path}")
                        
        except Exception as e:
            print(f"⚠️ Error in system sound fallback: {e}")
    
    def set_volume(self, volume: float):
        """Set volume for all sounds (0.0 to 1.0)"""
        volume = max(0.0, min(1.0, volume))  # Clamp to valid range
        
        if self.start_sound:
            self.start_sound.setVolume(volume)
        if self.stop_sound:
            self.stop_sound.setVolume(volume)
    
    def is_available(self) -> bool:
        """Check if sound effects are available"""
        return (self.start_sound is not None and 
                self.stop_sound is not None and
                self.start_sound.isLoaded() and 
                self.stop_sound.isLoaded()) 