"""
Unit tests for services
"""

import pytest
from uuid import uuid4
from datetime import datetime
from app.services.permission_service import PermissionService


class TestPermissionService:
    """Tests for PermissionService"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = PermissionService()
        self.dataset_id = uuid4()
        self.user_email = "test@example.com"
        self.admin_email = "admin@example.com"

    def test_check_permission_owner(self):
        """Test that owner has admin access"""
        owner_email = "owner@example.com"
        role = self.service.check_permission(
            self.dataset_id, owner_email, owner_email, False
        )
        assert role == "admin"

    def test_check_permission_public_dataset(self):
        """Test that public datasets are accessible to all"""
        role = self.service.check_permission(
            self.dataset_id, "anyone@example.com", "owner@example.com", True
        )
        assert role == "viewer"

    def test_check_permission_private_no_access(self):
        """Test that private datasets are not accessible without permission"""
        role = self.service.check_permission(
            self.dataset_id, "stranger@example.com", "owner@example.com", False
        )
        assert role is None

    def test_is_dataset_accessible_by_owner(self):
        """Test dataset accessibility for owner"""
        is_accessible = self.service.is_dataset_accessible(
            self.dataset_id, "owner@example.com", "owner@example.com", False
        )
        assert is_accessible is True

    def test_is_dataset_accessible_public(self):
        """Test dataset accessibility for public datasets"""
        is_accessible = self.service.is_dataset_accessible(
            self.dataset_id, "anyone@example.com", "owner@example.com", True
        )
        assert is_accessible is True

    def test_is_dataset_not_accessible_private(self):
        """Test dataset inaccessibility for unauthorized users"""
        is_accessible = self.service.is_dataset_accessible(
            self.dataset_id, "unauthorized@example.com", "owner@example.com", False
        )
        assert is_accessible is False
