# 📊 Dataset Manager Platform

A robust platform for managing, sharing, and protecting sensitive datasets with real-time data masking, batch ingestion, and schema versioning.

## 🚀 Quick Start (Docker)

The fastest way to get the entire stack (Backend, Frontend, and Databases) running:

```powershell
# 1. Start all backend services
docker-compose up --build

# 2. In a separate terminal, start the frontend
cd frontend
npm install
npm run dev
```

The backend includes a **graceful retry mechanism** for Cassandra, so it will wait automatically until the database is fully initialized.

## 🛠 Features

- **Multi-Service Architecture**: FastAPI + Cassandra (Primary DB) + Redis (Cache) + MinIO (Storage).
- **Graceful Startup**: Application-level retries for database connectivity, ensuring resilience in containerized environments.
- **Batch Ingestion**: Support for one-time, hourly, daily, weekly, and monthly data batches with per-batch isolation.
- **Schema Versioning**: Automatic schema evolution with version history, soft-deleted columns, and diff tracking.
- **Dynamic Data Masking**: 
  - 11 built-in rules (email, phone, SSN, credit card, name, IP, redact, hash, partial text, numeric round, custom regex).
  - Role-based masking: Admins see raw data, viewers/contributors see masked data.
- **Access Control & Sharing**:
  - Interactive "Manage Permissions" UI.
  - Grant/revoke access via email with role-specific permissions (Admin, Contributor, Viewer).
- **Auto-Schema Detection**: Automatically detects column types on file upload with schema evolution on subsequent batches.

## 📂 Project Structure

- `/app`: Backend FastAPI application.
  - `/core`: Config, security, and logging.
  - `/services`: Business logic (Datasets, Schema, Batch, Permissions, Masking).
  - `/schemas`: Pydantic models (BatchFrequency, BatchResponse, SchemaVersionResponse).
- `/frontend`: React + TypeScript frontend application.
  - `/store`: Redux Toolkit for state management (15 thunks).
  - `/api`: Axios-based API client (20 methods).
- `/scripts`: Database initialization and migration scripts.

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/datasets` | GET/POST | List and upload datasets (supports batch_frequency, batch_date) |
| `/api/v1/datasets/{id}/rows` | GET | Paginated, masked data preview (supports ?batch_id filter) |
| `/api/v1/datasets/{id}/permissions` | GET/POST | Manage sharing access |
| `/api/v1/datasets/{id}/schema` | GET/PATCH | Schema with version support (?version=N) and masking rules |
| `/api/v1/datasets/{id}/schema/history` | GET | List all schema versions with change summaries |
| `/api/v1/datasets/{id}/batches` | GET/DELETE | List / delete data batches |
| `/health` | GET | Service status and DB connectivity check |

## 🗄 Database Tables

| Table | Purpose |
|-------|---------|
| `datasets` | Dataset metadata (includes batch_frequency, schema_version) |
| `dataset_schema` | Versioned column definitions with soft-delete |
| `dataset_schema_versions` | Schema version history and change summaries |
| `dataset_batches` | Per-dataset batch metadata (date, rows, size, status) |
| `ds_rows_<uuid>` | Dedicated per-dataset row storage, partitioned by batch |
| `dataset_permissions` | Role-based access control per dataset |
| `users` | User accounts and global roles |
| `audit_log` | Access and modification tracking |

## 🧪 Testing

### Backend
```bash
# Activate virtual environment
venv\Scripts\activate            # Windows
source venv/bin/activate         # macOS/Linux

# Run all tests (15 tests — 8 schema + 7 batch)
pytest tests/ -v
```

### Manual Walkthrough
1. Log in.
2. Upload a CSV file with a **batch frequency** (e.g., Daily).
3. Go to the **Schema** tab and apply "Redact" to the 'Email' column.
4. Upload another CSV — observe **schema evolution** (new columns auto-detected).
5. Switch to the **Batches** tab to see all ingestion batches.
6. Use the **Schema Version** dropdown to browse historical schemas.
7. Invite another user as a "Viewer" and verify masked data in **Data Preview**.
