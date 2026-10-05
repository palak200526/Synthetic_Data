import os

from celery import Celery

_BROKER = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")
_BACKEND = os.getenv("REDIS_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "datrixa",
    broker=_BROKER,
    backend=_BACKEND,
    include=["backend.worker.tasks"],
)


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Celery 6.0 deprecation warning fix
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,

    # Long-running tasks (LLM, model training)
    task_time_limit=3600,
    task_soft_time_limit=3300,

    # Result expiry
    result_expires=3600,

    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)