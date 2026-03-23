"""
gpu_inference_server.py
========================
Drop-in GPU inference server providing:
  - Whisper STT  (POST /stt, Redis queue: stt_requests)
  - Stable Diffusion image generation (POST /imagine, Redis queue: imagine_requests)
  - TTS with streaming (POST /tts/stream — chunked audio out, text streamed in)
  - Synchronous TTS (POST /tts)

No Celery. Single process, async FastAPI + background threads for GPU work.

Dependencies (pip install):
    fastapi uvicorn[standard] redis python-multipart
    torch torchvision torchaudio
    openai-whisper
    diffusers transformers accelerate xformers safetensors
    TTS   (Coqui TTS — "pip install TTS")
    Pillow numpy soundfile

Optional: set env vars to override defaults (see CONFIG section).

Redis result keys expire after REDIS_RESULT_TTL seconds (default 300).
Audio is returned as raw PCM (s16le) for streaming, or WAV bytes for sync.
Images are returned as base64 PNG.

Usage:
    python gpu_inference_server.py
    # or with uvicorn directly:
    uvicorn gpu_inference_server:app --host 0.0.0.0 --port 8765 --workers 1
"""

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import queue
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ─────────────────────────── CONFIG ──────────────────────────────────────────

REDIS_URL            = os.getenv("REDIS_URL",            "redis://localhost:6379/0")
REDIS_RESULT_TTL     = int(os.getenv("REDIS_RESULT_TTL", "300"))

WHISPER_MODEL        = os.getenv("WHISPER_MODEL",        "base")          # tiny/base/small/medium/large
SD_MODEL_ID          = os.getenv("SD_MODEL_ID",          "runwayml/stable-diffusion-v1-5")
SD_DEVICE            = os.getenv("SD_DEVICE",            "cuda")
TTS_MODEL_NAME       = os.getenv("TTS_MODEL_NAME",       "tts_models/en/ljspeech/tacotron2-DDC")
TTS_VOCODER_NAME     = os.getenv("TTS_VOCODER_NAME",     "vocoder_models/en/ljspeech/hifigan_v2")
TTS_SPEAKER          = os.getenv("TTS_SPEAKER",          None)            # for multi-speaker models
TTS_LANGUAGE         = os.getenv("TTS_LANGUAGE",         None)

ENABLE_WHISPER       = os.getenv("ENABLE_WHISPER",       "1") == "1"
ENABLE_SD            = os.getenv("ENABLE_SD",            "1") == "1"
ENABLE_TTS           = os.getenv("ENABLE_TTS",           "1") == "1"
ENABLE_REDIS         = os.getenv("ENABLE_REDIS",         "1") == "1"

SERVER_HOST          = os.getenv("SERVER_HOST",          "0.0.0.0")
SERVER_PORT          = int(os.getenv("SERVER_PORT",      "8765"))

REDIS_STT_QUEUE      = "stt_requests"
REDIS_IMAGINE_QUEUE  = "imagine_requests"
REDIS_TTS_QUEUE      = "tts_requests"
REDIS_RESULT_PREFIX  = "result:"

SD_DEFAULT_STEPS     = int(os.getenv("SD_DEFAULT_STEPS",  "30"))
SD_DEFAULT_GUIDANCE  = float(os.getenv("SD_DEFAULT_GUIDANCE", "7.5"))
SD_DEFAULT_WIDTH     = int(os.getenv("SD_DEFAULT_WIDTH",  "512"))
SD_DEFAULT_HEIGHT    = int(os.getenv("SD_DEFAULT_HEIGHT", "512"))

TTS_STREAM_CHUNK_SENTENCES = os.getenv("TTS_STREAM_CHUNK_SENTENCES", "1") == "1"
TTS_SAMPLE_RATE      = 22050   # Coqui default; updated after model load

# ─────────────────────────── LOGGING ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("gpu_server")

# ─────────────────────────── GLOBALS ─────────────────────────────────────────

_whisper_model  = None
_sd_pipe        = None
_tts_synthesizer = None
_redis_client   = None

# Single-slot queues so the GPU is never double-booked per modality.
# Items: (job_id, payload_dict, result_future_or_queue)
_stt_queue      = queue.Queue(maxsize=64)
_sd_queue       = queue.Queue(maxsize=64)
_tts_queue      = queue.Queue(maxsize=64)

# ─────────────────────────── MODEL LOADING ───────────────────────────────────

