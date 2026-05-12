from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "DocIntel"
    app_env: str = "development"
    app_secret_key: str = "dev-secret-change-in-production"
    frontend_url: str = "http://localhost:5173"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/docintel.db"

    # AI - OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # JWT
    jwt_secret_key: str = "jwt-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # File Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # AWS S3 (optional)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # OCR
    tesseract_cmd: str = ""
    use_tesseract: bool = False

    # Rate Limiting
    rate_limit_per_minute: int = 60
    upload_rate_limit_per_minute: int = 10

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
