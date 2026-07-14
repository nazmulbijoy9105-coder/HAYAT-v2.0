"""
HAYAT v2.0 — OpenSearch Full-Text Engine
Legal document search with relevance ranking and highlighting.
"""

from typing import Dict, Any, List, Optional

from opensearchpy import AsyncOpenSearch
from opensearchpy.exceptions import NotFoundError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("hayat.db.opensearch")

_client: Optional[AsyncOpenSearch] = None

INDEX_CASES = f"{settings.opensearch_index_prefix}-cases"
INDEX_STATUTES = f"{settings.opensearch_index_prefix}-statutes"
INDEX_JUDGMENTS = f"{settings.opensearch_index_prefix}-judgments"
INDEX_DOCUMENTS = f"{settings.opensearch_index_prefix}-documents"


def get_opensearch_client() -> AsyncOpenSearch:
    """Get or create OpenSearch client."""
    global _client
    if _client is None:
        _client = AsyncOpenSearch(
            hosts=settings.opensearch_hosts,
            timeout=settings.opensearch_timeout,
            max_retries=settings.opensearch_max_retries,
            retry_on_timeout=True,
        )
    return _client


async def init_opensearch() -> None:
    """Initialize OpenSearch indices with legal-optimized mappings."""
    client = get_opensearch_client()

    # Case index mapping
    case_mapping = {
        "settings": {
            "number_of_shards": 3,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "legal_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop", "stemmer", "word_delimiter"],
                    },
                    "bengali_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase"],
                    },
                },
            },
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "analyzer": "legal_analyzer",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "citation": {"type": "keyword"},
                "case_number": {"type": "keyword"},
                "date": {"type": "date"},
                "court": {"type": "keyword"},
                "court_level": {"type": "keyword"},
                "bench": {"type": "keyword"},
                "area_of_law": {"type": "keyword"},
                "judge": {"type": "keyword"},
                "parties": {"type": "keyword"},
                "lawyers": {"type": "keyword"},
                "summary": {"type": "text", "analyzer": "legal_analyzer"},
                "full_text": {"type": "text", "analyzer": "legal_analyzer"},
                "ratio": {"type": "text", "analyzer": "legal_analyzer"},
                "obiter": {"type": "text", "analyzer": "legal_analyzer"},
                "held": {"type": "text", "analyzer": "legal_analyzer"},
                "statutes_cited": {"type": "keyword"},
                "cases_cited": {"type": "keyword"},
                "relief": {"type": "text"},
                "status": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "embedding_vector": {"type": "knn_vector", "dimension": settings.qdrant_vector_size},
            }
        },
    }

    # Statute index mapping
    statute_mapping = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "legal_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop", "stemmer"],
                    },
                },
            },
        },
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "legal_analyzer"},
                "act_number": {"type": "keyword"},
                "year": {"type": "integer"},
                "preamble": {"type": "text", "analyzer": "legal_analyzer"},
                "full_text": {"type": "text", "analyzer": "legal_analyzer"},
                "status": {"type": "keyword"},
                "sections": {
                    "type": "nested",
                    "properties": {
                        "number": {"type": "keyword"},
                        "title": {"type": "text"},
                        "text": {"type": "text", "analyzer": "legal_analyzer"},
                    },
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        },
    }

    indices = {
        INDEX_CASES: case_mapping,
        INDEX_STATUTES: statute_mapping,
        INDEX_JUDGMENTS: case_mapping,  # Reuse case mapping for judgments
        INDEX_DOCUMENTS: {
            "settings": {"number_of_shards": 2, "number_of_replicas": 1},
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "content": {"type": "text", "analyzer": "legal_analyzer"},
                    "document_type": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "date": {"type": "date"},
                    "created_at": {"type": "date"},
                }
            },
        },
    }

    for index_name, mapping in indices.items():
        try:
            exists = await client.indices.exists(index=index_name)
            if not exists:
                await client.indices.create(index=index_name, body=mapping)
                logger.info("opensearch_index_created", index=index_name)
            else:
                logger.info("opensearch_index_exists", index=index_name)
        except Exception as e:
            logger.error("opensearch_index_error", index=index_name, error=str(e))

    logger.info("opensearch_initialized")


async def close_opensearch() -> None:
    """Close OpenSearch connection."""
    global _client
    if _client:
        await _client.close()
        _client = None
        logger.info("opensearch_closed")


class SearchEngine:
    """
    Legal search engine with boolean, semantic, and citation network search.
    """

    def __init__(self):
        self.client = get_opensearch_client()

    async def search_cases(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Dict[str, str]]] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Search cases with relevance scoring."""
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "summary^2", "full_text", "ratio^2", "held^2"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]

        filter_clauses = []
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    filter_clauses.append({"terms": {key: value}})
                else:
                    filter_clauses.append({"term": {key: value}})

        body = {
            "from": (page - 1) * size,
            "size": size,
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "highlight": {
                "fields": {
                    "title": {},
                    "summary": {"fragment_size": 300, "number_of_fragments": 3},
                    "full_text": {"fragment_size": 300, "number_of_fragments": 3},
                    "ratio": {"fragment_size": 200, "number_of_fragments": 2},
                }
            },
            "sort": sort or [{"_score": {"order": "desc"}}, {"date": {"order": "desc"}}],
        }

        response = await self.client.search(index=INDEX_CASES, body=body)
        return {
            "total": response["hits"]["total"]["value"],
            "page": page,
            "size": size,
            "results": [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "source": hit["_source"],
                    "highlights": hit.get("highlight", {}),
                }
                for hit in response["hits"]["hits"]
            ],
        }

    async def search_statutes(
        self,
        query: str,
        year: Optional[int] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Search statutes and sections."""
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "preamble^2", "full_text", "sections.text"],
                    "type": "best_fields",
                }
            }
        ]

        filter_clauses = []
        if year:
            filter_clauses.append({"term": {"year": year}})

        body = {
            "from": (page - 1) * size,
            "size": size,
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
            "highlight": {
                "fields": {
                    "title": {},
                    "preamble": {"fragment_size": 300},
                    "full_text": {"fragment_size": 300, "number_of_fragments": 3},
                }
            },
        }

        response = await self.client.search(index=INDEX_STATUTES, body=body)
        return {
            "total": response["hits"]["total"]["value"],
            "page": page,
            "size": size,
            "results": [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "source": hit["_source"],
                    "highlights": hit.get("highlight", {}),
                }
                for hit in response["hits"]["hits"]
            ],
        }

    async def index_document(self, index: str, doc_id: str, document: Dict[str, Any]) -> None:
        """Index a document in OpenSearch."""
        await self.client.index(index=index, id=doc_id, body=document)

    async def delete_document(self, index: str, doc_id: str) -> None:
        """Delete a document from OpenSearch."""
        try:
            await self.client.delete(index=index, id=doc_id)
        except NotFoundError:
            pass
