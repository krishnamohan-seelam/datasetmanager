# 03 — Service Layer

`dataset-manager/app/services/` holds the domain logic. Each service is a plain class instantiated once
as a module-level singleton in `app/api/dependencies.py` (not a DI container — just shared instances
imported by routers). Services talk to Cassandra directly via `app/cassandra_client.py`; there is no
repository/ORM abstraction between services and CQL.

## DatasetService (`dataset_service.py`)

Owns dataset lifecycle. `create_dataset(...)`:
1. Registers dataset metadata (name, owner, visibility) in a shared metadata table.
2. Dynamically issues `CREATE TABLE IF NOT EXISTS {keyspace}.{table_name} (...)` to give the new dataset
   its own physical Cassandra table (see `04-data-layer.md` for why).
This is the one place in the codebase where DDL is executed at runtime based on user input — the table
name derivation and column typing here are effectively the write path for the whole per-dataset-table
architecture; any change to naming/typing rules must be made here and will affect `SchemaService`,
`BatchService`, and row read/write paths together.

## SchemaService (`schema_service.py`)

Tracks schema evolution independently from the physical table DDL:
- `create_schema` / `evolve_schema` — write a new schema version record.
- `_infer_columns(sample_row)` — infers column types from a sample row (used on ingestion when no
  explicit schema is supplied).
- `_diff_schemas` — computes added/removed/changed columns between versions.
- `_register_version` / `_get_latest_version` — version bookkeeping.
- `get_schema_history(dataset_id)` — full version lineage.
- `drop_column(dataset_id, column_name)` — **soft delete**: marks a column removed in the schema
  record rather than issuing `ALTER TABLE ... DROP COLUMN`, so the underlying Cassandra column still
  physically exists after this call. Code that reads schema must respect the soft-delete flag; code that
  reads raw Cassandra rows will still see the "dropped" column's data.
- `update_masking_rule` — associates a `MaskingRule` (see `06-cross-cutting-concerns.md`) with a column
  in the schema record; this is the only place masking configuration is persisted, read later by the
  row-read path to decide what to mask.

Schema metadata (versions, column defs, masking rules) lives in its own Cassandra table(s), separate from
the per-dataset data table — the data table has no knowledge of masking or versioning, both are overlaid
by this service at read time.

## BatchService (`batch_service.py`)

Manages ingestion batches (one-time/hourly/daily/weekly/monthly, per the README) as rows in a batches
table keyed by dataset: `create_batch`, `update_batch_status`, `get_batch`/`get_latest_batch`,
`list_batches`, `delete_batch`/`delete_all_batches`, `count_batches`. A batch is the unit of ingestion
isolation — rows written as part of one batch can be deleted/retried (`delete_batch`) without affecting
other batches in the same dataset table, which implies row records must carry a batch identifier column
to make `delete_batch` possible as a scoped operation in Cassandra (no multi-row transactions available).

## PermissionService (`permission_service.py`)

Per-(dataset, user) RBAC, independent of the JWT's default role claim (see `02-api-layer.md`):
`grant_permission`/`revoke_permission` (role is one of Admin/Owner/Viewer per dataset),
`get_user_permission`, `list_dataset_permissions`, `check_permission`, `is_dataset_accessible`. Every
dataset/row/schema endpoint that isn't admin-only should call `is_dataset_accessible` or
`check_permission` before returning data — this is the enforcement point for dataset-level RBAC described
in the README's security model.

## PaginationCacheService (`pagination_cache.py`)

Redis-backed cache for paginated row reads and dataset listings (default TTL 300s, Redis logical DB 1,
separate from any other Redis usage). Cache keys are explicitly scoped by **dataset, page, page_size, and
caller role** — not just by dataset+page — because masking output differs by role (`06-cross-cutting-
concerns.md`); caching without the role in the key would leak unmasked data to a lower-privileged user
hitting a warm cache entry. Any new caching added to the row-read path must preserve this role-scoping
invariant.
