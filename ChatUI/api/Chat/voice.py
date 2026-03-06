"""
Vera Voice API Router
=====================
Exposes STT (whisper.transcribe) and TTS (whisper.tts / tts.stream) tasks
from the orchestrator as HTTP endpoints, suitable for the duplex voice UI.

Mount in your main FastAPI app:
    from Vera.ChatUI.api.voice import router as voice_router
    app.include_router(voice_router)

Assumes:
    - `orchestrator` is accessible via vera_instance or as a module-level singleton
    - whisper.transcribe, whisper.tts, tts.stream tasks are registered
"""

import asyncio
import io
import logging
import os
import tempfile
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from Vera.ChatUI.api.session import get_or_create_vera, sessions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_orchestrator(session_id: Optional[str] = None):
    """
    Resolve orchestrator from vera instance or fall back to module-level singleton.
    We try three strategies so it works regardless of how Vera is wired up.
    """
    # Strategy 1: from a live vera instance
    if session_id and session_id in sessions:
        try:
            vera = get_or_create_vera(session_id)
            if hasattr(vera, 'orchestrator') and vera.orchestrator is not None:
                return vera.orchestrator
        except Exception:
            pass

    # Strategy 2: module-level singleton (common pattern in Vera codebase)
    try:
        from Vera.Tasks.orchestrator import orchestrator as global_orch
        if global_orch is not None:
            return global_orch
    except ImportError:
        pass

    # Strategy 3: try the task registry directly (tasks module)
    try:
        from Vera.Tasks import orchestrator as orch_module
        if hasattr(orch_module, 'orchestrator'):
            return orch_module.orchestrator
    except ImportError:
        pass

    return None


def _get_vera_instance(session_id: Optional[str] = None):
    """Get vera instance for a session, used to pass as first arg to tasks."""
    if session_id and session_id in sessions:
        try:
            return get_or_create_vera(session_id)
        except Exception:
            pass
    return None


async def _submit_and_wait(orchestrator, task_name: str, *args, timeout: float = 30.0, **kwargs):
    """Submit a task to the orchestrator and wait for the result in a thread."""
    loop = asyncio.get_event_loop()

    def _run():
        task_id = orchestrator.submit_task(task_name, *args, **kwargs)
        result = orchestrator.wait_for_result(task_id, timeout=timeout)
        return result

    result = await loop.run_in_executor(None, _run)
    return result


async def _submit_and_stream(orchestrator, task_name: str, *args, timeout: float = 60.0, **kwargs):
    """Submit a streaming task and yield chunks via an async generator."""
    loop = asyncio.get_event_loop()
    chunk_queue: asyncio.Queue = asyncio.Queue()

    def _run():
        task_id = orchestrator.submit_task(task_name, *args, **kwargs)
        try:
            for chunk in orchestrator.stream_result(task_id, timeout=timeout):
                # Put chunk onto the asyncio queue from the worker thread
                asyncio.run_coroutine_threadsafe(chunk_queue.put(chunk), loop)
        except Exception as e:
            asyncio.run_coroutine_threadsafe(chunk_queue.put(e), loop)
        finally:
            asyncio.run_coroutine_threadsafe(chunk_queue.put(None), loop)  # sentinel

    # Run in thread pool so we don't block the event loop
    loop.run_in_executor(None, _run)

    while True:
        item = await chunk_queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield item


# ─────────────────────────────────────────────────────────────────────────────
# STT — Speech to Text
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    language: str = Form(default="en"),
    model: str = Form(default="base"),
):
    """
    Transcribe uploaded audio using whisper.transcribe task.
    Accepts: webm, wav, mp3, ogg, m4a
    Returns: { "text": "...", "language": "en", "duration_ms": 123 }
    """
    orchestrator = _get_orchestrator(session_id)

    # Save uploaded audio to a temp file — Whisper needs a path
    suffix = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await audio.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()

        audio_path = tmp.name
        t0 = time.time()

        if orchestrator is not None:
            vera = _get_vera_instance(session_id)
            result = await _submit_and_wait(
                orchestrator,
                "whisper.transcribe",
                vera,           # vera_instance (first positional arg per task signature)
                audio_path,
                timeout=60.0,
            )

            if result is None:
                raise HTTPException(status_code=504, detail="Transcription timed out")

            if result.status.name == "FAILED":
                raise HTTPException(status_code=500, detail=f"Transcription failed: {result.error}")

            # result.result is the dict returned by whisper_transcribe
            output = result.result or {}
            if isinstance(output, dict) and "error" in output:
                raise HTTPException(status_code=500, detail=output["error"])

            text = ""
            if isinstance(output, dict):
                text = output.get("text", output.get("transcription", ""))
            elif isinstance(output, str):
                text = output

            return {
                "text": text.strip(),
                "language": language,
                "duration_ms": int((time.time() - t0) * 1000),
            }

        else:
            # ── Fallback: call whisper directly if available ──────────────────
            logger.warning("Orchestrator not available — attempting direct whisper call")
            try:
                import whisper as _whisper  # openai-whisper package
                wmodel = _whisper.load_model(model)
                result = wmodel.transcribe(audio_path, language=language)
                return {
                    "text": result.get("text", "").strip(),
                    "language": language,
                    "duration_ms": int((time.time() - t0) * 1000),
                }
            except ImportError:
                raise HTTPException(
                    status_code=503,
                    detail="Orchestrator not available and openai-whisper not installed"
                )

    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# TTS — Text to Speech (batch, returns audio file)
