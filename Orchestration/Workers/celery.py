from celery import Celery

celery = Celery(
    "gpu_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)