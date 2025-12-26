"""Celery application configuration."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "collaborative_workspace",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task tracking
    task_track_started=True,

    # Reliability settings
    task_acks_late=True,  # Ack after task completion
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time for fair distribution

    # Result settings
    result_expires=86400,  # 24 hours

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Task routes (optional, for future scaling)
    # By default we'll use the default queue for simplicity in local development
    # task_routes={
    #     "app.workers.tasks.execute_code_task": {"queue": "code_execution"},
    #     "app.workers.tasks.process_generic_job": {"queue": "default"},
    # },
)


# Task error handling hooks
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}
