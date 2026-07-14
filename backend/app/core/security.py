"""
HAYAT v2.0 — Security Layer
Authentication, authorization, encryption, and audit logging.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import structlog

from app.core.config import settings

logger = structlog.get_logger("hayat.security")

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.password_hash_rounds,
)


class TokenPayload(BaseModel):
    sub: str  # user_id
    jti: str  # token ID for revocation
    type: str  # access or refresh
    scopes: list[str] = []
    exp: datetime
    iat: datetime
    aud: str = "hayat-v2"
    iss: str = "hayat-auth"


class SecurityManager:
    """
    Enterprise-grade security manager.
    Handles JWT lifecycle, password hashing, and token revocation.
    """

    _revoked_tokens: set[str] = set()  # In production: use Redis

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def create_access_token(
        cls,
        user_id: str,
        scopes: list[str] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a JWT access token."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id,
            jti=str(uuid4()),
            type="access",
            scopes=scopes or [],
            exp=now + expires_delta,
            iat=now,
        )

        token = jwt.encode(
            payload.model_dump(mode="json"),
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        logger.info("access_token_created", user_id=user_id, jti=payload.jti)
        return token

    @classmethod
    def create_refresh_token(
        cls,
        user_id: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a JWT refresh token."""
        if expires_delta is None:
            expires_delta = timedelta(days=settings.refresh_token_expire_days)

        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id,
            jti=str(uuid4()),
            type="refresh",
            exp=now + expires_delta,
            iat=now,
        )

        return jwt.encode(
            payload.model_dump(mode="json"),
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

    @classmethod
    def decode_token(cls, token: str) -> Optional[TokenPayload]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
                audience="hayat-v2",
                issuer="hayat-auth",
            )
            token_data = TokenPayload(**payload)

            # Check revocation
            if token_data.jti in cls._revoked_tokens:
                logger.warning("token_revoked", jti=token_data.jti)
                return None

            return token_data
        except JWTError as e:
            logger.warning("token_decode_failed", error=str(e))
            return None

    @classmethod
    def revoke_token(cls, jti: str) -> None:
        """Revoke a token by its JTI."""
        cls._revoked_tokens.add(jti)
        logger.info("token_revoked", jti=jti)

    @classmethod
    def generate_api_key(cls) -> str:
        """Generate a secure API key for institution access."""
        return f"hayat_{uuid4().hex}_{uuid4().hex[:16]}"


# Role-based access control
class Permission:
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    CASE_READ = "case:read"
    CASE_WRITE = "case:write"
    STATUTE_READ = "statute:read"
    STATUTE_WRITE = "statute:write"
    AI_QUERY = "ai:query"
    AI_ADMIN = "ai:admin"
    ADMIN_FULL = "admin:full"
    ANALYTICS_READ = "analytics:read"
    KNOWLEDGE_GRAPH_READ = "kg:read"
    KNOWLEDGE_GRAPH_WRITE = "kg:write"


class Role:
    SUPER_ADMIN = [Permission.ADMIN_FULL]
    LEGAL_EDITOR = [
        Permission.DOCUMENT_READ, Permission.DOCUMENT_WRITE,
        Permission.CASE_READ, Permission.CASE_WRITE,
        Permission.STATUTE_READ, Permission.STATUTE_WRITE,
        Permission.AI_QUERY, Permission.KNOWLEDGE_GRAPH_READ, Permission.KNOWLEDGE_GRAPH_WRITE,
    ]
    RESEARCHER = [
        Permission.DOCUMENT_READ, Permission.CASE_READ, Permission.STATUTE_READ,
        Permission.AI_QUERY, Permission.KNOWLEDGE_GRAPH_READ, Permission.ANALYTICS_READ,
    ]
    PRACTITIONER = [
        Permission.DOCUMENT_READ, Permission.CASE_READ, Permission.STATUTE_READ,
        Permission.AI_QUERY, Permission.KNOWLEDGE_GRAPH_READ,
    ]
    PUBLIC = [
        Permission.DOCUMENT_READ, Permission.CASE_READ, Permission.STATUTE_READ,
    ]
    INSTITUTION = [
        Permission.DOCUMENT_READ, Permission.CASE_READ, Permission.STATUTE_READ,
        Permission.AI_QUERY, Permission.ANALYTICS_READ,
    ]


ROLE_MAP = {
    "super_admin": Role.SUPER_ADMIN,
    "legal_editor": Role.LEGAL_EDITOR,
    "researcher": Role.RESEARCHER,
    "practitioner": Role.PRACTITIONER,
    "public": Role.PUBLIC,
    "institution": Role.INSTITUTION,
}


def has_permission(user_role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    permissions = ROLE_MAP.get(user_role, [])
    return Permission.ADMIN_FULL in permissions or permission in permissions
