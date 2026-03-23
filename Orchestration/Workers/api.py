import io
import redis
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response

from tasks import generate_image, transcribe_audio
from celery.result import AsyncResult

app = FastAPI()

r = redis.Redis(host="localhost", port=6379)


@app.post("/image")
async def create_image(prompt: str):

    task = generate_image.delay(prompt)

    return {"task_id": task.id}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):

    audio_bytes = await file.read()

    task = transcribe_audio.delay(audio_bytes.hex())

    return {"task_id": task.id}


@app.get("/result/{task_id}")
async def get_result(task_id: str):

    result = AsyncResult(task_id)

    if result.ready():

        data = result.result

        if isinstance(data, str) and len(data) > 1000:
            return Response(bytes.fromhex(data), media_type="image/png")

        return {"result": data}

    return {"status": result.status}

from whisper_stream import stream

@app.websocket("/whisper-stream")
async def whisper_stream(ws):
    await stream(ws)