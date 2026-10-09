"""Server-side configuration. Secrets are never exported through REST."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", case_sensitive=False, env_ignore_empty=True
    )
    database_url: str = f"sqlite+aiosqlite:///{(PROJECT_ROOT / 'artifacts' / 'creditops.db').as_posix()}"
    telemetry_mode: Literal["persisted", "kafka"] = "persisted"
    kafka_bootstrap_servers: str = "127.0.0.1:19092"
    ai_provider: Literal["openai", "anthropic"] = "openai"
    openai_model: str = ""
    anthropic_model: str = ""
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    admin_api_key: SecretStr | None = None
    investigation_timeout_seconds: float = Field(default=45, ge=1, le=300)
    max_investigations_per_window: int = Field(default=8, ge=1, le=100)
    rate_limit_window_seconds: float = Field(default=60, ge=1, le=3600)
    replay_dir: Path = PROJECT_ROOT / "data" / "replay"
    project_root: Path = PROJECT_ROOT
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    max_request_bytes: int = Field(default=16384, ge=1024, le=65536)
    openai_input_usd_per_million: float | None = Field(default=None, ge=0)
    openai_output_usd_per_million: float | None = Field(default=None, ge=0)
    anthropic_input_usd_per_million: float | None = Field(default=None, ge=0)
    anthropic_output_usd_per_million: float | None = Field(default=None, ge=0)
    database_require_ssl: bool = False
    embeddings_enabled: bool = False
    public_demo: bool = True
    embedding_model: str = ""
    embedding_dimensions: int = Field(default=1536, ge=1, le=4096)


@lru_cache
def get_settings() -> Settings:
    return Settings()
