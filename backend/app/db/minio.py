"""
HAYAT v2.0 — MinIO Object Storage
PDFs, images, and original legal documents.
"""

from typing import Optional, BinaryIO
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("hayat.db.minio")

_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Get or create MinIO client."""
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


async def init_minio() -> None:
    """Initialize MinIO bucket."""
    client = get_minio_client()
    bucket = settings.minio_bucket

    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        # Set bucket policy for read-only access to authenticated users
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        client.set_bucket_policy(bucket, str(policy).replace("'", '"'))
        logger.info("minio_bucket_created", bucket=bucket)
    else:
        logger.info("minio_bucket_exists", bucket=bucket)


class DocumentStorage:
    """
    MinIO-backed document storage with versioning support.
    """

    def __init__(self):
        self.client = get_minio_client()
        self.bucket = settings.minio_bucket

    def upload_document(
        self,
        doc_id: str,
        data: BinaryIO,
        content_type: str,
        size: int,
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload a document to MinIO."""
        object_name = f"documents/{doc_id}/original.pdf"

        self.client.put_object(
            self.bucket,
            object_name,
            data,
            size,
            content_type=content_type,
            metadata=metadata or {},
        )

        logger.info("document_uploaded", doc_id=doc_id, object_name=object_name)
        return object_name

    def get_presigned_url(self, object_name: str, expiry: int = 3600) -> str:
        """Get presigned URL for document access."""
        return self.client.presigned_get_object(
            self.bucket,
            object_name,
            expires=timedelta(seconds=expiry),
        )

    def download_document(self, object_name: str) -> bytes:
        """Download document bytes."""
        response = self.client.get_object(self.bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    def delete_document(self, object_name: str) -> None:
        """Delete document from storage."""
        self.client.remove_object(self.bucket, object_name)
        logger.info("document_deleted", object_name=object_name)

    def document_exists(self, object_name: str) -> bool:
        """Check if document exists."""
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False
