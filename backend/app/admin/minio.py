import io
import logging
import uuid

from minio import Minio

from app.admin.config import MinioConfig

logger = logging.getLogger(__name__)


class MinioClient:
    def __init__(self, config: MinioConfig):
        self._client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        self._bucket = config.bucket
        self._bucket_ready = False
        try:
            self._ensure_bucket()
            self._bucket_ready = True
        except Exception as e:
            logger.warning("MinIO not available during startup (%s), will retry on first use", e)

    def _ensure_bucket(self):
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("Created MinIO bucket: %s", self._bucket)

    def _maybe_init_bucket(self):
        if not self._bucket_ready:
            self._ensure_bucket()
            self._bucket_ready = True

    def upload(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._maybe_init_bucket()
        self._client.put_object(
            self._bucket,
            object_key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get_presigned_url(self, object_key: str, expires_hours: int = 1) -> str:
        from datetime import timedelta

        self._maybe_init_bucket()
        return self._client.presigned_get_object(self._bucket, object_key, expires=timedelta(hours=expires_hours))

    def download(self, object_key: str) -> bytes:
        self._maybe_init_bucket()
        response = self._client.get_object(self._bucket, object_key)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    def delete(self, object_key: str) -> None:
        self._client.remove_object(self._bucket, object_key)

    @property
    def bucket(self) -> str:
        return self._bucket

    def build_skill_key(self, department_id: uuid.UUID | None, skill_id: uuid.UUID, filename: str) -> str:
        dept = str(department_id) if department_id else "global"
        return f"skills/{dept}/{skill_id}/{filename}"
