"""Central application settings, loaded from the environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "NIRVAAN"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "dev-only-insecure-secret-key-change-me"

    # Database
    database_url: str = "postgresql+psycopg://nirvaan:nirvaan@localhost:5432/nirvaan"
    use_sqlite_fallback: bool = True
    sqlite_path: str = "data/nirvaan.db"

    # Sessions / security
    session_cookie_name: str = "nirvaan_session"
    session_ttl_hours: int = 72
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    csrf_cookie_name: str = "nirvaan_csrf"
    rate_limit_login_per_min: int = 5
    rate_limit_api_per_min: int = 60

    # Redis (optional). Empty = single-process in-memory fallbacks for rate
    # limits, the shared cache and the job queue. See requirements-redis.txt.
    redis_url: str = ""

    # AI
    ai_provider_order: str = "ollama,local"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: int = 120
    ollama_embed_model: str = "qwen2.5:7b"

    # Market data
    market_data_provider: str = "mock"
    market_data_api_key: str = ""
    market_data_base_url: str = ""

    # Mail
    mail_backend: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "no-reply@nirvaan.local"

    # Uploads
    upload_dir: str = "data/uploads"
    max_upload_mb: int = 10

    # Walkthrough video linked from the landing hero ("Watch Demo").
    # Empty disables the button instead of sending people to a dead link.
    demo_video_url: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def provider_order(self) -> list[str]:
        return [p.strip() for p in self.ai_provider_order.split(",") if p.strip()]

    @property
    def effective_database_url(self) -> str:
        """Postgres is the intended target; SQLite is an explicit dev fallback."""
        if self.use_sqlite_fallback:
            path = (BASE_DIR / self.sqlite_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+pysqlite:///{path.as_posix()}"
        return self.database_url

    @property
    def is_sqlite(self) -> bool:
        return self.effective_database_url.startswith("sqlite")

    @property
    def upload_path(self) -> Path:
        p = BASE_DIR / self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
