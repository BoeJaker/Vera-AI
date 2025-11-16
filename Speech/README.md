# Speech Integration

## Overview

The **Speech** module provides multimodal voice interaction capabilities for Vera, including text-to-speech (TTS) synthesis and speech-to-text (STT) recognition. This enables natural, hands-free communication with Vera through voice commands and audio responses.

## Purpose

Speech integration enables:
- **Voice input** - Speak to Vera instead of typing
- **Voice output** - Hear Vera's responses spoken aloud
- **Hands-free operation** - Use Vera without keyboard/mouse
- **Accessibility** - Assist users with visual or mobility impairments
- **Natural interaction** - More human-like communication

## Architecture Role

```
User Speech → STT (Faster-Whisper) → Text Query
                                         ↓
                                    Vera Processing
                                         ↓
Text Response → TTS (VITS/Voice Model) → Audio Output → Speakers
```

Speech acts as an alternative I/O layer, converting between audio and text for Vera's core processing pipeline.

## Key Components

### Speech-to-Text (STT)
**Technology:** Faster-Whisper (optimized Whisper implementation)

Converts spoken audio into text:
- Real-time audio capture from microphone
- Noise filtering and preprocessing
- High-accuracy transcription
- Multiple language support
- Punctuation and capitalization

### Text-to-Speech (TTS)
**Technology:** VITS (Variational Inference with adversarial learning for TTS)

Converts text responses into natural speech:
- Multiple voice options (VCTK dataset)
- Natural prosody and intonation
- Adjustable speed and pitch
- Low latency for real-time interaction

## Key Files

| File | Purpose |
|------|---------|
| `speech.py` | Main speech integration module (STT + TTS) |

## Technologies

- **Faster-Whisper** - High-performance speech-to-text
- **TTS Library** - Text-to-speech synthesis
- **sounddevice** - Audio input/output capture
- **soundfile** - Audio file I/O (WAV format)
- **VCTK VITS** - Voice models for natural speech
- **numpy** - Audio signal processing

## Installation

### System Dependencies
```bash
# Install audio libraries (Linux)
sudo apt-get install portaudio19-dev python3-pyaudio

# Install FFmpeg (required for audio processing)
sudo apt-get install ffmpeg
```

### Python Dependencies
```bash
pip install faster-whisper
pip install TTS
pip install sounddevice soundfile
pip install numpy
```

### Download Voice Models
Voice models are automatically downloaded on first use. Manual download:
```bash
python3 -c "from TTS.api import TTS; TTS('tts_models/en/vctk/vits').save('/path/to/models')"
```

## Usage

### Basic Voice Interaction
```python
from Speech.speech import VoiceCommunication

voice = VoiceCommunication()

# Listen for voice input
print("Speak now...")
user_text = voice.listen()
print(f"You said: {user_text}")

# Generate voice response
response_text = "Hello! How can I help you today?"
voice.speak(response_text)
```

### Integration with Vera
```python
from Speech.speech import VoiceCommunication
from vera import Vera

voice = VoiceCommunication()
vera = Vera()

# Voice-based chat loop
while True:
    # Listen for user input
    user_query = voice.listen()

    if user_query.lower() in ["exit", "quit", "goodbye"]:
        voice.speak("Goodbye!")
        break

    # Process with Vera
    response = vera.process_query(user_query)

    # Speak response
    voice.speak(response)
```

### File-Based TTS
```python
# Convert text to audio file
voice.text_to_file(
    text="This is a test of the text-to-speech system.",
    output_path="output.wav"
)
```

### Voice Selection
```python
# Initialize with specific voice
voice = VoiceCommunication(
    voice_model="tts_models/en/vctk/vits",
    speaker_id="p225"  # Female British accent
)

# Available speakers: p225, p226, p227, etc.
# Each has different characteristics (gender, accent, age)
```

## Configuration

