Running the System

Start Redis:

redis-server

Start Celery GPU worker:

celery -A tasks worker --loglevel=info --concurrency=1

(concurrency 1 prevents GPU contention)

Start API server:

uvicorn api:app --host 0.0.0.0 --port 8000

Scaling GPU Workers

Run multiple workers on different machines:

celery -A tasks worker --hostname=gpu1@%h
celery -A tasks worker --hostname=gpu2@%h

They will all pull jobs from Redis.

Optional Redis Streaming Improvement

For higher performance streaming you can also publish transcripts:

redis.publish("whisper_stream", text)

Then multiple subscribers (UI, logging, etc.) receive live transcripts.

Recommended Production Improvements
1. GPU isolation
CUDA_VISIBLE_DEVICES=0 celery -A tasks worker
CUDA_VISIBLE_DEVICES=1 celery -A tasks worker
2. GPU batching (big speed boost)

Use:

vLLM style batching

diffusers pipeline batching

3. Redis task priority queues
celery -Q whisper
celery -Q diffusion
4. Job cancellation

Store task_id and call:

app.control.revoke(task_id, terminate=True)
Result

You now have a microservice GPU inference platform that supports:

async job queue

GPU workers

stable diffusion

whisper

streaming transcription

horizontal scaling