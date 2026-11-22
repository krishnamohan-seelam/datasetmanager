# Backend Code Review — Cycle 1

**Scope:** `dataset-manager/app/` (API, services, integrations, middleware, monitoring, core, plus
`app/auth_utils.py` and `app/cassandra_client.py`)
**Date:** 2026-11-21

**Method note:** This repo has no `CODING_STANDARDS.md`/`CONTRIBUTING.md` and no configured lint
(`black`/`flake8`/`mypy` are declared dev-dependencies but unconfigured), and there is no fixed point or
issue/spec to diff against — the ask was a review of `app/` as it stands, not a diff. So this cycle
adapts the usual Standards-vs-Spec method into a single pass: the Fowler smell baseline (judgement
calls, not hard rules) plus a general correctness/security/reliability review, split across three
parallel sub-reviews (API layer, service layer, integrations/middleware/monitoring) and merged here.
Duplicate findings surfaced from more than one angle have been merged into one entry.

**Totals:** 20 mandatory · 31 normal · 14 good-to-do (65 total)

---

## 🔴 Mandatory — fix before relying on this in anything resembling production

### Security

1. **`app/auth_utils.py:10` + `app/core/config.py:21-29` + `app/integrations/storage_factory.py:46-49` — Hardcoded, well-known secret/credential defaults ship as fallbacks.**
   `SECRET_KEY`/`JWT_SECRET_KEY` default to `"your-secret-key"` / `"your-secret-key-for-local-dev"`, and
   `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` default to `"minioadmin"`/`"minioadmin"` (also hardcoded again
   in `storage_factory.get_storage_service()`). Nothing forces an override outside dev. Anyone with repo
   access can forge valid JWTs for any user/role (including `admin`), and a deployment that forgets to
   set the MinIO env vars silently runs with default admin storage credentials over plaintext HTTP
   (`MINIO_SECURE` also defaults to `False`).

2. **`app/api/auth.py:19-25` (+ `app/schemas/common.py:215-219`) — Privilege escalation via unrestricted self-registration role.**
   `register()` takes `role = user_data.role or "viewer"` straight from client input; `RegisterRequest.role`
   has no pattern/enum validation (unlike `PermissionBase.role`, which does). Any unauthenticated caller
   can `POST /auth/register {"role": "admin"}` and get back an admin JWT.

3. **`app/api/permissions.py:42-47` — `grant_permission` bypasses the schema's role validation.**
   `role: str` is accepted as a raw, unvalidated parameter instead of going through `PermissionBase`
   (which has `pattern="^(admin|contributor|viewer)$"`). A caller authorized to manage permissions can
   grant an arbitrary role string with no server-side allow-list check.

4. **`app/main.py:58-64` — CORS wildcard origin combined with `allow_credentials=True`.**
   `allow_origins=["*"]` + `allow_credentials=True` lets any origin make credentialed requests against
   the API wherever a browser honors the combination — a CSRF/credential-theft vector. Pin an explicit
   origin allowlist if credentials are required.

5. **`app/middleware/rate_limit_audit.py` + `app/main.py:66-73` — Audit logging never persisted/published; rate limiting fully disabled; both create a false sense of security.**
   `AuditLogger.log_request` only calls `logger.info(...)` — it never writes to the `audit_log` Cassandra
   table (created in `scripts/init_cassandra.py` but never written to anywhere in `app/`) and never
   publishes via the already-built `KafkaEventProducer`. Separately, the fully-implemented
   `RateLimiter`/`rate_limit_middleware` is commented out in `main.py` (lines 69-73), so there is **no**
   brute-force/abuse protection running today despite the code existing and looking production-ready.
   Anyone auditing the README's security claims without checking what's actually mounted would be misled.

### Correctness / data integrity

6. **`app/api/datasets.py` + `app/api/rows.py` + `app/api/permissions.py` — Deliberately-raised `HTTPException`s are swallowed and rewritten as 500.**
   Nearly every handler does `except DatasetNotFoundException: ... except Exception as e: raise
   HTTPException(500, ...)` without `except HTTPException: raise` first. Since `HTTPException` is itself
   an `Exception`, every intentional 403 "Access denied" and 400 (e.g. bad `batch_date`, missing
   `confirm=true`) gets caught by the trailing handler and turned into a generic 500 — masking real
   authorization failures and bad requests as server errors. Systemic across `datasets.py`, `rows.py`,
   and `permissions.py`'s grant/revoke endpoints; only `auth.py` and `permissions.py`'s `get_permissions`
   re-raise `HTTPException` correctly.

