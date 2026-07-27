from minio import Minio

from app.core.config import Settings, get_settings


def build_minio_client(settings: Settings | None = None) -> Minio:
    app_settings = settings or get_settings()
    return Minio(
        endpoint=app_settings.minio_endpoint,
        access_key=app_settings.minio_access_key,
        secret_key=app_settings.minio_secret_key,
        secure=app_settings.minio_secure,
    )
