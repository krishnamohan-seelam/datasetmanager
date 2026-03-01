"""
Unit tests for SchemaService — versioned schema CRUD, evolution, and masking.
"""

import pytest
from uuid import uuid4
from app.services.schema_service import SchemaService


class TestSchemaService:
    """Tests for schema creation, evolution, and history"""

    def setup_method(self):
        self.service = SchemaService()
        self.dataset_id = uuid4()

    def teardown_method(self):
        """Ensure schema data is cleaned up after each test."""
        try:
            self.service.delete_schema(self.dataset_id)
        except Exception:
            pass

    def test_create_schema_from_sample(self):
        """Schema inferred from sample row with correct types and positions."""
        sample = {"name": "Alice", "age": 30, "score": 95.5}
        version = self.service.create_schema(self.dataset_id, sample)

        assert version == 1

        schema = self.service.get_schema(self.dataset_id)
        assert len(schema) == 3

        names = {col["name"] for col in schema}
        assert names == {"name", "age", "score"}

        # Verify ordering
        positions = [col["position"] for col in schema]
        assert positions == sorted(positions)

    def test_get_schema_returns_empty_for_unknown(self):
        """No schema exists returns empty list."""
        schema = self.service.get_schema(uuid4())
        assert schema == []

    def test_evolve_schema_no_change(self):
        """No evolution if columns haven't changed."""
        sample = {"name": "Alice", "age": 30}
        v1 = self.service.create_schema(self.dataset_id, sample)

        v2 = self.service.evolve_schema(self.dataset_id, {"name": "Bob", "age": 25})
        assert v2 == v1  # No change — same version

    def test_evolve_schema_add_column(self):
        """New column detected, version increments."""
        sample = {"name": "Alice", "age": 30}
        self.service.create_schema(self.dataset_id, sample)

        new_sample = {"name": "Bob", "age": 25, "email": "bob@x.com"}
        v2 = self.service.evolve_schema(self.dataset_id, new_sample)
        assert v2 == 2

        schema = self.service.get_schema(self.dataset_id, version=2)
        names = {col["name"] for col in schema}
        assert "email" in names

    def test_evolve_schema_drop_column(self):
        """Missing column marked is_active=false."""
        sample = {"name": "Alice", "age": 30, "phone": "123"}
        self.service.create_schema(self.dataset_id, sample)

        new_sample = {"name": "Bob", "age": 25}
        v2 = self.service.evolve_schema(self.dataset_id, new_sample)
        assert v2 == 2

        # Active columns should only be name and age
        active_schema = self.service.get_schema(self.dataset_id, version=2)
        active_names = {col["name"] for col in active_schema}
        assert "phone" not in active_names

        # Full schema should include phone as inactive
        full_schema = self.service.get_schema(
            self.dataset_id, version=2, include_inactive=True
        )
        phone_col = next(c for c in full_schema if c["name"] == "phone")
        assert phone_col["is_active"] is False

    def test_schema_history(self):
        """All versions returned, ordered DESC."""
        sample = {"name": "Alice", "age": 30}
        self.service.create_schema(self.dataset_id, sample)

        new_sample = {"name": "Bob", "age": 25, "email": "bob@x.com"}
        self.service.evolve_schema(self.dataset_id, new_sample)

        history = self.service.get_schema_history(self.dataset_id)
        assert len(history) == 2
        assert history[0]["version"] > history[1]["version"]

    def test_update_masking_rule(self):
        """Masking rule set on latest version."""
        sample = {"name": "Alice", "email": "alice@x.com"}
        self.service.create_schema(self.dataset_id, sample)

        self.service.update_masking_rule(self.dataset_id, "email", "email")

        schema = self.service.get_schema(self.dataset_id)
        email_col = next(c for c in schema if c["name"] == "email")
        assert email_col["mask_rule"] == "email"
        assert email_col["masked"] is True

    def test_delete_schema(self):
        """Hard-delete removes all versions."""
        sample = {"name": "Alice"}
        self.service.create_schema(self.dataset_id, sample)

        self.service.delete_schema(self.dataset_id)
        schema = self.service.get_schema(self.dataset_id)
        assert schema == []