7. **`app/api/auth.py:75-87` — Login doesn't check `is_active`; `full_name` is always lost.**
   The login query (`SELECT email, password_hash, role FROM users WHERE email = %s`) never checks
   `is_active`, so a deactivated account can still authenticate. It also never selects `full_name`, so
   the login response always returns a null name even though it's stored.

8. **`app/api/health.py:22` — New, unclosed Cassandra connection created on every health check.**
   `health_check()` instantiates a brand-new `CassandraClient(...)` per request instead of reusing the
   singleton already created in `api/dependencies.py`, and never closes it. A load balancer hitting
   `/health` frequently will leak a connection per check.

9. **`app/api/admin.py:31-37` — Dead/buggy duplicate result-handling in `get_admin_stats`.**
   `if users_result.one is not None` references the bound *method* (always truthy — `.one` is never
   called), so the computed `total_users` is discarded and silently recomputed in a redundant
   try/except right after, calling `.one()` twice unnecessarily.

10. **`app/api/datasets.py:118` + `app/services/dataset_service.py:219-280` — `list_datasets` silently truncates beyond 1000 datasets, computed client-side.**
    The API layer always asks the service for a fixed `page_size=1000` regardless of the caller's
    actual page/page_size, and the service itself runs `LIMIT 1000` then paginates/sorts in Python
    (`total = len(all_rows)`). Once the real dataset count exceeds 1000, later pages silently return
    empty/wrong data, `total` undercounts, and datasets beyond the first 1000 become invisible to
    search — not an edge case, a design-level correctness bug.

11. **`app/services/dataset_service.py` (`get_rows`/`export_dataset`, ~610-744) — `SELECT *` returns soft-deleted/schema-untracked columns, bypassing masking and soft-delete semantics.**
    When no explicit `columns` are requested, the row-read path uses `SELECT *`, returning every
    physical Cassandra column — including ones the schema has soft-deleted (`is_active=False`). Since
    the column→name map is built only from *active* schema columns, a soft-deleted or untracked column
    falls back to its raw name, is returned to the client, and is **never checked against
    `masking_config`** (keyed by original names) — a direct soft-delete violation and masking bypass.

12. **`app/services/pagination_cache.py` — Cache key omits `apply_masking`, enabling a masking bypass via cache poisoning.**
    The Redis key is `dataset_id:page:page_size:role` only — never `apply_masking`. Any call path that
    reads with `apply_masking=False` for a given role (e.g. an internal/admin tool) populates the cache
    under that role's key with unmasked data; a later legitimate `apply_masking=True` request for the
    same role/page is then served the cached **unmasked** data straight from Redis.

13. **`app/services/schema_service.py` (`evolve_schema`, ~65-169) — Race condition: read-then-increment schema version with no locking/CAS.**
    `_get_latest_version` is a plain `SELECT`, then `new_version = current_version + 1` is written with
    no lightweight transaction (`IF NOT EXISTS`) or lock. Two concurrent uploads to the same dataset can
    read the same version, both pick the same `new_version`, and race to write — corrupting version
    history (duplicate/overwritten version rows, inconsistent column sets per version).

14. **`app/services/schema_service.py:325-335` (+ `app/services/batch_service.py:234-245`) — Silent `except Exception: return 0` masks real failures as "doesn't exist yet."**
    `_get_latest_version` and `BatchService.count_batches` both swallow every exception and return `0`,
    making a transient Cassandra error indistinguishable from "no schema/batches yet." `evolve_schema`
    then treats the former as "first upload" and re-registers version 1 over an existing schema,
    corrupting version continuity; the batch-count version feeds a wrong `total_batches` into dataset
    metadata.