### Speech Recognition Settings
```python
voice = VoiceCommunication(
    # STT settings
    model_size="base",  # tiny, base, small, medium, large
    language="en",
    device="cpu",  # or "cuda" for GPU acceleration
    compute_type="int8",  # int8, float16, float32

    # Audio capture
    sample_rate=16000,
    channels=1,
    chunk_duration=5.0  # seconds
)
```

### TTS Settings
```python
voice = VoiceCommunication(
    # TTS settings
    voice_model="tts_models/en/vctk/vits",
    speaker_id="p225",
    speed=1.0,  # 0.5 to 2.0
    pitch=1.0,  # 0.5 to 2.0

    # Audio output
    output_device=None,  # None = default, or device index
    volume=1.0  # 0.0 to 1.0
)
```

### Faster-Whisper Model Sizes

| Model | Parameters | VRAM | Relative Speed | Accuracy |
|-------|-----------|------|----------------|----------|
| `tiny` | 39M | ~1GB | Fastest | Good |
| `base` | 74M | ~1GB | Very Fast | Better |
| `small` | 244M | ~2GB | Fast | Great |
| `medium` | 769M | ~5GB | Moderate | Excellent |
| `large` | 1550M | ~10GB | Slow | Best |

**Recommendation:** Use `base` or `small` for real-time interaction on CPU.

## Voice Models

### Available VCTK Speakers

```python
# List available speakers
from TTS.api import TTS
tts = TTS("tts_models/en/vctk/vits")
print(tts.speakers)

# Example speakers:
# p225 - Female, English (Southern England)
# p226 - Male, English (Southern England)
# p227 - Male, English (Southern England)
# p228 - Female, English (Southern England)
# ... (110 speakers total)
```

### Voice Characteristics
- **Gender:** Male and female options
- **Accents:** Various English accents (British, American, Irish, etc.)
- **Age:** Young adult to elderly
- **Tone:** Professional, casual, energetic

## Advanced Features

### Voice Activity Detection (VAD)
```python
# Automatic speech detection
voice = VoiceCommunication(enable_vad=True)

# Will automatically start/stop recording based on speech
user_text = voice.listen_with_vad(
    silence_duration=2.0  # Stop after 2s of silence
)
```

### Real-Time Streaming
```python
# Stream TTS output while generating
for audio_chunk in voice.speak_streaming(long_text):
    # Audio plays while text is being synthesized
    pass
```

### Noise Reduction
```python
voice = VoiceCommunication(
    enable_noise_reduction=True,
    noise_gate_threshold=-40  # dB
)
```

### Multi-Language Support
```python
# Speech recognition in different languages
voice_spanish = VoiceCommunication(
    language="es",  # Spanish
    voice_model="tts_models/es/css10/vits"
)

user_text = voice_spanish.listen()
voice_spanish.speak("Hola, ¿cómo estás?")
```

## Performance Optimization

### GPU Acceleration
```python
# Use GPU for faster STT
voice = VoiceCommunication(
    device="cuda",
    compute_type="float16"  # Faster on GPU
)
```

### Model Caching
Models are cached after first download:
```bash
# Cache location (Linux)
~/.cache/huggingface/hub/
~/.local/share/tts/

# Check cached models
ls ~/.cache/huggingface/hub/
```

### Corruption Recovery
If model files become corrupted, automatic redownload occurs:
```python
# Force model redownload
voice = VoiceCommunication(force_download=True)
```

## Integration Examples

### Voice-Activated Assistant
```python
import asyncio
from Speech.speech import VoiceCommunication
from vera import Vera

async def voice_assistant():
    voice = VoiceCommunication()
    vera = Vera()

    voice.speak("Voice assistant ready. How can I help?")

    while True:
        # Listen for wake word
        audio = voice.listen_continuous()

        if "vera" in audio.lower():
            voice.speak("Yes?")
            query = voice.listen()

            if query:
                response = await vera.process_query_async(query)
                voice.speak(response)

asyncio.run(voice_assistant())
```

