# 02 — API Layer

FastAPI routers under `dataset-manager/app/api/`, aggregated in `app/api/__init__.py` as `all_routers`
and registered in `app/main.py`. All routers are thin: they parse/validate the request, call a service
singleton from `app/api/dependencies.py`, and shape the response — no business logic lives in routers.

## Routers and routes

| Router | Routes | Purpose |
|---|---|---|
| `health.py` | (health check) | liveness/readiness |
| `auth.py` | `POST /register`, `POST /login`, `GET /me` | account creation, JWT issuance, identity lookup |
| `datasets.py` | `POST /`, `GET /`, `GET /{id}`, `GET /{id}/schema`, `GET /{id}/schema/history`, `PATCH /{id}/schema/{column}/masking`, `GET /{id}/batches`, `DELETE /{id}/batches/{batch_id}`, `PATCH /{id}/meta`, `DELETE /{id}` | dataset CRUD, schema introspection/history, per-column masking rule updates, batch management |
| `rows.py` | `GET /{dataset_id}/rows`, `GET /{dataset_id}/download` | paginated row reads (masked) and bulk export/download |
| `permissions.py` | `GET /{dataset_id}/permissions`, `POST /{dataset_id}/permissions`, `DELETE /{dataset_id}/permissions/{user_email}` | per-dataset RBAC grant management |
| `admin.py` | `GET /stats`, `GET /users`, `POST /cache/clear` | platform-wide admin stats, user listing, manual cache invalidation |

## Auth boundary

- `app/core/security.py` defines `get_current_user` (decodes the JWT via `app/auth_utils.py`, returns
  `{email, role, scopes}`) and `require_role(allowed_roles)`, a dependency factory routers use to gate
  endpoints by role (e.g. `admin.py` endpoints require `["admin"]`).
- Role in the JWT is a *default* role claim; **dataset-scoped** access still goes through
  `PermissionService` (per-dataset grants), so a user's JWT role and their effective permission on a
  given dataset are two different checks — routers that touch a specific dataset must do both.

## Shared dependencies (`app/api/dependencies.py`)

Centralizes service singletons (`DatasetService`, `PermissionService`, `SchemaService`, `BatchService`)
and helpers (CSV/JSON parsing via `csv`/`pandas` for ingestion, `app_logger`). Routers import from here
rather than instantiating services themselves — new routers should follow the same pattern instead of
constructing their own service instances.

## Response shaping

- `app/schemas/common.py` defines shared response envelopes, notably a generic `PaginatedResponse[T]`
  used by `GET /datasets` and `GET /{id}/batches`.
- `app/core/exceptions.py` defines a domain exception hierarchy (`DatasetManagerException` →
  `DatasetNotFoundException`, `InsufficientPermissionsException`, `InvalidFileFormatException`,
  `DatasetAlreadyExistsException`, `UploadFailedException`). There is **no global FastAPI exception
  handler mapping these to HTTP codes** — `app/main.py` only registers a catch-all `Exception` handler
  (generic 500). Instead, each router endpoint wraps its body in its own `try/except`, catching specific
  domain exceptions first (e.g. `except DatasetNotFoundException: raise HTTPException(404, ...)` in
  `datasets.py`) and a generic `except Exception` last (mapped to 500). This means adding a new domain
  exception type requires remembering to catch it in every router that can raise it — there is no single
  place that guarantees the mapping.
