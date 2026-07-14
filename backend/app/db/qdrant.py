"""
HAYAT v2.0 — Qdrant Vector Database
Semantic search and legal embeddings.
"""

from typing import List, Dict, Any, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("hayat.db.qdrant")

_client: Optional[AsyncQdrantClient] = None
COLLECTION_NAME = settings.qdrant_collection


def get_qdrant_client() -> AsyncQdrantClient:
    """Get or create Qdrant async client."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            grpc_port=settings.qdrant_grpc_port,
            api_key=settings.qdrant_api_key,
            prefer_grpc=True,
        )
    return _client


async def init_qdrant() -> None:
    """Initialize Qdrant collection for legal embeddings."""
    client = get_qdrant_client()

    collections = await client.get_collections()
    collection_names = [c.name for c in collections.collections]

    if COLLECTION_NAME not in collection_names:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=settings.qdrant_vector_size,
                distance=Distance.COSINE,
            ),
        )

        # Payload indexes for filtering
        await client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="document_type",
            field_type="keyword",
        )
        await client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="court_level",
            field_type="keyword",
        )
        await client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="date",
            field_type="integer",
        )

        logger.info("qdrant_collection_created", collection=COLLECTION_NAME)
    else:
        logger.info("qdrant_collection_exists", collection=COLLECTION_NAME)


async def close_qdrant() -> None:
    """Close Qdrant client."""
    global _client
    if _client:
        await _client.close()
        _client = None
        logger.info("qdrant_closed")


class EmbeddingStore:
    """
    Store and retrieve legal document embeddings.
    """

    def __init__(self):
        self.client = get_qdrant_client()

    async def upsert(
        self,
        points: List[PointStruct],
    ) -> None:
        """Upsert embedding vectors."""
        await self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )

    async def search(
        self,
        vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Semantic search by vector similarity."""
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            qdrant_filter = Filter(must=conditions)

        results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            limit=limit,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload,
            }
            for r in results
        ]

    async def delete_by_filter(self, key: str, value: Any) -> None:
        """Delete points by payload filter."""
        await self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key=key, match=MatchValue(value=value))]
            ),
        )
