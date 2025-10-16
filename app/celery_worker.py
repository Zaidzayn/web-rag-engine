# app/celery_worker.py
from celery import Celery
from .config import settings
from .services import process_url_content
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

celery_app = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_track_started=True
)

@celery_app.task(name="process_ingestion_task")
def process_ingestion_task(document_id: str, url: str):
    logger.info(f"Starting ingestion task for document_id: {document_id}, url: {url}")
    process_url_content(document_id, url)
    logger.info(f"Finished ingestion task for document_id: {document_id}")