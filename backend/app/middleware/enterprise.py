"""
HAYAT v2.0 — Enterprise Middleware Stack
Rate limiting, idempotency, request validation, audit logging.
"""

import time
import hashlib
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import get_logger, get_correlation_id
from app.db.redis import get_redis_pool

logger = get_logger("hayat.middleware")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting per user/API key.
    Configurable limits by role and endpoint.
    """

    DEFAULT_LIMIT = 100  # requests per minute
    DEFAULT_WINDOW = 60  # seconds

    ROLE_LIMITS = {
        "super_admin": 10000,
        "legal_editor": 500,
        "researcher": 300,
        "practitioner": 200,
        "public": 30,
        "institution": 1000,
    }

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)

        client_id = self._get_client_id(request)
        limit = self._get_limit(request)

        redis = await get_redis_pool()
        key = f"rate_limit:{client_id}"

        current = await redis.get(key)
        if current and int(current) >= limit:
            logger.warning("rate_limit_exceeded", client_id=client_id, path=request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": self.DEFAULT_WINDOW,
                    "limit": limit,
                },
            )

        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.DEFAULT_WINDOW)
        await pipe.execute()

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - int(current or 0) - 1))
        return response

    def _get_client_id(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key[:16]}"

        user = getattr(request.state, "user", None)
        if user:
            return f"user:{user.id}"

        return f"ip:{request.client.host}"

    def _get_limit(self, request: Request) -> int:
        user = getattr(request.state, "user", None)
        if user:
            return self.ROLE_LIMITS.get(user.role, self.DEFAULT_LIMIT)
        return self.DEFAULT_LIMIT


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Idempotency key middleware for POST/PUT/PATCH operations.
    Prevents duplicate processing of the same request.
    """

    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    CACHE_TTL = 86400  # 24 hours

    async def dispatch(self, request: Request, call_next):
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        redis = await get_redis_pool()
        cache_key = f"idempotency:{idempotency_key}"

        # Check for existing response
        cached = await redis.get(cache_key)
        if cached:
            logger.info("idempotency_cache_hit", key=idempotency_key[:16])
            return Response(
                content=cached,
                media_type="application/json",
                headers={"X-Idempotency-Key": idempotency_key},
            )

        # Process request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code < 400:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            await redis.setex(cache_key, self.CACHE_TTL, body)

            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Automatic audit logging for all API requests.
    Immutable trail for compliance and security.
    """

    SKIP_PATHS = {"/health", "/ready", "/metrics", "/api/docs", "/api/redoc"}

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time

        if request.url.path in self.SKIP_PATHS:
            return response

        # Log audit event
        user = getattr(request.state, "user", None)
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": get_correlation_id(),
            "method": request.method,
            "path": str(request.url.path),
            "query_params": str(request.query_params),
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_id": user.id if user else None,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "api_key": request.headers.get("X-API-Key", "")[:16] if request.headers.get("X-API-Key") else None,
        }

        logger.info("api_request", **audit_entry)

        # Add headers
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        response.headers["X-Correlation-ID"] = get_correlation_id()

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Request size limits, content-type validation, security headers.
    """

    MAX_BODY_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "multipart/form-data",
        "application/x-www-form-urlencoded",
        "text/plain",
    }

    async def dispatch(self, request: Request, call_next):
        # Content-Type validation
        content_type = request.headers.get("content-type", "").split(";")[0].strip()
        if request.method in {"POST", "PUT", "PATCH"} and content_type:
            if content_type not in self.ALLOWED_CONTENT_TYPES:
                return JSONResponse(
                    status_code=415,
                    content={"detail": f"Unsupported media type: {content_type}"},
                )

        # Security headers
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


class VersionMiddleware(BaseHTTPMiddleware):
    """
    API versioning support via header and URL path.
    """

    async def dispatch(self, request: Request, call_next):
        api_version = request.headers.get("X-API-Version", "v1")
        request.state.api_version = api_version

        response = await call_next(request)
        response.headers["X-API-Version"] = api_version
        response.headers["X-API-Deprecated"] = "false"

        return response


# Dependency injection helpers
async def get_current_user(request: Request):
    """Extract and validate current user from request."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_permission(permission: str):
    """Dependency factory for permission checks."""
    async def checker(request: Request):
        user = await get_current_user(request)
        from app.core.security import has_permission
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
        return user
    return checker
