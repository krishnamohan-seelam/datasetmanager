"""
Pytest configuration and fixtures.

All fixtures that create database resources guarantee cleanup
on pass, fail, OR error via yield + finalizer pattern.
"""

import pytest
import sys
from pathlib import Path
from uuid import uuid4

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.dataset_service import DatasetService
from app.services.schema_service import SchemaService
from app.services.batch_service import BatchService


# ── Managed Dataset Fixture ──────────────────────────────────────────────

@pytest.fixture
def managed_dataset():
    """
    Fixture that provides a factory to create datasets with
    guaranteed cleanup on exit — regardless of pass, fail, or error.

    Usage:
        def test_something(managed_dataset):
            ds_id = managed_dataset(name="Test", owner="test@x.com")
            # ... test logic ...
            # Cleanup happens automatically
    """
    service = DatasetService()
    created_ids = []

    def _create(**kwargs):
        kwargs.setdefault("name", f"test_ds_{uuid4().hex[:8]}")
        kwargs.setdefault("owner", "pytest@example.com")
        kwargs.setdefault("is_public", False)
        dataset_id = service.create_dataset(**kwargs)
        created_ids.append(dataset_id)
        return dataset_id

    yield _create

    # Finalizer — always runs
    for did in created_ids:
        try:
            service.delete_dataset(did)
        except Exception:
            pass


# ── Managed User Fixture ─────────────────────────────────────────────────

@pytest.fixture
def managed_user():
    """
    Fixture that provides a factory to create users with
    guaranteed cleanup on exit.

    Usage:
        def test_something(managed_user):
            user = managed_user(email="test@x.com", password="Pass123!")
            # ... test logic ...
            # Cleanup happens automatically
    """
    from app.cassandra_client import CassandraClient
    from app.core.config import settings

    db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
    keyspace = settings.CASSANDRA_KEYSPACE
    created_user_ids = []

    def _create(**kwargs):
        from app.auth_utils import hash_password
        from datetime import datetime

        user_id = uuid4()
        email = kwargs.get("email", f"testuser_{uuid4().hex[:8]}@example.com")
        password = kwargs.get("password", "TestPassword123!")
        full_name = kwargs.get("full_name", "Test User")
        role = kwargs.get("role", "viewer")

        password_hash = hash_password(password)
        now = datetime.utcnow()

        db.execute(
            f"""INSERT INTO {keyspace}.users
                (user_id, email, password_hash, full_name, role, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [user_id, email, password_hash, full_name, role, True, now, now],
        )
        created_user_ids.append(user_id)
        return {"user_id": user_id, "email": email, "role": role}

    yield _create

    # Finalizer — always runs
    for uid in created_user_ids:
        try:
            db.execute(
                f"DELETE FROM {keyspace}.users WHERE user_id = %s", [uid]
            )
        except Exception:
            pass


# ── Static Test Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def sample_dataset():
    """Sample dataset kwargs for testing"""
    return {
        "name": "Test Dataset",
        "description": "A test dataset",
        "owner": "test@example.com",
        "tags": "test,sample",
        "is_public": False,
        "masking_config": {
            "email": "email",
            "phone": "phone",
            "ssn": "ssn",
        },
    }


@pytest.fixture
def sample_rows():
    """Sample rows for testing"""
    return [
        {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "ssn": "123-45-6789",
        },
        {
            "id": 2,
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "555-987-6543",
            "ssn": "987-65-4321",
        },
        {
            "id": 3,
            "name": "Bob Johnson",
            "email": "bob@example.com",
            "phone": "555-456-7890",
            "ssn": "456-78-9012",
        },
    ]


@pytest.fixture
def test_user():
    """Test user fixture"""
    return {
        "email": "testuser@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User",
        "role": "viewer",
    }


@pytest.fixture
def admin_user():
    """Admin user fixture"""
    return {
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "full_name": "Admin User",
        "role": "admin",
    }
