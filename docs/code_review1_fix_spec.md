# Fix Specification — Cycle 1

**Input:** [`code_review1.md`](./code_review1.md) (20 mandatory · 31 normal · 14 good-to-do findings)

**Grouping principle:** findings are regrouped here by **feature/module** rather than by severity. Each
module below lists every finding from `code_review1.md` that touches its files, mandatory first. The
reason: if a module is being opened to fix a mandatory issue, its normal/good-to-do issues in the same
files are fixed in the *same* change — not deferred to a separate pass that re-touches the same code and
re-triggers review/test cycles. Findings that are genuinely cross-cutting (touch many modules in the same
small way) are pulled into a **Shared Abstractions** section instead and referenced from each module.

Each module section gives: scope, the findings it resolves (by their original bucket + number in
`code_review1.md`), the fix design, and acceptance criteria. This is a specification to implement
against — it does not change any code itself.

---

## Shared abstractions (build once, reuse across modules)

These come up in ≥2 modules below; build them first so each module's fix just consumes them instead of
re-solving the same problem per-file.

| Abstraction | Resolves | Used by |
|---|---|---|
| **`Role` enum** (`admin`/`contributor`/`viewer`) in `app/schemas/common.py`, replacing bare role strings everywhere | Normal #10 (primitive obsession), part of Mandatory #2/#3 | Module 2, 3, 4 |
| **`require_owner_or_admin(dataset, current_user)` dependency** — single accessibility/ownership check | Normal #1 (duplicated owner-or-admin check) | Module 3, 4, 5 |
| **`@translate_domain_exceptions` decorator or shared error-handling base** — re-raises `HTTPException` before the generic `except Exception`, and maps each `DatasetManagerException` subtype to its HTTP code in one place | Mandatory #6, Normal #9 | Module 4, 5, 6, 7 |
| **`StorageBackend` `Protocol`** declaring `upload_file`/`download_file`/`delete_file`/`delete_dataset_files`/`get_file_size`/`generate_presigned_url`/`archive_old_files` | Normal #21 | Module 10 |
| **Shared retry/backoff helper** (e.g. `app/utils/retry.py`, `with_retry(fn, attempts, backoff)`) for external-client connects | Normal #20 | Module 9, 10, 11 |
| **`PaginationCacheService` becomes the one row/listing cache**; `RedisCacheService` either folds into it or is scoped to non-row data only, with one invalidation entrypoint per dataset | Normal #23, Good-to-do #1 | Module 5 |
| **`PageRequest` value object** (`dataset_id, page, page_size, user_role, columns`) | Good-to-do #10 | Module 5 |

---

## Fix sequencing (phases)

Build top to bottom — later phases assume the shared abstractions and earlier modules' fixes exist.

| Phase | Modules | Why first/last |
|---|---|---|
| 0 | Shared abstractions above | Everything else consumes these |
| 1 | M1 Secrets & Config | Blocks safe deployment of anything else; touches config read by every module |
| 2 | M2 Authentication, M3 Authorization/RBAC | Security-critical; introduces `Role` enum used downstream |
| 3 | M4 Dataset CRUD & Listing, M8 Health Check | Core read/write correctness |
| 4 | M5 Rows Read Path (Masking + Cache), M6 Schema Versioning, M7 Batch Management | These three are tightly coupled (schema ↔ rows ↔ batches) — do as one connected pass |
| 5 | M9 Cassandra Connections & Startup | Infra reliability, lower urgency than data correctness |
| 6 | M10 Storage Backends, M11 Kafka Integration | Same tier as M9 |
| 7 | M12 Middleware (CORS/Audit/Rate-limit), M13 Logging, M14 Monitoring wiring | Cross-cutting polish once core paths are solid |

---

## Module 1 — Secrets & Configuration Hardening

**Files:** `app/core/config.py`, `app/auth_utils.py`, `app/integrations/storage_factory.py`

**Resolves:** Mandatory #1.

**Fix design:**
- Remove all hardcoded default values for `SECRET_KEY`, `JWT_SECRET_KEY`, `MINIO_ACCESS_KEY`,
  `MINIO_SECRET_KEY` from `config.py` and `storage_factory.py`. Keep `os.getenv(...)` but with no insecure
  fallback.
