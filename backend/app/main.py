"""
HAYAT v2.0 — FastAPI Application Entry Point
Production-ready with all enterprise middleware.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.logging import configure_logging, get_logger, get_correlation_id
from app.db.postgres import init_postgres, close_postgres
from app.db.neo4j import init_neo4j, close_neo4j
from app.db.opensearch import init_opensearch, close_opensearch
from app.db.qdrant import init_qdrant, close_qdrant
from app.db.redis import init_redis, close_redis
from app.db.minio import init_minio
from app.middleware.enterprise import (
    RateLimitMiddleware,
    IdempotencyMiddleware,
    AuditLogMiddleware,
    RequestValidationMiddleware,
    VersionMiddleware,
)
from app.api.v1 import auth, documents, cases, statutes, search, ai, analytics, monitoring

logger = get_logger("hayat.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("hayat_startup", version=settings.app_version, env=settings.environment)

    await init_postgres()
    await init_neo4j()
    await init_opensearch()
    await init_qdrant()
    await init_redis()
    await init_minio()

    yield

    await close_postgres()
    await close_neo4j()
    await close_opensearch()
    await close_qdrant()
    await close_redis()
    logger.info("hayat_shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url="/api/redoc" if settings.environment != "production" else None,
    openapi_url="/api/openapi.json" if settings.environment != "production" else None,
)

# Middleware stack (order matters)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestValidationMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(VersionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    from contextvars import copy_context
    cid = request.headers.get("X-Correlation-ID") or get_correlation_id()
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("unhandled_exception", path=str(request.url), error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "correlation_id": get_correlation_id(),
            "support": "Please contact support with the correlation ID above.",
        },
    )


# API Routes
app.include_router(monitoring.router, prefix="/health", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(cases.router, prefix="/api/v1/cases", tags=["Cases"])
app.include_router(statutes.router, prefix="/api/v1/statutes", tags=["Statutes"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Intelligence"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "layers": [
            "Layer 0: Legal Sources",
            "Layer 1: Acquisition",
            "Layer 2: Document Intelligence",
            "Layer 3: Legal Parsing",
            "Layer 4: Knowledge Graph",
            "Layer 5: Rule Engine",
            "Layer 6: Search Engine",
            "Layer 7: AI Intelligence",
            "Layer 8: Editorial",
            "Layer 9: Practice Tools",
            "Layer 10: Analytics",
            "Layer 11: API Platform",
            "Layer 12: Security",
        ],
        "docs": "/api/docs" if settings.environment != "production" else None,
        "health": "/health",
        "metrics": "/metrics",
    }
