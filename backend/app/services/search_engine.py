"""
HAYAT v2.0 — Legal Research Engine
Layer 6: Multi-modal search (text, semantic, citation, boolean, timeline).
"""

from typing import Dict, Any, List, Optional
import hashlib
import json

from app.core.config import settings
from app.core.logging import get_logger
from app.db.opensearch import SearchEngine as OpenSearchEngine, INDEX_CASES, INDEX_STATUTES
from app.db.qdrant import EmbeddingStore
from app.db.redis import CacheManager
from app.models.legal import CourtLevel

logger = get_logger("hayat.search")


class LegalSearchEngine:
    """
    Unified legal search combining:
    - Full-text (OpenSearch)
    - Semantic (Qdrant embeddings)
    - Citation network (Neo4j)
    - Boolean logic
    - Timeline filtering
    """

    def __init__(self):
        self.opensearch = OpenSearchEngine()
        self.embeddings = EmbeddingStore()
        self.cache = CacheManager()

    def _hash_query(self, query: str, filters: Optional[dict], page: int, size: int) -> str:
        """Generate cache key for search query."""
        key_data = f"{query}:{json.dumps(filters, sort_keys=True)}:{page}:{size}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    async def search_cases(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Dict[str, str]]] = None,
        page: int = 1,
        size: int = 20,
        use_semantic: bool = False,
    ) -> Dict[str, Any]:
        """Search cases with caching and optional semantic boost."""
        query_hash = self._hash_query(query, filters, page, size)

        # Check cache
        cached = await self.cache.get_search_results(query_hash)
        if cached:
            logger.info("search_cache_hit", query_hash=query_hash)
            return cached

        # Full-text search
        results = await self.opensearch.search_cases(
            query=query,
            filters=filters,
            sort=sort,
            page=page,
            size=size,
        )

        # Semantic search if enabled
        semantic_results = None
        if use_semantic and settings.enable_ai_layer:
            try:
                from app.services.ai_layer import AILayer
                ai = AILayer()
                vector = await ai.get_embedding(query)
                semantic_results_raw = await self.embeddings.search(
                    vector=vector,
                    limit=size,
                    filters={"document_type": "case"},
                )
                semantic_results = [
                    {
                        "id": r["id"],
                        "score": r["score"],
                        "source": r["payload"],
                    }
                    for r in semantic_results_raw
                ]
            except Exception as e:
                logger.warning("semantic_search_failed", error=str(e))

        response = {
            **results,
            "semantic_results": semantic_results,
        }

        # Cache results
        await self.cache.cache_search_results(query_hash, response)

        logger.info("search_completed", query=query[:50], total=results["total"], page=page)
        return response

    async def search_statutes(
        self,
        query: str,
        year: Optional[int] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Search statutes."""
        return await self.opensearch.search_statutes(
            query=query,
            year=year,
            page=page,
            size=size,
        )

    async def search_by_citation(self, citation: str) -> Optional[Dict[str, Any]]:
        """Exact citation lookup."""
        results = await self.opensearch.search_cases(
            query=citation,
            filters={"citation": citation},
            size=1,
        )
        if results["results"]:
            return results["results"][0]
        return None

    async def search_by_judge(self, judge_name: str, page: int = 1, size: int = 20) -> Dict[str, Any]:
        """Search cases by judge name."""
        return await self.opensearch.search_cases(
            query=judge_name,
            filters={"judge": judge_name},
            page=page,
            size=size,
        )

    async def search_by_section(self, act: str, section: str) -> Dict[str, Any]:
        """Search cases citing a specific section."""
        query = f'"Section {section} of the {act}"'
        return await self.opensearch.search_cases(
            query=query,
            page=1,
            size=50,
        )

    async def boolean_search(
        self,
        must_terms: List[str],
        should_terms: Optional[List[str]] = None,
        must_not_terms: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Boolean search with must/should/must_not clauses."""
        must_clauses = [
            {"match": {"full_text": term}} for term in must_terms
        ]

        should_clauses = []
        if should_terms:
            should_clauses = [
                {"match": {"full_text": term}} for term in should_terms
            ]

        must_not_clauses = []
        if must_not_terms:
            must_not_clauses = [
                {"match": {"full_text": term}} for term in must_not_terms
            ]

        filter_clauses = []
        if filters:
            for key, value in filters.items():
                filter_clauses.append({"term": {key: value}})

        body = {
            "from": (page - 1) * size,
            "size": size,
            "query": {
                "bool": {
                    "must": must_clauses,
                    "should": should_clauses,
                    "must_not": must_not_clauses,
                    "filter": filter_clauses,
                }
            },
        }

        response = await self.opensearch.client.search(index=INDEX_CASES, body=body)
        return {
            "total": response["hits"]["total"]["value"],
            "page": page,
            "size": size,
            "results": [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "source": hit["_source"],
                }
                for hit in response["hits"]["hits"]
            ],
        }

    async def timeline_search(
        self,
        query: str,
        start_year: int,
        end_year: int,
        granularity: str = "year",
    ) -> Dict[str, Any]:
        """Search with timeline aggregation."""
        body = {
            "size": 0,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "summary^2", "full_text"],
                }
            },
            "aggs": {
                "timeline": {
                    "date_histogram": {
                        "field": "date",
                        "calendar_interval": granularity,
                        "format": "yyyy",
                    }
                }
            },
        }

        response = await self.opensearch.client.search(index=INDEX_CASES, body=body)

        return {
            "query": query,
            "range": {"start": start_year, "end": end_year},
            "timeline": [
                {
                    "period": bucket["key_as_string"],
                    "count": bucket["doc_count"],
                }
                for bucket in response["aggregations"]["timeline"]["buckets"]
            ],
        }

    async def get_facets(self, query: str) -> Dict[str, Any]:
        """Get search facets for filtering."""
        body = {
            "size": 0,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "summary^2", "full_text"],
                }
            },
            "aggs": {
                "areas_of_law": {"terms": {"field": "area_of_law", "size": 20}},
                "courts": {"terms": {"field": "court", "size": 20}},
                "court_levels": {"terms": {"field": "court_level", "size": 10}},
                "years": {"date_histogram": {"field": "date", "calendar_interval": "year", "format": "yyyy"}},
                "judges": {"terms": {"field": "judge", "size": 20}},
            },
        }

        response = await self.opensearch.client.search(index=INDEX_CASES, body=body)

        return {
            "areas_of_law": {b["key"]: b["doc_count"] for b in response["aggregations"]["areas_of_law"]["buckets"]},
            "courts": {b["key"]: b["doc_count"] for b in response["aggregations"]["courts"]["buckets"]},
            "court_levels": {b["key"]: b["doc_count"] for b in response["aggregations"]["court_levels"]["buckets"]},
            "years": {b["key_as_string"]: b["doc_count"] for b in response["aggregations"]["years"]["buckets"]},
            "judges": {b["key"]: b["doc_count"] for b in response["aggregations"]["judges"]["buckets"]},
        }
