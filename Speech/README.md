# Speech Directory

## Table of Contents
- [Overview](#overview)
- [Files](#files)
- [Speech-to-Text](#speech-to-text)
- [Text-to-Speech](#text-to-speech)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Model Management](#model-management)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Speech directory implements Vera's voice interaction capabilities - providing speech-to-text (STT) transcription using Whisper and text-to-speech (TTS) synthesis using Coqui TTS, enabling natural voice-based interaction with the AI agent.

**Purpose:** Voice input/output for Vera
**Technology:** faster-whisper (STT) + Coqui TTS (TTS)
**Total Files:** 2 Python modules
**Status:** ✅ Production
**Model Size:** ~3GB (Whisper large-v2)

### Key Features

- **Speech-to-Text (STT)**: Whisper-based audio transcription
- **Text-to-Speech (TTS)**: Coqui TTS voice synthesis
- **Audio Recording**: Microphone input via sounddevice
- **Audio Playback**: System audio output
- **Model Caching**: Local model storage for offline use
- **Error Recovery**: Automatic cache repair on corruption
- **Multi-Voice Support**: Multiple TTS voice options
- **Real-Time Processing**: Low-latency audio processing

---

## Files

### `speech.py` - Main Speech Module

**Purpose:** Speech-to-text and text-to-speech implementation

**Size:** ~60 lines
**Dependencies:**
- faster-whisper (STT)
- Coqui TTS (TTS)
- sounddevice (audio I/O)
- soundfile (audio file handling)

**Key Components:**

```python
from faster_whisper import WhisperModel
from TTS.api import TTS
import sounddevice as sd
import soundfile as sf
import tempfile
import os
```

---

## Speech-to-Text

### Whisper Model Initialization

```python
model_size = "large-v2"
cache_dir = Path.home() / ".cache" / "whisper"

def load_whisper_model(model_size, cache_dir):
    """
    Load Whisper model with automatic cache repair

    Args:
        model_size: Model size (tiny, base, small, medium, large, large-v2)
        cache_dir: Local cache directory path

    Returns:
        WhisperModel instance

    Raises:
        Exception: If model loading fails after cache cleanup
    """
    try:
        print(f"[INFO] Loading Whisper model: {model_size}")
        stt_model = WhisperModel(model_size, download_root=str(cache_dir))
        return stt_model

    except FileNotFoundError as e:
        print(f"[WARNING] Whisper model cache seems corrupted: {e}")
        print("[INFO] Deleting cache and retrying...")
        shutil.rmtree(cache_dir, ignore_errors=True)

        try:
            stt_model = WhisperModel(model_size, download_root=str(cache_dir))
            return stt_model
        except Exception as e2:
            print("[ERROR] Failed to load Whisper model even after cache reset.")
            raise e2

# Initialize STT model
stt_model = load_whisper_model(model_size, cache_dir)
```

### Available Whisper Models

| Model | Size | Speed | Accuracy | VRAM Required |
|-------|------|-------|----------|---------------|
| tiny | 39M | Fastest | Good | ~1GB |
| base | 74M | Very Fast | Better | ~1GB |
| small | 244M | Fast | Very Good | ~2GB |
| medium | 769M | Medium | Excellent | ~5GB |
| large | 1550M | Slow | Best | ~10GB |
| large-v2 | 1550M | Slow | Best | ~10GB |

### Listen Function

```python
def listen():
    """
    Record audio from microphone and transcribe

    Process:
        1. Record 5 seconds of audio from default microphone
        2. Save to temporary WAV file
        3. Transcribe with Whisper
        4. Clean up temporary file
        5. Return transcription text

    Returns:
        str: Transcribed text

    Example:
        text = listen()
        print(f"You said: {text}")
    """
    print("[Listening...]")

    # Recording parameters
    duration = 5  # seconds
    samplerate = 16000  # Hz (Whisper expects 16kHz)

    # Record audio
    recording = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32"
    )
    sd.wait()  # Wait for recording to complete

    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        sf.write(tmp_wav.name, recording, samplerate)

        # Transcribe
        result = stt_model.transcribe(tmp_wav.name)

        # Cleanup
        os.unlink(tmp_wav.name)

        return result["text"]
```

### Transcription with Options

```python
def transcribe_audio(audio_file, language="en", task="transcribe"):
    """
    Transcribe audio file with advanced options

    Args:
        audio_file: Path to audio file
        language: Source language code (en, es, fr, etc.)
        task: "transcribe" or "translate" (translate to English)

    Returns:
        dict: Transcription results with segments and metadata

    Example:
        result = transcribe_audio("recording.wav", language="en")
        print(result["text"])
        for segment in result["segments"]:
            print(f"[{segment['start']:.2f}s] {segment['text']}")
    """
    segments, info = stt_model.transcribe(
        audio_file,
        language=language,
        task=task,
        beam_size=5,
        best_of=5,
        temperature=0.0
    )

    # Compile results
    full_text = ""
    segment_list = []

    for segment in segments:
        full_text += segment.text + " "
        segment_list.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        })

    return {
        "text": full_text.strip(),
        "segments": segment_list,
        "language": info.language,
        "duration": info.duration
    }
```

---

## Text-to-Speech

### TTS Model Initialization

```python
# Load TTS model
# Using VCTK (multi-speaker English)
tts_model = TTS(
    model_name="tts_models/en/vctk/vits",
    progress_bar=False,
    gpu=False  # Set to True if GPU available
)

print("[INFO] TTS model loaded")
```

### Available TTS Models

**English Models:**
- `tts_models/en/vctk/vits` - Multi-speaker (109 voices)
- `tts_models/en/ljspeech/tacotron2-DDC` - Single speaker, high quality
- `tts_models/en/ljspeech/glow-tts` - Fast, good quality
- `tts_models/en/jenny/jenny` - Natural female voice

**Multi-lingual Models:**
- `tts_models/multilingual/multi-dataset/your_tts` - 13 languages
- `tts_models/multilingual/multi-dataset/xtts_v2` - 16 languages

### Speak Function

```python
def speak(text):
    """
    Convert text to speech and play audio

    Process:
        1. Generate speech audio from text
        2. Save to temporary WAV file
        3. Load audio data
        4. Play through system audio
        5. Wait for playback to complete
        6. Clean up temporary file

    Args:
        text: Text to speak

    Example:
        speak("Hello, I am Vera!")
    """
    print(f"[Speaking] {text}")

    # Generate speech
    wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    tts_model.tts_to_file(text=text, file_path=wav_path)

    # Load and play
    data, fs = sf.read(wav_path, dtype='float32')
    sd.play(data, fs)
    sd.wait()  # Wait for playback to complete

    # Cleanup
    os.unlink(wav_path)
```

### Advanced TTS Options

```python
def speak_with_voice(text, speaker_id="p225", speed=1.0):
    """
    Speak with specific voice and speed

    Args:
        text: Text to speak
        speaker_id: VCTK speaker ID (p225-p376)
        speed: Speech speed multiplier (0.5-2.0)

    Example:
        speak_with_voice("Hello!", speaker_id="p230", speed=1.2)
    """
    wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    tts_model.tts_to_file(
        text=text,
        speaker=speaker_id,
        file_path=wav_path
    )

    # Load audio
    data, fs = sf.read(wav_path, dtype='float32')

    # Adjust speed (by resampling)
    adjusted_fs = int(fs * speed)

    # Play
    sd.play(data, adjusted_fs)
    sd.wait()

    os.unlink(wav_path)

def list_available_voices():
    """List all available TTS voices"""
    if hasattr(tts_model, 'speakers'):
        return tts_model.speakers
    return []

# Usage
voices = list_available_voices()
print(f"Available voices: {voices[:5]}...")  # Show first 5
```

---

## Usage Examples

### Voice Interaction Loop

```python
def voice_chat_loop():
    """
    Interactive voice chat with Vera

    Loop:
        1. Listen for user speech
        2. Transcribe to text
        3. Send to Vera
        4. Speak response
    """
    from vera import Vera

    vera = Vera()

    print("Voice chat started. Say 'exit' to quit.")

    while True:
        try:
            # Listen
            user_input = listen()
            print(f"You: {user_input}")

            # Check for exit
            if "exit" in user_input.lower():
                speak("Goodbye!")
                break

            # Get response from Vera
            response = vera.run(user_input)
            print(f"Vera: {response}")

            # Speak response
            speak(response)

        except KeyboardInterrupt:
            speak("Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

# Run voice chat
voice_chat_loop()
```

### Transcribe Audio File

```python
def transcribe_file(audio_path):
    """Transcribe an audio file"""
    result = transcribe_audio(audio_path)

    print(f"Duration: {result['duration']:.2f}s")
    print(f"Language: {result['language']}")
    print(f"\nTranscription:")
    print(result['text'])

    print(f"\nSegments:")
    for i, segment in enumerate(result['segments']):
        print(f"{i+1}. [{segment['start']:.2f}s - {segment['end']:.2f}s]")
        print(f"   {segment['text']}")

# Usage
transcribe_file("recording.wav")
```

### Voice Command Recognition

```python
def recognize_command():
    """
    Listen for and recognize voice commands

    Returns:
        tuple: (command_type, parameters)
    """
    text = listen().lower()

    # Parse commands
    if "search for" in text:
        query = text.split("search for")[1].strip()
        return ("search", query)

    elif "open" in text:
        app = text.split("open")[1].strip()
        return ("open", app)

    elif "what is" in text or "what's" in text:
        query = text.split("what is")[-1].split("what's")[-1].strip()
        return ("query", query)

    else:
        return ("chat", text)

# Usage
command_type, params = recognize_command()
print(f"Command: {command_type}")
print(f"Parameters: {params}")
```

---

## Configuration

### Audio Settings

```python
# Microphone settings
SAMPLE_RATE = 16000  # Hz (Whisper requires 16kHz)
CHANNELS = 1  # Mono
RECORDING_DURATION = 5  # seconds
CHUNK_SIZE = 1024

# List available audio devices
import sounddevice as sd
print(sd.query_devices())

# Set default input device
sd.default.device = (1, None)  # (input_device_id, output_device_id)
```

### Model Paths

```python
from pathlib import Path

# Whisper cache
WHISPER_CACHE = Path.home() / ".cache" / "whisper"

# TTS cache
TTS_CACHE = Path.home() / ".local" / "share" / "tts"

# Create directories if needed
WHISPER_CACHE.mkdir(parents=True, exist_ok=True)
TTS_CACHE.mkdir(parents=True, exist_ok=True)
```

---

## Model Management

### Download Models

```bash
# Download Whisper model
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v2')"

# Download TTS model
python -c "from TTS.api import TTS; TTS('tts_models/en/vctk/vits')"
```

### Model Storage

```
~/.cache/whisper/          # Whisper models
├── large-v2/
│   ├── model.bin
│   ├── config.json
│   └── vocabulary.txt

~/.local/share/tts/        # TTS models
└── tts_models--en--vctk--vits/
    ├── model_file.pth
    ├── config.json
    └── speakers.json
```

### Clear Model Cache

```python
import shutil
from pathlib import Path

def clear_whisper_cache():
    """Remove Whisper model cache"""
    cache_dir = Path.home() / ".cache" / "whisper"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("Whisper cache cleared")

def clear_tts_cache():
    """Remove TTS model cache"""
    cache_dir = Path.home() / ".local" / "share" / "tts"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("TTS cache cleared")
```

---

## Performance

### Optimization Tips

**1. Use Smaller Models for Real-Time:**
```python
# For real-time interaction, use smaller Whisper model
stt_model = WhisperModel("small")  # Instead of large-v2
```

**2. GPU Acceleration:**
```python
# Enable GPU for faster processing
stt_model = WhisperModel("large-v2", device="cuda")
tts_model = TTS("tts_models/en/vctk/vits", gpu=True)
```

**3. Batch Processing:**
```python
def batch_transcribe(audio_files):
    """Transcribe multiple files efficiently"""
    results = []
    for audio_file in audio_files:
        result = stt_model.transcribe(audio_file)
        results.append(result)
    return results
```

### Performance Benchmarks

| Operation | Small Model | Large Model | GPU Accelerated |
|-----------|-------------|-------------|-----------------|
| Transcribe 5s audio | ~0.5s | ~2s | ~0.2s |
| TTS generation (20 words) | ~1s | ~1s | ~0.3s |
| Model loading | ~2s | ~5s | ~3s |

---

## Troubleshooting

### Common Issues

**Microphone Not Found:**
```python
import sounddevice as sd

# List devices
print(sd.query_devices())

# Set specific device
sd.default.device = 1  # Use device ID from list
```

**Audio Playback Silent:**
```python
# Check system volume
# Verify audio output device
sd.default.device = (None, 0)  # Set output device

# Test playback
import numpy as np
test_tone = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
sd.play(test_tone, 16000)
sd.wait()
```

**Model Download Fails:**
```bash
# Manual download
# Whisper
wget https://huggingface.co/Systran/faster-whisper-large-v2/resolve/main/model.bin

# TTS
wget https://github.com/coqui-ai/TTS/releases/download/v0.13.0/tts_models.tar.gz
```

**Transcription Accuracy Poor:**
```python
# Adjust Whisper parameters
result = stt_model.transcribe(
    audio_file,
    beam_size=10,  # Increase beam search
    best_of=10,    # Generate more candidates
    temperature=0.0,  # Deterministic
    compression_ratio_threshold=2.4,  # Filter compression artifacts
    no_speech_threshold=0.6  # Filter silence
)
```

---

## Related Documentation

- [Vera Main README](../README.md)
- [ChatUI Integration](../ChatUI/README.md)
- [faster-whisper Documentation](https://github.com/guillaumekln/faster-whisper)
- [Coqui TTS Documentation](https://github.com/coqui-ai/TTS)

---

**Last Updated:** January 2025
**Maintainer:** Vera-AI Development Team
**Version:** 1.0.0