# ─────────────────────────────────────────────────────────────────────────────

class TTSSynthesizeRequest(BaseModel):
    text: str
    voice: str = "default"
    format: str = "wav"       # wav | mp3 | ogg
    session_id: Optional[str] = None
    speed: float = 1.0


@router.post("/synthesize")
async def synthesize_speech(req: TTSSynthesizeRequest):
    """
    Convert text to speech using whisper.tts task.
    Returns raw audio bytes with appropriate Content-Type.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    orchestrator = _get_orchestrator(req.session_id)
    vera = _get_vera_instance(req.session_id)

    # Generate a temp path for the output audio
    suffix = f".{req.format}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        output_path = tmp.name

    try:
        if orchestrator is not None:
            result = await _submit_and_wait(
                orchestrator,
                "whisper.tts",
                vera,
                req.text,
                req.voice,
                output_path,
                timeout=30.0,
            )

            if result is None:
                raise HTTPException(status_code=504, detail="TTS timed out")
            if result.status.name == "FAILED":
                raise HTTPException(status_code=500, detail=f"TTS failed: {result.error}")

            output = result.result or {}
            if isinstance(output, dict) and "error" in output:
                raise HTTPException(status_code=500, detail=output["error"])

            # Read the generated audio file
            audio_path = output_path
            if isinstance(output, dict):
                audio_path = output.get("audio_path", output_path)

        else:
            raise HTTPException(status_code=503, detail="Orchestrator not available")

        if not os.path.exists(audio_path):
            raise HTTPException(status_code=500, detail="TTS produced no output file")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        content_type_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }
        content_type = content_type_map.get(req.format, "audio/wav")

        return Response(
            content=audio_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="tts_output.{req.format}"',
                "Cache-Control": "no-cache",
            },
        )

    finally:
        try:
            os.unlink(output_path)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# TTS — Streaming (streams audio chunks as they are generated)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/synthesize/stream")
async def synthesize_speech_stream(req: TTSSynthesizeRequest):
    """
    Streaming TTS using tts.stream task.
    Returns audio chunks as they are generated (chunked transfer encoding).
    Each chunk is raw audio bytes.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    orchestrator = _get_orchestrator(req.session_id)
    vera = _get_vera_instance(req.session_id)

    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not available")

    content_type_map = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
    }
    content_type = content_type_map.get(req.format, "audio/wav")

    async def audio_generator():
        try:
            async for chunk in _submit_and_stream(
                orchestrator,
                "tts.stream",
                vera,
                req.text,
                req.voice,
                timeout=60.0,
            ):
                if chunk is None:
                    break
                if isinstance(chunk, dict) and "error" in chunk:
                    logger.error(f"TTS stream error: {chunk['error']}")
                    break
                # chunk should be bytes from the TTS model
                if isinstance(chunk, bytes):
                    yield chunk
                elif isinstance(chunk, dict) and "audio_data" in chunk:
                    yield chunk["audio_data"]
        except Exception as e:
            logger.error(f"TTS stream exception: {e}")

    return StreamingResponse(
        audio_generator(),
        media_type=content_type,
        headers={"Cache-Control": "no-cache"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status")
async def voice_status(session_id: Optional[str] = None):
    """Returns availability of STT and TTS services."""
    orchestrator = _get_orchestrator(session_id)
    has_orch = orchestrator is not None

    tasks_available = []
    if has_orch:
        # Try multiple ways the orchestrator might expose its registered tasks
        registered = set()
        try:
            if hasattr(orchestrator, 'registry'):
                reg = orchestrator.registry
                if hasattr(reg, 'list_tasks'):
                    registered = set(reg.list_tasks())
                elif hasattr(reg, 'tasks'):
                    registered = set(reg.tasks.keys())
                elif hasattr(reg, '_tasks'):
                    registered = set(reg._tasks.keys())
            elif hasattr(orchestrator, 'task_registry'):
                registered = set(orchestrator.task_registry.keys())
            elif hasattr(orchestrator, '_handlers'):
                registered = set(orchestrator._handlers.keys())
            elif hasattr(orchestrator, 'handlers'):
                registered = set(orchestrator.handlers.keys())
        except Exception as e:
            logger.warning(f"Could not enumerate tasks: {e}")

        logger.info(f"Registered tasks found: {registered}")
        VOICE_TASKS = ["whisper.transcribe", "whisper.tts", "tts.stream"]
        tasks_available = [t for t in VOICE_TASKS if t in registered]

    # Check for direct whisper fallback
    has_whisper_fallback = False
    try:
        import whisper  # noqa
        has_whisper_fallback = True
    except ImportError:
        pass

    # stt/tts available if tasks registered OR whisper package available as fallback
    stt_ok = (has_orch and "whisper.transcribe" in tasks_available) or has_whisper_fallback
    tts_ok = has_orch and ("whisper.tts" in tasks_available or "tts.stream" in tasks_available)

    return {
        "orchestrator": has_orch,
        "tasks_available": tasks_available,
        "stt_available": stt_ok,
        "tts_available": tts_ok,
        "tts_streaming_available": has_orch and "tts.stream" in tasks_available,
        "whisper_fallback": has_whisper_fallback,
    }