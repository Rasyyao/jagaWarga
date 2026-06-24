from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "JagaWarga"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # KIRIM API KEY
    KIRIMI_ID_API_KEY : str
    KIRIMI_DEVICE_ID : str
    KIRIMI_USER_CODE : str
    WA_BOT_NUMBER: str = ""
    KIRIMI_BASE_URL: str = "https://api.kirimi.id"

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
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT: int = 30
    LLM_MAX_TOKENS: int = 4096

    # Semantic dedup
    DEDUP_SIMILARITY_THRESHOLD: float = 0.90
    DEDUP_CACHE_TTL: int = 604800

    # OCR
    OCR_PROVIDER: str = "llm"

    # External
    VIRUSTOTAL_API_KEY: str = ""

    SERPAPI_KEY: str

    # Agent Penipuan URL checker
    URL_CHECK_BROWSER: str = "firefox"
    URL_CHECK_HEADLESS: bool = True
    URL_CHECK_TIMEOUT_MS: int = 15000
    URL_CHECK_MAX_TEXT_CHARS: int = 6000
    URL_CHECK_USE_LLM: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
