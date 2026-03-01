"""
Batch management service — lifecycle for dataset upload batches.

Each upload to a dataset creates an immutable batch identified by
(dataset_id, batch_date, batch_id).  Batches can be listed, queried,
and individually deleted.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from ..cassandra_client import CassandraClient
from ..core.config import settings
from ..core.exceptions import DatabaseException

logger = logging.getLogger(__name__)


class BatchService:
    """Service for dataset batch lifecycle management"""

    def __init__(self):
        self.db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        self.keyspace = settings.CASSANDRA_KEYSPACE

    # ── Public API ───────────────────────────────────────────────────

    def create_batch(
        self,
        dataset_id: UUID,
        batch_date: Optional[datetime] = None,
        file_format: str = "csv",
        size_bytes: int = 0,
        uploaded_by: str = "",
        schema_version: int = 1,
    ) -> UUID:
        """
        Register a new batch for a dataset.
        Returns the generated batch_id.
        """
        try:
            batch_id = uuid4()
            now = datetime.utcnow()
            batch_date = batch_date or now

            query = f"""
                INSERT INTO {self.keyspace}.dataset_batches
                (dataset_id, batch_id, batch_date, schema_version,
                 row_count, size_bytes, file_format, status,
                 uploaded_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.db.execute(query, [
                dataset_id, batch_id, batch_date, schema_version,
                0, size_bytes, file_format, "uploading",
                uploaded_by, now,
            ])

            logger.info(
                f"Created batch {batch_id} for dataset {dataset_id} "
                f"(date={batch_date.isoformat()})"
            )
            return batch_id

        except Exception as e:
            logger.error(f"Failed to create batch: {e}")
            raise DatabaseException(f"Failed to create batch: {str(e)}")

    def update_batch_status(
        self,
        dataset_id: UUID,
        batch_id: UUID,
        batch_date: datetime,
        status: str,
        row_count: int = 0,
        schema_version: Optional[int] = None,
    ) -> None:
        """Update batch status and row count after processing."""
        try:
            sets = ["status = %s", "row_count = %s"]
            values = [status, row_count]

            if schema_version is not None:
                sets.append("schema_version = %s")
                values.append(schema_version)

            values.extend([dataset_id, batch_date, batch_id])

            query = f"""
                UPDATE {self.keyspace}.dataset_batches
                SET {', '.join(sets)}
                WHERE dataset_id = %s AND batch_date = %s AND batch_id = %s
            """
            self.db.execute(query, values)

            logger.info(f"Updated batch {batch_id} status={status} rows={row_count}")

        except Exception as e:
            logger.error(f"Failed to update batch status: {e}")
            raise DatabaseException(f"Failed to update batch status: {str(e)}")

    def get_batch(self, dataset_id: UUID, batch_id: UUID) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific batch."""
        try:
            query = f"""
                SELECT batch_id, batch_date, schema_version, row_count,
                       size_bytes, file_format, status, uploaded_by, created_at
                FROM {self.keyspace}.dataset_batches
                WHERE dataset_id = %s
            """
            result = self.db.execute(query, [dataset_id])

            for row in result:
                if row.batch_id == batch_id:
                    return self._row_to_dict(row)
            return None

        except Exception as e:
            logger.error(f"Failed to get batch {batch_id}: {e}")
            raise DatabaseException(f"Failed to get batch: {str(e)}")

    def get_latest_batch(self, dataset_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the most recent batch for a dataset."""
        try:
            query = f"""
                SELECT batch_id, batch_date, schema_version, row_count,
                       size_bytes, file_format, status, uploaded_by, created_at
                FROM {self.keyspace}.dataset_batches
                WHERE dataset_id = %s
                LIMIT 1
            """
            row = self.db.execute(query, [dataset_id]).one()
            return self._row_to_dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get latest batch for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to get latest batch: {str(e)}")

    def list_batches(
        self,
        dataset_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List all batches for a dataset, newest first."""
        try:
            query = f"""
                SELECT batch_id, batch_date, schema_version, row_count,
                       size_bytes, file_format, status, uploaded_by, created_at
                FROM {self.keyspace}.dataset_batches
                WHERE dataset_id = %s
            """
            result = list(self.db.execute(query, [dataset_id]))
            total = len(result)

            offset = (page - 1) * page_size
            page_rows = result[offset: offset + page_size]

            batches = [self._row_to_dict(row) for row in page_rows]
            return batches, total

        except Exception as e:
            logger.error(f"Failed to list batches for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to list batches: {str(e)}")

    def delete_batch(self, dataset_id: UUID, batch_id: UUID) -> bool:
        """
        Delete a specific batch — removes batch registry entry
        and the corresponding rows from the ds_rows_* table.
        """
        try:
            # Find the batch to get batch_date (needed for partition key)
            batch = self.get_batch(dataset_id, batch_id)
            if not batch:
                return False

            # Delete rows for this batch from the row table (composite PK)
            table_name = f"ds_rows_{str(dataset_id).replace('-', '_')}"
            try:
                # With composite PK (batch_id, row_chunk_id), delete chunk by chunk
                chunk_id = 0
                while True:
                    # Check if this chunk has any rows (try to delete, CQL is idempotent)
                    self.db.execute(
                        f"DELETE FROM {self.keyspace}.{table_name} WHERE batch_id = %s AND row_chunk_id = %s",
                        [batch_id, chunk_id],
                    )
                    chunk_id += 1
                    if chunk_id > 100:  # Safety limit; datasets rarely have >100 chunks
                        break
            except Exception as e:
                logger.warning(f"Could not delete rows for batch {batch_id}: {e}")

            # Delete batch registry entry
            query = f"""
                DELETE FROM {self.keyspace}.dataset_batches
                WHERE dataset_id = %s AND batch_date = %s AND batch_id = %s
            """
            self.db.execute(query, [dataset_id, batch["batch_date"], batch_id])

            logger.info(f"Deleted batch {batch_id} from dataset {dataset_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete batch {batch_id}: {e}")
            raise DatabaseException(f"Failed to delete batch: {str(e)}")

    def delete_all_batches(self, dataset_id: UUID) -> int:
        """Delete all batches for a dataset (used on dataset deletion)."""
        try:
            query = f"""
                SELECT batch_date, batch_id
                FROM {self.keyspace}.dataset_batches
                WHERE dataset_id = %s
            """
            rows = list(self.db.execute(query, [dataset_id]))

            for row in rows:
                self.db.execute(
                    f"""DELETE FROM {self.keyspace}.dataset_batches
                        WHERE dataset_id = %s AND batch_date = %s AND batch_id = %s""",
                    [dataset_id, row.batch_date, row.batch_id],
                )

            logger.info(f"Deleted {len(rows)} batches for dataset {dataset_id}")
            return len(rows)

        except Exception as e:
            logger.error(f"Failed to delete all batches for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to delete all batches: {str(e)}")

    def count_batches(self, dataset_id: UUID) -> int:
        """Count total batches for a dataset."""
        try:
            query = f"""
                SELECT COUNT(*) as cnt
                FROM {self.keyspace}.dataset_batches
                WHERE dataset_id = %s
            """
            row = self.db.execute(query, [dataset_id]).one()
            return row.cnt if row else 0
        except Exception:
            return 0

    # ── Internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """Convert a Cassandra row to a dict."""
        return {
            "batch_id": row.batch_id,
            "batch_date": row.batch_date,
            "schema_version": row.schema_version,
            "row_count": row.row_count,
            "size_bytes": row.size_bytes,
            "file_format": row.file_format,
            "status": row.status,
            "uploaded_by": row.uploaded_by,
            "created_at": row.created_at,
        }
