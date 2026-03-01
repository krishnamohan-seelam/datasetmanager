"""
Unit tests for BatchService — batch lifecycle management.
"""

import pytest
from uuid import uuid4
from datetime import datetime
from app.services.batch_service import BatchService


class TestBatchService:
    """Tests for batch creation, listing, and deletion"""

    def setup_method(self):
        self.service = BatchService()
        self.dataset_id = uuid4()

    def teardown_method(self):
        """Ensure batch data is cleaned up after each test."""
        try:
            self.service.delete_all_batches(self.dataset_id)
        except Exception:
            pass

    def test_create_batch(self):
        """Batch registered with correct batch_date."""
        batch_date = datetime(2026, 3, 1, 0, 0, 0)
        batch_id = self.service.create_batch(
            dataset_id=self.dataset_id,
            batch_date=batch_date,
            file_format="csv",
            size_bytes=1024,
            uploaded_by="test@example.com",
        )

        assert batch_id is not None

        batch = self.service.get_batch(self.dataset_id, batch_id)
        assert batch is not None
        assert batch["file_format"] == "csv"
        assert batch["status"] == "uploading"
        assert batch["uploaded_by"] == "test@example.com"

    def test_update_batch_status(self):
        """Batch status and row_count update correctly."""
        batch_date = datetime(2026, 3, 1, 0, 0, 0)
        batch_id = self.service.create_batch(
            dataset_id=self.dataset_id,
            batch_date=batch_date,
        )

        self.service.update_batch_status(
            self.dataset_id, batch_id, batch_date,
            status="ready", row_count=500,
        )

        batch = self.service.get_batch(self.dataset_id, batch_id)
        assert batch["status"] == "ready"
        assert batch["row_count"] == 500

    def test_list_batches_ordered(self):
        """Batches returned newest-first."""
        dates = [
            datetime(2026, 2, 28),
            datetime(2026, 3, 1),
            datetime(2026, 3, 2),
        ]
        for d in dates:
            self.service.create_batch(
                dataset_id=self.dataset_id, batch_date=d,
            )

        batches, total = self.service.list_batches(self.dataset_id)
        assert total == 3
        assert len(batches) == 3

        # Newest first
        batch_dates = [b["batch_date"] for b in batches]
        assert batch_dates == sorted(batch_dates, reverse=True)

    def test_get_latest_batch(self):
        """Returns the most recent batch."""
        self.service.create_batch(
            dataset_id=self.dataset_id,
            batch_date=datetime(2026, 2, 28),
        )
        self.service.create_batch(
            dataset_id=self.dataset_id,
            batch_date=datetime(2026, 3, 1),
        )

        latest = self.service.get_latest_batch(self.dataset_id)
        assert latest is not None
        assert latest["batch_date"].date() == datetime(2026, 3, 1).date()

    def test_count_batches(self):
        """Count returns correct number."""
        for i in range(3):
            self.service.create_batch(
                dataset_id=self.dataset_id,
                batch_date=datetime(2026, 3, i + 1),
            )

        count = self.service.count_batches(self.dataset_id)
        assert count == 3

    def test_delete_all_batches(self):
        """Delete all removes everything."""
        for i in range(3):
            self.service.create_batch(
                dataset_id=self.dataset_id,
                batch_date=datetime(2026, 3, i + 1),
            )

        deleted = self.service.delete_all_batches(self.dataset_id)
        assert deleted == 3

        count = self.service.count_batches(self.dataset_id)
        assert count == 0

    def test_get_batch_nonexistent(self):
        """Returns None for unknown batch."""
        result = self.service.get_batch(self.dataset_id, uuid4())
        assert result is None
