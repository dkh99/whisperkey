# WhisperKey Android Keyboard Conversion Plan

## Executive Summary

This document outlines the complete conversion of WhisperKey from a Linux desktop voice transcription application to an Android keyboard (Input Method Editor - IME) with equivalent functionality. The conversion will replicate WhisperKey's core features: voice recording, transcription, LLM processing, and seamless text input within the Android ecosystem.

## Current WhisperKey Architecture Analysis

### Core Components (Linux)
| Component | Current Implementation | Purpose |
|-----------|----------------------|---------|
| **Audio Recording** | sounddevice + PortAudio | 16kHz mono audio capture |
| **Speech Recognition** | faster-whisper (local) | Offline speech-to-text |
| **Global Hotkeys** | pynput | System-wide key detection |
| **Text Input** | Clipboard + window focus | Paste transcribed text |
| **UI Framework** | PyQt6 + System Tray | User interface |
| **Background Service** | Python daemon | Always-running service |
| **History Storage** | SQLite | Transcription history |
| **LLM Processing** | OpenAI API | Text post-processing |
| **Window Management** | DBus/ydotool | Focus management |

### Key Features to Replicate
- **Voice Activation**: Global hotkeys (Win+Alt, Alt+Space)
- **Multiple Recording Modes**: Hold-to-talk, hands-free mode
- **Real-time Feedback**: Audio feedback, visual indicators
- **Transcription History**: Recent transcriptions with quick access
- **LLM Enhancement**: Optional text cleanup/improvement
- **Seamless Integration**: Direct text input without interrupting workflow

## Android Architecture Design

### 1. Android Input Method Editor (IME) Framework

**Primary Component**: Custom Keyboard Service extending `InputMethodService`

```
WhisperKeyKeyboard extends InputMethodService
├── Voice Input Button/UI
├── Traditional Keyboard Layout (fallback)
├── Voice Recording Service
├── Transcription Engine
├── History Management
└── Settings Interface
```

### 2. Core Android Components

#### A. InputMethodService (Main Keyboard)
- **Purpose**: Core keyboard service that Android apps communicate with
- **Responsibilities**:
  - Handle voice input requests
  - Manage keyboard UI
  - Process transcribed text
  - Interface with target applications via `InputConnection`

#### B. Voice Recording Service
- **Purpose**: Background service for audio capture
- **Implementation**: `AudioRecord` + `MediaRecorder`
- **Features**:
  - 16kHz mono recording
  - Real-time audio buffer management
  - Automatic noise detection
  - Recording state management

#### C. Transcription Engine
- **Purpose**: Convert audio to text
- **Options**:
  1. **Android Speech Recognition** (SpeechRecognizer)
  2. **Google Cloud Speech API** (cloud-based)
  3. **Whisper.cpp Android port** (local)
  4. **Hybrid approach** (local + cloud fallback)

#### D. UI Components
- **Keyboard Layout**: Custom view with voice input button
- **Voice Indicator**: Real-time recording feedback
- **History Panel**: Recent transcriptions
- **Settings Activity**: Configuration interface

## Technical Implementation Details

### 1. Audio Recording System

#### Current (Linux)
```python
import sounddevice as sd
import numpy as np

class AudioRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        # Uses PortAudio backend
```

#### Android Implementation
```java
public class VoiceRecorder {
    private AudioRecord audioRecord;
    private static final int SAMPLE_RATE = 16000;
    private static final int CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO;
    private static final int AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT;
    
    public void startRecording() {
        int bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT);
        audioRecord = new AudioRecord(MediaRecorder.AudioSource.MIC, 
                                    SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT, bufferSize);
        audioRecord.startRecording();
        // Start audio capture thread
    }
}
```

### 2. Speech Recognition Integration

#### Option A: Android SpeechRecognizer
```java
public class AndroidSpeechRecognizer {
    private SpeechRecognizer speechRecognizer;
    
    public void initialize() {
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context);
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override
            public void onResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                // Process transcription results
            }
        });
    }
}
```