def load_models():
    global _whisper_model, _sd_pipe, _tts_synthesizer, TTS_SAMPLE_RATE

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"Using device: {device}")

    if ENABLE_WHISPER:
        log.info(f"Loading Whisper ({WHISPER_MODEL})…")
        import whisper
        _whisper_model = whisper.load_model(WHISPER_MODEL, device=device)
        log.info("Whisper ready.")

    if ENABLE_SD:
        log.info(f"Loading Stable Diffusion ({SD_MODEL_ID})…")
        from diffusers import StableDiffusionPipeline
        dtype = torch.float16 if device == "cuda" else torch.float32
        _sd_pipe = StableDiffusionPipeline.from_pretrained(
            SD_MODEL_ID,
            torch_dtype=dtype,
            safety_checker=None,
        ).to(device)
        try:
            _sd_pipe.enable_xformers_memory_efficient_attention()
            log.info("xformers attention enabled.")
        except Exception:
            log.info("xformers not available, using default attention.")
        _sd_pipe.enable_attention_slicing()
        log.info("Stable Diffusion ready.")

    if ENABLE_TTS:
        log.info(f"Loading TTS ({TTS_MODEL_NAME})…")
        from TTS.api import TTS as CoquiTTS
        use_gpu = device == "cuda"
        _tts_synthesizer = CoquiTTS(
            model_name=TTS_MODEL_NAME,
            vocoder_name=TTS_VOCODER_NAME if TTS_VOCODER_NAME else None,
            gpu=use_gpu,
        )
        if hasattr(_tts_synthesizer, "synthesizer") and hasattr(
            _tts_synthesizer.synthesizer, "output_sample_rate"
        ):
            TTS_SAMPLE_RATE = _tts_synthesizer.synthesizer.output_sample_rate
        log.info(f"TTS ready. Sample rate: {TTS_SAMPLE_RATE} Hz")

# ─────────────────────────── REDIS HELPERS ───────────────────────────────────

def get_redis():
    global _redis_client
    if _redis_client is None:
        import redis as redis_lib
        _redis_client = redis_lib.from_url(REDIS_URL, decode_responses=False)
    return _redis_client


def redis_set_result(job_id: str, payload: dict):
    r = get_redis()
    r.setex(
        f"{REDIS_RESULT_PREFIX}{job_id}",
        REDIS_RESULT_TTL,
        json.dumps(payload),
    )


def redis_get_result(job_id: str) -> Optional[dict]:
    r = get_redis()
    raw = r.get(f"{REDIS_RESULT_PREFIX}{job_id}")
    if raw:
        return json.loads(raw)
    return None

# ─────────────────────────── WORKER THREADS ──────────────────────────────────

# ── STT worker ──────────────────────────────────────────────────────────────

def _stt_worker():
    log.info("STT worker started.")
    while True:
        job_id, payload, result_q = _stt_queue.get()
        try:
            audio_bytes = payload["audio_bytes"]
            language    = payload.get("language")
            task        = payload.get("task", "transcribe")  # transcribe | translate

            # Write to temp buffer that whisper can read
            audio_np = _bytes_to_float_array(audio_bytes)
            result = _whisper_model.transcribe(
                audio_np,
                language=language,
                task=task,
                fp16=torch.cuda.is_available(),
            )
            out = {"status": "ok", "text": result["text"].strip(), "language": result.get("language")}
        except Exception as e:
            log.error(f"STT error: {e}\n{traceback.format_exc()}")
            out = {"status": "error", "error": str(e)}

        if result_q is not None:
            result_q.put(out)
        else:
            redis_set_result(job_id, out)


def _bytes_to_float_array(audio_bytes: bytes) -> np.ndarray:
    """Load audio bytes (any format soundfile supports) into float32 mono."""
    buf = io.BytesIO(audio_bytes)
    data, sr = sf.read(buf, dtype="float32", always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)
    # Whisper expects 16 kHz
    if sr != 16000:
        import torchaudio
        tensor = torch.from_numpy(data).unsqueeze(0)
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
        data = resampler(tensor).squeeze(0).numpy()
    return data


# ── SD worker ───────────────────────────────────────────────────────────────

