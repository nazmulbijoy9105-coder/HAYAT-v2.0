"""
HAYAT v2.0 — Monitoring & Observability
Prometheus metrics, health checks, distributed tracing.
"""

import time
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, Response
from prometheus_client import Counter, Histogram, Gauge, Info

from app.core.config import settings
from app.core.logging import get_logger
from app.db.postgres import engine
from app.db.neo4j import get_neo4j_driver
from app.db.redis import get_redis_pool
from app.db.opensearch import get_opensearch_client
from app.db.qdrant import get_qdrant_client

logger = get_logger("hayat.monitoring")
router = APIRouter()

# Prometheus metrics
REQUEST_COUNT = Counter(
    "hayat_requests_total",
    "Total requests",
    ["method", "endpoint", "status"],
)

REQUEST_DURATION = Histogram(
    "hayat_request_duration_seconds",
    "Request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_CONNECTIONS = Gauge(
    "hayat_active_connections",
    "Active database connections",
    ["database"],
)

DOCUMENTS_PROCESSED = Counter(
    "hayat_documents_processed_total",
    "Documents processed",
    ["status", "document_type"],
)

AI_REQUESTS = Counter(
    "hayat_ai_requests_total",
    "AI layer requests",
    ["model", "status"],
)

AI_LATENCY = Histogram(
    "hayat_ai_latency_seconds",
    "AI request latency",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

SEARCH_QUERIES = Counter(
    "hayat_search_queries_total",
    "Search queries",
    ["search_type", "index"],
)

APP_INFO = Info("hayat_app", "Application information")
APP_INFO.info({"version": settings.app_version, "environment": settings.environment})


class HealthChecker:
    """
    Comprehensive health checks for all dependencies.
    Used by Kubernetes liveness and readiness probes.
    """

    @staticmethod
    async def check_postgres() -> Dict[str, Any]:
        """Check PostgreSQL connectivity."""
        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.scalar()
            return {"status": "healthy", "latency_ms": 0}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_neo4j() -> Dict[str, Any]:
        """Check Neo4j connectivity."""
        try:
            driver = await get_neo4j_driver()
            await driver.verify_connectivity()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_redis() -> Dict[str, Any]:
        """Check Redis connectivity."""
        try:
            redis = await get_redis_pool()
            await redis.ping()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_opensearch() -> Dict[str, Any]:
        """Check OpenSearch connectivity."""
        try:
            client = get_opensearch_client()
            await client.cluster.health()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_qdrant() -> Dict[str, Any]:
        """Check Qdrant connectivity."""
        try:
            client = get_qdrant_client()
            await client.get_collections()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @staticmethod
    async def check_rabbitmq() -> Dict[str, Any]:
        """Check RabbitMQ connectivity."""
        try:
            import aio_pika
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            await connection.close()
            return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    @classmethod
    async def full_health_check(cls) -> Dict[str, Any]:
        """Run all health checks."""
        start = time.time()

        checks = {
            "postgres": await cls.check_postgres(),
            "neo4j": await cls.check_neo4j(),
            "redis": await cls.check_redis(),
            "opensearch": await cls.check_opensearch(),
            "qdrant": await cls.check_qdrant(),
            "rabbitmq": await cls.check_rabbitmq(),
        }

        all_healthy = all(c["status"] == "healthy" for c in checks.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.app_version,
            "environment": settings.environment,
            "checks": checks,
            "duration_ms": round((time.time() - start) * 1000, 2),
        }


@router.get("/health")
async def health_check():
    """Liveness probe — basic check."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
async def readiness_check():
    """Readiness probe — all dependencies must be healthy."""
    health = await HealthChecker.full_health_check()

    if health["status"] == "healthy":
        return health
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=health)


@router.get("/metrics/deep")
async def deep_metrics():
    """Extended metrics for monitoring dashboards."""
    health = await HealthChecker.full_health_check()

    return {
        "health": health,
        "system": {
            "version": settings.app_version,
            "environment": settings.environment,
            "features": {
                "ai_layer": settings.enable_ai_layer,
                "knowledge_graph": settings.enable_knowledge_graph,
                "rule_engine": settings.enable_rule_engine,
                "analytics": settings.enable_analytics,
            },
        },
    }