### Dictation Mode
```python
# Dictate text without processing
voice = VoiceCommunication()

voice.speak("Dictation mode activated. Speak your text.")
dictated_text = voice.listen_long_form(max_duration=300)

# Save to file
with open("dictation.txt", "w") as f:
    f.write(dictated_text)

voice.speak("Dictation saved.")
```

### Phone Integration
```python
# Handle phone calls with Vera
def handle_call(call_audio_stream):
    voice = VoiceCommunication(
        input_stream=call_audio_stream,
        output_stream=call_audio_stream
    )

    voice.speak("Hello, this is Vera. How can I assist you?")

    while call_active:
        user_speech = voice.listen()
        response = vera.process_query(user_speech)
        voice.speak(response)
```

## Known Issues

### TTS Pacing
**Issue:** On slower hardware, TTS may speak faster than the LLM can generate responses, causing gaps or stuttering.

**Solutions:**
- Use faster LLM models for response generation
- Implement response buffering
- Adjust TTS speed: `voice.set_speed(0.8)`

### Latency
**Issue:** Noticeable delay between speech input and response.

**Solutions:**
- Use smaller Whisper models (`tiny` or `base`)
- Enable GPU acceleration
- Stream TTS output incrementally

### Audio Device Conflicts
**Issue:** Multiple applications competing for microphone/speakers.

**Solutions:**
```python
# List available audio devices
import sounddevice as sd
print(sd.query_devices())

# Select specific device
voice = VoiceCommunication(
    input_device=1,  # Microphone device index
    output_device=2  # Speaker device index
)
```

## Troubleshooting

### No Audio Input Detected
```bash
# Test microphone
python3 -c "
import sounddevice as sd
import numpy as np
duration = 5
print('Recording...')
audio = sd.rec(int(duration * 16000), samplerate=16000, channels=1)
sd.wait()
print('Playback...')
sd.play(audio, 16000)
sd.wait()
"
```

### STT Not Recognizing Speech
```python
# Increase sensitivity, reduce noise gate
voice = VoiceCommunication(
    noise_gate_threshold=-50,  # Lower threshold
    silence_threshold=0.02  # More sensitive
)
```

### TTS Voice Sounds Robotic
```python
# Try different speaker or model
voice = VoiceCommunication(
    speaker_id="p226",  # Different voice
    speed=0.9  # Slightly slower
)
```

### Model Download Fails
```bash
# Manual model download
huggingface-cli download openai/whisper-base

# Check internet connection and firewall
ping huggingface.co
```

## Accessibility Features

### Vision Impairment Support
- Full voice-based interaction without screen
- Audio feedback for all actions
- Descriptive TTS for visual elements

### Mobility Impairment Support
- Hands-free operation
- Voice commands for navigation
- Continuous listening mode

### Hearing Impairment Support
- Visual transcription display alongside TTS
- Adjustable volume and speed
- Text-only mode as fallback

## Future Enhancements (Planned)

- **Emotion Detection** - Analyze user emotion from voice
- **Voice Cloning** - Custom voice creation
- **Whisper TTS** - Integrated Whisper-based TTS
- **Multi-Speaker Support** - Distinguish multiple speakers
- **Streaming Recognition** - Real-time STT as user speaks
- **Voice Biometrics** - User identification via voice

## Related Documentation

- [Multimodal I/O Roadmap](../README.md#roadmap)
- [User Interface](../ChatUI/)
- [Vera Assistant Docs](../Vera%20Assistant%20Docs/)

## Contributing

To extend Speech capabilities:
1. Add new TTS models or voices
2. Implement emotion detection
3. Add voice cloning features
4. Optimize latency and quality
5. Add multi-language support

---

**Related Components:**
- [ChatUI](../ChatUI/) - Web interface with optional voice
- [Agents](../Agents/) - Cognitive units processing voice input
- [Vera Core](../vera.py) - Main processing pipeline
