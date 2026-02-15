"""
Pytest configuration and fixtures
"""

import pytest
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_dataset():
    """Sample dataset for testing"""
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