- Add a startup assertion in `Settings` (pydantic-settings validator) that fails fast if
  `APP_ENV != "development"` and any secret-bearing field is empty or matches a known-placeholder value
  (`"your-secret-key"`, `"minioadmin"`), raising at import time rather than at first use.
- For local/dev convenience, move the previous defaults into `.env.example`/a documented
  `docker-compose.yml` env block instead of into code, so "dev mode works out of the box" is preserved
  without the same defaults being silently valid in prod.

**Acceptance criteria:** starting the app with `APP_ENV=production` and no `SECRET_KEY`/`JWT_SECRET_KEY`/
MinIO vars set fails startup with a clear error, not a silent insecure default.

---

## Module 2 — Authentication (register / login / JWT)

**Files:** `app/api/auth.py`, `app/schemas/common.py` (`RegisterRequest`)

**Resolves:** Mandatory #2, Mandatory #7, Good-to-do #14, Good-to-do #13 (`auth_utils.py` dead example code).

**Fix design:**
- `RegisterRequest.role`: either remove the field entirely (server always assigns `viewer` on
  self-registration; role elevation only happens via an admin-only endpoint) or constrain it with the
  same `pattern="^(admin|contributor|viewer)$"` **and** reject `admin` specifically unless the request is
  made by an already-authenticated admin (self-registration should never be able to mint an admin).
  Recommended: remove `role` from `RegisterRequest` outright — simplest and closes the hole completely.
- Login query: add `is_active` to the `SELECT` and reject with 401 if `False`. Add `full_name` to the
  `SELECT` and populate it on the returned `User`.
- While touching `auth.py`: unify the `AuthResponse` shape between `register`/`login` (Good-to-do #14) —
  both always set `message`.
- While touching `auth_utils.py` for Module 1: delete the dead commented-out example block
  (Good-to-do #13).

**Acceptance criteria:** `POST /auth/register {"role": "admin"}` yields a `viewer` account (or a 4xx if
the field is removed and still sent); a deactivated user's login attempt returns 401; a successful login
response includes the stored `full_name`.

---

## Module 3 — Authorization / RBAC

**Files:** `app/api/permissions.py`, `app/core/security.py`, `app/services/permission_service.py`,
`app/schemas/common.py`

**Resolves:** Mandatory #3, Mandatory #6 (`permissions.py`'s grant/revoke endpoints — shared with Module
4/5), Normal #2, Normal #6, Good-to-do #9. (Normal #1 and #10 are resolved here via the shared `Role`
enum / `require_owner_or_admin` built in Module 0, then adopted by every router in Module 4/5 too.)

**Fix design:**
- `grant_permission`: change `user_email`/`role` from loose query params to a `PermissionGrantRequest`
  Pydantic body model reusing `PermissionBase`'s `role` pattern validation (Mandatory #3, Normal #6 — one
  fix covers both: moving to a body model is also how the query-param issue gets fixed).
