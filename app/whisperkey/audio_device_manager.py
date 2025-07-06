"""Audio device manager for automatic device switching during dictation.

Automatically switches to preferred microphone when recording starts,
and back to preferred audio output when recording stops.
"""
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple


class AudioDevice:
    """Represents an audio device"""
    def __init__(self, index: int, name: str, description: str, is_default: bool = False):
        self.index = index
        self.name = name
        self.description = description
        self.is_default = is_default
    
    def __repr__(self):
        default_marker = " (default)" if self.is_default else ""
        return f"AudioDevice({self.index}: {self.description}{default_marker})"


class AudioDeviceManager:
    """Manages automatic audio device switching for dictation"""
    
    def __init__(self):
        self.audio_system = self._detect_audio_system()
        
        # Legacy two-device configuration
        self.preferred_mic_device: Optional[str] = None
        self.preferred_output_device: Optional[str] = None
        self.original_mic_device: Optional[str] = None
        self.original_output_device: Optional[str] = None
        
        # New four-device configuration
        self.dictating_mic: Optional[str] = None
        self.dictating_output: Optional[str] = None
        self.normal_mic: Optional[str] = None
        self.normal_output: Optional[str] = None
        
        self.switching_enabled = False
        self.four_device_mode = False  # Track which mode we're using
        
        # Bluetooth profile management
        self.bluetooth_cards: Dict[str, str] = {}  # card_name -> original_profile
        self.bluetooth_switching_enabled = False
        
        print(f"🔊 Audio system detected: {self.audio_system}")
    
    def _detect_audio_system(self) -> str:
        """Detect whether we're using PulseAudio or PipeWire"""
        try:
            # Check for wpctl (PipeWire/WirePlumber)
            result = subprocess.run(['wpctl', '--version'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return "pipewire"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        try:
            # Check for pactl (PulseAudio)
            result = subprocess.run(['pactl', '--version'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return "pulseaudio"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return "unknown"
    
    def _clean_device_name(self, description: str, device_name: str) -> str:
        """Clean up device names to be more user-friendly"""
        # If description is meaningful, use it
        if description and not description.startswith('alsa_') and len(description) > 5:
            # Clean up common patterns
            cleaned = description
            
            # Remove redundant words
            cleaned = cleaned.replace(' Audio Device', '')
            cleaned = cleaned.replace(' Audio Controller', '')
            cleaned = cleaned.replace(' Digital Stereo (IEC958)', ' (Digital)')
            cleaned = cleaned.replace(' Analog Stereo', ' (Analog)')
            cleaned = cleaned.replace(' Speaker + Headphones', ' (Built-in)')
            cleaned = cleaned.replace(' Digital Microphone', ' (Built-in Mic)')
            cleaned = cleaned.replace(' Headphones Stereo Microphone', ' (Headset Mic)')
            
            # Shorten long technical names
            if 'Cannon Point-LP High Definition Audio Controller' in cleaned:
                cleaned = cleaned.replace('Cannon Point-LP High Definition Audio Controller', 'Built-in Audio')
            
            if 'USB PnP Audio Device' in cleaned:
                cleaned = cleaned.replace('USB PnP Audio Device', 'USB Audio')
            
            # Remove excessive technical details
            if len(cleaned) > 50:
                # Try to extract meaningful parts
                parts = cleaned.split()
                if len(parts) > 4:
                    # Keep first few meaningful words
                    meaningful_parts = []
                    for part in parts:
                        if not any(skip in part.lower() for skip in ['generic', 'controller', 'device']):
                            meaningful_parts.append(part)
                        if len(meaningful_parts) >= 3:
                            break
                    if meaningful_parts:
                        cleaned = ' '.join(meaningful_parts)
            
            return cleaned
        
        # Fallback: try to extract meaningful info from technical name
        if device_name:
            # Extract card type from technical names
            if 'usb' in device_name.lower():
                return "USB Audio Device"
            elif 'hdmi' in device_name.lower():
                if '1' in device_name:
                    return "HDMI Output 1"
                elif '2' in device_name:
                    return "HDMI Output 2"
                elif '3' in device_name:
                    return "HDMI Output 3"
                else:
                    return "HDMI Output"
            elif 'analog' in device_name.lower():
                if 'input' in device_name.lower() or 'source' in device_name.lower():
                    return "Built-in Microphone"
                else:
                    return "Built-in Speakers"
            elif 'digital' in device_name.lower():
                return "Digital Audio"
        
        # Last resort: return original description or a generic name
        return description if description else "Audio Device"
    
    def _get_device_description(self, device_name: str, device_type: str) -> str:
        """Get user-friendly description for a device from pactl"""
        try:
            result = subprocess.run(['pactl', 'list', device_type], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if f'Name: {device_name}' in line:
                        # Look for Description line in following lines
                        for j in range(i+1, min(i+10, len(lines))):
                            if lines[j].strip().startswith('Description:'):
                                return lines[j].split('Description:', 1)[1].strip()
                        break
        except Exception:
            pass
        return device_name  # fallback
    
    def get_audio_sinks(self) -> List[AudioDevice]:
        """Get list of available audio output devices (sinks)"""
        devices = []
        
        if self.audio_system == "pulseaudio":
            try:
                # Get current default sink
                result = subprocess.run(['pactl', 'info'], 
                                      capture_output=True, text=True, timeout=5)
                default_sink = None
                for line in result.stdout.split('\n'):
                    if line.startswith('Default Sink:'):
                        default_sink = line.split(':', 1)[1].strip()
                        break
                
                # Get all sinks
                result = subprocess.run(['pactl', 'list', 'short', 'sinks'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                index = int(parts[0])
                                name = parts[1]
                                # Get user-friendly description
                                description = self._get_device_description(name, 'sinks')
                                
                                is_default = (name == default_sink)
                                # Clean up the description for better user experience
                                clean_description = self._clean_device_name(description, name)
                                devices.append(AudioDevice(index, name, clean_description, is_default))
            except Exception as e:
                print(f"⚠️ Error getting PulseAudio sinks: {e}")
        
        elif self.audio_system == "pipewire":
            try:
                result = subprocess.run(['wpctl', 'status'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    in_sinks_section = False
                    
                    for line in lines:
                        if 'Sinks:' in line:
                            in_sinks_section = True
                            continue
                        elif in_sinks_section and line.strip() == '':
                            break
                        elif in_sinks_section and '│' in line:
                            # Parse wpctl output format
                            parts = line.split('│')
                            if len(parts) >= 2:
                                try:
                                    # Extract device info
                                    device_info = parts[1].strip()
                                    is_default = '*' in device_info
                                    # Extract index and description
                                    if '. ' in device_info:
                                        index_part, desc = device_info.split('. ', 1)
                                        index = int(index_part.replace('*', '').strip())
                                        description = desc.strip()
                                        name = f"sink_{index}"  # PipeWire uses numeric IDs
                                        # Clean up the description for better user experience
                                        clean_description = self._clean_device_name(description, name)
                                        devices.append(AudioDevice(index, name, clean_description, is_default))
                                except (ValueError, IndexError):
                                    continue
            except Exception as e:
                print(f"⚠️ Error getting PipeWire sinks: {e}")
        
        return devices
    
    def get_audio_sources(self) -> List[AudioDevice]:
        """Get list of available audio input devices (sources)"""
        devices = []
        
        if self.audio_system == "pulseaudio":
            try:
                # Get current default source
                result = subprocess.run(['pactl', 'info'], 
                                      capture_output=True, text=True, timeout=5)
                default_source = None
                for line in result.stdout.split('\n'):
                    if line.startswith('Default Source:'):
                        default_source = line.split(':', 1)[1].strip()
                        break
                
                # Get all sources
                result = subprocess.run(['pactl', 'list', 'short', 'sources'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip() and not line.strip().endswith('.monitor'):  # Skip monitor sources
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                index = int(parts[0])
                                name = parts[1]
                                # Get user-friendly description
                                description = self._get_device_description(name, 'sources')
                                
                                is_default = (name == default_source)
                                # Clean up the description for better user experience
                                clean_description = self._clean_device_name(description, name)
                                devices.append(AudioDevice(index, name, clean_description, is_default))
            except Exception as e:
                print(f"⚠️ Error getting PulseAudio sources: {e}")
        
        elif self.audio_system == "pipewire":
            try:
                result = subprocess.run(['wpctl', 'status'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    in_sources_section = False
                    
                    for line in lines:
                        if 'Sources:' in line:
                            in_sources_section = True
                            continue
                        elif in_sources_section and line.strip() == '':
                            break
                        elif in_sources_section and '│' in line:
                            # Parse wpctl output format
                            parts = line.split('│')
                            if len(parts) >= 2:
                                try:
                                    # Extract device info
                                    device_info = parts[1].strip()
                                    is_default = '*' in device_info
                                    # Skip monitor sources
                                    if '.monitor' in device_info:
                                        continue
                                    # Extract index and description
                                    if '. ' in device_info:
                                        index_part, desc = device_info.split('. ', 1)
                                        index = int(index_part.replace('*', '').strip())
                                        description = desc.strip()
                                        name = f"source_{index}"  # PipeWire uses numeric IDs
                                        # Clean up the description for better user experience
                                        clean_description = self._clean_device_name(description, name)
                                        devices.append(AudioDevice(index, name, clean_description, is_default))
                                except (ValueError, IndexError):
                                    continue
            except Exception as e:
                print(f"⚠️ Error getting PipeWire sources: {e}")
        
        return devices
    
    def set_default_sink(self, device_name: str) -> bool:
        """Set the default audio output device"""
        try:
            # Handle special Bluetooth HFP sink names
            if device_name.startswith('bt_hfp_sink_'):
                device_id = device_name.replace('bt_hfp_sink_', '')
                actual_device_name = f"bluez_output.{device_id}.1"
                
                # First, switch the Bluetooth card to HFP mode
                card_name = f"bluez_card.{device_id}"
                self._switch_bluetooth_card_to_headset(card_name)
                time.sleep(0.5)  # Wait for profile switch
                
                # Then set the sink
                device_name = actual_device_name
            
            if self.audio_system == "pulseaudio":
                result = subprocess.run(['pactl', 'set-default-sink', device_name], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Also move existing streams to the new sink
                    self._move_streams_to_sink(device_name)
                    return True
            elif self.audio_system == "pipewire":
                # For PipeWire, use wpctl with device index
                if device_name.startswith('sink_'):
                    device_index = device_name.replace('sink_', '')
                    result = subprocess.run(['wpctl', 'set-default', device_index], 
                                          capture_output=True, text=True, timeout=5)
                    return result.returncode == 0
        except Exception as e:
            print(f"⚠️ Error setting default sink: {e}")
        return False
    
    def set_default_source(self, device_name: str) -> bool:
        """Set the default audio input device"""
        try:
            # Handle special Bluetooth HFP source names
            if device_name.startswith('bt_hfp_source_'):
                device_id = device_name.replace('bt_hfp_source_', '')
                actual_device_name = f"bluez_input.{device_id}.0"
                
                # First, switch the Bluetooth card to HFP mode
                card_name = f"bluez_card.{device_id}"
                self._switch_bluetooth_card_to_headset(card_name)
                time.sleep(0.5)  # Wait for profile switch
                
                # Then set the source
                device_name = actual_device_name
            
            if self.audio_system == "pulseaudio":
                result = subprocess.run(['pactl', 'set-default-source', device_name], 
                                      capture_output=True, text=True, timeout=5)
                return result.returncode == 0
            elif self.audio_system == "pipewire":
                # For PipeWire, use wpctl with device index
                if device_name.startswith('source_'):
                    device_index = device_name.replace('source_', '')
                    result = subprocess.run(['wpctl', 'set-default', device_index], 
                                          capture_output=True, text=True, timeout=5)
                    return result.returncode == 0
        except Exception as e:
            print(f"⚠️ Error setting default source: {e}")
        return False
    
    def _move_streams_to_sink(self, sink_name: str):
        """Move all active audio streams to the specified sink (PulseAudio only)"""
        try:
            # Get active sink inputs
            result = subprocess.run(['pactl', 'list', 'short', 'sink-inputs'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 1:
                            stream_index = parts[0]
                            subprocess.run(['pactl', 'move-sink-input', stream_index, sink_name], 
                                         capture_output=True, timeout=3)
        except Exception as e:
            print(f"⚠️ Error moving streams: {e}")
    
    def get_current_default_sink(self) -> Optional[str]:
        """Get the current default audio output device"""
        try:
            if self.audio_system == "pulseaudio":
                result = subprocess.run(['pactl', 'info'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('Default Sink:'):
                            return line.split(':', 1)[1].strip()
            elif self.audio_system == "pipewire":
                # For PipeWire, find the device marked with *
                devices = self.get_audio_sinks()
                for device in devices:
                    if device.is_default:
                        return device.name
        except Exception as e:
            print(f"⚠️ Error getting current sink: {e}")
        return None
    
    def get_current_default_source(self) -> Optional[str]:
        """Get the current default audio input device"""
        try:
            if self.audio_system == "pulseaudio":
                result = subprocess.run(['pactl', 'info'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('Default Source:'):
                            return line.split(':', 1)[1].strip()
            elif self.audio_system == "pipewire":
                # For PipeWire, find the device marked with *
                devices = self.get_audio_sources()
                for device in devices:
                    if device.is_default:
                        return device.name
        except Exception as e:
            print(f"⚠️ Error getting current source: {e}")
        return None
    
    def configure_preferred_devices(self, mic_device: str, output_device: str):
        """Configure preferred devices for automatic switching"""
        self.preferred_mic_device = mic_device
        self.preferred_output_device = output_device
        self.switching_enabled = True
        print(f"🔊 Audio switching configured:")
        print(f"  📱 Preferred mic: {mic_device}")
        print(f"  🔊 Preferred output: {output_device}")
    
    def start_recording_audio_switch(self):
        """Switch to preferred devices when recording starts"""
        # If four-device mode is configured, use that instead
        if self.four_device_mode:
            return self.start_recording_audio_switch_four_device()
            
        if not self.switching_enabled or not self.preferred_mic_device:
            return
        
        # Store current devices
        self.original_mic_device = self.get_current_default_source()
        self.original_output_device = self.get_current_default_sink()
        
        print(f"🔄 Switching audio for recording...")
        print(f"  📱 Mic: {self.original_mic_device} → {self.preferred_mic_device}")
        
        # Switch to preferred microphone
        if self.set_default_source(self.preferred_mic_device):
            print(f"✅ Switched to preferred microphone")
        else:
            print(f"⚠️ Failed to switch to preferred microphone")
    
    def stop_recording_audio_switch(self):
        """Switch back to preferred output device when recording stops"""
        # If four-device mode is configured, use that instead
        if self.four_device_mode:
            return self.stop_recording_audio_switch_four_device()
            
        if not self.switching_enabled:
            return
        
        print(f"🔄 Switching audio after recording...")
        
        # Switch to preferred output device (for listening to music, etc.)
        if self.preferred_output_device:
            print(f"  🔊 Output: {self.original_output_device} → {self.preferred_output_device}")
            if self.set_default_sink(self.preferred_output_device):
                print(f"✅ Switched to preferred output device")
            else:
                print(f"⚠️ Failed to switch to preferred output device")
        
        # Optionally restore original microphone (or leave on preferred mic)
        # For now, we'll leave the mic on the preferred device since the user
        # might want to dictate again soon
    
    def disable_switching(self):
        """Disable automatic audio device switching"""
        self.switching_enabled = False
        self.four_device_mode = False
        print("🔊 Audio device switching disabled")
    
    def enable_switching(self):
        """Enable automatic audio device switching"""
        if self.preferred_mic_device and self.preferred_output_device:
            self.switching_enabled = True
            print("🔊 Audio device switching enabled")
        else:
            print("⚠️ Cannot enable switching: preferred devices not configured")
    
    def list_devices(self) -> Dict[str, List[AudioDevice]]:
        """Get lists of all available audio devices"""
        sources = self.get_audio_sources()
        sinks = self.get_audio_sinks()
        
        # Enhance with Bluetooth profile variants
        enhanced_sources, enhanced_sinks = self._add_bluetooth_profile_variants(sources, sinks)
        
        return {
            'sources': enhanced_sources,
            'sinks': enhanced_sinks
        }
    
    def _add_bluetooth_profile_variants(self, sources: List[AudioDevice], sinks: List[AudioDevice]) -> Tuple[List[AudioDevice], List[AudioDevice]]:
        """Add virtual device entries for Bluetooth profile variants"""
        enhanced_sources = sources.copy()
        enhanced_sinks = sinks.copy()
        
        # Get Bluetooth card information
        bluetooth_cards = self._get_bluetooth_card_info()
        
        for card_name, card_info in bluetooth_cards.items():
            # Extract device identifier from card name (e.g., bluez_card.20_18_5B_1E_72_6C -> 20_18_5B_1E_72_6C)
            if not card_name.startswith('bluez_card.'):
                continue
                
            device_id = card_name.replace('bluez_card.', '')
            profiles = card_info.get('profiles', {})
            
            # Get a user-friendly device name from existing devices or create one
            device_base_name = self._get_bluetooth_device_base_name(device_id, sources, sinks)
            
            # Check what profiles are available
            has_a2dp = any(profile.startswith('a2dp') for profile in profiles.keys())
            has_hfp = any(profile.startswith('headset-head-unit') for profile in profiles.keys())
            
            if has_a2dp and has_hfp:
                # This Bluetooth device supports both profiles
                # Add A2DP sink variant (high-quality audio output)
                a2dp_sink_name = f"bluez_output.{device_id}.1"  # A2DP sink
                a2dp_sink_desc = f"{device_base_name}"
                
                # Check if A2DP sink already exists in the list
                if not any(sink.name == a2dp_sink_name for sink in enhanced_sinks):
                    enhanced_sinks.append(AudioDevice(
                        index=9000 + len(enhanced_sinks),  # Use high index to avoid conflicts
                        name=a2dp_sink_name,
                        description=a2dp_sink_desc,
                        is_default=False
                    ))
                
                # Add HFP variants (handsfree with microphone)
                hfp_sink_name = f"bluez_output.{device_id}.1"  # HFP sink (same as A2DP but different profile)
                hfp_source_name = f"bluez_input.{device_id}.0"  # HFP source (microphone)
                
                hfp_sink_desc = f"Handsfree ({device_base_name})"
                hfp_source_desc = f"Handsfree ({device_base_name})"
                
                # Add HFP sink variant (lower quality but enables microphone)
                if not any(sink.description.startswith("Handsfree") and device_id in sink.name for sink in enhanced_sinks):
                    enhanced_sinks.append(AudioDevice(
                        index=9100 + len(enhanced_sinks),  # Use high index to avoid conflicts
                        name=f"bt_hfp_sink_{device_id}",  # Special name to identify HFP mode
                        description=hfp_sink_desc,
                        is_default=False
                    ))
                
                # Add HFP source variant (microphone)
                if not any(source.description.startswith("Handsfree") and device_id in source.name for source in enhanced_sources):
                    enhanced_sources.append(AudioDevice(
                        index=9200 + len(enhanced_sources),  # Use high index to avoid conflicts
                        name=f"bt_hfp_source_{device_id}",  # Special name to identify HFP mode
                        description=hfp_source_desc,
                        is_default=False
                    ))
        
        return enhanced_sources, enhanced_sinks
    
    def _get_bluetooth_device_base_name(self, device_id: str, sources: List[AudioDevice], sinks: List[AudioDevice]) -> str:
        """Get a user-friendly base name for a Bluetooth device"""
        # Look for existing Bluetooth devices with this ID to get the friendly name
        for device in sources + sinks:
            if device_id in device.name and 'bluez' in device.name:
                # Clean up the description to get base name
                desc = device.description
                # Remove common suffixes
                for suffix in [' (Built-in)', ' (Analog)', ' (Digital)', ' Stereo', ' Mono']:
                    desc = desc.replace(suffix, '')
                return desc
        
        # Fallback: try to get name from card description
        try:
            result = subprocess.run(['pactl', 'list', 'cards'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                in_target_card = False
                for line in lines:
                    if f'bluez_card.{device_id}' in line:
                        in_target_card = True
                    elif in_target_card and line.strip().startswith('device.description = '):
                        # Extract device description
                        desc = line.split('device.description = ')[1].strip().strip('"')
                        return desc
                    elif in_target_card and line.startswith('Card #'):
                        # Moved to next card
                        break
        except Exception:
            pass
        
        # Ultimate fallback: generic name
        return f"Bluetooth Device {device_id[-4:]}"
    
    def _get_bluetooth_card_info(self) -> Dict[str, Dict[str, str]]:
        """Get information about Bluetooth audio cards and their profiles"""
        bluetooth_cards = {}
        
        try:
            result = subprocess.run(['pactl', 'list', 'cards'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_card = None
                current_profiles = {}
                active_profile = None
                in_profiles_section = False
                
                for line in lines:
                    if line.startswith('Card #'):
                        # Save previous card if it was Bluetooth
                        if current_card and 'bluez' in current_card:
                            bluetooth_cards[current_card] = {
                                'active_profile': active_profile,
                                'profiles': current_profiles.copy()
                            }
                        
                        # Reset for new card
                        current_card = None
                        current_profiles = {}
                        active_profile = None
                        in_profiles_section = False
                    
                    elif line.strip().startswith('Name: ') and 'bluez' in line:
                        current_card = line.split('Name: ')[1].strip()
                        print(f"🔵 Found Bluetooth card: {current_card}")
                    
                    elif line.strip().startswith('Active Profile: '):
                        active_profile = line.split('Active Profile: ')[1].strip()
                        print(f"🔵 Active profile: {active_profile}")
                    
                    elif line.strip().startswith('Profiles:'):
                        in_profiles_section = True
                        print(f"🔵 Starting profiles section for {current_card}")
                        continue
                    
                    elif in_profiles_section and current_card:
                        # We're in the profiles section for a Bluetooth card
                        if line.strip() == '':
                            # Empty line might end the profiles section
                            continue
                        elif line.startswith('\t\t') and ':' in line:
                            # This is a profile line (indented with tabs)
                            profile_line = line.strip()
                            if ':' in profile_line:
                                profile_parts = profile_line.split(':', 1)
                                if len(profile_parts) >= 2:
                                    profile_name = profile_parts[0].strip()
                                    profile_desc = profile_parts[1].strip()
                                    current_profiles[profile_name] = profile_desc
                                    print(f"🔵 Found profile: {profile_name} -> {profile_desc}")
                        elif not line.startswith('\t') and line.strip():
                            # Non-indented line means we're out of profiles section
                            in_profiles_section = False
                
                # Don't forget the last card
                if current_card and 'bluez' in current_card:
                    bluetooth_cards[current_card] = {
                        'active_profile': active_profile,
                        'profiles': current_profiles.copy()
                    }
                    
        except Exception as e:
            print(f"⚠️ Error getting Bluetooth card info: {e}")
        
        print(f"🔵 Final Bluetooth cards detected: {bluetooth_cards}")
        return bluetooth_cards
    
    def _set_bluetooth_profile(self, card_name: str, profile: str) -> bool:
        """Set the profile for a Bluetooth card"""
        try:
            result = subprocess.run(['pactl', 'set-card-profile', card_name, profile], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"🔵 Switched {card_name} to {profile} profile")
                return True
            else:
                print(f"⚠️ Failed to switch {card_name} to {profile}: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Error setting Bluetooth profile: {e}")
        return False
    
    def enable_bluetooth_switching(self):
        """Enable automatic Bluetooth profile switching"""
        self.bluetooth_switching_enabled = True
        print("🔵 Bluetooth profile switching enabled")
    
    def disable_bluetooth_switching(self):
        """Disable automatic Bluetooth profile switching"""
        self.bluetooth_switching_enabled = False
        print("🔵 Bluetooth profile switching disabled")
    
    def switch_bluetooth_to_headset_mode(self):
        """Switch all Bluetooth devices to headset mode (for microphone use)"""
        if not self.bluetooth_switching_enabled:
            print("🔵 Bluetooth switching disabled, skipping headset mode switch")
            return
        
        print("🔵 Searching for Bluetooth cards...")
        bluetooth_cards = self._get_bluetooth_card_info()
        print(f"🔵 Found {len(bluetooth_cards)} Bluetooth cards: {list(bluetooth_cards.keys())}")
        
        # Always try direct detection to catch cards that might not be fully detected
        print("🔵 Also trying direct detection for any missed cards...")
        try:
            result = subprocess.run(['pactl', 'list', 'cards', 'short'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'bluez' in line and line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            card_name = parts[1]
                            if card_name not in bluetooth_cards:
                                print(f"🔵 Found additional Bluetooth card: {card_name}")
                                bluetooth_cards[card_name] = {'active_profile': 'unknown', 'profiles': {}}
        except Exception as e:
            print(f"⚠️ Error in direct Bluetooth detection: {e}")
        
        if not bluetooth_cards:
            print("🔵 No Bluetooth cards found at all")
            return
        
        for card_name, card_info in bluetooth_cards.items():
            current_profile = card_info['active_profile']
            available_profiles = card_info['profiles']
            
            print(f"🔵 Processing card {card_name}: current={current_profile}, available={list(available_profiles.keys())}")
            
            # Store the original profile for restoration
            if card_name not in self.bluetooth_cards:
                self.bluetooth_cards[card_name] = current_profile
            
            # Choose the best headset profile available
            headset_profiles = [
                'headset-head-unit-msbc',  # Preferred: mSBC codec
                'headset-head-unit-cvsd',  # Fallback: CVSD codec  
                'headset-head-unit'        # Generic headset
            ]
            
            # If no profiles detected or profile is A2DP, force switch to headset mode
            if not available_profiles or current_profile == 'a2dp-sink':
                print(f"🔵 Force switching {card_name} to headset mode (profiles not detected or in A2DP mode)")
                success = self._switch_bluetooth_card_to_headset(card_name)
                if success:
                    time.sleep(0.1)
                continue
            
            # Normal profile detection and switching
            target_profile = None
            for profile in headset_profiles:
                if profile in available_profiles:
                    target_profile = profile
                    break
            
            if target_profile and current_profile != target_profile:
                print(f"🔵 Switching {card_name} from {current_profile} to {target_profile}")
                self._set_bluetooth_profile(card_name, target_profile)
                # Minimal delay to let the profile switch settle
                time.sleep(0.1)
            elif target_profile and current_profile == target_profile:
                print(f"🔵 {card_name} already in headset mode ({current_profile})")
            else:
                print(f"⚠️ No suitable headset profile found for {card_name}, trying force switch...")
                self._switch_bluetooth_card_to_headset(card_name)
    
    def _switch_bluetooth_card_to_headset(self, card_name: str):
        """Switch a specific Bluetooth card to headset mode with EXACT WORKING SEQUENCE"""
        # BREAKTHROUGH: Found the exact working sequence from manual testing!
        # EXACT SEQUENCE: A2DP -> headset -> off -> headset (NO PORT SWITCHING!)
        try:
            print(f"🔵 Using EXACT WORKING SEQUENCE: A2DP -> headset -> off -> headset")
            
            # Step 1: Switch to headset mode (first switch)
            print(f"🔵 Step 1: Switching {card_name} to headset mode...")
            result1 = subprocess.run(['pactl', 'set-card-profile', card_name, 'headset-head-unit-msbc'], 
                                   capture_output=True, text=True, timeout=5)
            if result1.returncode != 0:
                print(f"⚠️ Step 1 failed for {card_name}: {result1.stderr}")
                return False
            
            print(f"✅ Step 1 successful: {card_name} to headset-head-unit-msbc")
            time.sleep(0.5)
            
            # Step 2: CRITICAL - Switch to OFF profile (reset connection)
            print(f"🔵 Step 2: Resetting connection (OFF profile)...")
            result2 = subprocess.run(['pactl', 'set-card-profile', card_name, 'off'], 
                                   capture_output=True, text=True, timeout=5)
            if result2.returncode != 0:
                print(f"⚠️ Step 2 failed for {card_name}: {result2.stderr}")
                return False
            
            print(f"✅ Step 2 successful: {card_name} disconnected")
            time.sleep(0.5)
            
            # Step 3: Switch back to headset mode (ACTIVATION!)
            print(f"🔵 Step 3: Switching back to headset mode (ACTIVATION)...")
            result3 = subprocess.run(['pactl', 'set-card-profile', card_name, 'headset-head-unit-msbc'], 
                                   capture_output=True, text=True, timeout=5)
            if result3.returncode != 0:
                print(f"⚠️ Step 3 failed for {card_name}: {result3.stderr}")
                return False
            
            print(f"✅ Step 3 successful: {card_name} back to headset-head-unit-msbc")
            time.sleep(1.0)  # Wait for profile to establish
            
            print(f"🎉 EXACT WORKING SEQUENCE SUCCESS: {card_name} microphone should now be active!")
            print(f"✅ Completed: A2DP -> headset -> off -> headset (NO PORT SWITCHING)")
            return True
                
        except Exception as e:
            print(f"⚠️ Error executing exact working sequence for {card_name}: {e}")
            return False
    
    def _switch_bluetooth_sink_port_to_handsfree(self, sink_name: str) -> bool:
        """Switch Bluetooth sink port to handsfree output (enables microphone)"""
        try:
            # Switch to headphone-hf-output port (handsfree output)
            result = subprocess.run(['pactl', 'set-sink-port', sink_name, 'headphone-hf-output'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"🔵 Successfully switched {sink_name} port to handsfree output")
                return True
            else:
                print(f"⚠️ Failed to switch {sink_name} port: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Error switching Bluetooth sink port: {e}")
        return False
    
    def _switch_bluetooth_sink_port_to_headphone(self, sink_name: str) -> bool:
        """Switch Bluetooth sink port back to headphone output (A2DP mode)"""
        try:
            # Switch to headphone-output port (A2DP high-quality output)
            result = subprocess.run(['pactl', 'set-sink-port', sink_name, 'headphone-output'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"🔵 Successfully switched {sink_name} port to headphone output")
                return True
            else:
                print(f"⚠️ Failed to switch {sink_name} port: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Error switching Bluetooth sink port: {e}")
        return False
    
    def _wait_for_bluetooth_source(self, card_name: str, max_wait_time: float = 3.0):
        """Wait for Bluetooth microphone source to become available after profile switch"""
        # Extract device ID from card name (e.g., bluez_card.20_18_5B_1E_72_6C -> 20_18_5B_1E_72_6C)
        if 'bluez_card.' in card_name:
            device_id = card_name.replace('bluez_card.', '')
            expected_source = f"bluez_input.{device_id}.0"
            
            print(f"🔵 Waiting for Bluetooth source {expected_source} to become available...")
            
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                try:
                    # Check if the Bluetooth input source exists
                    result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                                          capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and expected_source in result.stdout:
                        print(f"✅ Bluetooth source {expected_source} is now available")
                        return True
                except Exception:
                    pass
                
                time.sleep(0.2)  # Check every 200ms
            
            print(f"⚠️ Bluetooth source {expected_source} did not become available within {max_wait_time}s")
        return False
    
    def switch_bluetooth_to_a2dp_mode(self):
        """Switch all Bluetooth devices to A2DP mode (for high-quality audio)"""
        if not self.bluetooth_switching_enabled:
            return
        
        bluetooth_cards = self._get_bluetooth_card_info()
        
        for card_name, card_info in bluetooth_cards.items():
            current_profile = card_info['active_profile']
            available_profiles = card_info['profiles']
            
            # Choose the best A2DP profile available
            a2dp_profiles = [
                'a2dp-sink',     # Standard A2DP
                'a2dp-sink-sbc_xq'  # High-quality SBC if available
            ]
            
            target_profile = None
            for profile in a2dp_profiles:
                if profile in available_profiles:
                    target_profile = profile
                    break
            
            if target_profile and current_profile != target_profile:
                print(f"🔵 Switching {card_name} from {current_profile} to {target_profile}")
                try:
                    result = subprocess.run(['pactl', 'set-card-profile', card_name, target_profile], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        print(f"🔵 Switched {card_name} to {target_profile} profile")
                        
                        # Switch the sink port back to regular headphone output
                        sink_name = card_name.replace('bluez_card', 'bluez_output') + '.1'
                        port_result = subprocess.run(['pactl', 'set-sink-port', sink_name, 'headphone-output'], 
                                                    capture_output=True, text=True, timeout=3)
                        if port_result.returncode == 0:
                            print(f"🔵 Successfully switched {sink_name} port to headphone output")
                            print(f"🔵 Switched {sink_name} back to headphone port")
                        else:
                            print(f"⚠️ Failed to switch {sink_name} port: {port_result.stderr.strip()}")
                    else:
                        print(f"⚠️ Failed to switch {card_name}: {result.stderr.strip()}")
                except Exception as e:
                    print(f"⚠️ Error switching {card_name}: {e}")
            else:
                print(f"🔵 {card_name} already in A2DP mode ({current_profile})")
    
    def restore_bluetooth_profiles(self):
        """Restore original Bluetooth profiles on shutdown"""
        if not self.bluetooth_switching_enabled or not self.original_bluetooth_profiles:
            return
        
        print("🔵 Restoring original Bluetooth profiles...")
        for card_name, original_profile in self.original_bluetooth_profiles.items():
            try:
                result = subprocess.run(['pactl', 'set-card-profile', card_name, original_profile], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"🔵 Restored {card_name} to {original_profile}")
                else:
                    print(f"⚠️ Failed to restore {card_name}: {result.stderr.strip()}")
            except Exception as e:
                print(f"⚠️ Error restoring {card_name}: {e}")
    
    def configure_four_device_switching(self, dictating_mic: str = "", dictating_output: str = "", 
                                      normal_mic: str = "", normal_output: str = ""):
        """Configure four-device switching (separate devices for dictating vs normal use)"""
        self.switching_enabled = True
        self.four_device_mode = True
        self.dictating_mic = dictating_mic
        self.dictating_output = dictating_output  
        self.normal_mic = normal_mic
        self.normal_output = normal_output
        
        print(f"🔧 Four-device switching configured:")
        print(f"  📱 Dictating: mic={dictating_mic}, output={dictating_output}")
        print(f"  🎵 Normal: mic={normal_mic}, output={normal_output}")
    
    def start_recording_audio_switch_four_device(self):
        """Switch to dictating devices when recording starts (four-device mode)"""
        if not self.switching_enabled:
            return
        
        print(f"🔄 Switching to dictating devices...")
        
        # Switch Bluetooth devices to headset mode first (for microphone access)
        self.switch_bluetooth_to_headset_mode()
        
        # Switch to dictating microphone
        if self.dictating_mic:
            print(f"  📱 Mic: → {self.dictating_mic}")
            if self.set_default_source(self.dictating_mic):
                print(f"✅ Switched to dictating microphone")
            else:
                print(f"⚠️ Failed to switch to dictating microphone")
        
        # Switch to dictating output (might be muted or low volume speakers)
        if self.dictating_output:
            print(f"  🔊 Output: → {self.dictating_output}")
            if self.set_default_sink(self.dictating_output):
                print(f"✅ Switched to dictating output")
            else:
                print(f"⚠️ Failed to switch to dictating output")
    
    def stop_recording_audio_switch_four_device(self):
        """Switch to normal devices when recording stops (four-device mode)"""
        if not self.switching_enabled:
            return
        
        print(f"🔄 Switching to normal devices...")
        
        # Switch to normal microphone
        if self.normal_mic:
            print(f"  📱 Mic: → {self.normal_mic}")
            if self.set_default_source(self.normal_mic):
                print(f"✅ Switched to normal microphone")
            else:
                print(f"⚠️ Failed to switch to normal microphone")
        
        # Switch to normal output (for music, videos, etc.)
        if self.normal_output:
            print(f"  🔊 Output: → {self.normal_output}")
            if self.set_default_sink(self.normal_output):
                print(f"✅ Switched to normal output")
            else:
                print(f"⚠️ Failed to switch to normal output")
        
        # Switch Bluetooth devices back to A2DP mode (for high-quality music)
        self.switch_bluetooth_to_a2dp_mode() 