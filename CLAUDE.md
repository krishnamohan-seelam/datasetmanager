# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Dataset Manager Platform — a FastAPI + Cassandra backend with a React/TypeScript frontend for ingesting,
versioning, masking, and analyzing large-scale datasets. This is a work-in-progress learning project
(data engineering / data science / software engineering); unit test failures may exist.

Repo layout:
- `dataset-manager/` — backend (Python/FastAPI, Poetry)
- `frontend/` — frontend (React 18 + TypeScript, Vite)
- `docs/architecture/` — **the authoritative, code-derived architecture blueprint.** Layered by
  pattern (API → service → data → integration layer, plus cross-cutting concerns, ETL orchestration,
  frontend). Read `docs/architecture/README.md` first for anything architectural — it also lists known
  gaps/inconsistencies in the current code worth knowing before changing related areas.
- `Planning/` (including `Enhanced-PRD.md` and `Feature-Progress.md`) — historical planning/status docs.
  **Not kept in sync with the code** — each is now banner-marked as such. Use only to recover past
  intent/rationale, never as a description of current behavior.

## Commands

### Backend (run from `dataset-manager/`)

```bash
poetry install                                    # install deps
poetry run uvicorn app.main:app --reload          # run API (http://localhost:8000, docs at /docs)
poetry run python scripts/init_cassandra.py       # (re)initialize Cassandra keyspace/tables — required before first run
poetry run pytest                                 # run all tests
poetry run pytest tests/unit                      # unit tests only
poetry run pytest tests/unit/test_schema_service.py::TestClassName::test_name  # single test
poetry run pytest tests/integration                # integration tests (needs live Cassandra/Kafka/Redis/MinIO)
poetry run pytest tests/performance_benchmarks.py  # pytest-benchmark performance tests
poetry run black app tests                        # format
poetry run flake8 app                              # lint
poetry run mypy app                                # type check
```

Infra-only Docker (Cassandra, Kafka, Redis, MinIO) for local backend dev:
```bash
docker-compose up -d cassandra kafka redis minio
```
Full stack (backend + frontend + infra + Prometheus/Grafana):
```bash
docker-compose up --build -d
```

### Frontend (run from `frontend/`)

```bash
npm install
npm run dev       # Vite dev server, http://localhost:5173
npm run build     # tsc typecheck + vite build
npm run preview
```
Note: `vitest` and `@playwright/test` are listed as devDependencies but there are no test files, npm test
script, or vitest/playwright config in the repo yet — don't assume a working test command exists for the
frontend without checking first.

### Service URLs (via docker-compose)
Frontend `:5173` · API `:8000` (`/docs`) · MinIO console `:9001` · Cassandra `:9042` · Redis `:6379` ·
Kafka `:9092` · Prometheus `:9090` · Grafana `:3001`.

## Architecture

### Backend request flow
`app/main.py` builds the FastAPI app, registers exception handlers, CORS, the audit-logging middleware
(`app/middleware/rate_limit_audit.py` — rate limiting is implemented but currently commented out in
`main.py`), mounts `/metrics` (Prometheus via `app/monitoring/metrics.py`), and on startup calls
`scripts/init_cassandra.initialize_schema()`. Routers are aggregated in `app/api/__init__.py`
(`all_routers`) from `health`, `auth`, `datasets`, `rows`, `permissions`, `admin` — add new endpoint
modules there. `app/api/dependencies.py` holds shared service singletons (`DatasetService`,
`PermissionService`, `SchemaService`, `BatchService`) injected into routers.

Two files live directly under `app/` rather than in a subpackage and are widely imported:
`app/cassandra_client.py` (the Cassandra session/connection wrapper) and `app/auth_utils.py` (JWT
creation/decoding, `User` model).

### Dynamic per-dataset storage model
This is the core architectural idea: each dataset gets its **own Cassandra table**, created dynamically
at ingestion time by `DatasetService` (`app/services/dataset_service.py`, see the `CREATE TABLE IF NOT
EXISTS {keyspace}.{table_name}` in `create_dataset`), with typed columns inferred from the data rather
than a single shared generic table. `CASSANDRA_KEYSPACE` and connection settings come from
`app/core/config.py` (`Settings`, pydantic-settings, env-driven).

### Schema versioning
`SchemaService` (`app/services/schema_service.py`) tracks schema evolution per dataset: `create_schema` /
`evolve_schema` write new versions, `_infer_columns` infers types from a sample row, `_diff_schemas`
computes column-level diffs, `_register_version` / `_get_latest_version` manage version history, and
`drop_column` is a soft-delete rather than a destructive column drop. `get_schema_history` returns the
full version lineage for a dataset.

### Permissions / RBAC
`PermissionService` (`app/services/permission_service.py`) implements per-dataset role grants (Admin /
Owner / Viewer) with `grant_permission` / `revoke_permission` / `check_permission` /
`is_dataset_accessible`. Role is resolved per (dataset, user) pair, not globally.

### Data masking
`app/core/masking.py` defines `DataMasker` and the `MaskingRule` enum (email, phone, SSN, credit card,
name, IP, custom, plus frontend-aligned rules: redact, hash, partial_email, partial_text,
numeric_round). Masking is applied based on the requesting user's resolved permission role, not just a
static per-column flag — non-privileged roles see masked values at read time.

### Storage backend abstraction
`app/integrations/storage_factory.get_storage_service()` is a factory switching on the
`STORAGE_BACKEND` env var (`local` / `minio` / `aws`) to return `LocalStorageService` or
`S3StorageService` (the latter configured differently for MinIO vs. real AWS S3). Always go through this
factory rather than instantiating a storage backend directly, so storage stays swappable per environment.

### Event-driven audit logging
Kafka producer/consumer live in `app/integrations/kafka_producer.py` /
`kafka_consumer.py`. The audit-logging middleware in `app/middleware/rate_limit_audit.py` publishes an
event per API request for compliance/audit trail purposes, separate from Python application logging
(`app/utils/log_formatter.py`).

### ETL pipeline
`airflow/dags/dataset_etl_pipeline.py` defines the Airflow DAG for scheduled dataset validation/ingestion,
decoupled from the FastAPI request path — long-running or scheduled batch work belongs there, not in API
route handlers.

### Caching
`app/services/pagination_cache.py` + `app/integrations/redis_cache.py` cache paginated dataset row reads
in Redis rather than re-querying Cassandra per page.

### Frontend
Vite + React 18 + TypeScript, MUI for components, Redux Toolkit for state (`src/store/slices`), Recharts
for charts, React Hook Form + Zod for forms. `src/api/` holds a shared axios client (`axios.ts`) plus
per-resource wrapper modules (`auth.api.ts`, `datasets.api.ts`, `admin.api.ts`) — add new backend-facing
calls there rather than calling axios directly from components/pages. Routing is centralized in
`src/router.tsx`.

## Security model (from README)

- RBAC: Admin / Owner / Viewer, enforced via `PermissionService`.
- Data masking is automatic for non-admin users based on `MaskingRule`.
- Every data access/modification is audit-logged to Kafka.
- Rate limiting middleware exists for brute-force/API-abuse protection but is disabled by default in
  `app/main.py` (commented out) — enable deliberately for anything resembling production use.
