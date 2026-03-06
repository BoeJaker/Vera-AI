import asyncio
import sounddevice as sd
import numpy as np
import webrtcvad
from faster_whisper import WhisperModel
from openai import OpenAI
from TTS.api import TTS
import threading

# =====================================================
# CONFIGURATION
# =====================================================

MODEL_NAME = "gpt-oss:20b"
OLLAMA_URL = "http://192.168.0.250:11435/v1"

SAMPLE_RATE = 16000
FRAME_DURATION = 30  # ms
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)

MAX_HISTORY_TURNS = 10

# =====================================================
# INITIALIZE COMPONENTS
# =====================================================

client = OpenAI(
    base_url=OLLAMA_URL,
    api_key="ollama"
)

vad = webrtcvad.Vad(2)

whisper = WhisperModel(
    "base",
    device="cuda",   # change to "cpu" if needed
    compute_type="float16"
)

tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")

conversation = [
    {"role": "system", "content": "You are a natural real-time conversational assistant."}
]

audio_queue = asyncio.Queue()
text_queue = asyncio.Queue()
interrupt_event = asyncio.Event()

# =====================================================
# MICROPHONE STREAM TASK
# =====================================================

async def mic_stream():
    loop = asyncio.get_running_loop()

    def callback(indata, frames, time, status):
        audio_queue.put_nowait(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SIZE,
        callback=callback,
    ):
        while True:
            await asyncio.sleep(0.05)

# =====================================================
# STT WORKER (VAD + TRANSCRIPTION)
# =====================================================

async def stt_worker():
    buffer = []

    while True:
        frame = await audio_queue.get()
        pcm_bytes = frame.tobytes()

        if vad.is_speech(pcm_bytes, SAMPLE_RATE):
            buffer.append(frame)

        elif buffer:
            audio = np.concatenate(buffer).astype(np.float32) / 32768.0
            buffer.clear()

            segments, _ = whisper.transcribe(audio)
            text = " ".join([seg.text for seg in segments]).strip()

            if text:
                print(f"\nYou: {text}\n")
                interrupt_event.set()
                await text_queue.put(text)

# =====================================================
# LLM STREAM WORKER
# =====================================================

async def llm_worker():
    while True:
        user_text = await text_queue.get()

        conversation.append({"role": "user", "content": user_text})
        trim_history()

        interrupt_event.clear()

        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=conversation,
            stream=True,
            temperature=0.4
        )

        assistant_text = ""
        sentence_buffer = ""

        print("Assistant: ", end="", flush=True)

        for chunk in stream:
            if interrupt_event.is_set():
                break

            delta = chunk.choices[0].delta.content
            if not delta:
                continue

            print(delta, end="", flush=True)

            assistant_text += delta
            sentence_buffer += delta

            if sentence_boundary(sentence_buffer):
                asyncio.create_task(tts_speak(sentence_buffer))
                sentence_buffer = ""

        print("\n")

        if assistant_text:
            conversation.append({"role": "assistant", "content": assistant_text})

# =====================================================
# TTS (INTERRUPTIBLE)
# =====================================================

async def tts_speak(text):
    if interrupt_event.is_set():
        return

    loop = asyncio.get_running_loop()

    def blocking_tts():
        wav = tts.tts(text)
        sd.play(np.array(wav), samplerate=tts.synthesizer.output_sample_rate)
        sd.wait()

    await loop.run_in_executor(None, blocking_tts)

# =====================================================
# UTILITIES
# =====================================================

def sentence_boundary(text):
    return any(p in text for p in [".", "!", "?"])

def trim_history():
    global conversation
    if len(conversation) > MAX_HISTORY_TURNS * 2:
        conversation = [conversation[0]] + conversation[-MAX_HISTORY_TURNS * 2:]

# =====================================================
# MAIN
# =====================================================

async def main():
    print("Real-Time Local Voice Assistant Started")
    print("Speak into the mic. Interrupt at any time.\n")

    await asyncio.gather(
        mic_stream(),
        stt_worker(),
        llm_worker(),
    )

if __name__ == "__main__":
    asyncio.run(main())