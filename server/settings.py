from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Drupal DevOps Co-Pilot API"
    API_PREFIX: str = "/api"

    # CORS for Next.js dev
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@db:5432/copilot"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