def _sd_worker():
    log.info("SD worker started.")
    while True:
        job_id, payload, result_q = _sd_queue.get()
        try:
            prompt          = payload["prompt"]
            negative_prompt = payload.get("negative_prompt", "")
            steps           = int(payload.get("steps",    SD_DEFAULT_STEPS))
            guidance        = float(payload.get("guidance", SD_DEFAULT_GUIDANCE))
            width           = int(payload.get("width",    SD_DEFAULT_WIDTH))
            height          = int(payload.get("height",   SD_DEFAULT_HEIGHT))
            seed            = payload.get("seed")

            generator = None
            if seed is not None:
                generator = torch.Generator(device=SD_DEVICE).manual_seed(int(seed))

            with torch.inference_mode():
                image = _sd_pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=steps,
                    guidance_scale=guidance,
                    width=width,
                    height=height,
                    generator=generator,
                ).images[0]

            buf = io.BytesIO()
            image.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            out = {"status": "ok", "image_b64": b64, "format": "png"}
        except Exception as e:
            log.error(f"SD error: {e}\n{traceback.format_exc()}")
            out = {"status": "error", "error": str(e)}

        if result_q is not None:
            result_q.put(out)
        else:
            redis_set_result(job_id, out)


# ── TTS worker (sync) ────────────────────────────────────────────────────────

def _tts_worker():
    log.info("TTS worker started.")
    while True:
        job_id, payload, result_q = _tts_queue.get()
        try:
            wav = _tts_synthesize(payload["text"], payload)
            buf = io.BytesIO()
            sf.write(buf, wav, TTS_SAMPLE_RATE, format="WAV", subtype="PCM_16")
            b64 = base64.b64encode(buf.getvalue()).decode()
            out = {"status": "ok", "audio_b64": b64, "format": "wav", "sample_rate": TTS_SAMPLE_RATE}
        except Exception as e:
            log.error(f"TTS error: {e}\n{traceback.format_exc()}")
            out = {"status": "error", "error": str(e)}

        if result_q is not None:
            result_q.put(out)
        else:
            redis_set_result(job_id, out)


def _tts_synthesize(text: str, opts: dict) -> np.ndarray:
    """Run TTS and return float32 numpy array."""
    speaker  = opts.get("speaker",  TTS_SPEAKER)
    language = opts.get("language", TTS_LANGUAGE)
    kwargs = {}
    if speaker:
        kwargs["speaker"] = speaker
    if language:
        kwargs["language"] = language

    wav = _tts_synthesizer.tts(text=text, **kwargs)
    if not isinstance(wav, np.ndarray):
        wav = np.array(wav, dtype=np.float32)
    return wav


# ── Redis queue listener thread ──────────────────────────────────────────────

def _redis_listener():
    """
    Blocks on Redis lists for incoming jobs from external producers.
    Pushes them into the internal Python queues.
    Result is stored back in Redis under result:<job_id>.
    """
    if not ENABLE_REDIS:
        return
    log.info("Redis listener started.")
    r = get_redis()
    queues = []
    if ENABLE_WHISPER:
        queues.append(REDIS_STT_QUEUE)
    if ENABLE_SD:
        queues.append(REDIS_IMAGINE_QUEUE)
    if ENABLE_TTS:
        queues.append(REDIS_TTS_QUEUE)

    while True:
        try:
            item = r.blpop(queues, timeout=2)
            if item is None:
                continue
            queue_name, raw = item
            queue_name = queue_name.decode() if isinstance(queue_name, bytes) else queue_name
            msg = json.loads(raw)
            job_id = msg.get("job_id", str(uuid.uuid4()))

            if queue_name == REDIS_STT_QUEUE and ENABLE_WHISPER:
                # payload must include audio_b64
                audio_b64 = msg.get("audio_b64", "")
                msg["audio_bytes"] = base64.b64decode(audio_b64)
                _stt_queue.put((job_id, msg, None))

            elif queue_name == REDIS_IMAGINE_QUEUE and ENABLE_SD:
                _sd_queue.put((job_id, msg, None))

            elif queue_name == REDIS_TTS_QUEUE and ENABLE_TTS:
                _tts_queue.put((job_id, msg, None))

        except Exception as e:
            log.error(f"Redis listener error: {e}")
            time.sleep(1)


# ─────────────────────────── STARTUP / LIFESPAN ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()

    # Start GPU worker threads
    if ENABLE_WHISPER:
        t = threading.Thread(target=_stt_worker, daemon=True)
        t.start()

    if ENABLE_SD:
        t = threading.Thread(target=_sd_worker, daemon=True)
        t.start()

    if ENABLE_TTS:
        t = threading.Thread(target=_tts_worker, daemon=True)
        t.start()

    # Redis listener
    if ENABLE_REDIS:
        try:
            get_redis().ping()
            t = threading.Thread(target=_redis_listener, daemon=True)
            t.start()
            log.info("Redis connected and listener running.")
        except Exception as e:
            log.warning(f"Redis unavailable, listener disabled: {e}")

    yield
    log.info("Server shutting down.")


