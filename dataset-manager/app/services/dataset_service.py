"""
Dataset management service
"""

import json
import csv
import hashlib
import logging
import math
import re
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from io import StringIO, BytesIO

from ..cassandra_client import CassandraClient
from ..core.exceptions import (
    DatasetNotFoundException,
    DatasetAlreadyExistsException,
    DatabaseException,
)
from ..core.masking import DataMasker
from ..core.config import settings
from ..schemas.common import Role
from .pagination_cache import PaginationCacheService, PageRequest
from .schema_service import SchemaService
from .batch_service import BatchService


logger = logging.getLogger(__name__)


class DatasetService:
    """Service for dataset management operations"""

    def __init__(self):
        self.db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        self.keyspace = settings.CASSANDRA_KEYSPACE
        self.cache = PaginationCacheService(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
        )
        self.schema_service = SchemaService()
        self.batch_service = BatchService()

    def _get_table_name(self, dataset_id: UUID) -> str:
        """Generate a safe Cassandra table name from dataset ID"""
        # Cassandra table names should be alphanumeric with underscores
        # UUIDs are safe if we prefix them and replace hyphens
        return f"ds_rows_{str(dataset_id).replace('-', '_')}"

    def _get_cassandra_type(self, value: Any) -> str:
        """Map Python types to Cassandra types"""
        if isinstance(value, int):
            return "BIGINT"
        elif isinstance(value, float):
            return "DOUBLE"
        elif isinstance(value, bool):
            return "BOOLEAN"
        else:
            return "TEXT"

    def _sanitize_col_name(self, col_name: str) -> str:
        """Sanitize column name for Cassandra (alphanumeric and underscores)"""
        if not col_name:
            return "unknown_col"
        # Replace non-alphanumeric with underscore, lowercase everything
        safe = "".join([c if c.isalnum() else "_" for c in col_name]).lower()
        if safe[0].isdigit():
            safe = f"col_{safe}"
        return safe

    def _ensure_table_exists(self, dataset_id: UUID, table_name: str, sample_row: Optional[Dict[str, Any]] = None):
        """Ensure the specific table for the dataset exists with structured columns"""
        try:
            # Check if table already exists
            check_query = f"SELECT table_name FROM system_schema.tables WHERE keyspace_name = '{self.keyspace}' AND table_name = '{table_name}'"
            if self.db.execute(check_query).one():
                return

            # Base columns — batch_id is part of the composite partition key
            columns = [
                "batch_id UUID",
                "row_chunk_id INT",
                "row_id BIGINT"
            ]
            
            if sample_row:
                for col_name, value in sample_row.items():
                    safe_name = self._sanitize_col_name(col_name)
                    cass_type = self._get_cassandra_type(value)
                    columns.append(f"{safe_name} {cass_type}")
            else:
                # Fallback if no sample row (should not happen with new flow)
                columns.append("row_data TEXT")

            query = f"""
                CREATE TABLE IF NOT EXISTS {self.keyspace}.{table_name} (
                    {", ".join(columns)},
                    PRIMARY KEY ((batch_id, row_chunk_id), row_id)
                ) WITH CLUSTERING ORDER BY (row_id ASC);
            """
            self.db.execute(query)
            logger.info(f"Created structured table {table_name} for dataset {dataset_id}")
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            raise DatabaseException(f"Failed to create storage for dataset: {str(e)}")

    def _table_has_batch_id(self, table_name: str) -> bool:
        """Check if a ds_rows_* table has the batch_id column (new schema)."""
        try:
            query = (
                f"SELECT column_name FROM system_schema.columns "
                f"WHERE keyspace_name = '{self.keyspace}' AND table_name = '{table_name}' "
                f"AND column_name = 'batch_id'"
            )
            return self.db.execute(query).one() is not None
        except Exception:
            return False

    def create_dataset(
        self,
        name: str,
        owner: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = False,
        file_format: str = "csv",
        size_bytes: int = 0,
        status: str = "ready",
        masking_config: Optional[Dict[str, str]] = None,
        batch_frequency: str = "once",
    ) -> UUID:
        """Create a new dataset with batch tracking fields"""
        try:
            dataset_id = uuid4()
            created_at = datetime.utcnow()
            tags_str = self._format_tags(tags)

            query = f"""
                INSERT INTO {self.keyspace}.datasets 
                (dataset_id, name, description, owner, tags, is_public,
                 created_at, updated_at, row_count, size_bytes, file_format,
                 status, masking_config, batch_frequency, total_batches, schema_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            masking_config_json = json.dumps(masking_config or {})
            self.db.execute(
                query,
                [
                    dataset_id,
                    name,
                    description,
                    owner,
                    tags_str,
                    is_public,
                    created_at,
                    created_at,
                    0,
                    size_bytes,
                    file_format,
                    status,
                    masking_config_json,
                    batch_frequency,
                    0,
                    0,
                ],
            )

            # Invalidate global listing caches
            self.cache.invalidate_datasets_list()

            logger.info(f"Created dataset {dataset_id} for user {owner}")
            return dataset_id
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            raise DatabaseException(f"Failed to create dataset: {str(e)}")

    def get_dataset(self, dataset_id: UUID) -> Dict[str, Any]:
        """Get dataset metadata"""
        try:
            query = f"""
                SELECT dataset_id, name, description, owner, tags, is_public, 
                       created_at, updated_at, row_count, size_bytes, file_format, status, masking_config
                FROM {self.keyspace}.datasets
                WHERE dataset_id = %s
            """

            result = self.db.execute(query, [dataset_id])
            row = result.one()

            if not row:
                raise DatasetNotFoundException(f"Dataset {dataset_id} not found")

            masking_config = (
                json.loads(row.masking_config) if row.masking_config else {}
            )

            return {
                "id": row.dataset_id,
                "name": row.name,
                "description": row.description,
                "owner": row.owner,
                "tags": self._parse_tags(row.tags),
                "is_public": row.is_public,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "row_count": row.row_count,
                "size_bytes": getattr(row, "size_bytes", 0),
                "file_format": getattr(row, "file_format", "csv"),
                "status": getattr(row, "status", "ready"),
                "masking_config": masking_config,
            }
        except DatasetNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to get dataset: {e}")
            raise DatabaseException(f"Failed to get dataset: {str(e)}")

    def list_datasets(
        self, page: int = 1, page_size: int = 100, search: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List datasets with pagination and optional search (cached).

        Previously this always ran `LIMIT 1000` and paginated/summed in
        Python, so any page past the 1000th row silently returned
        empty/wrong data and `total` undercounted once the real dataset
        count exceeded 1000. Fixed here by scaling the scan to the requested
        page (so paging deep into a >1000-row table still returns real data)
        and computing `total` from an actual `COUNT(*)`, not `len(all_rows)`.

        Search still requires a full scan — Cassandra has no server-side
        text search here without a secondary index — but that scan is no
        longer capped at a hardcoded 1000 rows, so results and the reported
        total are no longer silently wrong past that cap.
        """
        try:
            # Check cache first
            cached = self.cache.get_datasets_list(page, page_size, search)
            if cached is not None:
                logger.debug(f"Cache hit for datasets list page={page}")
                return cached

            offset = (page - 1) * page_size
            select_cols = (
                "dataset_id, name, description, owner, tags, is_public, "
                "created_at, updated_at, row_count, size_bytes, file_format, status"
            )

            if search:
                # Full scan is unavoidable for a substring search without an
                # index, but it's no longer bounded at 1000 rows.
                query = f"SELECT {select_cols} FROM {self.keyspace}.datasets"
                all_rows = list(self.db.execute(query))

                search_lower = search.lower()
                matched_rows = [
                    row
                    for row in all_rows
                    if (row.name and search_lower in row.name.lower())
                    or (row.description and search_lower in row.description.lower())
                ]
                total = len(matched_rows)
                paginated_rows = matched_rows[offset : offset + page_size]
            else:
                # Scan exactly as far as this page needs rather than a fixed
                # cap, so page N is always reachable regardless of table size.
                scan_limit = offset + page_size
                query = f"SELECT {select_cols} FROM {self.keyspace}.datasets LIMIT {scan_limit}"
                paginated_rows = list(self.db.execute(query))[offset : offset + page_size]

                count_row = self.db.execute(
                    f"SELECT COUNT(*) as count FROM {self.keyspace}.datasets"
                ).one()
                total = count_row.count if count_row else 0

            datasets = [
                {
                    "id": row.dataset_id,
                    "name": row.name,
                    "description": row.description,
                    "owner": row.owner,
                    "tags": self._parse_tags(row.tags),
                    "is_public": row.is_public,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "row_count": row.row_count,
                    "size_bytes": getattr(row, "size_bytes", 0),
                    "file_format": getattr(row, "file_format", "csv"),
                    "status": getattr(row, "status", "ready"),
                }
                for row in paginated_rows
            ]

            # Store in cache
            self.cache.set_datasets_list(page, page_size, datasets, total, search)

            return datasets, total
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            raise DatabaseException(f"Failed to list datasets: {str(e)}")

    def update_dataset(self, dataset_id: UUID, **updates) -> Dict[str, Any]:
        """Update dataset metadata"""
        try:
            # Get current dataset
            dataset = self.get_dataset(dataset_id)

            # Build update query
            update_fields = []
            values = []

            for key, value in updates.items():
                if key == "masking_config":
                    # Unquoted, consistent with every other field here —
                    # masking_config isn't a CQL reserved word, so the quoting
                    # was never needed.
                    update_fields.append("masking_config = %s")
                    values.append(json.dumps(value))
                elif key == "tags":
                    update_fields.append("tags = %s")
                    values.append(self._format_tags(value))
                elif key in ["name", "description", "is_public"]:
                    update_fields.append(f"{key} = %s")
                    values.append(value)

            if not update_fields:
                return dataset

            update_fields.append("updated_at = %s")
            values.append(datetime.utcnow())
            values.append(dataset_id)

            query = f"""
                UPDATE {self.keyspace}.datasets
                SET {", ".join(update_fields)}
                WHERE dataset_id = %s
            """

            self.db.execute(query, values)
            logger.info(f"Updated dataset {dataset_id}")

            # Invalidate caches
            self.cache.invalidate_all_for_dataset(dataset_id)

            return self.get_dataset(dataset_id)
        except DatasetNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to update dataset: {e}")
            raise DatabaseException(f"Failed to update dataset: {str(e)}")

    def delete_dataset(self, dataset_id: UUID) -> bool:
        """Delete dataset and all associated data (schema, batches, rows, permissions)"""
        try:
            # Invalidate caches first
            self.cache.invalidate_all_for_dataset(dataset_id)

            # Delete dataset metadata
            query = f"DELETE FROM {self.keyspace}.datasets WHERE dataset_id = %s"
            self.db.execute(query, [dataset_id])

            # Delete schema (versions + columns) via SchemaService
            try:
                self.schema_service.delete_schema(dataset_id)
            except Exception as e:
                logger.warning(f"Failed to delete schema for {dataset_id}: {e}")

            # Delete all batches via BatchService
            try:
                self.batch_service.delete_all_batches(dataset_id)
            except Exception as e:
                logger.warning(f"Failed to delete batches for {dataset_id}: {e}")

            # Delete dynamic row table
            table_name = self._get_table_name(dataset_id)
            try:
                query = f"DROP TABLE IF EXISTS {self.keyspace}.{table_name}"
                self.db.execute(query)
                logger.info(f"Dropped table {table_name}")
            except Exception as e:
                logger.warning(f"Failed to drop table {table_name}: {e}")

            # Delete permissions
            query = (
                f"DELETE FROM {self.keyspace}.dataset_permissions WHERE dataset_id = %s"
            )
            self.db.execute(query, [dataset_id])

            logger.info(f"Deleted dataset {dataset_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete dataset: {e}")
            raise DatabaseException(f"Failed to delete dataset: {str(e)}")

    def insert_rows(
        self,
        dataset_id: UUID,
        rows: List[Dict[str, Any]],
        chunk_size: int = 10000,
        batch_size: int = 50,
        batch_id: Optional[UUID] = None,
        batch_date: Optional[datetime] = None,
        uploaded_by: str = "",
        file_format: str = "csv",
        size_bytes: int = 0,
    ) -> int:
        """Insert rows into dataset using batched writes.

        Creates a batch entry and evolves schema automatically.
        """
        try:
            from cassandra.query import BatchStatement, SimpleStatement, BatchType

            now = datetime.utcnow()
            batch_date = batch_date or now

            # Create batch entry if not provided
            if batch_id is None:
                batch_id = self.batch_service.create_batch(
                    dataset_id=dataset_id,
                    batch_date=batch_date,
                    file_format=file_format,
                    size_bytes=size_bytes,
                    uploaded_by=uploaded_by,
                )

            inserted_count = 0
            table_name = self._get_table_name(dataset_id)

            # Ensure table exists and evolve schema
            schema_version = 0
            if rows:
                self._ensure_table_exists(dataset_id, table_name, rows[0])
                # Evolve schema (creates v1 on first upload, diffs on subsequent)
                schema_version = self.schema_service.evolve_schema(
                    dataset_id, rows[0], batch_id
                )

            for chunk_id, i in enumerate(range(0, len(rows), chunk_size)):
                chunk = rows[i : i + chunk_size]
                batch = BatchStatement(batch_type=BatchType.UNLOGGED)
                batch_count = 0

                for row_id, row_data in enumerate(chunk):
                    cols = ["batch_id", "row_chunk_id", "row_id"]
                    placeholders = ["%s", "%s", "%s"]
                    values = [batch_id, chunk_id, row_id]

                    for col_name, val in row_data.items():
                        if val is None or (isinstance(val, float) and math.isnan(val)):
                            continue
                        cols.append(self._sanitize_col_name(col_name))
                        placeholders.append("%s")
                        values.append(val)

                    stmt = SimpleStatement(f"""
                        INSERT INTO {self.keyspace}.{table_name}
                        ({', '.join(cols)})
                        VALUES ({', '.join(placeholders)})
                    """)
                    batch.add(stmt, values)
                    batch_count += 1
                    inserted_count += 1

                    if batch_count >= batch_size:
                        self.db.execute(batch)
                        batch = BatchStatement(batch_type=BatchType.UNLOGGED)
                        batch_count = 0

                if batch_count > 0:
                    self.db.execute(batch)

            # Update dataset metadata
            total_batches = self.batch_service.count_batches(dataset_id)
            query = f"""
                UPDATE {self.keyspace}.datasets
                SET row_count = %s, updated_at = %s,
                    latest_batch_id = %s, latest_batch_date = %s,
                    total_batches = %s, schema_version = %s
                WHERE dataset_id = %s
            """
            self.db.execute(query, [
                inserted_count, now, batch_id, batch_date,
                total_batches, schema_version, dataset_id,
            ])

            # Update batch status
            self.batch_service.update_batch_status(
                dataset_id, batch_id, batch_date,
                status="ready",
                row_count=inserted_count,
                schema_version=schema_version,
            )

            # Invalidate caches: row pages (single entrypoint) + dataset listings
            self.cache.invalidate_dataset(dataset_id)
            self.cache.invalidate_datasets_list()

            logger.info(
                f"Inserted {inserted_count} rows into dataset {dataset_id} "
                f"(batch={batch_id}, schema_v={schema_version})"
            )
            return inserted_count
        except Exception as e:
            logger.error(f"Failed to insert rows: {e}")
            # Mark batch as failed
            if batch_id:
                try:
                    self.batch_service.update_batch_status(
                        dataset_id, batch_id, batch_date or datetime.utcnow(),
                        status="failed",
                    )
                except Exception:
                    pass
            raise DatabaseException(f"Failed to insert rows: {str(e)}")

    # ── Schema / Masking delegation ───────────────────────────────────
    # These thin wrappers delegate to SchemaService for backward compat.

    def get_dataset_schema(self, dataset_id: UUID) -> List[Dict[str, Any]]:
        """Get dataset schema columns (latest version, active only)."""
        return self.schema_service.get_schema(dataset_id)

    def update_masking_rule(
        self, dataset_id: UUID, column_name: str, mask_rule: Optional[str]
    ):
        """Update a column's masking rule.

        ``dataset_schema.masking_rule`` (via SchemaService) is the single source
        of truth for masking; ``datasets.masking_config`` is no longer written by
        this path nor read on the row/export path (Normal #12).
        """
        try:
            self.get_dataset(dataset_id)  # 404 if the dataset doesn't exist
            self.schema_service.update_masking_rule(dataset_id, column_name, mask_rule)

            # The masking change also changes the cache key (schema revision),
            # but clear eagerly so stale entries don't linger until TTL.
            self.cache.invalidate_dataset(dataset_id)

            logger.info(f"Updated masking rule for {dataset_id}:{column_name} to {mask_rule}")
        except Exception as e:
            logger.error(f"Failed to update masking rule for {dataset_id}:{column_name}: {e}")
            if isinstance(e, DatasetNotFoundException):
                raise
            raise DatabaseException(f"Failed to update masking rule: {str(e)}")

    # ── Read-path helpers ─────────────────────────────────────────────

    def _active_schema(self, dataset_id: UUID) -> List[Dict[str, Any]]:
        """Active (non-soft-deleted) schema columns, with legacy-table fallback."""
        try:
            schema = self.schema_service.get_schema(dataset_id)
            return [c for c in schema if c.get("is_active", True)]
        except Exception:
            # Legacy schema table might have a different PK - try direct query
            try:
                legacy_query = f"""
                    SELECT column_name, column_type, position, masking_rule
                    FROM {self.keyspace}.dataset_schema
                    WHERE dataset_id = %s
                """
                result = self.db.execute(legacy_query, [dataset_id])
                return [
                    {
                        "name": row.column_name,
                        "type": getattr(row, "column_type", "str"),
                        "mask_rule": getattr(row, "masking_rule", None),
                        "is_active": True,
                    }
                    for row in result
                ]
            except Exception:
                return []

    @staticmethod
    def _schema_revision(schema: List[Dict[str, Any]]) -> str:
        """Fingerprint of the active columns and their masking rules.

        Changes whenever the active column set (schema version / soft-delete) or
        any masking rule changes, so it segments the pagination cache key by
        schema version and masking revision (Mandatory #12).
        """
        material = "|".join(
            f"{c['name']}:{c.get('type')}:{c.get('mask_rule') or ''}" for c in schema
        )
        return hashlib.sha1(material.encode()).hexdigest()[:12]

    @staticmethod
    def _masking_rules(schema: List[Dict[str, Any]]) -> Dict[str, str]:
        return {c["name"]: c["mask_rule"] for c in schema if c.get("mask_rule")}

    def _select_clause(
        self,
        schema: List[Dict[str, Any]],
        base_cols: List[str],
        requested: Optional[List[str]] = None,
    ) -> str:
        """Build the SELECT list from active schema columns instead of ``*`` so
        soft-deleted / untracked physical columns are never returned
        (Mandatory #11). Explicitly requested columns are restricted to active ones.
        """
        if not schema:
            # No tracked schema at all (very old datasets): nothing can be
            # soft-deleted and no masking rules exist, so * is the only option.
            if not requested:
                return "*"
            names = requested
        else:
            active = [c["name"] for c in schema]
            if requested:
                active_set = set(active)
                names = [c for c in requested if c in active_set]
            else:
                names = active
        cols = list(base_cols)
        for name in names:
            safe = self._sanitize_col_name(name)
            if safe not in cols:
                cols.append(safe)
        return ", ".join(cols)

    @staticmethod
    def _apply_masking(
        row: Dict[str, Any], rules: Dict[str, str], user_role: str
    ) -> None:
        for col_name, mask_rule in rules.items():
            if col_name in row:
                row[col_name] = DataMasker.mask_value(row[col_name], mask_rule, user_role)

    def get_rows(self, req: PageRequest) -> Tuple[List[Dict[str, Any]], int]:
        """Get a paginated rows page with optional masking (cached)."""
        try:
            dataset_id = req.dataset_id
            dataset = self.get_dataset(dataset_id)

            # Active schema drives the select list, masking rules and cache key.
            schema = self._active_schema(dataset_id)
            schema_rev = self._schema_revision(schema)

            cached = self.cache.get_rows_page(req, schema_rev)
            if cached is not None:
                logger.debug(f"Cache hit for dataset {dataset_id} rows page={req.page}")
                return cached

            masking_rules = self._masking_rules(schema)

            table_name = self._get_table_name(dataset_id)
            use_legacy_query = not self._table_has_batch_id(table_name)

            batch_id = req.batch_id
            if not use_legacy_query and batch_id is None:
                latest_batch = self.batch_service.get_latest_batch(dataset_id)
                if latest_batch:
                    batch_id = latest_batch["batch_id"]
                else:
                    return [], 0

            name_map = {self._sanitize_col_name(c["name"]): c["name"] for c in schema}

            offset = (req.page - 1) * req.page_size
            chunk_id = offset // 10000
            start_row = offset % 10000

            base_cols = (
                ["row_chunk_id", "row_id"]
                if use_legacy_query
                else ["batch_id", "row_chunk_id", "row_id"]
            )
            select_clause = self._select_clause(
                schema, base_cols, list(req.columns) if req.columns else None
            )

            if use_legacy_query:
                query = f"""
                    SELECT {select_clause}
                    FROM {self.keyspace}.{table_name}
                    WHERE row_chunk_id = %s
                    ORDER BY row_id ASC
                    LIMIT %s
                """
                result = self.db.execute(query, [chunk_id, req.page_size + start_row])
            else:
                query = f"""
                    SELECT {select_clause}
                    FROM {self.keyspace}.{table_name}
                    WHERE batch_id = %s AND row_chunk_id = %s
                    ORDER BY row_id ASC
                    LIMIT %s
                """
                result = self.db.execute(
                    query, [batch_id, chunk_id, req.page_size + start_row]
                )
            rows = list(result)[start_row : start_row + req.page_size]

            do_mask = req.apply_masking and req.user_role != Role.ADMIN.value
            processed_rows = []
            for row in rows:
                row_dict = {}
                for field in row._fields:
                    if field in ("batch_id", "row_chunk_id", "row_id"):
                        continue
                    row_dict[name_map.get(field, field)] = getattr(row, field)
                if do_mask:
                    self._apply_masking(row_dict, masking_rules, req.user_role)
                processed_rows.append(row_dict)

            total = dataset.get("row_count", 0)
            self.cache.set_rows_page(req, processed_rows, total, schema_rev)
            return processed_rows, total
        except DatasetNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to get rows: {e}")
            raise DatabaseException(f"Failed to get rows: {str(e)}")

    def export_dataset(
        self,
        dataset_id: UUID,
        format: str = "csv",
        user_role: str = "viewer",
    ) -> bytes:
        """Export dataset to CSV or JSON (active schema columns only, masked for non-admins)."""
        try:
            self.get_dataset(dataset_id)
            table_name = self._get_table_name(dataset_id)
            has_batch_id = self._table_has_batch_id(table_name)

            schema = self._active_schema(dataset_id)
            name_map = {self._sanitize_col_name(c["name"]): c["name"] for c in schema}
            masking_rules = self._masking_rules(schema)

            if has_batch_id:
                latest_batch = self.batch_service.get_latest_batch(dataset_id)
                if not latest_batch:
                    return b""  # No data
                select_clause = self._select_clause(
                    schema, ["batch_id", "row_chunk_id", "row_id"]
                )
                query = (
                    f"SELECT {select_clause} FROM {self.keyspace}.{table_name} "
                    f"WHERE batch_id = %s AND row_chunk_id = %s"
                )
                key_params = [latest_batch["batch_id"]]
            else:
                select_clause = self._select_clause(schema, ["row_chunk_id", "row_id"])
                query = (
                    f"SELECT {select_clause} FROM {self.keyspace}.{table_name} "
                    f"WHERE row_chunk_id = %s"
                )
                key_params = []

            rows = []
            chunk_id = 0
            while True:
                result = list(self.db.execute(query, key_params + [chunk_id]))
                if not result:
                    break
                for row in result:
                    row_dict = {}
                    for field in row._fields:
                        if field in ("batch_id", "row_chunk_id", "row_id"):
                            continue
                        row_dict[name_map.get(field, field)] = getattr(row, field)
                    rows.append(row_dict)
                chunk_id += 1

            if user_role != Role.ADMIN.value:
                for row in rows:
                    self._apply_masking(row, masking_rules, user_role)

            if format.lower() == "json":
                return json.dumps(rows, default=str).encode()
            return self._export_csv(rows)
        except DatasetNotFoundException:
            raise
        except Exception as e:
            logger.error(f"Failed to export dataset: {e}")
            raise DatabaseException(f"Failed to export dataset: {str(e)}")

    @staticmethod
    def _export_csv(rows: List[Dict[str, Any]]) -> bytes:
        """Export rows to CSV format"""
        if not rows:
            return b""

        output = StringIO()
        fieldnames = rows[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)

        return output.getvalue().encode()

    @staticmethod
    def _parse_tags(tags_str: Optional[str]) -> List[str]:
        """Convert comma-separated string to list of tags"""
        if not tags_str:
            return []
        return [t.strip() for t in tags_str.split(",") if t.strip()]

    @staticmethod
    def _format_tags(tags: Any) -> str:
        """Convert list or string of tags to comma-separated string"""
        if not tags:
            return ""
        if isinstance(tags, str):
            return tags
        if isinstance(tags, list):
            return ",".join([str(t).strip() for t in tags if str(t).strip()])
        return str(tags)
