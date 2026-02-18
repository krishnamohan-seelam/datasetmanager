"""
Dataset management service
"""

import json
import csv
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
from .pagination_cache import PaginationCacheService


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

            # Base columns
            columns = [
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
                    PRIMARY KEY (row_chunk_id, row_id)
                ) WITH CLUSTERING ORDER BY (row_id ASC);
            """
            self.db.execute(query)
            logger.info(f"Created structured table {table_name} for dataset {dataset_id}")
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            raise DatabaseException(f"Failed to create storage for dataset: {str(e)}")

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
    ) -> UUID:
        """Create a new dataset"""
        try:
            dataset_id = uuid4()
            created_at = datetime.utcnow()
            tags_str = self._format_tags(tags)

            query = f"""
                INSERT INTO {self.keyspace}.datasets 
                (dataset_id, name, description, owner, tags, is_public, created_at, updated_at, row_count, size_bytes, file_format, status, masking_config)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ],
            )

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
        """List datasets with pagination and optional search (cached)"""
        try:
            # Check cache first
            cached = self.cache.get_datasets_list(page, page_size, search)
            if cached is not None:
                logger.debug(f"Cache hit for datasets list page={page}")
                return cached

            # Cache miss — query Cassandra
            query = f"""
                SELECT dataset_id, name, description, owner, tags, is_public, 
                       created_at, updated_at, row_count, size_bytes, file_format, status
                FROM {self.keyspace}.datasets
                LIMIT 1000
            """

            result = self.db.execute(query)
            all_rows = list(result)

            # Filter by search if provided
            if search:
                search_lower = search.lower()
                all_rows = [
                    row
                    for row in all_rows
                    if search_lower in row.name.lower()
                    or (row.description and search_lower in row.description.lower())
                ]

            # Apply pagination
            offset = (page - 1) * page_size
            paginated_rows = all_rows[offset : offset + page_size]

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

            total = len(all_rows)
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
        """Delete dataset and all associated data"""
        try:
            # Invalidate caches first
            self.cache.invalidate_all_for_dataset(dataset_id)

            # Delete dataset
            query = f"DELETE FROM {self.keyspace}.datasets WHERE dataset_id = %s"
            self.db.execute(query, [dataset_id])

            # Delete schema
            query = f"DELETE FROM {self.keyspace}.dataset_schema WHERE dataset_id = %s"
            self.db.execute(query, [dataset_id])

            # Delete dynamic table
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
        self, dataset_id: UUID, rows: List[Dict[str, Any]], chunk_size: int = 10000,
        batch_size: int = 50,
    ) -> int:
        """Insert rows into dataset using batched writes for throughput"""
        try:
            from cassandra.query import BatchStatement, SimpleStatement, BatchType

            inserted_count = 0
            table_name = self._get_table_name(dataset_id)

            # Ensure table exists before insertion, using the first row for schema
            if rows:
                self._ensure_table_exists(dataset_id, table_name, rows[0])
                # Infer and set schema metadata
                self.set_dataset_schema(dataset_id, rows[0])

            for chunk_id, i in enumerate(range(0, len(rows), chunk_size)):
                chunk = rows[i : i + chunk_size]
                batch = BatchStatement(batch_type=BatchType.UNLOGGED)
                batch_count = 0

                for row_id, row_data in enumerate(chunk):
                    # Build dynamic insert query
                    cols = ["row_chunk_id", "row_id"]
                    placeholders = ["%s", "%s"]
                    values = [chunk_id, row_id]

                    for col_name, val in row_data.items():
                        # Handle nulls
                        if val is None or (isinstance(val, float) and math.isnan(val)):
                            continue
                        cols.append(self._sanitize_col_name(col_name))
                        placeholders.append("%s")
                        values.append(val)

                    stmt = SimpleStatement(f"""
                        INSERT INTO {self.keyspace}.{table_name}
                        ({", ".join(cols)})
                        VALUES ({", ".join(placeholders)})
                    """)
                    batch.add(stmt, values)
                    batch_count += 1
                    inserted_count += 1

                    # Flush batch when it reaches batch_size
                    if batch_count >= batch_size:
                        self.db.execute(batch)
                        batch = BatchStatement(batch_type=BatchType.UNLOGGED)
                        batch_count = 0

                # Flush remaining rows in batch
                if batch_count > 0:
                    self.db.execute(batch)

            # Update row count
            query = f"""
                UPDATE {self.keyspace}.datasets
                SET row_count = %s, updated_at = %s
                WHERE dataset_id = %s
            """
            self.db.execute(query, [inserted_count, datetime.utcnow(), dataset_id])

            # Invalidate caches
            self.cache.invalidate_all_for_dataset(dataset_id)

            logger.info(f"Inserted {inserted_count} rows into dataset {dataset_id}")
            return inserted_count
        except Exception as e:
            logger.error(f"Failed to insert rows: {e}")
            raise DatabaseException(f"Failed to insert rows: {str(e)}")

    def set_dataset_schema(self, dataset_id: UUID, sample_row: Dict[str, Any]):
        """Infer and set dataset schema based on a sample row"""
        try:
            for col_name, value in sample_row.items():
                col_type = type(value).__name__
                query = f"""
                    INSERT INTO {self.keyspace}.dataset_schema
                    (dataset_id, column_name, column_type)
                    VALUES (%s, %s, %s)
                """
                self.db.execute(query, [dataset_id, col_name, col_type])
            logger.info(f"Set schema for dataset {dataset_id}")
        except Exception as e:
            logger.error(f"Failed to set schema: {e}")

    def get_dataset_schema(self, dataset_id: UUID) -> List[Dict[str, Any]]:
        """Get dataset schema and masking rules"""
        try:
            query = f"""
                SELECT column_name, column_type, masking_rule
                FROM {self.keyspace}.dataset_schema
                WHERE dataset_id = %s
            """
            result = self.db.execute(query, [dataset_id])
            return [
                {
                    "name": row.column_name,
                    "type": row.column_type,
                    "masking_rule": row.masking_rule
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            raise DatabaseException(f"Failed to get schema: {str(e)}")

    def update_masking_rule(self, dataset_id: UUID, column_name: str, mask_rule: Optional[str]):
        """Update masking rule for a specific column and sync to dataset metadata"""
        try:
            # 1. Update dataset_schema table
            query = f"""
                UPDATE {self.keyspace}.dataset_schema
                SET masking_rule = %s
                WHERE dataset_id = %s AND column_name = %s
            """
            self.db.execute(query, [mask_rule, dataset_id, column_name])

            # 2. Sync to masking_config in datasets table (for backward compatibility / convenience)
            dataset = self.get_dataset(dataset_id)
            config = dataset.get("masking_config", {})
            if mask_rule:
                config[column_name] = mask_rule
            else:
                config.pop(column_name, None)

            self.update_dataset(dataset_id, masking_config=config)

            # 3. Invalidate row caches since masking changed
            self.cache.invalidate_dataset(dataset_id)

            logger.info(f"Updated masking rule for {dataset_id}:{column_name}")
        except Exception as e:
            logger.error(f"Failed to update masking rule: {e}")
            raise DatabaseException(f"Failed to update masking rule: {str(e)}")

    def get_rows(
        self,
        dataset_id: UUID,
        page: int = 1,
        page_size: int = 100,
        user_role: str = "viewer",
        columns: Optional[List[str]] = None,
        apply_masking: bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated rows from dataset with optional masking (cached)"""
        try:
            # Build columns key for cache
            col_key = ",".join(sorted(columns)) if columns else None

            # Check cache first
            cached = self.cache.get_rows_page(
                dataset_id, page, page_size, user_role, col_key
            )
            if cached is not None:
                logger.debug(f"Cache hit for dataset {dataset_id} rows page={page}")
                return cached

            # Cache miss — query Cassandra
            dataset = self.get_dataset(dataset_id)
            masking_config = dataset.get("masking_config", {})

            # Get schema to map storage names back to original names
            schema = self.get_dataset_schema(dataset_id)
            name_map = {self._sanitize_col_name(s["name"]): s["name"] for s in schema}
            reverse_map = {s["name"]: self._sanitize_col_name(s["name"]) for s in schema}

            # Calculate which chunks to fetch
            offset = (page - 1) * page_size
            chunk_id = offset // 10000
            start_row = offset % 10000

            table_name = self._get_table_name(dataset_id)

            # Column-level SQL: select only requested columns if specified
            if columns:
                safe_cols = ["row_chunk_id", "row_id"]
                for col in columns:
                    safe_name = reverse_map.get(col, self._sanitize_col_name(col))
                    if safe_name not in safe_cols:
                        safe_cols.append(safe_name)
                select_clause = ", ".join(safe_cols)
            else:
                select_clause = "*"

            query = f"""
                SELECT {select_clause}
                FROM {self.keyspace}.{table_name}
                WHERE row_chunk_id = %s
                ORDER BY row_id ASC
                LIMIT %s
            """

            result = self.db.execute(
                query, [chunk_id, page_size + start_row]
            )
            rows = list(result)[start_row : start_row + page_size]

            processed_rows = []
            for row in rows:
                # Reconstruct row data from columns
                row_dict = {}
                for field in row._fields:
                    if field in ["row_chunk_id", "row_id"]:
                        continue
                    orig_name = name_map.get(field, field)
                    row_dict[orig_name] = getattr(row, field)

                # Apply masking
                if apply_masking and user_role != "admin":
                    for col_name, col_value in row_dict.items():
                        if col_name in masking_config:
                            mask_rule = masking_config[col_name]
                            row_dict[col_name] = DataMasker.mask_value(
                                col_value, mask_rule, user_role
                            )

                processed_rows.append(row_dict)

            total = dataset.get("row_count", 0)

            # Store in cache
            self.cache.set_rows_page(
                dataset_id, page, page_size, user_role,
                processed_rows, total, col_key
            )

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
        """Export dataset to CSV, JSON, or Parquet format"""
        try:
            dataset = self.get_dataset(dataset_id)

            # Get all rows (in production, this would be paginated)
            table_name = self._get_table_name(dataset_id)
            query = f"SELECT * FROM {self.keyspace}.{table_name}"
            result = self.db.execute(query)
            
            # Get schema for mapping
            schema = self.get_dataset_schema(dataset_id)
            name_map = {self._sanitize_col_name(s["name"]): s["name"] for s in schema}
            
            rows = []
            for row in result:
                row_dict = {}
                for field in row._fields:
                    if field in ["row_chunk_id", "row_id"]:
                        continue
                    orig_name = name_map.get(field, field)
                    row_dict[orig_name] = getattr(row, field)
                rows.append(row_dict)

            masking_config = dataset.get("masking_config", {})

            # Apply masking for non-admin users
            if user_role != "admin":
                for row in rows:
                    for col_name, col_value in row.items():
                        if col_name in masking_config:
                            mask_rule = masking_config[col_name]
                            row[col_name] = DataMasker.mask_value(
                                col_value, mask_rule, user_role
                            )

            if format.lower() == "csv":
                return self._export_csv(rows)
            elif format.lower() == "json":
                return json.dumps(rows, default=str).encode()
            else:
                # Default to CSV
                return self._export_csv(rows)
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
