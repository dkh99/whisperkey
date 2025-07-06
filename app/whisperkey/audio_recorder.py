import gc
import queue
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.recording_thread = None
        self.stream = None  # Keep reference to current stream
        
        # Bluetooth/PulseAudio recording support
        self.use_pulseaudio = False
        self.pulseaudio_source = None
        self.pulseaudio_process = None
        
        # Set default device to None to use system default
        sd.default.samplerate = sample_rate
        sd.default.channels = channels
        sd.default.dtype = np.float32
        
    def start_recording(self):
        """Start recording audio from the default microphone"""
        if self.is_recording:
            print("⚠️ AudioRecorder: Already recording, ignoring start request")
            return
            
        # Check if previous recording thread is still alive
        if self.recording_thread and self.recording_thread.is_alive():
            print("⚠️ AudioRecorder: Previous recording thread still running, forcing cleanup")
            self.force_cleanup()
            time.sleep(0.2)  # Give cleanup time to work
            
        print("🎤 AudioRecorder: Starting recording...")
        self.is_recording = True
        self.audio_queue = queue.Queue()
        
        # Start recording in a separate thread with timeout protection
        self.recording_thread = threading.Thread(target=self._record_with_timeout)
        self.recording_thread.daemon = True  # Make it a daemon thread
        self.recording_thread.start()
        print(f"🎤 AudioRecorder: Recording thread started, is_recording={self.is_recording}")
    
    def _record_with_timeout(self):
        """Internal method with timeout protection"""
        print("🎤 AudioRecorder: _record_with_timeout thread started")
        
        try:
            # Check if we need to use PulseAudio directly for Bluetooth microphones
            self._wait_for_bluetooth_microphone_if_needed()
            
            if self.use_pulseaudio:
                # Use PulseAudio directly for Bluetooth microphones
                self._record_with_pulseaudio()
            else:
                # Use sounddevice for regular microphones
                self._record_with_sounddevice()
                
        except Exception as e:
            print(f"❌ AudioRecorder: Recording setup error: {e}")
            self.is_recording = False
        finally:
            print("🎤 AudioRecorder: Entering cleanup...")
            self._cleanup_stream()
            print("🎤 AudioRecorder: _record_with_timeout thread finished")
    
    def _record_with_sounddevice(self):
        """Record using sounddevice (for regular microphones)"""
        # Set a timeout for the entire recording setup
        setup_timeout = 2.0  # 2 seconds max for setup
        start_time = time.time()
        
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio callback status: {status}")
            if self.is_recording:
                self.audio_queue.put(indata.copy())
        
        print("🎤 AudioRecorder: Creating audio stream with timeout protection...")
        
        # Create stream with minimal settings
        try:
            self.stream = sd.InputStream(
                callback=audio_callback,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.float32,
                blocksize=512,  # Smaller blocksize for responsiveness
                latency='low'   # Request low latency
            )
            
            if time.time() - start_time > setup_timeout:
                raise Exception("Stream creation timed out")
            
            print("🎤 AudioRecorder: Stream created, starting...")
            self.stream.start()
            print("🎤 AudioRecorder: Stream started successfully!")
            
            # Recording loop with quick exit
            print("🎤 AudioRecorder: Entering recording loop...")
            while self.is_recording:
                time.sleep(0.01)  # Very responsive
                
            print("🎤 AudioRecorder: Exited recording loop")
            
        except Exception as stream_error:
            print(f"❌ AudioRecorder: Stream error: {stream_error}")
            self.is_recording = False
            return
    
    def _record_with_pulseaudio(self):
        """Record using PipeWire/PulseAudio (for Bluetooth microphones)"""
        import subprocess
        import os
        
        print(f"🔵 AudioRecorder: Using PipeWire/PulseAudio to record from {self.pulseaudio_source}")
        
        # Check if system is running PipeWire
        is_pipewire = os.path.exists('/usr/bin/pw-record')
        if not is_pipewire:
            # Also check by looking for pipewire processes
            try:
                result = subprocess.run(['pgrep', 'pipewire'], capture_output=True, text=True, timeout=2)
                is_pipewire = result.returncode == 0
            except:
                is_pipewire = False
        
        if is_pipewire:
            print("🔵 AudioRecorder: Detected PipeWire system, using pw-record")
            self._record_with_pipewire()
        else:
            print("🔵 AudioRecorder: Detected PulseAudio system, using parec")
            self._record_with_parec()
    
    def _record_with_pipewire(self):
        """Record using PipeWire native tools"""
        import subprocess
        import tempfile
        
        try:
            # First, get the PipeWire node ID for the Bluetooth source
            print(f"🔵 AudioRecorder: Finding PipeWire node for {self.pulseaudio_source}")
            
            # Get node ID from wpctl status
            result = subprocess.run(['wpctl', 'status'], capture_output=True, text=True, timeout=3)
            if result.returncode != 0:
                print(f"⚠️ Failed to get wpctl status: {result.stderr}")
                return
            
            # Parse the output to find the Bluetooth source node ID
            node_id = None
            lines = result.stdout.split('\n')
            in_sources_section = False
            
            for line in lines:
                if '├─ Sources:' in line:
                    in_sources_section = True
                    continue
                elif '├─' in line and in_sources_section:
                    # Exited sources section
                    break
                elif in_sources_section and 'HUAWEI FreeLace Pro 2' in line:
                    # Extract node ID (number at start of line)
                    parts = line.strip().split('.')
                    if parts and parts[0].strip().replace('*', '').strip().isdigit():
                        node_id = parts[0].strip().replace('*', '').strip()
                        break
            
            if not node_id:
                print(f"⚠️ Could not find PipeWire node ID for Bluetooth source")
                return
                
            print(f"🔵 AudioRecorder: Found PipeWire node ID: {node_id}")
            
            # Set as default source using wpctl
            try:
                result = subprocess.run(['wpctl', 'set-default', node_id], 
                                     capture_output=True, text=True, timeout=3)
                if result.returncode != 0:
                    print(f"⚠️ Failed to set default source: {result.stderr}")
                else:
                    print(f"✅ Set node {node_id} as default source")
            except Exception as e:
                print(f"⚠️ Error setting default source: {e}")
            
            # Create a temporary WAV file for pw-record
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_wav_path = temp_file.name
            
            # Use pw-record to record from the specific node
            cmd = [
                'pw-record',
                '--target', node_id,
                '--rate', str(self.sample_rate),
                '--channels', str(self.channels),
                temp_wav_path
            ]
            
            print(f"🔵 AudioRecorder: Starting pw-record command: {' '.join(cmd)}")
            self.pulseaudio_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Give process a moment to start
            time.sleep(0.2)
            if self.pulseaudio_process.poll() is not None:
                stderr_output = self.pulseaudio_process.stderr.read().decode('utf-8', errors='ignore')
                print(f"❌ pw-record process failed immediately: {stderr_output}")
                return
            
            print("🔵 AudioRecorder: pw-record started successfully!")
            
            # Monitor the process and simulate audio chunks for VoxVibe
            chunks_received = 0
            last_check_time = time.time()
            
            print("🔵 AudioRecorder: Entering PipeWire recording loop...")
            while self.is_recording and self.pulseaudio_process and self.pulseaudio_process.poll() is None:
                try:
                    current_time = time.time()
                    
                    # Check if WAV file exists and is growing
                    if os.path.exists(temp_wav_path):
                        file_size = os.path.getsize(temp_wav_path)
                        if file_size > 44:  # WAV header is 44 bytes
                            chunks_received += 1
                            
                            if chunks_received <= 5:
                                print(f"🔵 pw-record working: WAV file size {file_size} bytes (chunk {chunks_received})")
                            
                            # Simulate audio chunk for VoxVibe's queue
                            # We create a small dummy chunk to keep VoxVibe happy
                            # The actual audio will be read at the end
                            if current_time - last_check_time >= 0.1:  # Every 100ms
                                dummy_chunk = np.zeros((160, 1), dtype=np.float32)  # 10ms of silence at 16kHz
                                self.audio_queue.put(dummy_chunk)
                                last_check_time = current_time
                    
                    time.sleep(0.05)  # Check every 50ms
                    
                except Exception as read_error:
                    print(f"⚠️ PipeWire monitoring error: {read_error}")
                    time.sleep(0.1)
                    continue
            
            print(f"🔵 AudioRecorder: Exited PipeWire recording loop (chunks received: {chunks_received})")
            
            # Cleanup: terminate pw-record and read final WAV file
            if self.pulseaudio_process:
                self.pulseaudio_process.terminate()
                self.pulseaudio_process.wait(timeout=2.0)
            
            # Read the final WAV file and add real audio to queue
            if os.path.exists(temp_wav_path) and os.path.getsize(temp_wav_path) > 44:
                try:
                    import wave
                    with wave.open(temp_wav_path, 'rb') as wav_file:
                        frames = wav_file.readframes(wav_file.getnframes())
                        if frames:
                            audio_data = np.frombuffer(frames, dtype=np.int16)
                            audio_data = audio_data.astype(np.float32) / 32768.0
                            
                            # Reshape for channels
                            if self.channels > 1:
                                audio_data = audio_data.reshape(-1, self.channels)
                            else:
                                audio_data = audio_data.reshape(-1, 1)
                            
                            # Clear the dummy chunks and add real audio
                            while not self.audio_queue.empty():
                                try:
                                    self.audio_queue.get_nowait()
                                except:
                                    break
                            
                            # Add real audio data
                            self.audio_queue.put(audio_data)
                            print(f"🔵 AudioRecorder: Successfully read {len(audio_data)} samples from WAV file")
                except Exception as wav_error:
                    print(f"⚠️ Error reading WAV file: {wav_error}")
            
            # Cleanup temporary file
            try:
                os.unlink(temp_wav_path)
            except:
                pass
                
        except Exception as pw_error:
            print(f"❌ AudioRecorder: PipeWire error: {pw_error}")
            self.is_recording = False
    
    def _record_with_parec(self):
        """Record using PulseAudio parec (fallback for pure PulseAudio systems)"""
        import subprocess
        
        try:
            # First, properly activate the Bluetooth source
            print(f"🔵 AudioRecorder: Activating Bluetooth source...")
            
            # Step 1: Set as default source
            try:
                result = subprocess.run(['pactl', 'set-default-source', self.pulseaudio_source], 
                                     capture_output=True, text=True, timeout=3)
                if result.returncode != 0:
                    print(f"⚠️ Failed to set default source: {result.stderr}")
                else:
                    print(f"✅ Set {self.pulseaudio_source} as default source")
            except Exception as e:
                print(f"⚠️ Error setting default source: {e}")
            
            # Step 2: Unsuspend the source
            try:
                result = subprocess.run(['pactl', 'suspend-source', self.pulseaudio_source, 'false'], 
                                     capture_output=True, text=True, timeout=3)
                if result.returncode != 0:
                    print(f"⚠️ Failed to unsuspend source: {result.stderr}")
                else:
                    print(f"✅ Unsuspended source {self.pulseaudio_source}")
            except Exception as e:
                print(f"⚠️ Error unsuspending source: {e}")
            
            # Step 3: Wait for source to become ready
            time.sleep(0.5)  # Give more time for Bluetooth source to activate
            
            # Step 4: Verify source is available and not suspended
            try:
                result = subprocess.run(['pactl', 'list', 'sources', 'short'], 
                                     capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    sources = result.stdout
                    if self.pulseaudio_source in sources:
                        if 'SUSPENDED' in sources:
                            print(f"⚠️ Source {self.pulseaudio_source} is still suspended")
                        else:
                            print(f"✅ Source {self.pulseaudio_source} is active and ready")
                    else:
                        print(f"⚠️ Source {self.pulseaudio_source} not found in source list")
            except Exception as e:
                print(f"⚠️ Error checking source status: {e}")
            
            # Use parec to record from PulseAudio source - try s16le format first
            cmd = [
                'parec',
                '--device', self.pulseaudio_source,
                '--rate', str(self.sample_rate),
                '--channels', str(self.channels),
                '--format', 's16le',  # Use 16-bit signed little endian
                '--raw',
                '--latency-msec', '50'  # Low latency
            ]
            
            print(f"🔵 AudioRecorder: Starting parec command: {' '.join(cmd)}")
            self.pulseaudio_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Unbuffered
            )
            
            # Give process a moment to start and check for errors
            time.sleep(0.2)  # Increased wait time
            if self.pulseaudio_process.poll() is not None:
                stderr_output = self.pulseaudio_process.stderr.read().decode('utf-8', errors='ignore')
                print(f"❌ PulseAudio process failed immediately: {stderr_output}")
                return
            
            print("🔵 AudioRecorder: PulseAudio recording started successfully!")
            
            # Read audio data in chunks
            chunk_size = 512 * self.channels * 2  # 512 samples * channels * 2 bytes per int16
            chunks_received = 0
            no_data_count = 0
            max_no_data = 50  # Allow 50 empty reads before giving up
            
            print("🔵 AudioRecorder: Entering PulseAudio recording loop...")
            while self.is_recording and self.pulseaudio_process and self.pulseaudio_process.poll() is None:
                try:
                    # Read chunk from parec with timeout
                    import select
                    
                    # Check if data is available to read (non-blocking)
                    ready, _, _ = select.select([self.pulseaudio_process.stdout], [], [], 0.1)
                    
                    if ready:
                        data = self.pulseaudio_process.stdout.read(chunk_size)
                        if data:
                            chunks_received += 1
                            no_data_count = 0  # Reset counter
                            
                            if chunks_received <= 5:  # Log first few chunks
                                print(f"🔵 Received audio chunk {chunks_received}: {len(data)} bytes")
                            
                            # Convert s16le bytes to numpy array
                            audio_chunk = np.frombuffer(data, dtype=np.int16)
                            
                            # Convert to float32 and normalize
                            audio_chunk = audio_chunk.astype(np.float32) / 32768.0
                            
                            # Reshape if stereo
                            if self.channels > 1:
                                audio_chunk = audio_chunk.reshape(-1, self.channels)
                            else:
                                audio_chunk = audio_chunk.reshape(-1, 1)
                            
                            # Add to queue
                            self.audio_queue.put(audio_chunk)
                        else:
                            no_data_count += 1
                            if no_data_count > max_no_data:
                                print(f"🔵 No data received after {max_no_data} attempts, stopping")
                                break
                    else:
                        # No data ready to read
                        no_data_count += 1
                        if no_data_count > max_no_data:
                            print(f"🔵 No data available after {max_no_data} attempts, stopping")
                            break
                        time.sleep(0.01)
                    
                except Exception as read_error:
                    print(f"⚠️ PulseAudio read error: {read_error}")
                    time.sleep(0.01)
                    continue
            
            print(f"🔵 AudioRecorder: Exited PulseAudio recording loop (chunks received: {chunks_received})")
            
            # Check if process exited with error
            if self.pulseaudio_process and self.pulseaudio_process.poll() is not None:
                stderr_output = self.pulseaudio_process.stderr.read().decode('utf-8', errors='ignore')
                if stderr_output:
                    print(f"⚠️ PulseAudio stderr: {stderr_output}")
            
        except Exception as pa_error:
            print(f"❌ AudioRecorder: PulseAudio error: {pa_error}")
            self.is_recording = False
    
    def _cleanup_stream(self):
        """Clean up the audio stream or PulseAudio process"""
        # Clean up sounddevice stream
        if self.stream:
            try:
                print("🎤 AudioRecorder: Stopping stream...")
                self.stream.stop()
                print("🎤 AudioRecorder: Closing stream...")
                self.stream.close()
                print("✅ AudioRecorder: Stream closed successfully")
            except Exception as e:
                print(f"⚠️ AudioRecorder: Stream cleanup error: {e}")
            finally:
                self.stream = None
        
        # Clean up PulseAudio process
        if self.pulseaudio_process:
            try:
                print("🔵 AudioRecorder: Terminating PulseAudio process...")
                self.pulseaudio_process.terminate()
                self.pulseaudio_process.wait(timeout=2.0)
                print("✅ AudioRecorder: PulseAudio process terminated")
            except Exception as e:
                print(f"⚠️ AudioRecorder: PulseAudio cleanup error: {e}")
                try:
                    self.pulseaudio_process.kill()
                    print("🔵 AudioRecorder: PulseAudio process killed")
                except:
                    pass
            finally:
                self.pulseaudio_process = None
    
    def stop_recording(self) -> Optional[np.ndarray]:
        """Stop recording and return the recorded audio data"""
        print(f"🛑 AudioRecorder: stop_recording called, is_recording={self.is_recording}")
        
        if not self.is_recording:
            print("⚠️ AudioRecorder: Not recording, nothing to stop")
            return None
            
        print("🛑 AudioRecorder: Setting is_recording=False")
        self.is_recording = False
        
        # Wait a short time for the recording loop to exit
        if self.recording_thread:
            print("🛑 AudioRecorder: Waiting for recording thread to finish...")
            self.recording_thread.join(timeout=1.0)  # Wait up to 1 second
            
            if self.recording_thread.is_alive():
                print("⚠️ AudioRecorder: Thread still alive after timeout, forcing cleanup")
                self.force_cleanup()
            else:
                print("✅ AudioRecorder: Recording thread finished successfully")
        
        # Collect any audio chunks that might be available
        print(f"🛑 AudioRecorder: Collecting audio chunks from queue (size: {self.audio_queue.qsize()})")
        audio_chunks = []
        while not self.audio_queue.empty():
            try:
                chunk = self.audio_queue.get_nowait()
                audio_chunks.append(chunk)
            except queue.Empty:
                break
        
        print(f"🛑 AudioRecorder: Collected {len(audio_chunks)} audio chunks")
        
        if not audio_chunks:
            print("❌ AudioRecorder: No audio chunks collected")
            return None
        
        # Concatenate all chunks into a single array
        audio_data = np.concatenate(audio_chunks, axis=0)
        
        # If stereo, convert to mono by averaging channels
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        print(f"✅ AudioRecorder: Final audio data: {len(audio_data)} samples, max amplitude: {np.max(np.abs(audio_data)):.4f}")
        return audio_data
    
    def get_available_devices(self):
        """Get list of available audio input devices"""
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
        
        return input_devices
    
    def set_device(self, device_id: int):
        """Set the audio input device by ID"""
        try:
            sd.default.device[0] = device_id  # Set input device
            return True
        except Exception as e:
            print(f"Error setting device: {e}")
            return False
    
    def force_cleanup(self):
        """Force cleanup of all audio resources - call this to ensure microphone is released"""
        print("🧹 AudioRecorder: Force cleanup called")
        
        # Stop recording if active
        if self.is_recording:
            self.is_recording = False
        
        # Clean up the current stream
        self._cleanup_stream()
        
        # Force stop all sounddevice operations
        try:
            print("🧹 AudioRecorder: Force stopping all sounddevice streams...")
            sd.stop()  # Stop ALL sounddevice streams
            sd.default.reset()  # Reset sounddevice state
            print("✅ AudioRecorder: Force cleanup completed")
        except Exception as e:
            print(f"⚠️ AudioRecorder: Force cleanup error: {e}")
        
        # Force garbage collection
        gc.collect()
        
        # Give a moment for cleanup to take effect
        time.sleep(0.1)
        
        print("🧹 AudioRecorder: All cleanup operations completed")
    
    def _wait_for_bluetooth_microphone_if_needed(self):
        """Check if we need to use PulseAudio directly for Bluetooth microphones"""
        try:
            import subprocess
            
            # Get current default source
            result = subprocess.run(['pactl', 'get-default-source'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                current_source = result.stdout.strip()
                
                # Check if it's a Bluetooth input device
                if 'bluez_input' in current_source:
                    print(f"🔵 Bluetooth microphone detected: {current_source}")
                    print(f"🔵 Will use PulseAudio directly for Bluetooth recording")
                    
                    # Set flag to use PulseAudio instead of sounddevice
                    self.use_pulseaudio = True
                    self.pulseaudio_source = current_source
                    
                    print(f"🔵 Bluetooth microphone setup complete - using PulseAudio")
                    return
                    
            # Not a Bluetooth microphone, use sounddevice normally
            self.use_pulseaudio = False
            self.pulseaudio_source = None
                    
        except Exception as e:
            # Don't fail if we can't detect - just continue with sounddevice
            print(f"🔵 Could not detect microphone type: {e}")
            self.use_pulseaudio = False
            self.pulseaudio_source = None