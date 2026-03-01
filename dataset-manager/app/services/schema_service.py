"""
Schema management service — versioned, per-dataset column metadata.

Handles schema inference, evolution (column add/remove/type-change),
masking rule management, and schema history tracking.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from ..cassandra_client import CassandraClient
from ..core.config import settings
from ..core.exceptions import DatabaseException, DatasetNotFoundException

logger = logging.getLogger(__name__)


class SchemaService:
    """Service for versioned dataset schema operations"""

    def __init__(self):
        self.db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        self.keyspace = settings.CASSANDRA_KEYSPACE

    # ── Public API ───────────────────────────────────────────────────

    def create_schema(
        self,
        dataset_id: UUID,
        sample_row: Dict[str, Any],
        batch_id: Optional[UUID] = None,
    ) -> int:
        """
        Create initial schema (version 1) from a sample data row.
        Returns the version number.
        """
        try:
            version = 1
            now = datetime.utcnow()
            columns = self._infer_columns(sample_row)

            # Persist each column
            for col in columns:
                self._insert_column(dataset_id, version, col, now)

            # Register version metadata
            self._register_version(
                dataset_id, version, batch_id, now,
                column_count=len(columns),
                change_summary="Initial schema",
            )

            logger.info(
                f"Created schema v{version} for dataset {dataset_id} "
                f"({len(columns)} columns)"
            )
            return version

        except Exception as e:
            logger.error(f"Failed to create schema for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to create schema: {str(e)}")

    def evolve_schema(
        self,
        dataset_id: UUID,
        new_sample_row: Dict[str, Any],
        batch_id: Optional[UUID] = None,
    ) -> int:
        """
        Compare incoming data against the latest schema version.
        If columns changed, create a new version. Otherwise, return the
        current version unchanged.

        Returns the (possibly new) version number.
        """
        try:
            current_cols = self.get_schema(dataset_id)

            # First upload — no existing schema
            if not current_cols:
                return self.create_schema(dataset_id, new_sample_row, batch_id)

            diff = self._diff_schemas(current_cols, new_sample_row)

            # No changes — reuse current version
            if not diff["added"] and not diff["removed"] and not diff["changed"]:
                current_version = self._get_latest_version(dataset_id)
                return current_version

            # Build new version
            current_version = self._get_latest_version(dataset_id)
            new_version = current_version + 1
            now = datetime.utcnow()

            # Carry forward active columns, applying changes
            new_columns = []
            position = 0

            # Carry forward existing columns (mark removed ones inactive)
            for col in current_cols:
                if col["name"] in diff["removed"]:
                    new_columns.append({
                        **col,
                        "position": position,
                        "is_active": False,
                        "removed_at": now,
                    })
                elif col["name"] in diff["changed"]:
                    new_type = type(new_sample_row[col["name"]]).__name__
                    new_columns.append({
                        **col,
                        "type": new_type,
                        "position": position,
                        "is_active": True,
                    })
                else:
                    new_columns.append({
                        **col,
                        "position": position,
                        "is_active": True,
                    })
                position += 1

            # Add new columns
            for col_name in diff["added"]:
                value = new_sample_row[col_name]
                new_columns.append({
                    "name": col_name,
                    "type": type(value).__name__,
                    "position": position,
                    "is_active": True,
                    "masking_rule": None,
                    "added_at": now,
                })
                position += 1

            # Persist
            for col in new_columns:
                self._insert_column(dataset_id, new_version, col, now)

            # Build change summary
            parts = []
            if diff["added"]:
                parts.append(f"+{len(diff['added'])} cols")
            if diff["removed"]:
                parts.append(f"-{len(diff['removed'])} cols")
            if diff["changed"]:
                parts.append(f"~{len(diff['changed'])} type changes")
            summary = ", ".join(parts)

            active_count = sum(1 for c in new_columns if c.get("is_active", True))
            self._register_version(
                dataset_id, new_version, batch_id, now,
                column_count=active_count,
                change_summary=summary,
            )

            logger.info(
                f"Schema evolved to v{new_version} for dataset {dataset_id}: {summary}"
            )
            return new_version

        except DatabaseException:
            raise
        except Exception as e:
            logger.error(f"Failed to evolve schema for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to evolve schema: {str(e)}")

    def get_schema(
        self,
        dataset_id: UUID,
        version: Optional[int] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get schema columns for a dataset.
        If version is None, returns the latest version.
        By default only returns active columns.
        """
        try:
            if version is None:
                version = self._get_latest_version(dataset_id)
                if version == 0:
                    return []

            query = f"""
                SELECT column_name, column_type, position, masking_rule,
                       is_active, added_at, removed_at
                FROM {self.keyspace}.dataset_schema
                WHERE dataset_id = %s AND version = %s
                ORDER BY position ASC
            """
            result = self.db.execute(query, [dataset_id, version])

            columns = []
            for row in result:
                if not include_inactive and not row.is_active:
                    continue
                columns.append({
                    "name": row.column_name,
                    "type": row.column_type,
                    "position": row.position,
                    "mask_rule": row.masking_rule,
                    "masked": bool(row.masking_rule),
                    "is_active": row.is_active,
                    "added_at": row.added_at,
                    "removed_at": row.removed_at,
                })
            return columns

        except Exception as e:
            logger.error(f"Failed to get schema for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to get schema: {str(e)}")

    def get_schema_history(self, dataset_id: UUID) -> List[Dict[str, Any]]:
        """Return all schema versions with metadata."""
        try:
            query = f"""
                SELECT version, batch_id, created_at, column_count, change_summary
                FROM {self.keyspace}.dataset_schema_versions
                WHERE dataset_id = %s
                ORDER BY version DESC
            """
            result = self.db.execute(query, [dataset_id])
            return [
                {
                    "version": row.version,
                    "batch_id": row.batch_id,
                    "created_at": row.created_at,
                    "column_count": row.column_count,
                    "change_summary": row.change_summary,
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to get schema history for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to get schema history: {str(e)}")

    def update_masking_rule(
        self,
        dataset_id: UUID,
        column_name: str,
        mask_rule: Optional[str],
    ) -> None:
        """Update masking rule on the latest schema version for a column."""
        try:
            version = self._get_latest_version(dataset_id)
            if version == 0:
                raise DatabaseException("No schema exists for this dataset")

            # Find position for this column
            schema = self.get_schema(dataset_id, version, include_inactive=True)
            col = next((c for c in schema if c["name"] == column_name), None)
            if col is None:
                raise DatabaseException(f"Column '{column_name}' not found in schema")

            query = f"""
                UPDATE {self.keyspace}.dataset_schema
                SET masking_rule = %s
                WHERE dataset_id = %s AND version = %s AND position = %s
            """
            self.db.execute(query, [mask_rule, dataset_id, version, col["position"]])

            logger.info(f"Updated masking for {dataset_id}:{column_name} = {mask_rule}")

        except DatabaseException:
            raise
        except Exception as e:
            logger.error(f"Failed to update masking rule: {e}")
            raise DatabaseException(f"Failed to update masking rule: {str(e)}")

    def drop_column(self, dataset_id: UUID, column_name: str) -> int:
        """Soft-delete a column by marking is_active=false. Returns new version."""
        try:
            current_cols = self.get_schema(dataset_id, include_inactive=True)
            current_version = self._get_latest_version(dataset_id)
            new_version = current_version + 1
            now = datetime.utcnow()

            for col in current_cols:
                is_target = col["name"] == column_name
                self._insert_column(dataset_id, new_version, {
                    **col,
                    "is_active": False if is_target else col["is_active"],
                    "removed_at": now if is_target else col.get("removed_at"),
                }, now)

            active_count = sum(
                1 for c in current_cols
                if c["name"] != column_name and c.get("is_active", True)
            )
            self._register_version(
                dataset_id, new_version, None, now,
                column_count=active_count,
                change_summary=f"Dropped column: {column_name}",
            )

            logger.info(f"Soft-deleted column {column_name} in dataset {dataset_id}")
            return new_version

        except Exception as e:
            logger.error(f"Failed to drop column: {e}")
            raise DatabaseException(f"Failed to drop column: {str(e)}")

    def delete_schema(self, dataset_id: UUID) -> None:
        """Hard-delete all schema data for a dataset (used on dataset deletion)."""
        try:
            self.db.execute(
                f"DELETE FROM {self.keyspace}.dataset_schema WHERE dataset_id = %s",
                [dataset_id],
            )
            self.db.execute(
                f"DELETE FROM {self.keyspace}.dataset_schema_versions WHERE dataset_id = %s",
                [dataset_id],
            )
            logger.info(f"Deleted all schema data for dataset {dataset_id}")
        except Exception as e:
            logger.error(f"Failed to delete schema: {e}")
            raise DatabaseException(f"Failed to delete schema: {str(e)}")

    # ── Internal helpers ─────────────────────────────────────────────

    def _get_latest_version(self, dataset_id: UUID) -> int:
        """Return the latest schema version number, or 0 if none exists."""
        try:
            query = f"""
                SELECT version FROM {self.keyspace}.dataset_schema_versions
                WHERE dataset_id = %s LIMIT 1
            """
            row = self.db.execute(query, [dataset_id]).one()
            return row.version if row else 0
        except Exception:
            return 0

    def _insert_column(
        self,
        dataset_id: UUID,
        version: int,
        col: Dict[str, Any],
        now: datetime,
    ) -> None:
        """Insert a single column into the schema table."""
        query = f"""
            INSERT INTO {self.keyspace}.dataset_schema
            (dataset_id, version, column_name, column_type, position,
             masking_rule, is_active, added_at, removed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.db.execute(query, [
            dataset_id,
            version,
            col["name"],
            col.get("type", "str"),
            col.get("position", 0),
            col.get("masking_rule") or col.get("mask_rule"),
            col.get("is_active", True),
            col.get("added_at", now),
            col.get("removed_at"),
        ])

    def _register_version(
        self,
        dataset_id: UUID,
        version: int,
        batch_id: Optional[UUID],
        created_at: datetime,
        column_count: int,
        change_summary: str,
    ) -> None:
        """Register a schema version in the versions table."""
        query = f"""
            INSERT INTO {self.keyspace}.dataset_schema_versions
            (dataset_id, version, batch_id, created_at, column_count, change_summary)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        self.db.execute(query, [
            dataset_id, version, batch_id, created_at,
            column_count, change_summary,
        ])

    @staticmethod
    def _infer_columns(sample_row: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Infer column metadata from a sample data row."""
        columns = []
        for position, (col_name, value) in enumerate(sample_row.items()):
            columns.append({
                "name": col_name,
                "type": type(value).__name__,
                "position": position,
                "is_active": True,
                "masking_rule": None,
            })
        return columns

    @staticmethod
    def _diff_schemas(
        current_cols: List[Dict[str, Any]],
        new_sample_row: Dict[str, Any],
    ) -> Dict[str, set]:
        """
        Compare current schema against a new sample row.
        Returns added, removed, and type-changed column names.
        """
        current_names = {c["name"] for c in current_cols if c.get("is_active", True)}
        new_names = set(new_sample_row.keys())

        changed = set()
        for name in current_names & new_names:
            current_type = next(
                c["type"] for c in current_cols if c["name"] == name
            )
            new_type = type(new_sample_row[name]).__name__
            if current_type != new_type:
                changed.add(name)

        return {
            "added": new_names - current_names,
            "removed": current_names - new_names,
            "changed": changed,
        }
