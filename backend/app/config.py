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

    # Jira integration
    JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "")
    JIRA_PAT_TOKEN: str = os.getenv("JIRA_PAT_TOKEN", "")

    # Slack integration
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")

    # SMTP configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    class Config:
        env_file = ".env"

settings = Settings()