15. **`app/services/batch_service.py:168-232` (+ `schema_service.py`'s `drop_column`/`update_masking_rule`) — Mutations never invalidate the pagination cache.**
    `delete_batch`/`delete_all_batches` remove Cassandra rows/registry entries but never call
    `PaginationCacheService.invalidate_*`. Cached row pages for deleted data are served from Redis for
    up to the default 300s TTL after the underlying data is gone — deleted rows returned to users.
    Column drops and masking-rule changes have the same gap: no invalidation hook, so changes don't
    propagate until TTL expiry.

16. **`app/services/dataset_service.py:450-462` — `row_count` is overwritten with only the latest batch's size, not accumulated.**
    `insert_rows` sets `row_count = <this call's inserted_count>` instead of adding to the existing
    total. After a second batch upload, `row_count` reflects only the newest batch — and this value is
    what `get_rows`'s pagination `total` and `list_datasets` surface to clients.

17. **`app/services/dataset_service.py:61-69,86-90,426-431` — `_sanitize_col_name` can map distinct column names to the same physical column.**
    Every non-alphanumeric character is replaced with `_` and lowercased, so `"Col-1"`, `"Col_1"`, and
    `"COL 1"` all sanitize to `"col_1"`. This either causes a duplicate-column `CREATE TABLE` failure or
    — worse — silently overwrites one logical column's value with another's on every row insert, with no
    collision detection.

18. **`app/services/dataset_service.py:408-431` — Table schema/version is inferred from a single sample row (`rows[0]`) for the whole batch.**
    If later rows in the same `insert_rows` call have extra/different columns (common with sparse
    uploads), the per-row insert loop references physical columns never added to the table — a Cassandra
    error mid-batch, leaving a partially-inserted, inconsistent batch.

### Reliability / operability

19. **`app/integrations/local_storage.py:10,76` — `NameError` on import: `Union` used in a type annotation but never imported.**
    `download_file`'s return annotation is `Union[str, BinaryIO]`, but line 10 only imports `Optional,
    BinaryIO`. With no `from __future__ import annotations`, this raises `NameError` the moment the
    module loads — **`LocalStorageService` is currently broken and cannot be used** when
    `STORAGE_BACKEND=local`.

20. **`app/cassandra_client.py:14-50` + `app/main.py:32-35` — Blocking singleton constructor with an unbounded retry loop can hang app startup for minutes, with no error handling.**
    The Cassandra client retries 30× with `time.sleep(5)` (up to 150s) while holding a lock; `main.py`'s
    `startup_event` calls `initialize_schema()` synchronously with no try/except, so a slow/unavailable
    Cassandra blocks the entire ASGI startup and any failure is an opaque, unhandled exception with no
    structured error or circuit breaker. Compounded by `main.py:41-52`'s single global `Exception`
    handler, which also means every other unhandled error (validation, DB, Redis/S3 connection failures)
    returns an identical generic 500 — operators can't distinguish a real bug from an expected 4xx.

---

## 🟡 Normal — should fix, not urgent

### API layer

1. **`app/api/datasets.py`, `rows.py`, `permissions.py` (~10 call sites) — Duplicated owner-or-admin/accessibility check (Duplicated Code / Data Clump).** The same `dataset["owner"] != current_user["email"] and current_user["role"] != "admin"` pattern (or the equivalent 5-field call into `permission_service.is_dataset_accessible`) is copy-pasted across nearly every endpoint. A future authorization-rule change means editing every call site. Should be one dependency/helper.
2. **`app/core/security.py:38-56` — `require_role()` is built but unused; `admin.py` hand-rolls an equivalent `require_admin()` instead.** Speculative generality sitting next to a duplicate, inconsistent implementation of the same concept.
3. **`app/api/dependencies.py` — Divergent Change: mixes service-singleton wiring, a raw Cassandra client used directly for auth queries, and an unrelated file-parsing helper (`parse_file_content`) in one module.** Three unrelated reasons to touch this file.
4. **`app/api/admin.py:31-57,86-96` + `app/services/dataset_service.py:219-280` — Unbounded full-table scans / fetch-all-then-paginate-in-memory.** `get_admin_stats` runs `SELECT COUNT(*)` over `users`/`datasets` (expensive full scans in Cassandra), and listing endpoints fetch the whole table into Python before sorting/paginating. Doesn't scale; risks timeouts/OOM as data grows.
5. **`app/api/admin.py:11-12` — Unused imports (`CassandraClient`, `settings`)** left over from refactoring; the module actually uses `db` from `dependencies.py`.
6. **`app/api/permissions.py:45-46,71` — `user_email`/`role` passed as query params instead of a validated request body.** Emails end up in URLs/access/proxy logs, and bypasses the `PermissionBase` Pydantic model that already exists for this exact shape.
7. **`app/api/datasets.py:50-55` — Fragile file-extension derivation can throw or misclassify.** `f".{file.filename.split('.')[-1].lower()}"` assumes a non-None filename containing a dot; a file with no extension either raises `AttributeError` (falls through to a generic 500) or produces a misleading "extension."
8. **`app/api/datasets.py:57-58` + `app/api/dependencies.py:37-56` — No upload size limit before reading the whole file into memory.** `content = await file.read()` has no size cap and `parse_file_content` parses fully in memory — a large upload can exhaust server memory.
9. **Throughout `admin.py`, `datasets.py`, `permissions.py`, `rows.py` — Broad `except Exception` swallows/obscures root causes**, which combined with finding #6 (mandatory) makes intentional 4xx and genuine bugs indistinguishable to the client.
10. **`app/api/datasets.py`, `permissions.py`, `admin.py` (~a dozen sites) — Primitive Obsession: role is a bare string compared ad hoc everywhere**, instead of a shared `Role` enum (a precedent, `BatchFrequency`, already exists in `schemas/common.py`). Typos/new role names aren't caught by type checking.

### Service / data layer

11. **`app/services/dataset_service.py:44-48` + `batch_service.py:180` — Duplicated Cassandra table-name construction (`f"ds_rows_{...}"`) in two places.** A naming-scheme change must be made in both or the services disagree on which physical table to touch.
12. **`app/services/dataset_service.py` + `schema_service.py` — Masking rules have two divergent sources of truth kept in sync by hand.** `datasets.masking_config` (JSON blob) and `dataset_schema.masking_rule` (per column) are updated in separate, non-transactional steps; a failure between them silently diverges the two.
13. **Every service in `app/services/` — each opens its own independent Cassandra connection to the same cluster**, and `DatasetService` additionally instantiates `BatchService()`/`SchemaService()` internally — one singleton holding 3+ sessions. No visible `close()`/shutdown path anywhere.
14. **Pervasive bare/broad `except Exception` across `dataset_service.py`, `schema_service.py`, `batch_service.py`** that `pass`es or falls back to an empty/degraded result with no re-raise — hides real bugs behind innocuous-looking defaults that feed into business logic (see mandatory #14).
15. **`app/services/dataset_service.py:496-498` — `get_dataset_schema` is a pure pass-through (Middle Man)** with no added logic over `schema_service.get_schema(dataset_id)`.
16. **`app/core/masking.py:19,219` — `MaskingRule.CUSTOM` enum member is dead code.** Dispatch actually checks `mask_rule.startswith("custom:")`, never referencing the enum — misleading, unreachable.
17. **`app/services/dataset_service.py:61-69` — No reserved-keyword handling in `_sanitize_col_name`.** A column literally named `select`/`token`/`key` sanitizes to itself and produces invalid/ambiguous CQL, surfacing as a runtime error on upload instead of being caught at validation time.

### Integrations / middleware / monitoring

18. **`app/integrations/kafka_producer.py:17-52` — Thread-unsafe singleton.** `get_instance()` does check-then-set on `cls._instance` with no lock (unlike `cassandra_client.py`, which does use one); concurrent first calls can construct multiple `KafkaProducer`s. `__init__` is also public, so anyone can bypass the "singleton" entirely.
19. **`app/integrations/kafka_consumer.py:51-90` — Duplicated subscribe/consume pattern; only the last subscription before `_consume()` blocks actually does anything.** Three near-identical `subscribe_to_X` methods suggest multi-topic use, but the class can't actually consume more than one topic/handler per instance. `enable_auto_commit=True` with no offset management also risks message loss on crash.
20. **Across `cassandra_client.py`, `kafka_producer.py`, `kafka_consumer.py`, `redis_cache.py`, `s3_storage.py` — Ad-hoc, inconsistent retry/error-handling per client (Shotgun Surgery risk).** Cassandra retries 30× over 150s; Kafka/Redis/S3 all raise immediately on first failure. No shared retry/backoff utility; fixing resiliency means touching every file individually.
21. **`app/integrations/local_storage.py` + `s3_storage.py` + `storage_factory.py` — No shared interface/ABC; backends drift.** Same method names by convention only, no `Protocol`, so a type checker won't catch signature drift (see next finding, which is exactly that).
22. **`local_storage.py:151-166` vs `s3_storage.py:194-215` — `generate_presigned_url` has non-interchangeable semantics.** S3 returns a real time-limited HTTPS URL; local returns a raw filesystem path with no expiry/access control — code treating this as "a URL" will leak local paths on the local backend.
23. **`app/integrations/redis_cache.py` vs `app/services/pagination_cache.py` — Two uncoordinated Redis-backed cache classes with overlapping responsibility**, own connections, own key namespaces. Invalidating one doesn't invalidate the other; risk of key collisions and incomplete invalidation.
24. **`app/integrations/s3_storage.py:56-69` — Constructor performs a side-effecting `create_bucket` call on every instantiation**, relying on catching `ClientError` for "already exists" — surprising side effect for a constructor, and inconsistent error-code handling across S3 vs MinIO.
25. **`app/integrations/s3_storage.py:162-183,217-249` — `delete_dataset_files`/`archive_old_files` don't paginate `list_objects_v2`**, silently truncating at 1000 keys — same bug duplicated in both methods, gets worse as data grows.
26. **`app/monitoring/metrics.py` — Many metrics defined (Kafka, ETL, auth, masking) with no producer code calling them.** Kafka producer/consumer never touch `DatasetManagerMetrics`; these will read zero on `/metrics` forever, misleading anyone building Grafana panels (`grafana_config.py` references several of them).
27. **`app/main.py:85` — `/metrics` mounted with no auth**, exposing the full Prometheus registry (per-endpoint/error-type cardinality) to anyone who can reach the service — compounded by the CORS wildcard (mandatory #4).
28. **`app/main.py:20,32-35` — Unusual layering: app imports `scripts.init_cassandra` at runtime**, and `startup_event` has no try/except or logging through `app_logger` on failure.
29. **`app/utils/log_formatter.py:15-18` — Module-level `logging.basicConfig()` as an import side effect**, which can clobber/conflict with logging configured elsewhere (e.g. uvicorn) depending on import order; the formatter also does no PII/secret redaction, and `audit_logging_middleware` logs a client-controlled `X-User-Email` header value straight through it.
30. **`app/middleware/rate_limit_audit.py:160` — Audit identity trusts an unauthenticated, client-supplied `X-User-Email` header** with no check against the JWT subject — any client can spoof it (currently moot only because the audit log isn't persisted anywhere — see mandatory #5).
31. **`app/middleware/rate_limit_audit.py:20-51` — `RateLimiter` state is in-memory only**, so it doesn't scale across multiple workers/instances — the effective limit becomes `requests_per_minute × num_workers` and never evicts stale IP entries.

---

## 🟢 Good to do — low-risk polish

1. **`app/integrations/redis_cache.py:96-134`** — `invalidate_dataset`/`invalidate_user_cache` duplicate the same scan-and-delete loop; extract a shared `_invalidate_pattern(pattern)` helper.
2. **`app/cassandra_client.py:41,44,47`** — Uses `print()` instead of `logging`, bypassing the JSON formatter/log pipeline used everywhere else.
3. **`app/cassandra_client.py:5`** — Minor PEP8 nit: missing space after a comma in an import.
4. **`app/integrations/kafka_consumer.py:141-152`** — `create_audit_event_handler`'s handler is an unfinished stub (`# Store in audit database/log`, never implemented) — remove or implement.
5. **`app/monitoring/grafana_config.py:364-377,485-487`** — Dashboard/alert export helpers and a `__main__` block look like one-off CLI tooling bundled into the monitoring module rather than `scripts/`.
6. **`app/middleware/rate_limit_audit.py:178-196`** — `cors_headers()` is dead code; CORS is actually configured via `CORSMiddleware` in `main.py`, so this duplicate, unused implementation risks drifting and confusing readers.
7. **`app/core/masking.py:201-222`** — `mask_value`'s `if/elif` chain is a Repeated-Switches candidate; a `Dict[str, Callable]` dispatch table would avoid editing this method for every new rule.
8. **`app/services/dataset_service.py:294`** — Inconsistent quoting: `"masking_config"` is quoted in the `UPDATE` statement, every other field isn't, with no comment explaining why.
9. **`app/services/permission_service.py:115-141`** — `check_permission`/`is_dataset_accessible` trust the caller-supplied `user_role` with no docstring note that it must come from a server-verified auth context.
10. **`app/services/dataset_service.py:531-540` + `pagination_cache.py:80-123`** — Repeated parameter clump `(dataset_id, page, page_size, user_role, columns)` threaded through multiple signatures; consider a small `PageRequest` value object.
11. **`app/api/datasets.py:122-125`** — Tags are stored/parsed as a comma-joined string and split back into a list at the call site, duplicating logic the response/update models already express as `List[str]`.
12. **`app/api/dependencies.py:34`** — Module-level Cassandra client constructed at import time, making setup implicit and harder to mock in tests.
13. **`app/auth_utils.py:68-71`** — Dead, commented-out example usage left in the module; remove or move to docs/tests.
14. **`app/api/auth.py:95-99` vs `54-59`** — `register`'s response includes a `message` field that `login`'s omits (relies on an `Optional` default) — minor response-shape inconsistency between two otherwise parallel endpoints.

---

## Note on CQL injection

Checked specifically given the dynamic per-dataset table creation pattern: table/keyspace names used in
f-string-interpolated CQL (`dataset_service.py`, `batch_service.py`, `schema_service.py`) are derived
from the `dataset_id` UUID and server-side `settings.CASSANDRA_KEYSPACE`, not raw user strings, and
`_sanitize_col_name`'s character-whitelist blocks CQL-breaking characters in column names — no classic
string-escaping injection path was found. The real risk in this area is the **column-name collision and
reserved-keyword gaps** already listed above (mandatory #17, normal #17), not injection.
