from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "real_estate_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
