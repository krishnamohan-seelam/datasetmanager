# 01 — System Overview

## Context

A single-tenant-per-deployment platform where users upload datasets (files), which are validated, stored,
and made queryable with per-column PII masking and per-dataset RBAC. Everything runs behind one FastAPI
backend; the frontend is a separate SPA that only talks to that API.

```
                     ┌──────────────────────────┐
   Browser  ───────▶ │  Frontend (React/Vite)    │
                     │  :5173                    │
                     └────────────┬──────────────┘
                                  │ HTTPS/JSON (VITE_API_BASE_URL)
                                  ▼
                     ┌──────────────────────────┐
                     │  FastAPI backend          │
                     │  app/main.py  :8000       │
                     └───┬─────┬─────┬─────┬─────┘
                         │     │     │     │
           Cassandra ◀──┘     │     │     └──▶ Kafka (audit/ETL events)
           (:9042)            │     └──▶ Redis (:6379, pagination cache)
                               └──▶ S3 / MinIO / local FS (raw file storage)

   Airflow (separate scheduler/worker process) ── triggered via Kafka event ── runs
   dataset_etl_pipeline DAG, reads/writes the same Cassandra + storage backend.

   Prometheus (:9090) scrapes FastAPI's /metrics; Grafana (:3001) visualizes it.
```

## Containers (docker-compose services)

| Service | Image/Build | Port(s) | Role |
|---|---|---|---|
| `fastapi` | built from `dataset-manager/Dockerfile` | 8000 | API backend |
| `frontend` | built from `frontend/Dockerfile` | 5173 | SPA |
| `cassandra` | `cassandra:4.1` | 9042 | primary datastore |
| `redis` | `redis:7.2` | 6379 | pagination/result cache |
| `minio` | `minio/minio` | 9000/9001 | S3-compatible object storage (default `STORAGE_BACKEND`) |
| `prometheus` | `prom/prometheus` | 9090 | metrics scraping |
| `grafana` | `grafana/grafana` | 3001 (mapped from 3000) | dashboards |

Kafka and Airflow are part of the design (code exists for both — `app/integrations/kafka_*`,
`airflow/dags/dataset_etl_pipeline.py`) but are **not** services in `docker-compose.yml` — they must be
run separately if exercised.

## Request lifecycle (typical: list rows of a dataset)

1. Browser calls `GET /api/v1/datasets/{id}/rows` with a JWT bearer token (frontend's `axios.ts`
   attaches it; see `src/api/`).
2. `audit_logging_middleware` (always on) logs the request; rate limiting middleware exists but is
   disabled (see `06-cross-cutting-concerns.md`).
3. FastAPI resolves the route in `app/api/rows.py`, which depends on `get_current_user` /
   `require_role` (`app/core/security.py`) to authenticate and resolve role.
4. `PermissionService.is_dataset_accessible` checks the caller's per-dataset role.
5. `pagination_cache` (`app/services/pagination_cache.py`, backed by Redis) is checked before hitting
   Cassandra for the page of rows.
6. On a cache miss, `DatasetService`/Cassandra client queries the dataset's dedicated table.
7. `DataMasker` (`app/core/masking.py`) applies masking rules per column based on the caller's role
   before the response is serialized.
8. Prometheus counters/histograms in `app/monitoring/metrics.py` are updated throughout (API, cache,
   masking, DB).

## Technology stack (as used in code, not just declared)

- **Backend**: Python 3.11, FastAPI 0.110, Pydantic v2 (+ pydantic-settings for env config), served by
  Uvicorn. Poetry for dependency management.
- **Primary datastore**: Apache Cassandra 4.1 via `cassandra-driver`, one physical table per dataset
  (see `04-data-layer.md`).
- **Cache**: Redis 7.2, used specifically for paginated row-read caching, not as a general cache layer.
- **Object storage**: pluggable — local filesystem, MinIO, or AWS S3, selected by `STORAGE_BACKEND` env
  var via a factory (`05-integration-layer.md`).
- **Messaging**: Kafka, used for audit event publication and as the ETL trigger mechanism for Airflow.
- **Orchestration**: Apache Airflow, one DAG (`dataset_etl_pipeline`), manually/Kafka-triggered
  (`schedule_interval=None`).
- **Auth**: JWT (PyJWT) + Passlib/bcrypt password hashing, `OAuth2PasswordBearer` flow.
- **Monitoring**: `prometheus-client`, metrics mounted at `/metrics`; Grafana provisioned via
  docker-compose volumes under `dataset-manager/monitoring/`.
- **Frontend**: React 18 + TypeScript, Vite build, Redux Toolkit, MUI, Recharts, React Hook Form + Zod.
