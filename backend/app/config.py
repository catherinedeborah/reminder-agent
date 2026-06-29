import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./reminder.db")
    VLLM_API_BASE: str = os.getenv("VLLM_API_BASE", "http://localhost:8100/v1")
    VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "mock-key")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "google/gemma-4-E4B-it")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-reminder-agent-key-change-in-prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 1 day

    class Config:
        env_file = ".env"

settings = Settings()
