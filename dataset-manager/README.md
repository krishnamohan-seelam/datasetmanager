# 📊 Dataset Manager Platform

A robust platform for managing, sharing, and protecting sensitive datasets with real-time data masking.

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
- **Dynamic Data Masking**: 
  - Redact, Hash, and Partial masking rules.
  - Role-based masking: Admins see raw data, viewers/contributors see masked data.
- **Access Control & Sharing**:
  - Interactive "Manage Permissions" UI.
  - Grant/revoke access via email with role-specific permissions (Viewer vs. Contributor).
- **Auto-Schema Detection**: Automatically detects column types on file upload.

## 📂 Project Structure

- `/app`: Backend FastAPI application.
  - `/core`: Config, security, and logging.
  - `/services`: Business logic (Datasets, Permissions, Masking).
- `/frontend`: React + TypeScript frontend application.
  - `/store`: Redux Toolkit for state management.
  - `/api`: Axios-based API client.
- `/scripts`: Database initialization and utility scripts.

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/datasets` | GET/POST | List and upload datasets |
| `/api/v1/datasets/{id}/rows` | GET | Paginated, masked data preview |
| `/api/v1/datasets/{id}/permissions` | GET/POST | Manage sharing access |
| `/api/v1/datasets/{id}/schema` | GET/PATCH | Configure data masking rules |
| `/health` | GET | Service status and DB connectivity check |

## 🧪 Testing

1. Log in.
2. Upload a CSV file (e.g., users.csv).
3. Go to the **Schema** tab and apply "Redact" to the 'Email' column.
4. Invite another user as a "Viewer".
5. Log in as that user and verify the email field is hidden in the **Data Preview**.