#### Option B: Google Cloud Speech API
```java
public class CloudSpeechRecognizer {
    private SpeechClient speechClient;
    
    public void transcribe(byte[] audioData) {
        RecognitionAudio audio = RecognitionAudio.newBuilder()
            .setContent(ByteString.copyFrom(audioData))
            .build();
        
        RecognitionConfig config = RecognitionConfig.newBuilder()
            .setEncoding(RecognitionConfig.AudioEncoding.LINEAR16)
            .setSampleRateHertz(16000)
            .setLanguageCode("en-US")
            .build();
        
        RecognizeResponse response = speechClient.recognize(config, audio);
        // Process results
    }
}
```

### 3. Input Method Integration

#### Current (Linux)
```python
# Uses clipboard + window focus
def _paste_text_with_method(self, text: str, paste_method: str):
    clipboard.setText(text)
    window_manager.paste_to_previous_window()
```

#### Android Implementation
```java
public class WhisperKeyIME extends InputMethodService {
    @Override
    public View onCreateInputView() {
        return createKeyboardView();
    }
    
    private void insertTranscribedText(String text) {
        InputConnection ic = getCurrentInputConnection();
        if (ic != null) {
            ic.commitText(text, 1);
        }
    }
    
    private void handleVoiceInput() {
        // Start voice recording
        voiceRecorder.startRecording();
        showVoiceRecordingUI();
    }
}
```

### 4. UI Design and User Experience

#### Keyboard Layout
```xml
<!-- keyboard_layout.xml -->
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:orientation="vertical"
    android:layout_width="match_parent"
    android:layout_height="wrap_content">
    
    <!-- Voice Input Button -->
    <Button
        android:id="@+id/voice_button"
        android:layout_width="match_parent"
        android:layout_height="60dp"
        android:text="🎤 Hold to Speak"
        android:background="@drawable/voice_button_background" />
    
    <!-- Traditional Keyboard (Optional) -->
    <include layout="@layout/traditional_keyboard" />
    
    <!-- History Panel -->
    <RecyclerView
        android:id="@+id/history_recycler"
        android:layout_width="match_parent"
        android:layout_height="120dp"
        android:visibility="gone" />
</LinearLayout>
```

#### Voice Recording States
```java
public enum RecordingState {
    IDLE,           // Not recording
    RECORDING,      // Active recording
    PROCESSING,     // Transcribing audio
    READY          // Ready to paste
}
```

### 5. Background Service Architecture

#### Service Hierarchy
```
WhisperKeyKeyboardService (InputMethodService)
├── VoiceRecordingService (Background Service)
├── TranscriptionService (IntentService)
├── HistoryService (Data Management)
└── LLMProcessingService (API Integration)
```

#### Background Service Implementation
```java
public class VoiceRecordingService extends Service {
    private final IBinder binder = new VoiceRecordingBinder();
    
    public class VoiceRecordingBinder extends Binder {
        VoiceRecordingService getService() {
            return VoiceRecordingService.this;
        }
    }
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        // Handle voice recording requests
        return START_STICKY; // Keep service running
    }
}
```

## Development Phases

### Phase 1: Foundation (Weeks 1-2)
#### Goals
- Set up Android project structure
- Implement basic InputMethodService
- Create minimal keyboard UI
- Establish audio recording capability

#### Deliverables
- Basic keyboard that can be installed and activated
- Simple voice recording functionality
- Project structure with proper architecture

#### Key Tasks
1. Create Android Studio project
2. Implement `WhisperKeyIME` extending `InputMethodService`
3. Add audio recording permissions
4. Implement `VoiceRecorder` class
5. Create basic keyboard layout XML
6. Test on emulator and device

### Phase 2: Core Voice Functionality (Weeks 3-4)
#### Goals
- Implement speech recognition
- Add voice activation UI
- Handle recording states
- Basic transcription workflow

#### Deliverables
- Working voice-to-text input
- Recording state management
- Visual feedback during recording

