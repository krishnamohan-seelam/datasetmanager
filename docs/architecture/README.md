# Architecture Blueprint — Dataset Manager

This folder is the **authoritative, code-derived** description of the system. Everything here was
produced by reading the current source (not by reading the old planning docs), so it reflects what the
code actually does today, including gaps and inconsistencies.

Everything under `../Planning/*` (including `Enhanced-PRD.md` and `Feature-Progress.md`) is **historical
narrative** (release write-ups, status snapshots, roadmap drafts). Those files are not kept in sync with
the code and should not be treated as a source of truth — use them only to recover *intent* or *history*
behind a decision, never to answer "what does the system currently do." See the banner added to the top
of each for a pointer back here.

## How this blueprint is organized

The system is a straightforward **layered architecture** on the backend (presentation → service →
integration → data), with cross-cutting concerns (security, masking, audit, monitoring) injected across
layers via middleware/dependencies, plus a separate orchestration plane (Airflow) and an independent
frontend SPA that talks to the backend only through its HTTP API. Each document below covers one layer or
cross-cutting concern:

1. [01-system-overview.md](./01-system-overview.md) — context diagram, containers, request lifecycle, tech stack
2. [02-api-layer.md](./02-api-layer.md) — FastAPI routers, request/response shapes, auth boundary
3. [03-service-layer.md](./03-service-layer.md) — domain services: datasets, schema versioning, batches, permissions, pagination cache
4. [04-data-layer.md](./04-data-layer.md) — Cassandra data model, per-dataset dynamic tables, schema versioning store
5. [05-integration-layer.md](./05-integration-layer.md) — storage backend factory (S3/MinIO/local), Kafka, Redis
6. [06-cross-cutting-concerns.md](./06-cross-cutting-concerns.md) — auth/RBAC, data masking, audit logging, rate limiting, monitoring
7. [07-etl-orchestration.md](./07-etl-orchestration.md) — Airflow DAG and its relationship to the API/Kafka
8. [08-frontend-architecture.md](./08-frontend-architecture.md) — React/Redux/MUI structure and its mapping to backend resources

## Known gaps / inconsistencies found while deriving this (worth fixing, not just documenting around)

- Rate limiting middleware (`app/middleware/rate_limit_audit.py`) is implemented but **commented out** in
  `app/main.py` — it does not run today.
- `app/cassandra_client.py` and `app/auth_utils.py` live directly under `app/` rather than in `core/` or
  `integrations/`, breaking the otherwise consistent package layout.
- Frontend has `vitest` and `@playwright/test` as devDependencies but no test files, no `npm test` script,
  and no vitest/playwright config — the test tooling is scaffolded but unused.
- `pyproject.toml` has no `[tool.pytest.ini_options]` / markers, so unit vs. integration separation is by
  directory convention (`tests/unit`, `tests/integration`) only, not enforced by pytest config.