app = FastAPI(title="GPU Inference Server", version="1.0.0", lifespan=lifespan)

# ─────────────────────────── HELPERS ─────────────────────────────────────────

def _sync_dispatch(q: queue.Queue, job_id: str, payload: dict, timeout: int = 120) -> dict:
    """Submit a job synchronously and wait for its result."""
    result_q: queue.Queue = queue.Queue()
    try:
        q.put_nowait((job_id, payload, result_q))
    except queue.Full:
        raise HTTPException(status_code=503, detail="Server busy, try again later.")
    try:
        return result_q.get(timeout=timeout)
    except queue.Empty:
        raise HTTPException(status_code=504, detail="Inference timed out.")

# ─────────────────────────── ROUTES ──────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "whisper": _whisper_model is not None,
        "stable_diffusion": _sd_pipe is not None,
        "tts": _tts_synthesizer is not None,
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


# ── STT ──────────────────────────────────────────────────────────────────────

@app.post("/stt")
async def stt(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    task: str = Form("transcribe"),
):
    """
    Transcribe audio. Upload as multipart/form-data with field 'file'.
    Supports any audio format soundfile can read (wav, mp3, flac, ogg…).
    Returns: { text, language }
    """
    if not ENABLE_WHISPER or _whisper_model is None:
        raise HTTPException(status_code=503, detail="Whisper not loaded.")
    audio_bytes = await file.read()
    job_id = str(uuid.uuid4())
    result = _sync_dispatch(_stt_queue, job_id, {
        "audio_bytes": audio_bytes,
        "language": language,
        "task": task,
    })
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── Image generation ─────────────────────────────────────────────────────────

class ImagineRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    steps: int = SD_DEFAULT_STEPS
    guidance: float = SD_DEFAULT_GUIDANCE
    width: int = SD_DEFAULT_WIDTH
    height: int = SD_DEFAULT_HEIGHT
    seed: Optional[int] = None


@app.post("/imagine")
async def imagine(req: ImagineRequest):
    """
    Generate an image from a text prompt.
    Returns: { image_b64: "<base64 PNG>", format: "png" }
    """
    if not ENABLE_SD or _sd_pipe is None:
        raise HTTPException(status_code=503, detail="Stable Diffusion not loaded.")
    job_id = str(uuid.uuid4())
    result = _sync_dispatch(_sd_queue, job_id, req.model_dump(), timeout=180)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── TTS (sync) ───────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    speaker: Optional[str] = None
    language: Optional[str] = None


@app.post("/tts")
async def tts(req: TTSRequest):
    """
    Synthesise speech for the given text.
    Returns: { audio_b64: "<base64 WAV>", format: "wav", sample_rate: int }
    """
    if not ENABLE_TTS or _tts_synthesizer is None:
        raise HTTPException(status_code=503, detail="TTS not loaded.")
    job_id = str(uuid.uuid4())
    result = _sync_dispatch(_tts_queue, job_id, req.model_dump())
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── TTS streaming ─────────────────────────────────────────────────────────────
#
# Two streaming modes:
#   1. POST /tts/stream  — full text body, sentence-chunked PCM stream out
#   2. POST /tts/stream/ingest — body streamed in line-by-line, PCM out
#
# Audio is raw signed 16-bit PCM at TTS_SAMPLE_RATE Hz, little-endian.
# Set Content-Type: audio/pcm and X-Sample-Rate response header.
# Clients can pipe directly to ffplay:
#   curl -s -X POST http://host:8765/tts/stream -d '{"text":"Hello"}' \
#     | ffplay -f s16le -ar 22050 -ac 1 -i pipe:0
# ─────────────────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Very simple sentence splitter that preserves natural TTS chunks."""
    import re
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def _wav_to_pcm_s16le(wav: np.ndarray) -> bytes:
    """Convert float32 numpy array to raw s16le bytes."""
    clipped = np.clip(wav, -1.0, 1.0)
    pcm = (clipped * 32767).astype(np.int16)
    return pcm.tobytes()


