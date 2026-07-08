import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_bearer_token: str | None = None
    max_image_mb: float = 5.0
    log_level: str = "INFO"
    provider: str = "mock"
    version: str = "phase-1"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_bearer_token=os.getenv("API_BEARER_TOKEN") or None,
            max_image_mb=float(os.getenv("MAX_IMAGE_MB", "5.0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            provider=os.getenv("MODEL_PROVIDER", "mock"),
            version=os.getenv("BACKEND_VERSION", "phase-1"),
        )


def get_settings() -> Settings:
    return Settings.from_env()
