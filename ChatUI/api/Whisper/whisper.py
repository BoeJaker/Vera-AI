from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, FileResponse
from openai import OpenAI
import uuid
import os
import io
import asyncio

router = APIRouter()
client = OpenAI()

# Directory to store generated audio (if needed)
AUDIO_DIR = "generated_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)


@router.get("/tts")
async def text_to_speech(
    text: str = Query(..., description="Text to convert to speech"),
    stream: bool = Query(False, description="Stream audio chunks instead of returning full file"),
    voice: str = Query("alloy", description="Voice ID"),
    format: str = Query("mp3", description="Audio format: mp3/wav/ogg/etc"),
):
    """
    Convert text → speech using Whisper (gpt-4o-mini-tts / gpt-4o-audio-preview)
    Supports:
      - StreamingResponse (chunked)
      - Full file response
    """

    if stream:
        async def audio_stream_generator():
            """Stream audio chunks as they're generated."""
            response = client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,
                format=format
            )

            # iterate over chunks
            async for chunk in response.iter_bytes():
                yield chunk
        
        return StreamingResponse(
            audio_stream_generator(),
            media_type=f"audio/{format}"
        )

    else:
        # Generate full audio file
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
            format=format
        )

        audio_bytes = response.read()
        file_id = f"tts_{uuid.uuid4()}.{format}"
        output_path = os.path.join(AUDIO_DIR, file_id)

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return FileResponse(
            output_path,
            media_type=f"audio/{format}",
            filename=file_id
        )
