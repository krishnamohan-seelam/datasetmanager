# 08 — Frontend Architecture

`frontend/` is a standalone Vite + React 18 + TypeScript SPA that talks to the backend only via the HTTP
API (base URL from `VITE_API_BASE_URL`, default `http://localhost:8000/api/v1` per
`docker-compose.yml`) — it holds no server-side logic and no direct access to Cassandra/Redis/Kafka.

## Layers, mapped to backend resources

- **`src/api/`** — the only place HTTP calls are made. `axios.ts` is the shared client (attaches the JWT
  from auth state); `auth.api.ts`, `datasets.api.ts`, `admin.api.ts` are thin per-resource wrappers
  matching the backend routers in `02-api-layer.md`, but not 1:1 by file — rows (`GET
  /datasets/{id}/rows`) and permissions (`GET`/`POST`/`DELETE /datasets/{id}/permissions`) calls both
  live inside `datasets.api.ts` rather than their own `rows.api.ts`/`permissions.api.ts`. New
  backend-facing calls belong in this directory, never inlined in a component.
- **`src/store/slices/`** — Redux Toolkit slices: `authSlice`, `datasetsSlice`, `adminSlice`, composed in
  `src/store/index.ts`. Note the `serializableCheck` middleware config explicitly ignores file-upload and
  file-download related action/state paths (`datasets/uploadDataset/pending`,
  `datasets/downloadDataset/fulfilled`, `payload.file`, `datasets.uploadData.file`) — this is because raw
  `File`/`Blob` objects are (deliberately) kept in Redux state for the upload/download flows, which
  Redux's default serializability check would otherwise flag; don't "fix" those warnings by removing the
  ignore list without also removing files from state.
- **`src/pages/`** — route-level screens, organized by resource: `auth/` (Login/Register),
  `datasets/` (List/Upload/Detail), `data/` (presumably row browsing/masking view), `admin/` (admin
  panel) — mirroring the backend's `auth`/`datasets`/`rows`/`admin` router split.
- **`src/components/`** — reusable UI, split the same way (`common/`, `data/`, `datasets/`, `layout/`).
  `components/common/ProtectedRoute` + `components/layout/AppLayout` are the two structural pieces
  wrapping every authenticated route (see routing below).
- **`src/types/`** — `common.types.ts`, `dataset.types.ts`, `user.types.ts`, the TS mirror of backend
  response shapes (`app/schemas/common.py`'s `PaginatedResponse[T]` etc.) — kept hand-written here, not
  generated from the backend, so a backend response shape change will not be caught by the type system
  until someone updates these manually.

## Routing (`src/router.tsx`)

`createBrowserRouter` with two public routes (`/login`, `/register`) and everything else nested under a
single `ProtectedRoute` → `AppLayout` subtree, defaulting `/` to a redirect to `/datasets`. Route-level
access control is therefore binary (authenticated or not) at the router level — any finer-grained
authorization (e.g. hiding admin-only routes from non-admins, or dataset-level permission checks) has to
be enforced inside the page/component itself by reading role/permission state from the store, not by the
router.

## State/data flow

Standard Redux Toolkit pattern: a page dispatches a thunk (e.g. `datasetsSlice`'s upload/download/list
actions) → the thunk calls into `src/api/*.api.ts` → the slice's reducers update `datasets` state →
components re-render off `useSelector`. There is no separate client-side cache layer (no React Query/SWR)
— all caching of backend data is server-side (Redis, `03-service-layer.md`/`05-integration-layer.md`);
the frontend re-fetches on navigation/action rather than relying on a stale-while-revalidate cache.
