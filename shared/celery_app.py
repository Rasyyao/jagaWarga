from celery import Celery
from shared.config import get_settings

settings = get_settings()

celery_app = Celery(
    "jagawarga",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["agent_input_handler.tasks"],
)

