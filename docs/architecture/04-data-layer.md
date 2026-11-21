# 04 — Data Layer (Cassandra)

Schema bootstrap lives in `dataset-manager/scripts/init_cassandra.py` (`initialize_schema()`), run both
manually (`poetry run python scripts/init_cassandra.py`) and automatically on every API startup
(`app/main.py`'s `startup_event`). All DDL is `CREATE TABLE IF NOT EXISTS` plus a block of `ALTER TABLE`
statements for `datasets` wrapped in `try/except` per statement — this is how the project does additive
migrations: there is no numbered migration history, re-running the script is idempotent-by-convention
(failures are swallowed and logged, not raised), and `scripts/migrate_schema_v3.py` / `migrate_v2.py`
exist as one-off historical migrations outside this mechanism.

Keyspace: `dataset_manager` (configurable via `CASSANDRA_KEYSPACE`), replication factor 1
(`SimpleStrategy`) — single-node/dev-oriented, not production replication.

## Fixed (shared) tables

| Table | Partition key | Clustering | Purpose |
|---|---|---|---|
| `datasets` | `dataset_id` | — | Dataset metadata: name, owner, visibility, row/size counts, `status`, `masking_config`, batch tracking fields (`latest_batch_id`, `total_batches`, `schema_version`, ...) |
| `dataset_batches` | `dataset_id` | `batch_date DESC, batch_id DESC` | One row per ingestion batch; `status`, `row_count`, `size_bytes`, `uploaded_by` |
| `dataset_schema` | `dataset_id` | `version DESC, position ASC` | One row per **column per schema version**: `column_type`, `position`, `masking_rule`, `is_active`, `removed_at` — this is where `SchemaService.drop_column`'s soft-delete lands (`is_active=false`/`removed_at` set, row kept) |
| `dataset_schema_versions` | `dataset_id` | `version DESC` | One row per schema version: `batch_id`, `column_count`, `change_summary` — the version-level audit trail that `dataset_schema` rows hang off of |
| `dataset_permissions` | `dataset_id` | — (clustered by `user_email`) | Per-(dataset,user) RBAC role, `granted_at` |
| `audit_log` | `dataset_id` | `log_id DESC` (TIMEUUID) | Action audit trail: `user_email`, `action`, `ip_address`, `details` — written by the audit-logging middleware, not by services directly |
| `users` | `user_id` | — | Account records: `password_hash`, `full_name`, `role`, `is_active` |

Two secondary indexes exist: `datasets_name_idx` (on `datasets.name`) and `users_email_idx` (on
`users.email`) — needed because Cassandra can't filter on non-partition-key columns otherwise, but
secondary indexes on Cassandra don't scale well with cardinality/cluster size; fine for current
single-node dev usage, a risk to revisit before any multi-node deployment.

## Dynamic (per-dataset) tables

This is the architecturally distinctive part: **every dataset gets its own physical Cassandra table**,
created at ingestion time by `DatasetService.create_dataset` (`app/services/dataset_service.py`) via a
runtime `CREATE TABLE IF NOT EXISTS {keyspace}.{table_name} (...)`, with column names/types derived from
the uploaded data (via `SchemaService._infer_columns` when no explicit schema is given). This trades
Cassandra's "wide, generic table" convention for one table per dataset so that:
- each dataset's rows are typed natively instead of stored as a generic blob/JSON column,
- a dataset can be dropped/resized independently of every other dataset,
- but it also means the number of Cassandra tables grows one-to-one with the number of datasets — a
  scaling consideration for clusters with many datasets (Cassandra has practical limits on table/column
  family count per cluster).

Row-level data in these per-dataset tables carries a batch identifier column (consistent with
`BatchService.delete_batch` being able to scope deletes to one batch within a dataset's table) and is
read back through `DatasetService`/`rows.py`, with masking applied from the current `dataset_schema`
version's `masking_rule` per column, not stored pre-masked.

## Relationship between the three "schema" concepts — easy to confuse

- **Physical table DDL** (`DatasetService`) — the actual Cassandra column definitions for a dataset's
  data table. Changing this requires an actual `ALTER TABLE`/new table.
- **Schema version records** (`SchemaService` / `dataset_schema`, `dataset_schema_versions`) — the
  logical, versioned view of columns (type, position, masking rule, active/removed), used for history,
  diffing, and masking lookups. This can diverge from the physical table (e.g. a soft-deleted column is
  "removed" here but still physically present).
- **`datasets.schema_version`** — a denormalized pointer on the dataset row to its current schema
  version number, used to avoid a lookup against `dataset_schema_versions` just to know "what version is
  this dataset on."
