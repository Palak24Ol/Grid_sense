"""
config.py — Environment configuration using Pydantic BaseSettings.

All values come from environment variables or .env file.
Copy .env.example → .env and fill in values before running.
"""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://gridsense:gridsense@localhost:5432/gridsense"

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ── Artifact directory ─────────────────────────────────────────────────────
    # Absolute path to ml/artifacts/ — resolved relative to this file if relative
    ARTIFACT_DIR: str = str(Path(__file__).parent.parent / "ml" / "artifacts")

    # ── Environment ────────────────────────────────────────────────────────────
    ENV: str = "development"  # development | production

    # ── Mock mode ──────────────────────────────────────────────────────────────
    # Set to "true" to serve mock predictions before artifacts are trained
    MOCK_MODE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def artifact_path(self) -> Path:
        return Path(self.ARTIFACT_DIR)

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance. Call this everywhere instead of Settings()."""
    return Settings()