#### Key Tasks
1. Integrate Android SpeechRecognizer
2. Implement recording state machine
3. Add visual indicators (recording, processing)
4. Handle transcription results
5. Implement text insertion via InputConnection
6. Add error handling and permissions

### Phase 3: Advanced Features (Weeks 5-6)
#### Goals
- Multiple recording modes
- Transcription history
- LLM integration
- Settings interface

#### Deliverables
- Hold-to-talk and hands-free modes
- History panel with recent transcriptions
- Optional LLM text enhancement
- User settings

#### Key Tasks
1. Implement recording modes (hold-to-talk, hands-free)
2. Create history storage with SQLite
3. Add history UI panel
4. Integrate OpenAI API for LLM processing
5. Create settings activity
6. Add keyboard themes and customization

### Phase 4: Polish and Optimization (Weeks 7-8)
#### Goals
- Performance optimization
- UI/UX improvements
- Testing and bug fixes
- Documentation

#### Deliverables
- Optimized, production-ready application
- Comprehensive testing
- User documentation
- Play Store preparation

#### Key Tasks
1. Performance profiling and optimization
2. UI/UX refinements
3. Comprehensive testing (unit, integration, device)
4. Battery usage optimization
5. Memory management improvements
6. Create user documentation

## Technical Challenges and Solutions

### 1. Audio Recording in Background
**Challenge**: Android restricts background audio recording
**Solution**: Use foreground service with notification for active recording

### 2. Speech Recognition Accuracy
**Challenge**: Matching faster-whisper quality on Android
**Solution**: Hybrid approach - local processing with cloud fallback

### 3. Real-time Processing
**Challenge**: Low latency transcription
**Solution**: Streaming recognition with partial results

### 4. Battery Optimization
**Challenge**: Continuous voice monitoring drains battery
**Solution**: Intelligent activation, doze mode compatibility

### 5. Permissions and Privacy
**Challenge**: Microphone access and user trust
**Solution**: Clear privacy policy, minimal permissions, local processing preference

## Architecture Diagrams

### High-Level Architecture
```
┌─────────────────────┐
│   Android Apps      │
│  (Text Input)       │
└─────────┬───────────┘
          │ InputConnection
┌─────────▼───────────┐
│  WhisperKey Keyboard   │
│  (InputMethodService)│
├─────────────────────┤
│ • Voice UI          │
│ • Recording States  │
│ • Text Processing   │
│ • History Management│
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  Background Services │
├─────────────────────┤
│ • Voice Recording   │
│ • Speech Recognition│
│ • LLM Processing    │
│ • History Storage   │
└─────────────────────┘
```

### Component Interaction Flow
```
User Input → Voice Button → Recording Service → Audio Capture
                                    ↓
Transcription ← Speech Recognition ← Audio Processing
      ↓
LLM Processing (Optional) → Text Enhancement
      ↓
History Storage ← Final Text → InputConnection → Target App
```

## Dependencies and Libraries

### Core Android Dependencies
```gradle
dependencies {
    implementation 'androidx.core:core-ktx:1.9.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'androidx.lifecycle:lifecycle-runtime-ktx:2.6.2'
    implementation 'androidx.recyclerview:recyclerview:1.3.1'
    
    // Audio and Speech
    implementation 'androidx.media:media:1.6.0'
    
    // Database
    implementation 'androidx.room:room-runtime:2.4.3'
    implementation 'androidx.room:room-ktx:2.4.3'
    kapt 'androidx.room:room-compiler:2.4.3'
    
    // Network (for LLM API)
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'com.squareup.okhttp3:logging-interceptor:4.10.0'
    
    // Testing
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
}
```

### Optional Dependencies
```gradle
// For advanced speech recognition
implementation 'com.google.cloud:google-cloud-speech:2.16.0'

// For local Whisper processing
implementation 'com.github.whispercpp:whisper-android:1.0.0'

// For UI enhancements
implementation 'com.google.android.material:material:1.9.0'
```

## Permissions Requirements