def _pcm_header(sample_rate: int, num_samples: int) -> bytes:
    """Minimal WAV header for a PCM stream when client wants full WAV."""
    import struct
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header


def _tts_stream_sentences(sentences: list[str], opts: dict) -> AsyncGenerator:
    """Synthesise sentences one at a time, yielding raw PCM bytes per sentence."""

    audio_gen_q: queue.Queue = queue.Queue()

    def _generate():
        for sentence in sentences:
            try:
                wav = _tts_synthesize(sentence, opts)
                audio_gen_q.put(("chunk", _wav_to_pcm_s16le(wav)))
            except Exception as e:
                audio_gen_q.put(("error", str(e)))
                return
        audio_gen_q.put(("done", None))

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()
    return audio_gen_q


async def _stream_tts_response(sentences: list[str], opts: dict) -> AsyncGenerator[bytes, None]:
    """Async generator that yields PCM chunks as they are synthesised."""
    loop = asyncio.get_event_loop()
    audio_gen_q = _tts_stream_sentences(sentences, opts)

    while True:
        # Poll the queue without blocking the event loop
        try:
            kind, data = await loop.run_in_executor(None, lambda: audio_gen_q.get(timeout=60))
        except queue.Empty:
            break

        if kind == "done":
            break
        elif kind == "error":
            log.error(f"TTS stream error: {data}")
            break
        else:
            yield data


@app.post("/tts/stream")
async def tts_stream(req: TTSRequest):
    """
    Stream synthesised PCM audio as it is generated, sentence by sentence.
    Response: chunked transfer, Content-Type: audio/pcm
    Play with: ffplay -f s16le -ar 22050 -ac 1 -i pipe:0
    """
    if not ENABLE_TTS or _tts_synthesizer is None:
        raise HTTPException(status_code=503, detail="TTS not loaded.")

    sentences = _split_sentences(req.text)
    if not sentences:
        raise HTTPException(status_code=400, detail="Empty text.")

    opts = {"speaker": req.speaker, "language": req.language}

    return StreamingResponse(
        _stream_tts_response(sentences, opts),
        media_type="audio/pcm",
        headers={
            "X-Sample-Rate": str(TTS_SAMPLE_RATE),
            "X-Channels": "1",
            "X-Bit-Depth": "16",
            "Transfer-Encoding": "chunked",
        },
    )


@app.post("/tts/stream/ingest")
async def tts_stream_ingest(request_body: dict):
    """
    Accepts a JSON body with 'text' as newline-delimited sentences.
    Synthesises each line as it arrives (simulated streaming input).
    Streams raw PCM back.

    For true streaming text in, POST the body with Transfer-Encoding: chunked
    and newline-delimited sentences; each line will be synthesised and streamed
    back immediately.

    Body: { "lines": ["sentence one", "sentence two", ...], "speaker": null, "language": null }
    """
    if not ENABLE_TTS or _tts_synthesizer is None:
        raise HTTPException(status_code=503, detail="TTS not loaded.")

    lines = request_body.get("lines", [])
    if isinstance(lines, str):
        lines = [l.strip() for l in lines.splitlines() if l.strip()]
    lines = [l for l in lines if l]

    if not lines:
        raise HTTPException(status_code=400, detail="No lines provided.")

    opts = {
        "speaker":  request_body.get("speaker",  TTS_SPEAKER),
        "language": request_body.get("language", TTS_LANGUAGE),
    }

    async def _gen():
        for line in lines:
            async for chunk in _stream_tts_response([line], opts):
                yield chunk

    return StreamingResponse(
        _gen(),
        media_type="audio/pcm",
        headers={
            "X-Sample-Rate": str(TTS_SAMPLE_RATE),
            "X-Channels": "1",
            "X-Bit-Depth": "16",
        },
    )


# ── Async result polling (for Redis-submitted jobs) ───────────────────────────

@app.get("/result/{job_id}")
async def get_result(job_id: str):
    """
    Poll the result of a Redis-submitted job.
    Returns 202 while pending, 200 with result when done.
    """
    if not ENABLE_REDIS:
        raise HTTPException(status_code=404, detail="Redis not enabled.")
    result = redis_get_result(job_id)
    if result is None:
        return JSONResponse(status_code=202, content={"status": "pending", "job_id": job_id})
    return result


# ─────────────────────────── ENTRYPOINT ──────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "gpu_inference_server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        workers=1,           # MUST be 1 — GPU models are not fork-safe
        log_level="info",
    )