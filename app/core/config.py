from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_SQLITE_PATH = DEFAULT_DATA_DIR / "app.db"


class Settings(BaseSettings):
    app_name: str = "Novel Multi-Agent Backend V15 Diagnostics P0"
    app_version: str = "0.15.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    auto_create_tables: bool = True

    agent_provider: str = "mock"
    agent_model: str = "mock-creative-writer-v1"
    agent_api_base_url: str | None = None
    agent_api_key: str | None = None
    agent_timeout_seconds: float = Field(default=45.0, ge=5.0, le=300.0)
    agent_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    agent_fallback_to_mock: bool = True
    agent_log_string_limit: int = Field(default=300, ge=50, le=2000)
    agent_log_collection_limit: int = Field(default=5, ge=1, le=20)

    agent_max_retries: int = Field(default=2, ge=0, le=6)
    agent_retry_backoff_ms: int = Field(default=800, ge=50, le=10000)
    agent_retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)
    agent_retry_on_statuses: str = "408,409,429,500,502,503,504"

    agent_enable_rate_limit: bool = True
    agent_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)

    agent_enable_circuit_breaker: bool = True
    agent_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    agent_circuit_cooldown_seconds: int = Field(default=60, ge=5, le=3600)
    agent_circuit_half_open_max_calls: int = Field(default=1, ge=1, le=10)

    publish_require_quality_delta: bool = False
    publish_delta_similarity_threshold: float = Field(default=0.98, ge=0.0, le=1.0)
    publish_delta_min_changed_paragraphs: int = Field(default=1, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def agent_retryable_status_codes(self) -> set[int]:
        result: set[int] = set()
        for item in self.agent_retry_on_statuses.split(","):
            raw = item.strip()
            if not raw:
                continue
            try:
                result.add(int(raw))
            except ValueError:
                continue
        return result


settings = Settings()
