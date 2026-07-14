import pytest
from datetime import timedelta

from app.core.security import SecurityManager, has_permission, Permission, Role

class TestSecurityManager:
    def test_hash_password(self):
        password = "test_password_123"
        hashed = SecurityManager.hash_password(password)
        assert hashed != password
        assert SecurityManager.verify_password(password, hashed)

    def test_verify_password_wrong(self):
        hashed = SecurityManager.hash_password("correct")
        assert not SecurityManager.verify_password("wrong", hashed)

    def test_create_and_decode_token(self):
        token = SecurityManager.create_access_token("user_123", scopes=["read"])
        assert token is not None

        payload = SecurityManager.decode_token(token)
        assert payload is not None
        assert payload.sub == "user_123"
        assert "read" in payload.scopes

    def test_decode_invalid_token(self):
        assert SecurityManager.decode_token("invalid.token.here") is None

    def test_revoke_token(self):
        token = SecurityManager.create_access_token("user_123")
        payload = SecurityManager.decode_token(token)
        SecurityManager.revoke_token(payload.jti)
        assert SecurityManager.decode_token(token) is None

    def test_generate_api_key(self):
        key = SecurityManager.generate_api_key()
        assert key.startswith("hayat_")
        assert len(key) > 20

class TestRBAC:
    def test_super_admin_has_all_permissions(self):
        assert has_permission("super_admin", Permission.ADMIN_FULL)
        assert has_permission("super_admin", Permission.DOCUMENT_READ)
        assert has_permission("super_admin", Permission.AI_QUERY)

    def test_public_limited_permissions(self):
        assert has_permission("public", Permission.DOCUMENT_READ)
        assert not has_permission("public", Permission.DOCUMENT_WRITE)
        assert not has_permission("public", Permission.AI_QUERY)

    def test_researcher_permissions(self):
        assert has_permission("researcher", Permission.AI_QUERY)
        assert has_permission("researcher", Permission.ANALYTICS_READ)
        assert not has_permission("researcher", Permission.DOCUMENT_WRITE)
