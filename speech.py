from faster_whisper import WhisperModel
import sounddevice as sd
import soundfile as sf
from TTS.api import TTS
import tempfile
import os
import shutil
from pathlib import Path


model_size = "large-v2"
cache_dir = Path.home() / ".cache" / "whisper"

def load_whisper_model(model_size, cache_dir):
    """Load Whisper model, auto-repair cache if broken."""
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

# Load STT model safely
stt_model = load_whisper_model(model_size, cache_dir)

print("Downloaded to ~/.cache/whisper")

# Load StyleTTS2 or your chosen TTS model
tts_model = TTS(model_name="tts_models/en/vctk/vits", progress_bar=False, gpu=False)

def listen():
    print("[Listening...]")
    duration = 5  # seconds
    samplerate = 16000
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype="float32")
    sd.wait()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        sf.write(tmp_wav.name, recording, samplerate)
        result = stt_model.transcribe(tmp_wav.name)
        os.unlink(tmp_wav.name)
        return result["text"]

def speak(text):
    print(f"[Speaking] {text}")
    wav_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    tts_model.tts_to_file(text=text, file_path=wav_path)
    data, fs = sf.read(wav_path, dtype='float32')
    sd.play(data, fs)
    sd.wait()
    os.unlink(wav_path)
