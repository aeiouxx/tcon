from functools import lru_cache
from pydantic import BaseSettings, Field

# FIXME: One might argue that server and dispatcher should have
# their own configurations, however the intent is for these two
# applications to be tightly coupled


class Settings(BaseSettings):
    http_port: int = Field(
        6969, description="REST API port exposed by FastAPI")
    log_level: str = Field("DEBUG", description="Root log level")
    start_paused: bool = Field(
        default=True, description="Whether to pause the simulation on launch (WARNING: will need to be unpaused manually!)")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
