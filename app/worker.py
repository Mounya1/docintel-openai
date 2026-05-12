"""
Celery Worker — optional async task queue for heavy processing.

Usage:
  celery -A app.worker worker --loglevel=info --concurrency=4

When Redis is available, document processing runs via Celery tasks
instead of FastAPI BackgroundTasks. This allows:
  - Horizontal scaling of workers
  - Task retry with backoff
  - Progress monitoring
  - Dead-letter queue for failed jobs
"""

import asyncio
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery = Celery(
    "docintel",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_max_retries=3,
    task_default_retry_delay=30,
)


@celery.task(bind=True, max_retries=3, default_retry_delay=30, name="docintel.process_document")
def process_document_task(self, document_id: str, uploader_id: str = "system"):
    """Celery task wrapper for the async pipeline."""
    try:
        asyncio.run(_async_process(document_id, uploader_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)


async def _async_process(document_id: str, uploader_id: str):
    from app.database import AsyncSessionLocal
    from app.services.pipeline import process_document
    async with AsyncSessionLocal() as session:
        await process_document(document_id, session, uploader_id)
