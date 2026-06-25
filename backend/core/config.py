from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Interviewer Backend"
    PORT: int = 8000

    HF_TOKEN: str = ""
    HF_FALLBACK_TOKEN: Optional[str] = None
    HF_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    HF_FALLBACK_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    INFERENCE_PROVIDER: str = "hf"  # set to "local" to use a self-hosted inference endpoint
    LOCAL_INFERENCE_URL: Optional[str] = None
    LOCAL_INFERENCE_TOKEN: Optional[str] = None

    DATABASE_URL: str = ""
    DB_MIN_CONNECTIONS: int = 2
    DB_MAX_CONNECTIONS: int = 10

    MAX_QUESTIONS_DEFAULT: int = 8
    MAX_RETRIES: int = 3
    RETRY_DELAY_MS: int = 1000
    REQUEST_TIMEOUT_SECONDS: int = 60

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    class Config:
        env_file = ".env"


settings = Settings()
