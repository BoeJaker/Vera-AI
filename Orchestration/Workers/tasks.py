import io
import torch
from PIL import Image
from celery_app import celery

from diffusers import StableDiffusionPipeline
from faster_whisper import WhisperModel


device = "cuda" if torch.cuda.is_available() else "cpu"

sd_pipe = None
whisper_model = None


def load_models():
    global sd_pipe, whisper_model

    if sd_pipe is None:
        sd_pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16
        ).to(device)

    if whisper_model is None:
        whisper_model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16"
        )


@celery.task(bind=True)
def generate_image(self, prompt):

    load_models()

    image = sd_pipe(prompt).images[0]

    buf = io.BytesIO()
    image.save(buf, format="PNG")

    return buf.getvalue().hex()


@celery.task(bind=True)
def transcribe_audio(self, audio_bytes):

    load_models()

    audio_stream = io.BytesIO(bytes.fromhex(audio_bytes))

    segments, info = whisper_model.transcribe(audio_stream)

    text = ""
    for seg in segments:
        text += seg.text

    return text