### Manifest Permissions
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.WAKE_LOCK" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
```

### Runtime Permissions
- **RECORD_AUDIO**: Essential for voice recording
- **INTERNET**: Required for LLM API calls
- **FOREGROUND_SERVICE**: For background recording service

## Security and Privacy Considerations

### Data Privacy
- **Local Processing**: Prioritize on-device speech recognition
- **Encrypted Storage**: Secure transcription history
- **Minimal Data**: Only store necessary information
- **User Control**: Clear data deletion options

### Security Measures
- **Permission Auditing**: Regular permission reviews
- **Secure API**: Encrypted communication with LLM services
- **Input Validation**: Sanitize all user inputs
- **Background Monitoring**: Prevent unauthorized access

## Testing Strategy

### Unit Testing
- Audio recording components
- Speech recognition integration
- Text processing logic
- History management

### Integration Testing
- Keyboard service integration
- Background service communication
- API integration testing
- Database operations

### Device Testing
- Multiple Android versions (API 23+)
- Various device manufacturers
- Different screen sizes and orientations
- Performance on low-end devices

### User Testing
- Voice recognition accuracy
- User interface usability
- Battery usage impact
- Real-world usage scenarios

## Performance Optimization

### Audio Processing
- **Efficient Buffering**: Minimize memory allocation
- **Thread Management**: Separate audio capture thread
- **Compression**: Use appropriate audio formats
- **Batch Processing**: Process audio in optimized chunks

### Memory Management
- **Object Pooling**: Reuse audio buffers
- **Garbage Collection**: Minimize object creation
- **Weak References**: Prevent memory leaks
- **Background Cleanup**: Release resources when inactive

### Battery Optimization
- **Doze Mode**: Handle Android power management
- **Intelligent Activation**: Only activate when needed
- **CPU Optimization**: Minimize background processing
- **Network Efficiency**: Batch API calls

## Deployment and Distribution

### Build Configuration
```gradle
android {
    compileSdk 34
    
    defaultConfig {
        applicationId "com.WhisperKey.keyboard"
        minSdk 23
        targetSdk 34
        versionCode 1
        versionName "1.0.0"
    }
    
    buildTypes {
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}
```

### Play Store Preparation
- **App Signing**: Set up Play App Signing
- **Store Listing**: Screenshots, descriptions, keywords
- **Privacy Policy**: Comprehensive privacy documentation
- **Testing Track**: Beta testing with select users

## Migration from Linux Version

### Data Migration
- **History Export**: Export transcription history
- **Settings Transfer**: Migrate user preferences
- **API Keys**: Secure transfer of authentication

### Feature Parity
- **Core Features**: Ensure all essential features work
- **Performance**: Match or exceed Linux performance
- **User Experience**: Maintain familiar workflow

## Future Enhancements

### Advanced Features
- **Multi-language Support**: Dynamic language switching
- **Custom Vocabularies**: User-defined terminology
- **Voice Commands**: System control via voice
- **Offline Mode**: Complete offline functionality

### Platform Expansion
- **iOS Version**: Swift/Objective-C implementation
- **Web Version**: WebRTC-based solution
- **Cross-platform**: React Native or Flutter

## Success Metrics

### Technical Metrics
- **Transcription Accuracy**: >95% for clear speech
- **Response Time**: <2 seconds end-to-end
- **Battery Usage**: <5% per hour of active use
- **Memory Usage**: <50MB average

### User Metrics
- **Adoption Rate**: Downloads and active users
- **User Retention**: 30-day retention rate
- **User Satisfaction**: App store ratings
- **Usage Patterns**: Feature usage analytics

## Conclusion

This comprehensive plan outlines the complete conversion of WhisperKey from a Linux desktop application to a fully-featured Android keyboard. The phased approach ensures systematic development while maintaining the core functionality that makes WhisperKey valuable to users. The Android version will provide the same seamless voice-to-text experience within the mobile ecosystem, potentially reaching a much larger user base.

The estimated development timeline is 8 weeks for a complete, production-ready application, with the flexibility to extend features based on user feedback and market requirements. 