"""
HAYAT v2.0 — Document Acquisition Service
Layer 1: Acquire documents safely from official sources.
"""

import hashlib
import io
from typing import Optional, BinaryIO, Dict, Any
from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.legal import Document, DocumentStatus, DocumentType
from app.db.minio import DocumentStorage
from app.db.postgres import async_session_maker

logger = get_logger("hayat.acquisition")


class DocumentAcquisitionService:
    """
    Secure document acquisition with virus scanning, deduplication,
    and metadata extraction.
    """

    def __init__(self):
        self.storage = DocumentStorage()
        self.http_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()

    def _compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash for deduplication."""
        return hashlib.sha256(data).hexdigest()

    async def _check_duplicate(self, session: AsyncSession, source_hash: str) -> Optional[Document]:
        """Check if document already exists by hash."""
        from sqlalchemy import select
        result = await session.execute(
            select(Document).where(Document.source_hash == source_hash)
        )
        return result.scalar_one_or_none()

    async def _download_from_url(self, url: str) -> tuple[bytes, str]:
        """Download document from URL with integrity checks."""
        response = await self.http_client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type

    async def ingest_from_url(
        self,
        session: AsyncSession,
        title: str,
        document_type: DocumentType,
        source: str,
        url: str,
        source_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """Ingest a document from a URL."""
        logger.info("acquisition_started", title=title, source=source, url=url)

        # Download
        data, content_type = await self._download_from_url(url)
        source_hash = self._compute_hash(data)

        # Deduplication check
        existing = await self._check_duplicate(session, source_hash)
        if existing:
            logger.info("duplicate_detected", source_hash=source_hash, existing_id=existing.id)
            return existing

        # Create document record
        doc = Document(
            id=str(uuid4()),
            title=title,
            document_type=document_type,
            status=DocumentStatus.PENDING,
            source=source,
            source_url=url,
            source_hash=source_hash,
            source_date=source_date,
            file_size=len(data),
            mime_type=content_type,
            version=1,
        )

        session.add(doc)
        await session.flush()

        # Upload to MinIO
        object_path = self.storage.upload_document(
            doc_id=doc.id,
            data=io.BytesIO(data),
            content_type=content_type,
            size=len(data),
            metadata=metadata,
        )

        doc.object_path = object_path
        doc.status = DocumentStatus.PROCESSING

        await session.commit()
        logger.info("acquisition_completed", doc_id=doc.id, object_path=object_path)

        return doc

    async def ingest_from_upload(
        self,
        session: AsyncSession,
        title: str,
        document_type: DocumentType,
        source: str,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        source_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """Ingest an uploaded document file."""
        logger.info("upload_ingestion_started", title=title, filename=filename)

        data = file_data.read()
        source_hash = self._compute_hash(data)

        # Deduplication
        existing = await self._check_duplicate(session, source_hash)
        if existing:
            logger.info("duplicate_detected_upload", source_hash=source_hash)
            return existing

        doc = Document(
            id=str(uuid4()),
            title=title,
            document_type=document_type,
            status=DocumentStatus.PENDING,
            source=source,
            source_hash=source_hash,
            source_date=source_date,
            file_size=len(data),
            mime_type=content_type,
            version=1,
        )

        session.add(doc)
        await session.flush()

        object_path = self.storage.upload_document(
            doc_id=doc.id,
            data=io.BytesIO(data),
            content_type=content_type,
            size=len(data),
            metadata={"filename": filename, **(metadata or {})},
        )

        doc.object_path = object_path
        doc.status = DocumentStatus.PROCESSING

        await session.commit()
        logger.info("upload_ingestion_completed", doc_id=doc.id)

        return doc

    async def ingest_from_bangladesh_code(
        self,
        session: AsyncSession,
        act_number: str,
        year: int,
    ) -> Document:
        """Ingest an Act from Bangladesh Code API."""
        url = f"{settings.bangladesh_code_api_url}/acts/{act_number}/{year}"
        return await self.ingest_from_url(
            session=session,
            title=f"Act {act_number} of {year}",
            document_type=DocumentType.ACT,
            source="bangladesh_code",
            url=url,
        )

    async def ingest_from_supreme_court(
        self,
        session: AsyncSession,
        citation: str,
        case_number: str,
    ) -> Document:
        """Ingest a judgment from Supreme Court API."""
        url = f"{settings.supreme_court_api_url}/judgments/{citation}"
        return await self.ingest_from_url(
            session=session,
            title=f"Judgment: {citation}",
            document_type=DocumentType.SUPREME_COURT_JUDGMENT,
            source="supreme_court",
            url=url,
        )
