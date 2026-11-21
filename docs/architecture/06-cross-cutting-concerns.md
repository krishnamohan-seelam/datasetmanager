# 06 — Cross-Cutting Concerns

Concerns that cut across every layer rather than belonging to one: auth/RBAC, masking, audit logging,
rate limiting, and monitoring.

## Authentication & authorization

Two independent layers, easy to conflate (see also `02-api-layer.md`):

1. **Authentication + default role** — JWT-based. `app/auth_utils.py` issues/decodes tokens
   (`create_access_token`/`decode_access_token`), `app/core/security.py`'s `get_current_user` dependency
   decodes the bearer token into `{email, role, scopes}`, and `require_role([...])` gates whole endpoints
   by that token-level role (used by `admin.py`). Passwords are hashed with Passlib/bcrypt.
2. **Per-dataset authorization** — `PermissionService` (`03-service-layer.md`), independent grants of
   Admin/Owner/Viewer scoped to one dataset at a time, stored in `dataset_permissions`. A user can be a
   token-level "viewer" generally but "owner" of a specific dataset they created — `is_dataset_accessible`
   / `check_permission` is the actual gate for dataset/row/schema endpoints, not `require_role`.

## Data masking

`app/core/masking.py` — `DataMasker` + `MaskingRule` enum. Two families of rules coexist:
- **Pattern-based PII rules**: `email`, `phone`, `ssn`, `credit_card`, `name`, `ip`, `custom` — these
  correspond to the README's "Email, SSN, Phone, CC + 7 more rules" claim.
- **Frontend-aligned generic rules**: `redact` (full redaction), `hash` (truncated hash), `partial_email`,
  `partial_text`, `numeric_round` — added to match masking options exposed in the dataset schema UI
  (`PATCH /{id}/schema/{column}/masking`), not the original PII-pattern set.

A column's active rule is stored in `dataset_schema.masking_rule` (per schema version — see
`04-data-layer.md`) via `SchemaService.update_masking_rule`, and applied at **read time** in the
rows/download path — data is stored unmasked in Cassandra and masked only in the response, meaning
anyone with direct Cassandra access (or a code path that bypasses the row-read service) sees unmasked
data. Masking is driven by the caller's resolved role for that dataset (admin generally exempt,
non-admin masked), consistent with the pagination cache keying by role (`03-service-layer.md`).

## Audit logging

`app/middleware/rate_limit_audit.py`'s `audit_logging_middleware` is registered unconditionally in
`app/main.py` and runs on every request. **Verified: it only writes to the Python application log**
(`AuditLogger.log_request`/`log_data_access`/`log_permission_change` all end in `logger.info(...)`). It
does **not** write to the `audit_log` Cassandra table and does **not** publish to Kafka — a
repo-wide search (`grep -rl "audit_log" app/ scripts/`) shows `audit_log` is referenced only in
`scripts/init_cassandra.py`'s `CREATE TABLE` statement; nothing in `app/` ever inserts into it or reads
from it. The table is created and otherwise dead. Likewise no code path calls `KafkaEventProducer` from
the audit middleware. Any claim of a persisted, queryable audit trail (e.g. for compliance) is **not
currently true** — today "audit logging" means lines in stdout/the app logger, which are not retained
anywhere beyond normal log retention. Building a real audit trail would mean either writing
`AuditLogger` methods to the `audit_log` table directly, or wiring them to publish via
`KafkaEventProducer` as originally intended.

## Rate limiting — present but inert

`rate_limit_audit.py` also defines `RateLimiter` and `rate_limit_middleware`, but in `app/main.py` the
block that wires it up is **commented out**:
```python
# rate_limiter = RateLimiter(requests_per_minute=60)
# async def _rate_limit_dispatch(request, call_next):
#     return await rate_limit_middleware(request, call_next, rate_limiter)
# app.add_middleware(BaseHTTPMiddleware, dispatch=_rate_limit_dispatch)
```
The README's "Rate Limiting: Integrated middleware to prevent brute-force and API abuse" describes code
that exists but is not active in the running app. Treat the API today as **not** rate-limited unless this
is re-enabled.

## Monitoring

`app/monitoring/metrics.py` (`DatasetManagerMetrics`) defines a wide set of `prometheus-client`
Counters/Histograms/Gauges spanning every layer: API (`api_requests_total`,
`api_request_duration_seconds`, `api_errors_total`), dataset volume (`datasets_total`,
`dataset_rows_total`, `dataset_storage_bytes`), auth (`auth_login_total`, `active_sessions`),
permissions (`permission_checks_total`), masking (`masking_operations_total`,
`masking_duration_seconds`), cache (`cache_hits_total`/`cache_misses_total`/`cache_size_bytes`), DB
(`db_query_duration_seconds`, `db_connection_pool_size`), ETL (`etl_jobs_total`,
`etl_job_duration_seconds`, `etl_rows_processed_total`), Kafka (`kafka_messages_produced_total`,
`kafka_messages_consumed_total`, `kafka_consumer_lag`), and S3 (`s3_upload_bytes_total`,
`s3_download_bytes_total`, `s3_operation_duration_seconds`). A `track_api_call` decorator/helper wraps
endpoints to populate the API-level metrics. The `/metrics` ASGI app is mounted in `app/main.py` via
`prometheus_client.make_asgi_app`, scraped by the `prometheus` docker-compose service, visualized by
`grafana` (provisioning config under `dataset-manager/monitoring/`). Given that Kafka/ETL aren't wired
into the default running stack (`05-integration-layer.md`, `07-etl-orchestration.md`), their metrics will
likely sit at zero in a default `docker-compose up` — don't read a flat `etl_jobs_total`/
`kafka_consumer_lag` panel as "broken," it may just mean those subsystems were never invoked.
