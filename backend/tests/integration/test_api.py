import pytest

class TestHealthEndpoints:
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    async def test_root_endpoint(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "HAYAT" in data["name"]
        assert len(data["layers"]) == 13

class TestAuthEndpoints:
    async def test_register_user(self, client):
        response = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "secure_password_123",
            "full_name": "Test User",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    async def test_login_user(self, client):
        # First register
        await client.post("/api/v1/auth/register", json={
            "email": "login@test.com",
            "password": "secure_password_123",
            "full_name": "Login Test",
        })

        # Then login
        response = await client.post("/api/v1/auth/login", data={
            "username": "login@test.com",
            "password": "secure_password_123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

class TestCaseEndpoints:
    async def test_create_case(self, client, sample_case_data):
        response = await client.post("/api/v1/cases/", json=sample_case_data)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == sample_case_data["title"]
        assert data["citation"] == sample_case_data["citation"]

    async def test_list_cases(self, client, sample_case_data):
        # Create a case first
        await client.post("/api/v1/cases/", json=sample_case_data)

        response = await client.get("/api/v1/cases/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["results"]) >= 1

    async def test_get_case(self, client, sample_case_data):
        create_response = await client.post("/api/v1/cases/", json=sample_case_data)
        case_id = create_response.json()["id"]

        response = await client.get(f"/api/v1/cases/{case_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == case_id

    async def test_search_cases(self, client, sample_case_data):
        await client.post("/api/v1/cases/", json=sample_case_data)

        response = await client.post("/api/v1/search/", json={
            "query": "Test Case",
            "search_type": "natural_language",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

class TestSecurityHeaders:
    async def test_security_headers_present(self, client):
        response = await client.get("/health")
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Strict-Transport-Security" in response.headers
