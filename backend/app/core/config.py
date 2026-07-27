from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Quotify", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_version: str = "0.1.0"
    app_timezone: str = Field(default="Asia/Ho_Chi_Minh", alias="APP_TIMEZONE")

    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")  # nosec B104
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_secret_key_file: str | None = Field(default=None, alias="JWT_SECRET_KEY_FILE")
    jwt_refresh_secret_key: str = Field(
        default="change-me-too",
        alias="JWT_REFRESH_SECRET_KEY",
    )
    jwt_refresh_secret_key_file: str | None = Field(
        default=None,
        alias="JWT_REFRESH_SECRET_KEY_FILE",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )
    auth_token_transport: str = Field(default="hybrid", alias="AUTH_TOKEN_TRANSPORT")
    auth_refresh_cookie_name: str = Field(
        default="quotify_refresh_token",
        alias="AUTH_REFRESH_COOKIE_NAME",
    )
    auth_logged_in_cookie_name: str = Field(
        default="quotify_logged_in",
        alias="VITE_AUTH_LOGGED_IN_COOKIE_NAME",
    )
    auth_refresh_cookie_secure: bool = Field(
        default=False,
        alias="AUTH_REFRESH_COOKIE_SECURE",
    )
    auth_refresh_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        alias="AUTH_REFRESH_COOKIE_SAMESITE",
    )
    auth_refresh_cookie_path: str = Field(
        default="/api/v1/auth",
        alias="AUTH_REFRESH_COOKIE_PATH",
    )
    auth_seed_admin_email: str = Field(
        default="admin@quotify.local",
        alias="AUTH_SEED_ADMIN_EMAIL",
    )
    auth_seed_admin_password: str = Field(
        default="change-me-admin-password",
        alias="AUTH_SEED_ADMIN_PASSWORD",
    )
    auth_seed_update_admin_password: bool = Field(
        default=False,
        alias="AUTH_SEED_UPDATE_ADMIN_PASSWORD",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/app",
        alias="DATABASE_URL",
    )
    database_url_file: str | None = Field(default=None, alias="DATABASE_URL_FILE")

    minio_endpoint: str = Field(default="minio:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_access_key_file: str | None = Field(default=None, alias="MINIO_ACCESS_KEY_FILE")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_secret_key_file: str | None = Field(default=None, alias="MINIO_SECRET_KEY_FILE")
    minio_bucket: str = Field(default="app-local", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    smtp_host: str = Field(default="mailpit", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_secure: bool = Field(default=False, alias="SMTP_SECURE")
    smtp_from_email: str = Field(default="noreply@quotify.local", alias="SMTP_FROM_EMAIL")
    admin_email_for_backups: str = Field(
        default="admin@quotify.local", alias="ADMIN_EMAIL_FOR_BACKUPS"
    )

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        alias="CORS_ORIGINS",
    )
    trusted_proxy_cidrs: str = Field(default="", alias="TRUSTED_PROXY_CIDRS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["plain", "json"] = Field(default="json", alias="LOG_FORMAT")
    security_headers_enabled: bool = Field(
        default=True,
        alias="SECURITY_HEADERS_ENABLED",
    )
    security_hsts_enabled: bool = Field(
        default=False,
        alias="SECURITY_HSTS_ENABLED",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        alias="RATE_LIMIT_WINDOW_SECONDS",
    )
    rate_limit_auth_login: int = Field(
        default=5,
        alias="RATE_LIMIT_AUTH_LOGIN",
    )
    rate_limit_files_upload: int = Field(
        default=10,
        alias="RATE_LIMIT_FILES_UPLOAD",
    )
    rate_limit_users_avatar_upload: int = Field(
        default=10,
        alias="RATE_LIMIT_USERS_AVATAR_UPLOAD",
    )
    rate_limit_users_import: int = Field(
        default=5,
        alias="RATE_LIMIT_USERS_IMPORT",
    )
    rate_limit_users_export: int = Field(
        default=10,
        alias="RATE_LIMIT_USERS_EXPORT",
    )
    observability_enabled: bool = Field(default=True, alias="OBSERVABILITY_ENABLED")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    metrics_path: str = Field(default="/metrics", alias="METRICS_PATH")
    readiness_path: str = Field(default="/ready", alias="READINESS_PATH")
    otel_enabled: bool = Field(default=True, alias="OTEL_ENABLED")
    otel_service_name: str = Field(
        default="quotify-backend",
        alias="OTEL_SERVICE_NAME",
    )
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    otel_exporter_otlp_insecure: bool = Field(
        default=True,
        alias="OTEL_EXPORTER_OTLP_INSECURE",
    )
    otel_exporter_otlp_headers: str | None = Field(
        default=None,
        alias="OTEL_EXPORTER_OTLP_HEADERS",
    )
    slo_api_availability_target: float = Field(
        default=99.9,
        alias="SLO_API_AVAILABILITY_TARGET",
    )
    slo_api_p95_ms: int = Field(default=400, alias="SLO_API_P95_MS")
    slo_auth_login_p95_ms: int = Field(default=500, alias="SLO_AUTH_LOGIN_P95_MS")
    slo_import_job_success_rate: float = Field(
        default=99.0,
        alias="SLO_IMPORT_JOB_SUCCESS_RATE",
    )
    backup_root: str = Field(default="./backups", alias="BACKUP_ROOT")
    backup_retention_days: int = Field(default=14, alias="BACKUP_RETENTION_DAYS")

    def model_post_init(self, __context: object) -> None:
        self._apply_secret_file("jwt_secret_key", self.jwt_secret_key_file)
        self._apply_secret_file("jwt_refresh_secret_key", self.jwt_refresh_secret_key_file)
        self._apply_secret_file("database_url", self.database_url_file)
        self._apply_secret_file("minio_access_key", self.minio_access_key_file)
        self._apply_secret_file("minio_secret_key", self.minio_secret_key_file)

    def _apply_secret_file(self, field_name: str, secret_file: str | None) -> None:
        if not secret_file:
            return

        secret_path = Path(secret_file)
        secret_value = secret_path.read_text(encoding="utf-8").strip()
        if not secret_value:
            raise ValueError(f"Secret file for {field_name} is empty: {secret_file}")
        object.__setattr__(self, field_name, secret_value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