- `grant_permission`/`revoke_permission`: add `except HTTPException: raise` before the generic
  `except Exception` handler, same as Module 4/5 (Mandatory #6).
- Delete `require_role()` from `security.py` if genuinely unused after `admin.py` is migrated to call it
  (Normal #2) — or, inverse decision: keep `require_role()` and change `admin.py` to use it instead of its
  own hand-rolled `require_admin()`, deleting the duplicate. Prefer the latter (one implementation, not
  zero) so the dependency is actually exercised and tested.
- Add a one-line docstring to `check_permission`/`is_dataset_accessible` stating `user_role` must come
  from a server-verified auth context (`get_current_user`), never from client input (Good-to-do #9).

**Acceptance criteria:** granting a permission with an invalid role string returns 422 from Pydantic
validation before reaching `PermissionService`; `admin.py` and any other admin-only route use the same
`require_role`/`require_admin` implementation.

---

## Module 4 — Dataset CRUD & Listing (incl. Admin stats)

**Files:** `app/api/datasets.py`, `app/api/admin.py`, `app/services/dataset_service.py` (CRUD/listing
parts only — row-read masking lives in Module 5)

**Resolves:** Mandatory #6 (`datasets.py` — shared with Module 3/5), Mandatory #9, Mandatory #10,
Normal #4, Normal #5, Normal #7, Normal #8, Normal #9 (applied
here for datasets.py/admin.py; Module 5/6/7 apply the same shared decorator to their own files), Good-to-do
#11, Good-to-do #8, Good-to-do #12 (`dependencies.py` import-time client — fixed as part of touching
dependency wiring for this module).

**Fix design:**
- `admin.py:get_admin_stats` — remove the dead `if users_result.one is not None` branch; call `.one()`
  exactly once per count query (Mandatory #9). Remove unused `CassandraClient`/`settings` imports
  (Normal #5).
- `list_datasets` (both `datasets.py` and `dataset_service.py`) — push pagination down to Cassandra
  instead of fetching up to 1000 rows and paginating in Python: use the caller's real `page`/`page_size`
  in the query (Cassandra paging state / `LIMIT` per page, or at minimum raise the hard cap and compute
  `total` from an actual count rather than `len(all_rows)`) (Mandatory #10). Apply the same fix to
  `admin.py`'s `list_users`/`get_admin_stats` full-table scans (Normal #4).
- Adopt the shared `@translate_domain_exceptions` pattern (or equivalent base-class try/except) across
  every handler in `datasets.py`, `admin.py` so `HTTPException` is never re-caught by the generic
  `except Exception` (Mandatory #6 applies to this module's files too; Normal #9 is the same fix).
- `datasets.py` upload path: validate `file.filename` is non-None and contains a dot before deriving the
  extension, raising `InvalidFileFormatException` explicitly instead of letting `AttributeError` fall
  through (Normal #7). Add a `MAX_UPLOAD_SIZE` check (reuse the frontend's `VITE_UPLOAD_MAX_SIZE` value
  as the server-side source of truth) before/while reading the upload into memory (Normal #8).
- Tags: change `DatasetMetadataUpdate`/response models' handling so tags are `List[str]` end-to-end,
  removing the manual comma-split/join in `datasets.py` (Good-to-do #11).
- `update_dataset`: either quote all updated column identifiers consistently or none, with a comment if
  one must differ (Good-to-do #8).
- `dependencies.py`: move the module-level `db = CassandraClient(...)` behind a `get_db()` 
  function/dependency rather than a side effect of import (Good-to-do #12) — this also sets up Module 9's
  connection-sharing work.

**Acceptance criteria:** `/admin/stats` returns correct counts with no dead branch; `/datasets?page=2` on
a dataset count > 1000 returns real data, not empty/wrong; an upload with no file extension returns 400,
not 500; uploads over the configured max size are rejected before full in-memory parsing.

---

## Module 5 — Rows Read Path: Masking & Pagination Cache

**Files:** `app/services/dataset_service.py` (`get_rows`, `export_dataset`), `app/services/pagination_cache.py`,
`app/core/masking.py`, `app/integrations/redis_cache.py`, `app/api/rows.py`

**Resolves:** Mandatory #6 (`rows.py` — shared with Module 3/4), Mandatory #11, Mandatory #12,
Mandatory #15 (the cache-invalidation half that applies to
row/column/masking changes — the batch-delete half is Module 7), Normal #12, Normal #16, Normal #23,
Good-to-do #1, Good-to-do #7, Good-to-do #10, plus Normal #9/#1 applied to `rows.py`.

**Fix design:**
- `get_rows`/`export_dataset`: when `columns` isn't explicitly requested, build the select list from the
  **active** schema columns (`SchemaService.get_schema`, `is_active=True`) instead of `SELECT *`, so
  soft-deleted/untracked physical columns never reach the client or bypass masking (Mandatory #11).
- `pagination_cache._rows_key`: add `apply_masking` to the key. Also bump/segment the key by current
  `dataset.schema_version` and `masking_config` revision (not just role) so a masking-rule change is
  itself a natural cache-key change in addition to the explicit invalidation in Mandatory #15/#16
  (Mandatory #12).
- Add one invalidation entrypoint — `PaginationCacheService.invalidate_dataset(dataset_id)` — and call it
  from every mutation path that changes a dataset's rows, schema, or masking config: `insert_rows`,
  `drop_column`, `update_masking_rule` (this module), and `delete_batch`/`delete_all_batches` (Module 7)
  (Mandatory #15).
- Introduce the `PageRequest` value object (`dataset_id, page, page_size, user_role, columns`) and thread
  it through `get_rows`/`get_rows_page`/`set_rows_page` instead of the five-parameter clump
  (Good-to-do #10).
- Consolidate caching: decide `PaginationCacheService` owns all row/listing caching;
  `RedisCacheService` is scoped to dataset-metadata/user-listing/query-result caching only, and its
  `invalidate_dataset` must also call the pagination cache's invalidation (or be merged into one service)
  so a single "dataset changed" signal clears both (Normal #23). While in `redis_cache.py`, extract the
  duplicated scan-and-delete loop in `invalidate_dataset`/`invalidate_user_cache` into one
  `_invalidate_pattern(pattern)` helper (Good-to-do #1).
- Reconcile the two masking-config sources of truth (`datasets.masking_config` JSON blob vs.
  `dataset_schema.masking_rule` per column): make `dataset_schema.masking_rule` the single source, and
  have `get_rows` read masking rules from the schema service only; `update_masking_rule` writes to one
  place (Normal #12). Remove the dead `MaskingRule.CUSTOM` enum member or wire it up to actually be
  reachable instead of the ad hoc `"custom:"` string prefix (Normal #16). Replace `mask_value`'s
  `if/elif` chain with a `Dict[str, Callable]` dispatch table while touching this file (Good-to-do #7).
- Apply the shared `@translate_domain_exceptions` pattern to `rows.py` (Normal #9/#1 for this file).

**Acceptance criteria:** a soft-deleted column never appears in a row/export response regardless of
caller role; toggling `apply_masking` for the same dataset/page/role never serves the other mode's cached
result; dropping a column or changing a masking rule is reflected on the very next read, not after a
300s TTL; deleting a batch removes its rows from the next cached read too (verified jointly with
Module 7).

---

## Module 6 — Schema Versioning

**Files:** `app/services/schema_service.py`, `app/services/dataset_service.py` (`_sanitize_col_name`,
`_ensure_table_exists`, `_get_table_name`), `app/services/batch_service.py` (`_get_table_name` only)

**Resolves:** Mandatory #13, Mandatory #14 (schema half), Mandatory #17, Mandatory #18, Normal #11,
Normal #15, Normal #17.

**Fix design:**
- `evolve_schema`/`_get_latest_version`: use a Cassandra lightweight transaction (`INSERT ... IF NOT
  EXISTS` on the new version row, or a `UPDATE ... SET version = ? WHERE dataset_id = ? IF version = ?`
  CAS pattern against a per-dataset version counter) instead of read-then-increment, so two concurrent
  uploads can't both win the same version number (Mandatory #13).
- `_get_latest_version`: stop swallowing all exceptions into `return 0`. Let infrastructure errors
  (timeouts, connection errors) propagate as a 5xx; only treat "query succeeded, zero rows" as "no schema
  yet" (Mandatory #14 — apply the identical fix to `BatchService.count_batches`, same bug, same file
  family).
- `_sanitize_col_name`: detect collisions by tracking already-used sanitized names per table-creation
  call and raising `InvalidFileFormatException` (with a clear "column names X and Y both sanitize to Z"
  message) instead of silently overwriting data (Mandatory #17). While here, add a CQL reserved-word
  check and suffix/escape as needed (Normal #17).
- `_ensure_table_exists`/schema inference: derive the column set from a **union** of all rows in the
  batch (or at minimum the first N rows / a configurable sample), not just `rows[0]`, before issuing
  `CREATE TABLE`/`evolve_schema`, so heterogeneous batches don't fail mid-insert (Mandatory #18).
- Extract the duplicated `f"ds_rows_{str(dataset_id).replace('-', '_')}"` table-name expression into one
  shared helper (e.g. `app/services/naming.py:dataset_table_name(dataset_id)`) used by both
  `DatasetService` and `BatchService` (Normal #11).
- `DatasetService.get_dataset_schema`: either delete it and have callers use `SchemaService` directly, or
  give it a reason to exist (e.g. merge masking metadata per Module 5's single-source-of-truth decision)
  (Normal #15).

**Acceptance criteria:** two concurrent uploads to the same dataset never produce a corrupted/duplicate
schema version; a transient Cassandra error during a schema-version lookup surfaces as an error, not a
silent "re-create version 1"; uploading columns `"Col-1"` and `"Col_1"` in the same batch fails fast with
a clear message instead of corrupting data; a batch with rows of varying shape is fully ingested or fails
atomically, not partially.

---

## Module 7 — Batch Management

**Files:** `app/services/batch_service.py`, `app/services/dataset_service.py` (`insert_rows`'s
`row_count` update)

**Resolves:** Mandatory #14 (batch half, same fix as Module 6), Mandatory #15 (batch-delete half),
Mandatory #16, Normal #11 (shared table-name helper from Module 6).

**Fix design:**
- `insert_rows`: change the `row_count` update from `SET row_count = %s` (this call's count) to an
  accumulating update — either `SET row_count = row_count + %s` if the Cassandra counter semantics allow
  it for this column type, or read-add-write guarded by the same CAS approach as Module 6's schema
  version fix if plain counters aren't usable on this table (Mandatory #16).
- `delete_batch`/`delete_all_batches`: after removing rows/registry entries, call the new
  `PaginationCacheService.invalidate_dataset(dataset_id)` from Module 5 (Mandatory #15).
- `count_batches`: same fix as `_get_latest_version` in Module 6 — don't swallow real errors into `0`.
- Use the shared `dataset_table_name()` helper from Module 6 instead of its own duplicated expression.

**Acceptance criteria:** uploading two batches of 100 rows each leaves `row_count == 200`, not `100`;
deleting a batch means its rows are gone from the very next read (cached or not).

---

## Module 8 — Health Check

**Files:** `app/api/health.py`, `app/api/dependencies.py`

**Resolves:** Mandatory #8.

**Fix design:** `health_check()` uses the existing singleton `db` from `dependencies.py` instead of
constructing a new `CassandraClient`. If a lightweight liveness probe against Cassandra is wanted beyond
"is the shared client object alive," reuse the shared client's session to run `SELECT now() FROM
system.local` or equivalent, never instantiate a second client.

**Acceptance criteria:** repeated calls to `/health` do not grow the Cassandra connection count.

---

## Module 9 — Cassandra Connection Management & Startup

**Files:** `app/cassandra_client.py`, `app/main.py` (`startup_event`), every service's `__init__`
(`dataset_service.py`, `schema_service.py`, `batch_service.py`, `permission_service.py`)

**Resolves:** Mandatory #20, Normal #13, Good-to-do #2, Good-to-do #3.

**Fix design:**
- Replace the blocking 30× `time.sleep(5)` retry loop with the shared retry helper (bounded, with
  jittered backoff and a configurable max total wait, e.g. 30s not 150s), and raise a specific
  `CassandraUnavailableError` (new, in `core/exceptions.py`) instead of a bare `Exception`.
- `main.py`'s `startup_event`: wrap `initialize_schema()` in try/except, log via `app_logger` on failure,
  and fail FastAPI startup explicitly (don't let an unhandled exception produce an opaque hang/crash).
- Make every service accept an injected `CassandraClient` (constructor parameter, default to a
  module-level shared instance built once in `dependencies.py`) instead of each constructing its own —
  collapses N connections down to 1 shared session, consistent with the `get_db()` change started in
  Module 4.
- While touching `cassandra_client.py`: replace `print()` calls with `logger` (Good-to-do #2) and fix the
  missing-space import nit (Good-to-do #3).

**Acceptance criteria:** a single Cassandra session is shared by all services (verifiable via connection
count on the Cassandra side); a Cassandra outage at startup fails the container/process with a clear
logged error within a bounded time, not an indefinite hang.

---

## Module 10 — Storage Backends (S3 / MinIO / Local)

**Files:** `app/integrations/local_storage.py`, `app/integrations/s3_storage.py`,
`app/integrations/storage_factory.py`

**Resolves:** Mandatory #19, Normal #21, Normal #22, Normal #24, Normal #25 (plus Mandatory #1's
storage-factory piece, already done in Module 1).

**Fix design:**
- Fix the `Union` import in `local_storage.py` (trivial — add `Union` to the `typing` import) — this one
  alone is a one-line, ship-immediately fix regardless of sequencing (Mandatory #19).
- Introduce the `StorageBackend` `Protocol` from Shared Abstractions; have `get_storage_service()`'s
  return type annotation reference it, and run `mypy`/structural check in CI against both
  implementations (Normal #21).
- `generate_presigned_url`: give `LocalStorageService` an actual expiring, access-controlled mechanism
  (e.g. a signed token + a dedicated download route that validates it and streams the file) instead of
  returning a raw filesystem path, so callers can treat the return value identically across backends
  (Normal #22).
- `S3StorageService.__init__`/`_connect`: move the `create_bucket` provisioning call out of the
  constructor into an explicit, idempotent `ensure_bucket()` method called once at startup (alongside
  Module 9's startup sequencing), not on every instantiation (Normal #24).
- `delete_dataset_files`/`archive_old_files`: loop with `list_objects_v2`'s `ContinuationToken` until
  `IsTruncated` is `False`, in one shared private helper both methods call (Normal #25).

**Acceptance criteria:** `STORAGE_BACKEND=local` starts without `NameError`; a dataset with >1000 stored
objects is fully deleted/archived, not just its first 1000 keys; calling `generate_presigned_url` on
either backend returns something a client can actually fetch without special-casing the backend.

---

## Module 11 — Kafka Integration

**Files:** `app/integrations/kafka_producer.py`, `app/integrations/kafka_consumer.py`

**Resolves:** Normal #18, Normal #19, Good-to-do #4.

**Fix design:**
- `KafkaEventProducer.get_instance()`: guard the check-then-set with a `threading.Lock`, matching
  `CassandraClient`'s pattern; make `__init__` private-by-convention (leading underscore + a module-level
  factory function) so callers can't bypass the singleton.
- `KafkaEventConsumer`: either support multiple topic subscriptions with per-topic callback dispatch in
  one `_consume` loop (poll, inspect topic, route to the registered handler), or make the
  one-subscription-per-instance behavior explicit in the API (rename methods / docstring) so it's not
  misleading. Add explicit offset commit after successful handler execution instead of relying solely on
  `enable_auto_commit=True`.
- Remove or finish `create_audit_event_handler`'s stub (Good-to-do #4) — this is also where Module 12's
  "wire audit logging to Kafka" decision gets implemented, if that's the chosen direction (see Module 12).

**Acceptance criteria:** concurrent first calls to `get_instance()` never create more than one
`KafkaProducer`; a consumer instance can be subscribed to more than one topic with distinct handlers
without silently ignoring all but the last.

---

## Module 12 — Middleware: CORS, Audit Logging, Rate Limiting

**Files:** `app/main.py`, `app/middleware/rate_limit_audit.py`

**Resolves:** Mandatory #4, Mandatory #5, Normal #27, Normal #30, Normal #31, Good-to-do #6.

**Fix design:**
- CORS: replace `allow_origins=["*"]` with an explicit allowlist read from config (e.g.
  `CORS_ALLOWED_ORIGINS` env var, comma-separated), keeping `allow_credentials=True` only because origins
  are now pinned (Mandatory #4).
- Audit logging: decide and implement one durable sink — write `AuditLogger.log_request`/
  `log_data_access`/`log_permission_change` to the `audit_log` Cassandra table (reuse the shared client
  from Module 9) and/or publish via `KafkaEventProducer` (reusing Module 11's hardened producer). Either
  way, stop relying on `logger.info` alone as "the audit trail" (Mandatory #5, audit half).
- Rate limiting: re-enable `rate_limit_middleware` in `main.py`. Since `RateLimiter`'s in-memory state
  doesn't scale across workers (Normal #31), back it with Redis (shared counter per IP with a TTL) instead
  of the in-process `defaultdict`, so the fix for "disabled" and the fix for "doesn't scale" are done
  together rather than re-enabling something that's still broken under multiple workers (Mandatory #5,
  rate-limit half + Normal #31).
- Audit identity: stop trusting the client-supplied `X-User-Email` header; read the authenticated user
  from the request's resolved JWT (via the same dependency `get_current_user` uses) when available, and
  mark `anonymous` otherwise rather than echoing an unverified client header (Normal #30).
- `/metrics`: gate behind either network-level restriction (documented, not code) or a minimal shared
  secret/basic-auth check in `main.py`, since this is a public ASGI mount (Normal #27).
- Delete the unused `cors_headers()` function now that `CORSMiddleware` is confirmed as the single source
  of CORS config (Good-to-do #6).

**Acceptance criteria:** requests from a non-allowlisted origin are rejected by the browser/CORS
preflight; `audit_log` (Cassandra) or the Kafka audit topic actually receives an entry for every API
call; rate limiting is active and effective across more than one running worker process; `/metrics` is
not reachable by an anonymous client in the default deployment.

---

## Module 13 — Logging

**Files:** `app/utils/log_formatter.py`

**Resolves:** Normal #29 (the two sub-issues: import-time `basicConfig` side effect, and no
secret/PII redaction).

**Fix design:**
- Replace the module-level `logging.basicConfig(...)` call with an explicit `configure_logging()`
  function called once from `main.py` at startup (after uvicorn's own logging is set up, or coordinated
  with it) rather than as an import side effect.
- Add a redaction step to `JsonFormatter.format` for known-sensitive field names (`password`,
  `password_hash`, `authorization`, `token`) before serializing, as a defense-in-depth measure
  independent of Module 12's audit-identity fix.

**Acceptance criteria:** importing `log_formatter` anywhere no longer reconfigures the root logger as a
side effect; a log line that happens to include a `password_hash` field is redacted in the emitted JSON.

---

## Module 14 — Monitoring / Metrics Wiring

**Files:** `app/monitoring/metrics.py`, `app/monitoring/grafana_config.py`, call sites in
`app/integrations/kafka_producer.py`/`kafka_consumer.py`, `app/api/auth.py`, `app/core/masking.py`

**Resolves:** Normal #26, Good-to-do #5.

**Fix design:**
- For each metric in `DatasetManagerMetrics` that currently has no producer (`kafka_messages_produced/
  consumed_total`, `kafka_consumer_lag`, `etl_jobs_total`, `etl_job_duration_seconds`,
  `etl_rows_processed_total`, `auth_login_total`, `masking_operations_total`, `masking_duration_seconds`),
  either (a) add the `.inc()`/`.observe()` call at the real call site once that subsystem is wired up
  (Kafka producer/consumer per Module 11, login per Module 2, masking per Module 5), or (b) remove the
  metric definition if the corresponding subsystem (ETL/Airflow) isn't going to be exercised by this
  deployment, so Grafana panels don't silently show permanent zeros for things that were never going to
  run.
- Move `export_dashboard_json`/`export_alert_rules_yaml` and the `__main__` block out of
  `monitoring/grafana_config.py` into `scripts/`, consistent with how other one-off tooling is organized
  in this repo (Good-to-do #5).

**Acceptance criteria:** every metric exposed at `/metrics` either has at least one call site that can
increment/observe it, or is removed; dashboard-export tooling lives in `scripts/`, not in the runtime
monitoring module.

---

## Summary table

| Module | Mandatory | Normal | Good-to-do |
|---|---|---|---|
| 1. Secrets & Config | #1 | — | — |
| 2. Authentication | #2, #7 | — | #13, #14 |
| 3. Authorization/RBAC | #3, #6 (shared) | #2, #6 (#1, #10 shared) | #9 |
| 4. Dataset CRUD & Admin | #6 (shared), #9, #10 | #4, #5, #7, #8, #9 | #8, #11, #12 |
| 5. Rows/Masking/Cache | #6 (shared), #11, #12, #15 (half) | #12, #16, #23 (#1, #9 shared) | #1, #7, #10 |
| 6. Schema Versioning | #13, #14 (half), #17, #18 | #11, #15, #17 | — |
| 7. Batch Management | #14 (half), #15 (half), #16 | #11 (shared) | — |
| 8. Health Check | #8 | — | — |
| 9. Cassandra Connections | #20 | #13 | #2, #3 |
| 10. Storage Backends | #19 | #21, #22, #24, #25 | — |
| 11. Kafka Integration | — | #18, #19 | #4 |
| 12. CORS/Audit/Rate-limit | #4, #5 | #27, #30, #31 | #6 |
| 13. Logging | — | #29 | — |
| 14. Monitoring Wiring | — | #26 | #5 |

Every mandatory, normal, and good-to-do item from `code_review1.md` is accounted for above. Most appear
in exactly one module; a few genuinely span multiple files touched by different modules (Mandatory #6
across `permissions.py`/`datasets.py`/`rows.py`; Mandatory #14 and #15 each have a schema-service half
and a batch-service half; Normal #1, #9, #11 are the same fix pattern applied independently in more than
one module's files) — these are marked "(shared)" / "(half)" in each module's own "Resolves" line and in
this table, so the fix is still done once per file, just counted against every module whose files it
touches.
