"""
Integration tests for API endpoints
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestAuthEndpoints:
    """Tests for authentication endpoints"""

    def test_register_new_user(self):
        """Test user registration"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"newuser_{datetime.now().timestamp()}@example.com",
                "password": "TestPassword123!",
                "full_name": "New User",
                "role": "viewer"
            },
        )
        assert response.status_code == 200
        assert response.json()["user"]["email"].startswith("newuser_")

    def test_login_user(self):
        """Test user login"""
        # First register
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "logintest@example.com",
                "password": "TestPassword123!",
                "full_name": "Login Test",
                "role": "viewer"
            },
        )

        # Then login
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "logintest@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "WrongPassword"},
        )
        assert response.status_code == 401


class TestDatasetEndpoints:
    """Tests for dataset endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test user and token"""
        # Register test user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "dstest@example.com",
                "password": "TestPassword123!",
                "full_name": "Dataset Test",
                "role": "admin"
            },
        )

        # Login to get token
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "dstest@example.com", "password": "TestPassword123!"},
        )
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()


class TestPermissionEndpoints:
    """Tests for permission endpoints"""

    def test_get_current_user(self):
        """Test getting current user info"""
        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "userinfo@example.com",
                "password": "Password123!",
                "full_name": "User Info",
                "role": "viewer"
            },
        )

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "userinfo@example.com", "password": "Password123!"},
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get user info
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == "userinfo@example.com"
