from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "JagaWarga"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # WhatsApp Cloud API
    WA_PHONE_NUMBER_ID: str
    WA_ACCESS_TOKEN: str
    WA_VERIFY_TOKEN: str

    # Celery + Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # PostgreSQL + pgvector
    DATABASE_URL: str = "postgresql+asyncpg://jagawarga:password@localhost:5432/jagawarga"

    # IndoBERT
    CLASSIFIER_MODEL_PATH: str = "./models/indobert-intent"
    CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.65
    CLASSIFIER_DROP_THRESHOLD: float = 0.70

    # LLM
    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: str
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_TIMEOUT: int = 30

    # Semantic dedup
    DEDUP_SIMILARITY_THRESHOLD: float = 0.90
    DEDUP_CACHE_TTL: int = 604800

    # OCR
    OCR_PROVIDER: str = "llm"

    # External
    VIRUSTOTAL_API_KEY: str = ""

    SERPAPI_KEY: str

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()