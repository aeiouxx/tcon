from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    http_port: int = Field(
        6969, description="REST API port exposed by FastAPI")
    log_level: str = Field("DEBUG", description="Root log level")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
