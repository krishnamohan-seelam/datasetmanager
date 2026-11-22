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

    # Bounded retries for the version-claim CAS loop below. Each retry means
    # another writer won the race for the version number we tried; this caps
    # how many times we re-read-and-retry before giving up (Mandatory #13).
    _MAX_VERSION_CLAIM_ATTEMPTS = 5

    def __init__(self):
        self.db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        self.keyspace = settings.CASSANDRA_KEYSPACE
        self._pagination_cache = None

    def _get_pagination_cache(self):
        """Lazily-constructed handle to the row-page cache, only needed by
        drop_column's invalidation call. Same lazy-construction pattern as
        RedisCacheService's pagination-cache handle (app/integrations/redis_cache.py)."""
        if self._pagination_cache is None:
            from .pagination_cache import PaginationCacheService

            self._pagination_cache = PaginationCacheService(
                host=settings.REDIS_HOST, port=settings.REDIS_PORT
            )
        return self._pagination_cache

    # ── Public API ───────────────────────────────────────────────────

    def create_schema(
        self,
        dataset_id: UUID,
        sample_row: Dict[str, Any],
        batch_id: Optional[UUID] = None,
        masking_config: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        Create initial schema (version 1) from a sample data row.
        Returns the version number.

        `masking_config` (column_name -> mask_rule) is applied to the
        inferred columns only here, at creation — it's the one point where a
        caller (dataset upload) can seed masking rules before any column
        exists yet. Folded in from the M5 handoff note: dataset-creation-time
        masking config used to be written to the now-dead `datasets.masking_config`
        blob and never actually applied; this is where it has to land instead,
        since the schema doesn't exist until first upload.

        Concurrency: if another writer wins the race to create version 1
        first, falls back to evolving against the schema that writer just
        created, instead of this call silently re-registering version 1 over
        it (Mandatory #13).
        """
        try:
            version = self._try_claim_v1(dataset_id, sample_row, batch_id, masking_config)
            if version is not None:
                return version
            return self.evolve_schema(dataset_id, sample_row, batch_id)
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(f"Failed to create schema for {dataset_id}: {e}")
            raise DatabaseException(f"Failed to create schema: {str(e)}")

    def evolve_schema(
        self,
        dataset_id: UUID,
        new_sample_row: Dict[str, Any],
        batch_id: Optional[UUID] = None,
        masking_config: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        Compare incoming data against the latest schema version.
        If columns changed, create a new version. Otherwise, return the
        current version unchanged.

        Returns the (possibly new) version number.

        Concurrency (Mandatory #13): version numbers are claimed via a
        Cassandra lightweight transaction (INSERT ... IF NOT EXISTS), not a
        plain read-then-increment. If another writer claims the version
        number this call computed first, this re-reads the now-current
        state and retries (bounded by `_MAX_VERSION_CLAIM_ATTEMPTS`) instead
        of two concurrent uploads both winning the same version number and
        corrupting history.
        """
        try:
            for _attempt in range(self._MAX_VERSION_CLAIM_ATTEMPTS):
                current_cols = self.get_schema(dataset_id)

                # First upload — no existing schema yet.
                if not current_cols:
                    version = self._try_claim_v1(dataset_id, new_sample_row, batch_id, masking_config)
                    if version is not None:
                        return version
                    continue  # someone else claimed v1 between our check and now

                diff = self._diff_schemas(current_cols, new_sample_row)

                # No changes — reuse current version.
                if not diff["added"] and not diff["removed"] and not diff["changed"]:
                    return self._get_latest_version(dataset_id)

                current_version = self._get_latest_version(dataset_id)
                new_version = current_version + 1
                now = datetime.utcnow()

                # Carry forward active columns, applying changes
                new_columns = []
                position = 0

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

                # Claim the version number BEFORE writing any column rows, so
                # a losing writer never leaves orphaned column data behind at
                # a version number it didn't win.
                claimed = self._claim_version(
                    dataset_id, new_version, batch_id, now,
                    column_count=active_count,
                    change_summary=summary,
                )
                if not claimed:
                    continue  # another writer claimed new_version first — retry

                for col in new_columns:
                    self._insert_column(dataset_id, new_version, col, now)

                logger.info(
                    f"Schema evolved to v{new_version} for dataset {dataset_id}: {summary}"
                )
                return new_version

            raise DatabaseException(
                f"Could not evolve schema for dataset {dataset_id} after "
                f"{self._MAX_VERSION_CLAIM_ATTEMPTS} attempts — too many concurrent writers"
            )

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
        """Soft-delete a column by marking is_active=false. Returns new version.

        Same CAS version-claim as evolve_schema (Mandatory #13's bug class
        applies here too: a concurrent evolve_schema or another drop_column
        call could otherwise race on the same new_version).

        Invalidates the pagination cache on success — the row/column half of
        Mandatory #15 that M5 left as a TODO for this module, since dropping
        a column changes what get_rows/export_dataset return.
        """
        try:
            for _attempt in range(self._MAX_VERSION_CLAIM_ATTEMPTS):
                current_cols = self.get_schema(dataset_id, include_inactive=True)
                current_version = self._get_latest_version(dataset_id)
                new_version = current_version + 1
                now = datetime.utcnow()

                active_count = sum(
                    1 for c in current_cols
                    if c["name"] != column_name and c.get("is_active", True)
                )
                claimed = self._claim_version(
                    dataset_id, new_version, None, now,
                    column_count=active_count,
                    change_summary=f"Dropped column: {column_name}",
                )
                if not claimed:
                    continue  # another writer claimed new_version first — retry

                for col in current_cols:
                    is_target = col["name"] == column_name
                    self._insert_column(dataset_id, new_version, {
                        **col,
                        "is_active": False if is_target else col["is_active"],
                        "removed_at": now if is_target else col.get("removed_at"),
                    }, now)

                try:
                    self._get_pagination_cache().invalidate_dataset(dataset_id)
                except Exception as e:
                    logger.warning(f"Cache invalidation failed after dropping column {column_name}: {e}")

                logger.info(f"Soft-deleted column {column_name} in dataset {dataset_id}")
                return new_version

            raise DatabaseException(
                f"Could not drop column '{column_name}' for dataset {dataset_id} after "
                f"{self._MAX_VERSION_CLAIM_ATTEMPTS} attempts — too many concurrent writers"
            )

        except DatabaseException:
            raise
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

    def _try_claim_v1(
        self,
        dataset_id: UUID,
        sample_row: Dict[str, Any],
        batch_id: Optional[UUID],
        masking_config: Optional[Dict[str, str]],
    ) -> Optional[int]:
        """Attempt to claim version 1 via CAS. Returns 1 if this call won the
        claim (and has persisted the columns), or None if another writer
        already claimed it — the caller must fall back to evolving instead."""
        now = datetime.utcnow()
        columns = self._infer_columns(sample_row, masking_config)
        claimed = self._claim_version(
            dataset_id, 1, batch_id, now,
            column_count=len(columns),
            change_summary="Initial schema",
        )
        if not claimed:
            return None
        for col in columns:
            self._insert_column(dataset_id, 1, col, now)
        logger.info(f"Created schema v1 for dataset {dataset_id} ({len(columns)} columns)")
        return 1

    def _claim_version(
        self,
        dataset_id: UUID,
        version: int,
        batch_id: Optional[UUID],
        created_at: datetime,
        column_count: int,
        change_summary: str,
    ) -> bool:
        """Atomically claim a schema version number via a Cassandra
        lightweight transaction (INSERT ... IF NOT EXISTS). Returns True if
        this call won the claim, False if another writer already registered
        this version number — the caller must retry against the new current
        state rather than overwrite it.

        This is the fix for Mandatory #13: the previous read-then-increment
        (`new_version = current_version + 1`, written with no guard) let two
        concurrent uploads both pick the same new_version and race to write.
        """
        query = f"""
            INSERT INTO {self.keyspace}.dataset_schema_versions
            (dataset_id, version, batch_id, created_at, column_count, change_summary)
            VALUES (%s, %s, %s, %s, %s, %s)
            IF NOT EXISTS
        """
        result = self.db.execute(
            query, [dataset_id, version, batch_id, created_at, column_count, change_summary]
        )
        return bool(result.was_applied)

    def _get_latest_version(self, dataset_id: UUID) -> int:
        """Return the latest schema version number, or 0 if none exists yet.

        Only an empty result means "no schema yet". A transient Cassandra
        error (timeout, connection failure) now propagates as a
        DatabaseException instead of being swallowed into 0 — previously
        that made evolve_schema treat a transient failure as "first upload"
        and re-register version 1 over an existing schema (Mandatory #14).
        """
        query = f"""
            SELECT version FROM {self.keyspace}.dataset_schema_versions
            WHERE dataset_id = %s LIMIT 1
        """
        try:
            row = self.db.execute(query, [dataset_id]).one()
        except Exception as e:
            raise DatabaseException(f"Failed to look up schema version for {dataset_id}: {e}")
        return row.version if row else 0

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

    @staticmethod
    def _infer_columns(
        sample_row: Dict[str, Any], masking_config: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Infer column metadata from a sample data row.

        `masking_config` (column_name -> mask_rule), when given, seeds each
        column's masking_rule at creation time.
        """
        masking_config = masking_config or {}
        columns = []
        for position, (col_name, value) in enumerate(sample_row.items()):
            columns.append({
                "name": col_name,
                "type": type(value).__name__,
                "position": position,
                "is_active": True,
                "masking_rule": masking_config.get(col_name),
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
