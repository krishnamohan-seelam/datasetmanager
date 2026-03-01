---
copilot: true
copilot-context: prd
---

# Product Requirements Document: Dataset Manager Platform

**Version:** 3.0  
**Last Updated:** March 1, 2026  
**Project Type:** Scalable Backend System for Dataset Management  
**Technology Stack:** Python, FastAPI, Apache Cassandra, Apache Airflow, React (MUI v7)

---

## GitHub Copilot Instructions

When generating code for this project:
- **Framework**: Use FastAPI with async/await patterns
- **Database**: Apache Cassandra with cassandra-driver
- **ETL**: Use PySpark for large datasets (>1M rows), Pandas for smaller ones
- **Orchestration**: Apache Airflow DAGs with error handling and retry logic
- **Message Queue**: Apache Kafka for async task processing
- **Testing**: pytest with pytest-asyncio, minimum 80% coverage
- **Code Style**: Follow PEP 8, use type hints throughout
- **Security**: Use OAuth2 with JWT tokens, implement role-based access with decorators
- **Documentation**: Generate OpenAPI schema automatically via FastAPI
- **Error Handling**: Use custom exception classes, return structured error responses
- **Logging**: Use Python logging with JSON format for structured logs

---

## Table of Contents
1. [Objective](#objective)
2. [Technology Stack](#technology-stack)
3. [Assumptions](#assumptions)
4. [User Stories](#user-stories)
5. [Acceptance Criteria](#acceptance-criteria)
6. [Technical Constraints & Design Decisions](#technical-constraints--design-decisions)
7. [API Endpoints](#api-endpoints)
8. [Data Storage & Metadata](#data-storage--metadata)
9. [Security & Compliance](#security--compliance)
10. [Code Examples for Copilot Reference](#code-examples-for-copilot-reference)
11. [Project Structure](#project-structure)
12. [Implementation Priorities](#implementation-priorities)
13. [Testing Requirements](#testing-requirements)
14. [Environment Configuration](#environment-configuration)
15. [Dependencies](#dependencies)
16. [Good-to-Have Features](#good-to-have-features)
17. [Out of Scope](#out-of-scope)

---

## Objective

Build a scalable backend system for uploading, managing, and sharing large datasets, inspired by Kaggle Datasets. The product must offer robust ETL, metadata management, secure API endpoints, and support for billions of rows with role-based access and data masking.

### Key Goals
- Handle datasets from 1MB to 10TB seamlessly
- Support 10,000+ concurrent users
- Provide role-based access control (Admin, Contributor, Viewer)
- Implement intelligent data masking for sensitive information
- Enable efficient search and discovery of datasets
- Maintain comprehensive audit logs for compliance

---

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI (async/await)
- **API Gateway**: NGINX or Kong (for production)

### Data Processing
- **ETL**: 
  - Pandas (datasets < 1M rows)
  - Future implementation: PySpark (datasets > 1M rows)
- **Orchestration**: Apache Airflow
- **Message Queue**: Apache Kafka

### Storage
- **NoSQL Database**: Apache Cassandra
- **Object Storage**: AWS S3 / Google Cloud Storage (for raw files)
- **Cache**: Redis (for metadata and query results)

### Middleware
- **Authentication**: OAuth2 + JWT
- **API Gateway**: Rate limiting, request validation
- **Monitoring**: Prometheus + Grafana

### Frontend (Phase 2)
- **Framework**: Vite + React + TypeScript
- **State Management**: Redux Toolkit
- **UI Library**: MUI v7 (Material-UI)
- **Charts**: Recharts
- **API Client**: Axios with JWT interceptors

---

## Assumptions

1. Datasets may be massive (multi-million to billion rows)
2. Sensitive data requires masking based on user roles
3. Data queries need pagination (max 1000 rows per page)
4. API endpoints must be secure and RESTful
5. System should handle 100+ dataset uploads per day
6. Average dataset size: 100MB - 5GB
7. Peak concurrent users: 10,000
8. Data retention: Minimum 5 years with archival strategy
9. 99.9% uptime SLA requirement
10. Multi-region deployment capability required

---

## User Stories

### Data Scientists & Analysts
1. **As a data scientist**, I want to upload a dataset (CSV, JSON, Parquet), so that I can share and analyze it online
2. **As a data scientist**, I want to search datasets by name, tags, and metadata, so that I can discover relevant data quickly
3. **As a data scientist**, I want to preview dataset rows before downloading, so that I can verify it meets my needs
4. **As a data scientist**, I want to download datasets in multiple formats, so that I can use them in my preferred tools

### Administrators
5. **As an admin**, I want to define roles and access permissions for each dataset, so that I can control data access
6. **As an admin**, I want to view audit logs of all dataset access and modifications, so that I can ensure compliance
7. **As an admin**, I want to configure masking rules for sensitive columns, so that I can protect user privacy

### General Users
8. **As a user**, I want to view datasets with sensitive columns masked according to my role, so that I see only authorized data
9. **As a user**, I want to see dataset statistics and metadata, so that I can understand the data before using it
10. **As a user**, I want to receive notifications when datasets I follow are updated, so that I stay informed

### Engineers & DevOps
11. **As an engineer**, I want to build ETL pipelines for periodic dataset ingestion and validation, so that data is always current
12. **As an engineer**, I want comprehensive error logs and monitoring, so that I can troubleshoot issues quickly
13. **As a developer**, I want pagination for browsing query results efficiently, so that large datasets don't overwhelm the system

---

## Acceptance Criteria

### Core Functionality
- ✅ System ingests datasets (CSV, JSON, Parquet) and stores them in a scalable NoSQL database
- ✅ Metadata (name, schema, owner, roles, masking, statistics) is tracked for each dataset
- ✅ REST API exposes: upload, metadata fetch/update, list/search, paginated data preview/download, deletion
- ✅ All endpoints are protected with role-based access control (admin/contributor/viewer)
- ✅ Sensitive columns are masked according to metadata rules before delivery to non-admins
- ✅ All row access endpoints implement pagination and optional filtering
- ✅ ETL jobs validate, transform, and anonymize on ingestion; errors are logged

### Performance
- ✅ API response time: <200ms for metadata endpoints
- ✅ API response time: <2s for paginated data endpoints
- ✅ Support datasets up to 10TB
- ✅ ETL throughput: Process minimum 1M rows/minute
- ✅ Handle 10,000 concurrent API requests

### Security & Compliance
- ✅ All sensitive data is encrypted at rest and in transit
- ✅ Audit logs capture all access and modification events
- ✅ GDPR-compliant data deletion (right to be forgotten)
- ✅ Role-based access enforced at API and data layer

---

## Technical Constraints & Design Decisions

### Database Schema (Apache Cassandra)

#### Table: datasets
**Purpose**: Store dataset metadata (includes batch/schema tracking)
```cql
CREATE TABLE datasets (
    dataset_id UUID PRIMARY KEY,
    name TEXT,
    description TEXT,
    owner_email TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    row_count BIGINT,
    size_bytes BIGINT,
    file_format TEXT,
    status TEXT, -- 'uploading', 'processing', 'ready', 'failed'
    storage_path TEXT,
    version INT,
    tags SET<TEXT>,
    is_public BOOLEAN,
    batch_frequency TEXT,     -- 'once', 'hourly', 'daily', 'weekly', 'monthly'
    latest_batch_id UUID,
    latest_batch_date TIMESTAMP,
    total_batches INT,
    schema_version INT,
    INDEX (owner_email),
    INDEX (name)
);
```

#### Table: dataset_schema
**Purpose**: Store versioned column metadata and masking rules with soft-delete support
```cql
CREATE TABLE dataset_schema (
    dataset_id UUID,
    column_name TEXT,
    column_type TEXT,
    is_nullable BOOLEAN,
    is_masked BOOLEAN,
    mask_rule TEXT,
    position INT,
    version INT,          -- Schema version when column was added
    is_active BOOLEAN,    -- false = soft-deleted (column dropped)
    added_at TIMESTAMP,
    removed_at TIMESTAMP, -- Set when is_active becomes false
    PRIMARY KEY (dataset_id, column_name)
);
```

#### Table: dataset_schema_versions
**Purpose**: Track schema version metadata and change summaries
```cql
CREATE TABLE dataset_schema_versions (
    dataset_id UUID,
    version INT,
    batch_id UUID,
    created_at TIMESTAMP,
    column_count INT,
    change_summary TEXT,
    PRIMARY KEY (dataset_id, version)
) WITH CLUSTERING ORDER BY (version DESC);
```

#### Table: dataset_batches
**Purpose**: Track individual data ingestion batches per dataset
```cql
CREATE TABLE dataset_batches (
    dataset_id UUID,
    batch_id UUID,
    batch_date TIMESTAMP,
    schema_version INT,
    row_count BIGINT,
    size_bytes BIGINT,
    file_format TEXT,
    status TEXT,          -- 'processing', 'ready', 'failed'
    uploaded_by TEXT,
    created_at TIMESTAMP,
    PRIMARY KEY (dataset_id, batch_date, batch_id)
) WITH CLUSTERING ORDER BY (batch_date DESC, batch_id DESC);
```

#### Table: dataset_rows (Legacy Pattern)
> [!NOTE]
> The original shared `dataset_rows` table has been refactored for scalability. Each dataset now has its own dedicated table for row storage.

#### Table: ds_rows_<uuid> (Current Pattern)
**Purpose**: Dedicated storage for each dataset's rows with structured columns.
**Partitioning**: By `batch_id` + `row_chunk_id` for batch-isolated access.
```cql
CREATE TABLE ds_rows_<dataset_id> (
    batch_id UUID,       -- Batch partition key
    row_chunk_id INT,    -- Chunk partition key
    row_id BIGINT,       -- Clustering key
    -- Dynamic columns based on dataset schema
    col1 TEXT,
    col2 INT,
    col3 DOUBLE,
    ...,
    PRIMARY KEY ((batch_id, row_chunk_id), row_id)
) WITH CLUSTERING ORDER BY (row_id ASC);
```

#### Table: dataset_permissions
**Purpose**: Store role-based access control
```cql
CREATE TABLE dataset_permissions (
    dataset_id UUID,
    user_email TEXT,
    role TEXT, -- 'admin', 'contributor', 'viewer'
    granted_at TIMESTAMP,
    granted_by TEXT,
    PRIMARY KEY ((dataset_id), user_email)
);
```

#### Table: audit_log
**Purpose**: Track all access and modifications
```cql
CREATE TABLE audit_log (
    log_id TIMEUUID,
    dataset_id UUID,
    user_email TEXT,
    action TEXT, -- 'upload', 'download', 'view', 'update', 'delete'
    timestamp TIMESTAMP,
    ip_address TEXT,
    details TEXT, -- JSON with additional info
    PRIMARY KEY ((dataset_id), log_id)
) WITH CLUSTERING ORDER BY (log_id DESC);
```

#### Table: etl_jobs
**Purpose**: Track ETL job execution
```cql
CREATE TABLE etl_jobs (
    job_id UUID PRIMARY KEY,
    dataset_id UUID,
    job_type TEXT, -- 'upload_processing', 'validation', 'transformation'
    status TEXT, -- 'queued', 'running', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    processed_rows BIGINT,
    INDEX (dataset_id)
);
```

#### Table: users
**Purpose**: Store user accounts and global roles
```cql
CREATE TABLE users (
    email TEXT PRIMARY KEY,
    username TEXT,
    password_hash TEXT,
    role TEXT, -- 'admin', 'user'
    created_at TIMESTAMP,
    last_login TIMESTAMP
);
```

### Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| Metadata API Response | <200ms | p95 latency |
| Data Query API Response (Cached) | <100ms | p95 latency |
| Data Query API Response (Cold) | <2s | p95 latency |
| Concurrent Users | 10,000+ | Load testing |
| Dataset Size Support | Up to 10TB | Integration testing |
| ETL Throughput | 1M rows/min | Processing benchmarks |
| Bulk Insert Throughput | 100K rows/sec | Cassandra Batch optimization |
| Uptime SLA | 99.9% | Monthly availability |

#### Pagination Caching (Redis)
- **Performance**: Reduces p95 latency for paginated queries from ~1.5s to <80ms.

#### Storage Factory Pattern
- **Overview**: The system implements a factory pattern for storage backends.
- **Backends supported**: AWS S3, MinIO (local S3 compatible), and Local Filesystem fallback.
- **Benefit**: Seamless transition between development, staging, and production environments without code changes.

### Masking Strategies

#### Built-in Masking Rules

| Data Type | Rule Name | Example Input | Masked Output |
|-----------|-----------|---------------|---------------|
| Email | `email` | john.doe@example.com | jo***@example.com |
| Email (Partial) | `partial_email` | john.doe@example.com | jo***@example.com |
| Phone | `phone` | +1-555-123-4567 | ***-***-4567 |
| SSN | `ssn` | 123-45-6789 | ***-**-6789 |
| Credit Card | `credit_card` | 4532-1234-5678-9010 | ****-****-****-9010 |
| Name | `name` | John Michael Doe | J*** M*** D*** |
| Text (Partial) | `partial_text` | Sensitive Content | Sen***... |
| IP Address | `ip` | 192.168.1.100 | 192.168.***.*** |
| Redact | `redact` | Any Value | ******** |
| Hash | `hash` | Secret Data | a1b2c3d4... (SHA256) |
| Numeric Round | `numeric_round` | 12345 | 12300 |
| Custom Regex | `custom:pattern` | User defined | User defined |

#### Masking Implementation
```python
# Example masking function signature
def mask_value(value: str, mask_rule: str, user_role: str) -> str:
    """Apply masking rule to value based on user role"""
    if user_role == "admin":
        return value  # Admins see everything
    
    if mask_rule == "email":
        return mask_email(value)
    elif mask_rule == "phone":
        return mask_phone(value)
    # ... other rules
    
    return value
```

### ETL Pipeline Architecture

```
Upload → S3 Storage → Kafka Event → Airflow DAG Trigger
                                          ↓
                              ┌───────────────────────┐
                              │   Validation Stage    │
                              │  - Schema check       │
                              │  - Data quality       │
                              │  - Virus scan         │
                              └───────────┬───────────┘
                                          ↓
                              ┌───────────────────────┐
                              │ Transformation Stage  │
                              │  - Type conversion    │
                              │  - Null handling      │
                              │  - Deduplication      │
                              └───────────┬───────────┘
                                          ↓
                              ┌───────────────────────┐
                              │   Loading Stage       │
                              │  - Chunk rows         │
                              │  - Write to Cassandra │
                              │  - Update metadata    │
                              └───────────┬───────────┘
                                          ↓
                              ┌───────────────────────┐
                              │   Indexing Stage      │
                              │  - Generate stats     │
                              │  - Create search idx  │
                              │  - Mark as 'ready'    │
                              └───────────────────────┘
```

---

## API Endpoints

### Base URL
- **Development**: `http://localhost:8000/api/v1`
- **Production**: `https://api.dataset-manager.com/api/v1`

Authorization: Bearer <jwt_token>
```

### Endpoint Specifications

#### 0. Authentication
```http
POST /auth/register
POST /auth/login
GET /auth/me
```

#### 1. List/Search Datasets
```http
GET /datasets
```

**Query Parameters**:
- `page` (int, default=1): Page number
- `page_size` (int, default=100, max=1000): Items per page
- `search` (str, optional): Search in name, description, tags
- `owner` (str, optional): Filter by owner email
- `tags` (str, optional): Comma-separated tags
- `is_public` (bool, optional): Filter public/private datasets
- `sort_by` (str, optional): `created_at`, `updated_at`, `name`, `row_count`
- `order` (str, optional): `asc`, `desc` (default)

**Response** (200 OK):
```json
{
  "total": 150,
  "page": 1,
  "page_size": 100,
  "pages": 2,
  "datasets": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "customer_demographics_2024",
      "description": "Customer data with demographics",
      "owner": "data.scientist@company.com",
      "created_at": "2024-10-15T10:30:00Z",
      "updated_at": "2024-10-20T14:22:00Z",
      "row_count": 1500000,
      "size_bytes": 45000000,
      "file_format": "csv",
      "tags": ["customers", "demographics", "2024"],
      "is_public": false,
      "status": "ready"
    }
  ]
}
```

---

#### 2. Upload New Dataset
```http
POST /datasets
```

**Headers**:
- `Content-Type: multipart/form-data`

**Body** (multipart/form-data):
- `file` (file, required): Dataset file (CSV, JSON, Parquet)
- `name` (str, required): Dataset name
- `description` (str, optional): Dataset description
- `tags` (str, optional): Comma-separated tags
- `is_public` (bool, default=false): Public visibility
- `masking_config` (json, optional): Column masking configuration
- `batch_frequency` (str, optional, default='once'): One of `once`, `hourly`, `daily`, `weekly`, `monthly`
- `batch_date` (str, optional): ISO-8601 datetime for this batch. Defaults to current time.

**Example masking_config**:
```json
{
  "email": "email",
  "phone_number": "phone",
  "ssn": "ssn"
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "customer_demographics_2024",
  "row_count": 1500000,
  "status": "ready",
  "batch_frequency": "daily"
}
```

**Response** (400 Bad Request):
```json
{
  "error": {
    "code": "INVALID_FILE_FORMAT",
    "message": "Unsupported file format. Allowed: csv, json, parquet",
    "details": {
      "file_extension": ".xlsx"
    }
  }
}
```

---

#### 3. Get Dataset Metadata
```http
GET /datasets/{dataset_id}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "customer_demographics_2024",
  "description": "Customer data with demographics",
  "owner": "data.scientist@company.com",
  "created_at": "2024-10-15T10:30:00Z",
  "updated_at": "2024-10-20T14:22:00Z",
  "row_count": 1500000,
  "size_bytes": 45000000,
  "file_format": "csv",
  "status": "ready",
  "storage_path": "s3://datasets/550e8400-e29b-41d4-a716-446655440000/data.csv",
  "version": 1,
  "tags": ["customers", "demographics", "2024"],
  "is_public": false,
  "schema": [
    {
      "name": "customer_id",
      "type": "string",
      "nullable": false,
      "masked": false,
      "position": 0
    },
    {
      "name": "email",
      "type": "string",
      "nullable": true,
      "masked": true,
      "mask_rule": "email",
      "position": 1
    },
    {
      "name": "age",
      "type": "integer",
      "nullable": true,
      "masked": false,
      "position": 2
    }
  ],
  "statistics": {
    "total_rows": 1500000,
    "total_columns": 15,
    "null_count": 1250,
    "duplicate_rows": 0
  },
  "permissions": {
    "admins": ["admin@company.com"],
    "contributors": ["data-team@company.com"],
    "viewers": ["analytics@company.com", "marketing@company.com"]
  },
    }
  ]
}
```

---

#### 3.5 Schema & Masking Rules
```http
GET /datasets/{id}/schema?version=N   # Optional version param
GET /datasets/{id}/schema/history      # List all schema versions
PATCH /datasets/{id}/schema/{col}/masking
```

**GET /schema Response** (200 OK):
```json
[
  {
    "name": "email",
    "type": "string",
    "nullable": true,
    "masked": true,
    "mask_rule": "email",
    "position": 1,
    "is_active": true
  }
]
```

**GET /schema/history Response** (200 OK):
```json
[
  {
    "version": 2,
    "batch_id": "...",
    "created_at": "2026-03-01T10:00:00Z",
    "column_count": 15,
    "change_summary": "Added: new_col; Dropped: old_col"
  }
]
```

**PATCH Body**:
```json
{
  "mask_rule": "email"
}
```

---

#### 3.6 Batch Management
```http
GET /datasets/{id}/batches                # List all batches (paginated)
DELETE /datasets/{id}/batches/{batch_id}   # Delete a specific batch
```

**GET /batches Response** (200 OK):
```json
{
  "total": 12,
  "page": 1,
  "page_size": 20,
  "pages": 1,
  "items": [
    {
      "batch_id": "...",
      "batch_date": "2026-03-01T00:00:00Z",
      "schema_version": 2,
      "row_count": 50000,
      "size_bytes": 12000000,
      "status": "ready",
      "uploaded_by": "user@company.com",
      "created_at": "2026-03-01T10:30:00Z"
    }
  ]
}
```

---

#### 4. Download Dataset
```http
GET /datasets/{dataset_id}/download
```

**Query Parameters**:
- `format` (str, optional): `csv`, `json`, `parquet` (default: original format)
- `masked` (bool, default=true): Apply masking rules based on user role

**Response** (200 OK):
- **Headers**:
  - `Content-Type`: application/octet-stream
  - `Content-Disposition`: attachment; filename="customer_demographics_2024.csv"
- **Body**: File stream

**Response** (403 Forbidden):
```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "You do not have permission to download this dataset",
    "details": {
      "required_role": "contributor",
      "current_role": "viewer"
    }
  }
}
```

---

#### 5. Get Paginated Rows
```http
GET /datasets/{dataset_id}/rows
```

**Query Parameters**:
- `page` (int, default=1): Page number
- `page_size` (int, default=100, max=1000): Rows per page
- `batch_id` (uuid, optional): Filter rows by specific batch
- `filters` (json, optional): Column filters (e.g., `{"age": {"gt": 30}}`)
- `columns` (str, optional): Comma-separated column names to return
- `masked` (bool, default=true): Apply masking rules

**Example filters**:
```json
{
  "age": {"gt": 30, "lt": 50},
  "city": {"in": ["New York", "Los Angeles"]},
  "status": {"eq": "active"}
}
```

**Response** (200 OK):
```json
{
  "total": 1500000,
  "page": 1,
  "page_size": 100,
  "pages": 15000,
  "rows": [
    {
      "customer_id": "CUST001",
      "email": "jo***@example.com",
      "age": 34,
      "city": "New York",
      "status": "active"
    },
    {
      "customer_id": "CUST002",
      "email": "sa***@example.com",
      "age": 42,
      "city": "Los Angeles",
      "status": "active"
    }
  ]
}
```

---

#### 6. Update Dataset Metadata
```http
PATCH /datasets/{dataset_id}/meta
```

**Request Body**:
```json
{
  "name": "customer_demographics_2024_updated",
  "description": "Updated description",
  "tags": ["customers", "demographics", "2024", "verified"],
  "is_public": true,
  "masking_config": {
    "email": "email",
    "ssn": "ssn"
  },
  "permissions": {
    "admins": ["admin@company.com", "new.admin@company.com"],
    "contributors": ["data-team@company.com"],
    "viewers": ["analytics@company.com"]
  }
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Dataset metadata updated successfully",
  "updated_fields": ["name", "tags", "is_public", "permissions"]
}
```

**Response** (403 Forbidden):
```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Only admins can update dataset metadata",
    "details": {
      "required_role": "admin",
      "current_role": "contributor"
    }
  }
}
```

---

#### 7. Delete Dataset
```http
DELETE /datasets/{dataset_id}
```

**Query Parameters**:
- `confirm` (bool, required=true): Confirmation flag

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Dataset deleted successfully",
  "deleted_rows": 1500000,
  "deleted_size_bytes": 45000000
}
```

**Response** (403 Forbidden):
```json
{
  "error": {
    "code": "INSUFFICIENT_PERMISSIONS",
    "message": "Only admins can delete datasets",
    "details": {
      "required_role": "admin",
      "current_role": "contributor"
    }
  }
}
```

---

#### 8. Get ETL Job Status
```http
GET /datasets/{dataset_id}/jobs/{job_id}
```

**Response** (200 OK):
```json
{
  "job_id": "660e8400-e29b-41d4-a716-446655440001",
  "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_type": "upload_processing",
  "status": "running",
  "progress": 45.5,
  "started_at": "2024-11-02T10:00:00Z",
  "completed_at": null,
  "processed_rows": 682500,
  "total_rows": 1500000,
  "error_message": null
}
```

---

#### 9. Health Check
```http
GET /health
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "timestamp": "2024-11-02T11:30:00Z",
  "version": "1.0.0",
  "services": {
    "cassandra": "healthy",
    "redis": "healthy",
    "kafka": "healthy",
    "s3": "healthy"
  }
}
```

---

## Data Storage & Metadata

### Storage Strategy

#### Raw Files (Object Storage - S3/GCS)
- **Path Pattern**: `s3://bucket-name/{dataset_id}/raw/{filename}`
- **Retention**: 90 days (configurable)
- **Encryption**: Server-side encryption (SSE-S3 or SSE-KMS)
- **Versioning**: Enabled for disaster recovery

#### Processed Data (Cassandra)
- **Partitioning**: By `(dataset_id, row_chunk_id)` for efficient row-range queries
- **Chunk Size**: 10,000 rows per chunk
- **Replication Factor**: 3 (configurable)
- **Consistency Level**: QUORUM for writes, LOCAL_QUORUM for reads

#### Metadata Cache (Redis)
- **TTL**: 1 hour for dataset metadata
- **Keys**: `dataset:{dataset_id}`, `dataset:search:{hash}`, `user:permissions:{email}`
- **Invalidation**: On update/delete operations

### Metadata Schema

Each dataset stores:
- **Basic Info**: name, description, owner, timestamps
- **Schema Definition**: versioned column definitions with soft-delete, masking rules
- **Batch Metadata**: ingestion frequency, batch dates, per-batch row counts
- **Statistics**: row count, size, null counts, duplicates
- **Access Control**: role assignments (admin/contributor/viewer)
- **Lineage**: ETL job history, transformations applied
- **Audit Trail**: All access and modification events

### Version Control
- Each metadata update increments version number
- Previous versions stored for rollback capability
- Version history retained for 1 year

---

## Security & Compliance

### Authentication & Authorization

#### JWT Token Structure
```json
{
  "sub": "user@company.com",
  "role": "contributor",
  "permissions": ["read:datasets", "write:datasets"],
  "exp": 1699012800,
  "iat": 1699009200
}
```

#### Role Hierarchy

| Role | Permissions |
|------|-------------|
| **Admin** | All operations, see unmasked data, manage permissions, delete datasets |
| **Contributor** | Upload datasets, update own datasets, view with masking, download |
| **Viewer** | View datasets (masked), search, preview (limited rows) |

### Data Masking Enforcement

1. **API Layer**: Apply masking before response serialization
2. **Database Layer**: Store unmasked data, mask during query
3. **Download Layer**: Generate masked export files for non-admins

### Encryption

- **In Transit**: TLS 1.3 for all API communications
- **At Rest**: 
  - S3: AES-256 server-side encryption
  - Cassandra: Transparent data encryption (TDE)
  - Redis: Encrypted RDB snapshots

### Audit Logging

All operations logged with:
- User identity (email)
- Timestamp
- Action type (upload, download, view, update, delete)
- IP address
- Request details
- Response status

**Retention**: 7 years for compliance

### GDPR Compliance

- **Right to Access**: Users can request all data associated with them
- **Right to Erasure**: Complete deletion of user data and datasets
- **Data Portability**: Export user data in machine-readable format
- **Consent Management**: Track data usage consent

---

## Code Examples for Copilot Reference

### Expected API Response Format

#### Success Response
```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "customer_data_2024",
    "status": "ready",
    "message": "Dataset processed successfully"
}
```

#### Error Response
```python
{
    "error": {
        "code": "DATASET_NOT_FOUND",
        "message": "Dataset with id '550e8400-...' not found",
        "details": {
            "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2024-11-02T11:30:00Z"
        }
    }
}
```

### Expected Role Decorator Pattern

```python
from functools import wraps
from fastapi import HTTPException, Depends
from typing import List

def require_role(allowed_roles: List[str]):
    """
    Decorator to enforce role-based access control.
    
    Usage:
        @router.get("/datasets/{dataset_id}")
        @require_role(["admin", "contributor"])
        async def get_dataset(dataset_id: str, current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=Depends(get_current_user), **kwargs):
            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": f"Required role: {', '.join(allowed_roles)}",
                            "details": {
                                "required_role": allowed_roles,
                                "current_role": current_user.role
                            }
                        }
                    }
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
```

### Expected Pagination Pattern

```python
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Reusable pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=100, ge=1, le=1000, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database query"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Return limit for database query"""
        return self.page_size

class PaginatedResponse(BaseModel, Generic[T]):
    """Reusable paginated response wrapper"""
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")
    items: List[T] = Field(description="Items in current page")
    
    @classmethod
    def create(cls, items: List[T], total: int, params: PaginationParams):
        """Factory method to create paginated response"""
        pages = (total + params.page_size - 1) // params.page_size
        return cls(
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=pages,
            items=items
        )
```

### Expected Masking Function Pattern

```python
import re
from typing import Optional

class DataMasker:
    """Centralized data masking utilities"""
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email: john.doe@example.com -> jo***@example.com"""
        if '@' not in email:
            return email
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            return f"{local[0]}***@{domain}"
        return f"{local[:2]}***@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone: +1-555-123-4567 -> ***-***-4567"""
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 4:
            return '***'
        return f"***-***-{digits[-4:]}"
    
    @staticmethod
    def mask_ssn(ssn: str) -> str:
        """Mask SSN: 123-45-6789 -> ***-**-6789"""
        digits = re.sub(r'\D', '', ssn)
        if len(digits) < 4:
            return '***'
        return f"***-**-{digits[-4:]}"
    
    @staticmethod
    def mask_credit_card(cc: str) -> str:
        """Mask credit card: 4532-1234-5678-9010 -> ****-****-****-9010"""
        digits = re.sub(r'\D', '', cc)
        if len(digits) < 4:
            return '****'
        return f"****-****-****-{digits[-4:]}"
    
    @staticmethod
    def mask_value(value: str, mask_rule: str, user_role: str) -> str:
        """
        Apply masking rule based on user role.
        Admins always see unmasked data.
        """
        if user_role == "admin":
            return value
        
        masking_functions = {
            "email": DataMasker.mask_email,
            "partial_email": DataMasker.mask_partial_email,
            "phone": DataMasker.mask_phone,
            "ssn": DataMasker.mask_ssn,
            "credit_card": DataMasker.mask_credit_card,
            "name": DataMasker.mask_name,
            "partial_text": DataMasker.mask_partial_text,
            "ip": DataMasker.mask_ip,
            "redact": DataMasker.mask_redact,
            "hash": DataMasker.mask_hash,
            "numeric_round": DataMasker.mask_numeric_round,
        }
        
        mask_fn = masking_functions.get(mask_rule)
        if mask_fn:
            return mask_fn(value)
        
        # Handle custom regex masking
        if mask_rule.startswith("custom:"):
            pattern = mask_rule[7:]  # Remove 'custom:' prefix
            return re.sub(pattern, '***', value)
        
        return value
```

### Expected Exception Handling Pattern

```python
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from typing import Optional

class DatasetManagerException(Exception):
    """Base exception for dataset manager"""
    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

class DatasetNotFoundException(DatasetManagerException):
    """Raised when dataset is not found"""
    def __init__(self, dataset_id: str):
        super().__init__(
            code="DATASET_NOT_FOUND",
            message=f"Dataset with id '{dataset_id}' not found",
            details={"dataset_id": dataset_id}
        )

class InsufficientPermissionsException(DatasetManagerException):
    """Raised when user lacks required permissions"""
    def __init__(self, required_role: str, current_role: str):
        super().__init__(
            code="INSUFFICIENT_PERMISSIONS",
            message=f"Required role: {required_role}",
            details={
                "required_role": required_role,
                "current_role": current_role
            }
        )

class InvalidFileFormatException(DatasetManagerException):
    """Raised when uploaded file format is invalid"""
    def __init__(self, file_extension: str):
        super().__init__(
            code="INVALID_FILE_FORMAT",
            message=f"Unsupported file format. Allowed: csv, json, parquet",
            details={"file_extension": file_extension}
        )

async def dataset_manager_exception_handler(
    request: Request, 
    exc: DatasetManagerException
) -> JSONResponse:
    """Global exception handler for custom exceptions"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )
```

### Expected Cassandra Client Pattern

```python
from cassandra.cluster import Cluster, Session
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CassandraClient:
    """Singleton Cassandra connection manager"""
    
    _instance: Optional['CassandraClient'] = None
    _session: Optional[Session] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def connect(
        self,
        hosts: List[str],
        port: int,
        keyspace: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Session:
        """Establish connection to Cassandra cluster"""
        if self._session is not None:
            return self._session
        
        try:
            auth_provider = None
            if username and password:
                auth_provider = PlainTextAuthProvider(
                    username=username,
                    password=password
                )
            
            cluster = Cluster(
                contact_points=hosts,
                port=port,
                auth_provider=auth_provider
            )
            
            self._session = cluster.connect(keyspace)
            logger.info(f"Connected to Cassandra keyspace: {keyspace}")
            return self._session
            
        except Exception as e:
            logger.error(f"Failed to connect to Cassandra: {e}")
            raise
    
    def execute(
        self,
        query: str,
        parameters: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Execute CQL query and return results as list of dicts"""
        if self._session is None:
            raise RuntimeError("Cassandra session not initialized")
        
        try:
            statement = SimpleStatement(query)
            rows = self._session.execute(statement, parameters)
            return [dict(row._asdict()) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def close(self):
        """Close Cassandra connection"""
        if self._session:
            self._session.cluster.shutdown()
            self._session = None
            logger.info("Cassandra connection closed")
```

---

## Project Structure

```
dataset-manager/                          # Backend (Python/FastAPI)
├── app/
│   ├── main.py                           # Application entry & middleware
│   ├── auth_utils.py                     # Auth & JWT utilities
│   ├── cassandra_client.py               # Database singleton
│   ├── api/                              # Endpoint handlers
│   │   ├── auth.py, datasets.py, rows.py, permissions.py
│   ├── core/                             # Config, exceptions, masking engine
│   ├── services/
│   │   ├── dataset_service.py            # Dataset lifecycle (delegates to Schema/Batch)
│   │   ├── schema_service.py             # Versioned schema CRUD & evolution
│   │   ├── batch_service.py              # Batch lifecycle management
│   │   ├── permission_service.py         # RBAC enforcement
│   │   └── pagination_cache.py           # Redis pagination cache
│   ├── integrations/                     # Kafka, Redis, S3, Storage Factory
│   └── monitoring/                       # Prometheus & Grafana
├── airflow/                              # ETL DAGs
├── scripts/
│   ├── init_cassandra.py                 # DDL init (incl. batch/schema tables)
│   └── migrate_schema_v3.py             # Migration to versioned schema
├── tests/                                # Unit, Integration, Benchmarks
└── docker-compose.yml                    # Multi-service orchestration

frontend/                                 # Frontend (Vite/React/TS)
├── src/
│   ├── api/                              # Axios client & API definitions
│   ├── components/                       # Layout & Common components
│   ├── pages/                            # Auth, Datasets, Admin pages
│   ├── store/                            # Redux Toolkit slices
│   ├── theme/                            # MUI v7 styling
│   └── types/                            # TypeScript interfaces
├── package.json
└── tsconfig.json
```

---

## Implementation Priorities

### Phase 1: Core Infrastructure (Weeks 1-2) [COMPLETED]
**Goal**: Set up foundational backend infrastructure

#### Tasks
1. **Project Setup**
   - Initialize Python project with Poetry/pip
   - Set up FastAPI application structure
   - Configure logging and environment variables
   - Create Docker Compose for local development

2. **Database Setup**
   - Install and configure Cassandra locally
   - Create keyspace and initial tables
   - Implement Cassandra client with connection pooling
   - Set up Redis for caching

3. **Authentication System**
   - Implement JWT token generation and validation
   - Create user authentication endpoints (login, register)
   - Build RBAC decorator system
   - Add role-based middleware

4. **Basic API Endpoints**
   - Implement health check endpoint
   - Create basic error handling
   - Add request/response logging middleware
   - Set up CORS configuration

**Deliverables**:
- [x] FastAPI app running locally
- [x] Cassandra connected and schema initialized
- [x] JWT authentication working
- [x] Health check endpoint responding

---

### Phase 2: Dataset Management (Weeks 3-4) [COMPLETED]
**Goal**: Implement core dataset upload and metadata management

#### Tasks
1. **File Upload**
   - Implement multipart file upload endpoint
   - Validate file format (CSV, JSON, Parquet)
   - Store files in local storage (later migrate to S3)
   - Create dataset metadata record

2. **Metadata Management**
   - Build dataset CRUD endpoints
   - Implement schema extraction from uploaded files
   - Store dataset statistics (row count, size, etc.)
   - Add pagination to dataset listing

3. **Permission System**
   - Implement dataset permission model
   - Create endpoints to manage dataset permissions
   - Enforce permission checks in dataset endpoints
   - Add owner/admin/contributor/viewer roles

4. **Search & Discovery**
   - Implement search by name, description, tags
   - Add filtering by owner, visibility, tags
   - Implement sorting options
   - Optimize search queries with caching

**Deliverables**:
- [x] Upload dataset endpoint working
- [x] List/search datasets with pagination
- [x] Get dataset metadata endpoint
- [x] Update/delete dataset endpoints with permission checks

---

### Phase 3: Data Access & Masking (Weeks 5-6) [COMPLETED]
**Goal**: Enable data querying with role-based masking

#### Tasks
1. **Data Storage**
   - Implement chunked row storage in Cassandra
   - Create row insertion logic during upload
   - Optimize partitioning for query performance
   - Add row count tracking

2. **Data Masking**
   - Build masking engine with built-in rules
   - Implement email, phone, SSN masking
   - Add custom regex masking support
   - Create masking configuration per dataset

3. **Row Query Endpoint**
   - Implement paginated row query
   - Add column filtering support
   - Apply masking based on user role
   - Optimize query performance with indexes

4. **Data Export**
   - Implement dataset download endpoint
   - Support CSV, JSON, Parquet export formats
   - Apply masking during export
   - Stream large files efficiently

**Deliverables**:
- [x] Get rows endpoint with pagination and masking
- [x] Download dataset with format conversion
- [x] Masking rules applied correctly per role
- [x] Performance tested with 1M+ row datasets

---

### Phase 4: ETL Pipeline (Weeks 7-8) [COMPLETED]
**Goal**: Build automated ETL for dataset processing

#### Tasks
1. **ETL Framework**
   - Set up Apache Airflow locally
   - Create DAG templates for dataset processing
   - Implement ETL job tracking in database
   - Add job status endpoints

2. **Validation Stage**
   - Implement schema validation
   - Add data quality checks (null counts, duplicates)
   - Validate data types and constraints
   - Log validation errors

3. **Transformation Stage**
   - Build data type conversion logic
   - Implement null handling strategies
   - Add deduplication logic
   - Create data normalization utilities

4. **Loading Stage**
   - Implement batch row insertion to Cassandra
   - Optimize chunk size for performance
   - Update metadata after successful load
   - Handle partial failures with rollback

**Deliverables**:
- [x] Airflow DAG triggered on dataset upload
- [x] Validation, transformation, loading stages complete
- [x] ETL job status tracked and queryable
- [x] Error handling and retry logic implemented

---

### Phase 5: Middleware & Messaging (Weeks 9-10) [COMPLETED]
**Goal**: Add async processing with Kafka and middleware

#### Tasks
1. **Kafka Setup**
   - Install and configure Kafka locally
   - Create topics for dataset events
   - Implement Kafka producer for upload events
   - Build Kafka consumer for ETL triggers

2. **Async Processing**
   - Refactor upload to publish Kafka event
   - Consume events to trigger Airflow DAGs
   - Implement job status updates via Kafka
   - Add retry logic for failed events

3. **Rate Limiting**
   - Implement rate limiting middleware
   - Configure limits per endpoint
   - Add rate limit headers in responses
   - Store rate limit data in Redis

4. **Audit Logging**
   - Implement audit log middleware
   - Log all dataset access events
   - Store audit logs in Cassandra
   - Create audit log query endpoints

**Deliverables**:
- [x] Kafka integrated for async processing
- [x] Upload events trigger ETL via Kafka
- [x] Rate limiting active on all endpoints
- [x] Audit logs captured and queryable

---

### Phase 6: Cloud Storage & Scalability (Weeks 11-12) [COMPLETED]
**Goal**: Migrate to cloud storage and optimize for scale

#### Tasks
1. **S3/GCS Integration**
   - Implement S3 storage service
   - Migrate file upload to S3
   - Update ETL to read from S3
   - Add S3 presigned URLs for downloads

2. **Caching Optimization**
   - Implement Redis caching for metadata
   - Cache search results with TTL
   - Cache user permissions
   - Add cache invalidation logic

3. **Performance Tuning**
   - Optimize Cassandra queries
   - Add database indexes
   - Tune batch sizes for ETL
   - Implement connection pooling

4. **Monitoring & Alerts**
   - Set up Prometheus metrics
   - Create Grafana dashboards
   - Add health check for all services
   - Implement alerting for failures

**Deliverables**:
- [x] Files stored in S3/GCS
- [x] Metadata cached in Redis
- [x] Prometheus metrics exposed
- [x] Grafana dashboards operational

---

### Phase 7: Frontend Development (Weeks 13-16) [COMPLETED]
**Goal**: Build React frontend for dataset management

#### Tasks
1. **Project Setup**
   - Initialize React project with TypeScript
   - Set up Redux Toolkit for state management
   - Configure Axios for API calls
   - Add Material-UI/Ant Design components

2. **Authentication Pages**
   - Build login page
   - Build registration page
   - Implement JWT storage in Redux
   - Add protected route wrapper

3. **Dataset Management Pages**
   - Build dataset listing page with search/filters
   - Create dataset detail page
   - Implement dataset upload form with batch frequency selector
   - Add dataset editing form

4. **Data Viewing Pages**
   - Build data preview table with pagination and batch filtering
   - Add column sorting and filtering
   - Implement masked data display
   - Create download button with format selection

5. **Batch & Schema Management Pages**
   - Build Batches tab with paginated batch table
   - Schema version dropdown for historical schema browsing
   - Dropped-column visual treatment (strikethrough + opacity)
   - Batch info sidebar (frequency, total batches, schema version)
   - Frequency badge on dataset list cards

6. **Admin Pages**
   - Build user management page
   - Create permission management UI
   - Add audit log viewer
   - Implement dataset deletion with confirmation

**Deliverables**:
- [x] React app running locally (Vite + TS + MUI v7)
- [x] Login and registration working with JWT persistence
- [x] Dataset CRUD operations via UI (List, Detail, Upload, Update, Delete)
- [x] Data preview and analytics functional
- [x] Admin pages operational
- [x] Batch management UI (list, delete, paginate)
- [x] Schema versioning UI (history, version selector)
- [x] Upload form with ingestion schedule (frequency + batch date)

---

### Phase 8: Performance & Optimization (Weeks 17-18) [COMPLETED]
**Goal**: Sub-millisecond pagination and high-throughput ingestion

#### Tasks
1. **Per-Dataset Table Architecture**
   - Refactor shared table to dynamic `ds_rows_<uuid>` tables
   - Implement structured column storage

2. **Redis Pagination Cache**
   - Implement `PaginationCacheService`
   - Add automated cache invalidation on data changes

3. **Ingestion Benchmarking**
   - Add large-scale insert benchmarks (1M+ rows)
   - Implement Cassandra BatchStatement optimizations

**Deliverables**:
- [x] Dedicated tables for each dataset
- [x] Cold read latency <2s, Warm read latency <100ms
- [x] Batch inserts achieving 100k rows/sec

---

### Phase 9: Testing & Documentation (Weeks 19-20)
**Goal**: Comprehensive testing and documentation

#### Tasks
1. **Unit Testing**
   - Write tests for all services
   - Test masking functions
   - Test validators and transformers
   - Achieve 80%+ code coverage

2. **Integration Testing**
   - Test all API endpoints
   - Test ETL pipeline end-to-end
   - Test authentication flows
   - Test permission enforcement

3. **E2E Testing**
   - Test complete upload workflow
   - Test search and discovery
   - Test download with masking
   - Test admin operations

4. **Documentation**
   - Write API documentation (OpenAPI/Swagger)
   - Create developer setup guide
   - Write deployment guide
   - Create user documentation

**Deliverables**:
- [/] 80%+ test coverage (Mainly Backend)
- [/] All integration tests passing (Backend)
- [ ] E2E tests automated
- [ ] Complete documentation published

---

### Phase 10: Production Deployment (Weeks 21-22)
**Goal**: Deploy to production environment

#### Tasks
1. **Infrastructure Setup**
   - Set up Kubernetes cluster
   - Deploy Cassandra cluster (3+ nodes)
   - Deploy Redis cluster
   - Set up Kafka cluster

2. **Application Deployment**
   - Containerize all services
   - Create Kubernetes manifests
   - Set up CI/CD pipeline (GitHub Actions)
   - Deploy backend services

3. **Security Hardening**
   - Enable TLS/SSL
   - Configure firewall rules
   - Set up secrets management (Vault)
   - Enable audit logging

4. **Monitoring & Operations**
   - Deploy Prometheus and Grafana
   - Set up alerting (PagerDuty/Slack)
   - Configure log aggregation (ELK/Loki)
   - Create runbooks for operations

**Deliverables**:
- [ ] Production environment live
- [ ] All services deployed and healthy
- [ ] Monitoring and alerting active
- [ ] CI/CD pipeline operational

---

## Testing Requirements

### Unit Tests
Test all business logic in isolation with mocked dependencies.

**Coverage Requirements**: Minimum 80% overall, 90% for critical paths

**Example Test Structure**:
```python
import pytest
from app.core.masking import DataMasker

class TestDataMasker:
    """Unit tests for data masking functions"""
    
    def test_mask_email_standard(self):
        """Test email masking with standard email"""
        result = DataMasker.mask_email("john.doe@example.com")
        assert result == "jo***@example.com"
    
    def test_mask_email_short_local(self):
        """Test email masking with short local part"""
        result = DataMasker.mask_email("ab@example.com")
        assert result == "a***@example.com"
    
    def test_mask_phone_with_country_code(self):
        """Test phone masking with country code"""
        result = DataMasker.mask_phone("+1-555-123-4567")
        assert result == "***-***-4567"
    
    @pytest.mark.parametrize("role,expected", [
        ("admin", "john.doe@example.com"),
        ("contributor", "jo***@example.com"),
        ("viewer", "jo***@example.com"),
    ])
    def test_mask_value_by_role(self, role, expected):
        """Test masking applied correctly based on role"""
        result = DataMasker.mask_value(
            "john.doe@example.com",
            "email",
            role
        )
        assert result == expected
```

### Integration Tests
Test API endpoints with test database.

**Example Test Structure**:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)

@pytest.fixture
def auth_headers():
    """Authentication headers for different roles"""
    return {
        "admin": {"Authorization": "Bearer admin_token"},
        "contributor": {"Authorization": "Bearer contributor_token"},
        "viewer": {"Authorization": "Bearer viewer_token"},
    }

@pytest.mark.asyncio
class TestDatasetEndpoints:
    """Integration tests for dataset endpoints"""
    
    async def test_upload_dataset_success(self, client, auth_headers):
        """Test successful dataset upload as admin"""
        with open("tests/fixtures/test_data.csv", "rb") as f:
            response = client.post(
                "/api/v1/datasets",
                files={"file": ("test.csv", f, "text/csv")},
                data={
                    "name": "test_dataset",
                    "description": "Test dataset",
                    "tags": "test,integration"
                },
                headers=auth_headers["admin"]
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "test_dataset"
        assert data["status"] == "uploading"
    
    async def test_upload_dataset_invalid_format(self, client, auth_headers):
        """Test upload with invalid file format"""
        with open("tests/fixtures/test_data.txt", "rb") as f:
            response = client.post(
                "/api/v1/datasets",
                files={"file": ("test.txt", f, "text/plain")},
                data={"name": "test_dataset"},
                headers=auth_headers["admin"]
            )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "INVALID_FILE_FORMAT"
    
    async def test_get_dataset_metadata(self, client, auth_headers, test_dataset_id):
        """Test retrieving dataset metadata"""
        response = client.get(
            f"/api/v1/datasets/{test_dataset_id}",
            headers=auth_headers["contributor"]
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_dataset_id
        assert "schema" in data
        assert "permissions" in data
    
    async def test_get_rows_with_masking(self, client, auth_headers, test_dataset_id):
        """Test row retrieval with masking applied for non-admin"""
        response = client.get(
            f"/api/v1/datasets/{test_dataset_id}/rows?page=1&page_size=10",
            headers=auth_headers["viewer"]
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert len(data["rows"]) > 0
        
        # Verify masking applied (check for *** pattern)
        first_row = data["rows"][0]
        assert "***" in first_row["email"]  # Email should be masked
    
    async def test_delete_dataset_insufficient_permissions(
        self, client, auth_headers, test_dataset_id
    ):
        """Test deletion fails for non-admin"""
        response = client.delete(
            f"/api/v1/datasets/{test_dataset_id}?confirm=true",
            headers=auth_headers["viewer"]
        )
        
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
```

### E2E Tests
Test complete workflows from upload to download.

**Example Test Structure**:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
import time

@pytest.mark.e2e
class TestFullDatasetWorkflow:
    """End-to-end tests for complete dataset workflows"""
    
    async def test_complete_dataset_lifecycle(self, client, auth_headers):
        """Test full lifecycle: upload -> process -> query -> download -> delete"""
        
        # Step 1: Upload dataset
        with open("tests/fixtures/customer_data.csv", "rb") as f:
            upload_response = client.post(
                "/api/v1/datasets",
                files={"file": ("customer_data.csv", f, "text/csv")},
                data={
                    "name": "e2e_test_dataset",
                    "description": "E2E test dataset",
                    "tags": "test,e2e,customers",
                    "is_public": "false"
                },
                headers=auth_headers["admin"]
            )
        
        assert upload_response.status_code == 201
        dataset_id = upload_response.json()["id"]
        job_id = upload_response.json()["job_id"]
        
        # Step 2: Wait for ETL job to complete (poll status)
        max_wait = 60  # seconds
        start_time = time.time()
        job_status = None
        
        while time.time() - start_time < max_wait:
            status_response = client.get(
                f"/api/v1/datasets/{dataset_id}/jobs/{job_id}",
                headers=auth_headers["admin"]
            )
            job_status = status_response.json()["status"]
            
            if job_status in ["completed", "failed"]:
                break
            
            time.sleep(2)
        
        assert job_status == "completed", "ETL job did not complete successfully"
        
        # Step 3: Query dataset metadata
        metadata_response = client.get(
            f"/api/v1/datasets/{dataset_id}",
            headers=auth_headers["admin"]
        )
        
        assert metadata_response.status_code == 200
        metadata = metadata_response.json()
        assert metadata["status"] == "ready"
        assert metadata["row_count"] > 0
        
        # Step 4: Query rows with pagination
        rows_response = client.get(
            f"/api/v1/datasets/{dataset_id}/rows?page=1&page_size=100",
            headers=auth_headers["contributor"]
        )
        
        assert rows_response.status_code == 200
        rows_data = rows_response.json()
        assert len(rows_data["rows"]) > 0
        assert rows_data["total"] == metadata["row_count"]
        
        # Step 5: Download dataset
        download_response = client.get(
            f"/api/v1/datasets/{dataset_id}/download?format=csv",
            headers=auth_headers["contributor"]
        )
        
        assert download_response.status_code == 200
        assert "Content-Disposition" in download_response.headers
        
        # Step 6: Update metadata
        update_response = client.patch(
            f"/api/v1/datasets/{dataset_id}/meta",
            json={
                "description": "Updated description for E2E test",
                "tags": ["test", "e2e", "updated"]
            },
            headers=auth_headers["admin"]
        )
        
        assert update_response.status_code == 200
        
        # Step 7: Delete dataset
        delete_response = client.delete(
            f"/api/v1/datasets/{dataset_id}?confirm=true",
            headers=auth_headers["admin"]
        )
        
        assert delete_response.status_code == 200
        
        # Step 8: Verify deletion
        verify_response = client.get(
            f"/api/v1/datasets/{dataset_id}",
            headers=auth_headers["admin"]
        )
        
        assert verify_response.status_code == 404
```

### Test Data Fixtures

Create test fixtures in `tests/fixtures/`:
- **test_data.csv**: Small CSV file (100 rows) with sample data
- **large_dataset.csv**: Large CSV file (1M rows) for performance testing
- **customer_data.csv**: Realistic customer data with PII for masking tests
- **invalid_data.csv**: CSV with data quality issues for validation tests
- **test_data.json**: JSON format test data
- **test_data.parquet**: Parquet format test data

---

## Environment Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# ============================================
# Application Settings
# ============================================
APP_NAME=dataset-manager
ENVIRONMENT=development  # development, staging, production
DEBUG=True
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
API_VERSION=v1

# ============================================
# Security Settings
# ============================================
SECRET_KEY=your-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ============================================
# Database - Apache Cassandra
# ============================================
CASSANDRA_HOSTS=localhost,cassandra-node-2,cassandra-node-3
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=dataset_manager
CASSANDRA_REPLICATION_FACTOR=3
CASSANDRA_USERNAME=cassandra
CASSANDRA_PASSWORD=cassandra

# ============================================
# Cache - Redis
# ============================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_TTL_METADATA=3600  # 1 hour in seconds
REDIS_TTL_SEARCH=1800    # 30 minutes

# ============================================
# Message Queue - Apache Kafka
# ============================================
KAFKA_BOOTSTRAP_SERVERS=localhost:9092,kafka-broker-2:9092
KAFKA_TOPIC_DATASET_EVENTS=dataset-events
KAFKA_CONSUMER_GROUP=dataset-consumers
KAFKA_SECURITY_PROTOCOL=PLAINTEXT

# ============================================
# ETL - Apache Airflow
# ============================================
AIRFLOW_API_URL=http://localhost:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
AIRFLOW_DAG_DATASET_UPLOAD=dataset_upload_processing

# ============================================
# Object Storage - AWS S3
# ============================================
AWS_REGION=us-east-1
S3_BUCKET_RAW_DATA=dataset-manager-raw
S3_BUCKET_PROCESSED_DATA=dataset-manager-processed
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Or for Google Cloud Storage:
# GCS_BUCKET_RAW_DATA=dataset-manager-raw
# GCS_CREDENTIALS_PATH=/path/to/credentials.json

# ============================================
# API Rate Limiting
# ============================================
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_BURST=20

# ============================================
# Upload Constraints
# ============================================
MAX_UPLOAD_SIZE_MB=5000  # 5GB
ALLOWED_FILE_EXTENSIONS=csv,json,parquet
MAX_ROWS_PER_DATASET=10000000000  # 10 billion

# ============================================
# Monitoring - Prometheus
# ============================================
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# ============================================
# Frontend (Phase 2)
# ============================================
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,https://app.dataset-manager.com
```

### Docker Compose for Local Development

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Apache Cassandra
  cassandra:
    image: cassandra:4.1
    container_name: cassandra
    ports:
      - "9042:9042"
    environment:
      - CASSANDRA_CLUSTER_NAME=dataset-manager-cluster
      - CASSANDRA_DC=dc1
      - CASSANDRA_RACK=rack1
    volumes:
      - cassandra_data:/var/lib/cassandra
    healthcheck:
      test: ["CMD", "cqlsh", "-e", "describe keyspaces"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Apache Kafka (with Zookeeper)
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    container_name: zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    volumes:
      - zookeeper_data:/var/lib/zookeeper

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    volumes:
      - kafka_data:/var/lib/kafka

  # Apache Airflow (simplified single-node)
  airflow:
    image: apache/airflow:2.7.3
    container_name: airflow
    depends_on:
      - postgres
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - AIRFLOW__CORE__FERNET_KEY=your-fernet-key-here
      - AIRFLOW__WEBSERVER__SECRET_KEY=your-secret-key-here
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
    ports:
      - "8080:8080"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - airflow_logs:/opt/airflow/logs
    command: >
      bash -c "airflow db init &&
               airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com &&
               airflow webserver & airflow scheduler"

  # PostgreSQL (for Airflow metadata)
  postgres:
    image: postgres:15
    container_name: postgres
    environment:
      - POSTGRES_USER=airflow
      - POSTGRES_PASSWORD=airflow
      - POSTGRES_DB=airflow
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # FastAPI Backend
  backend:
    build: .
    container_name: backend
    depends_on:
      - cassandra
      - redis
      - kafka
    ports:
      - "8000:8000"
    environment:
      - CASSANDRA_HOSTS=cassandra
      - REDIS_HOST=redis
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - AIRFLOW_API_URL=http://airflow:8080
    volumes:
      - ./app:/app/app
      - ./tests:/app/tests
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  cassandra_data:
  redis_data:
  zookeeper_data:
  kafka_data:
  airflow_logs:
  postgres_data:
```

---

## Dependencies

### Backend Dependencies (`requirements.txt`)

```
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0

# Database
cassandra-driver==3.28.0
redis==5.0.1

# Message Queue
kafka-python==2.0.2

# Authentication & Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
cryptography==41.0.7

# Data Processing
pandas==2.1.3
pyspark==3.5.0
pyarrow==14.0.1  # For Parquet support
openpyxl==3.1.2  # For Excel support (optional)

# ETL & Orchestration
apache-airflow==2.7.3
apache-airflow-providers-apache-spark==4.3.0

# Cloud Storage
boto3==1.29.7  # AWS S3
google-cloud-storage==2.10.0  # Google Cloud Storage (optional)

# Utilities
python-dotenv==1.0.0
pyyaml==6.0.1

# Monitoring
prometheus-client==0.19.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
httpx==0.25.2  # For TestClient
faker==20.1.0  # For generating test data

# Development
black==23.12.0  # Code formatter
flake8==6.1.0  # Linter
mypy==1.7.1  # Type checker
```

### Frontend Dependencies (`package.json`)

```json
{
  "name": "dataset-manager-frontend",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "typescript": "^5.3.2",
    "@reduxjs/toolkit": "^1.9.7",
    "react-redux": "^8.1.3",
    "axios": "^1.6.2",
    "@mui/material": "^5.14.19",
    "@mui/icons-material": "^5.14.19",
    "@emotion/react": "^11.11.1",
    "@emotion/styled": "^11.11.0",
    "recharts": "^2.10.3",
    "date-fns": "^2.30.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.42",
    "@types/react-dom": "^18.2.17",
    "@types/node": "^20.10.4",
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.5",
    "eslint": "^8.55.0",
    "prettier": "^3.1.0"
  }
}
```

---

## Good-to-Have Features

These features are not in the initial scope but can be added in future iterations:

### Phase 10+ Enhancements

1. **Advanced Analytics**
   - Dataset usage statistics and analytics
   - Popular datasets leaderboard
   - User activity dashboards
   - Data quality scoring

2. **Collaboration Features**
   - Dataset comments and discussions
   - Dataset versioning with diff visualization
   - Fork/clone datasets
   - Team workspaces

3. **Data Transformation UI**
   - Visual ETL pipeline builder
   - Custom transformation scripts
   - Scheduled data refreshes
   - Data lineage visualization

4. **ML Integration**
   - Auto-generate dataset statistics
   - Data profiling and anomaly detection
   - Automated data quality checks
   - ML model training integration

5. **Advanced Search**
   - Full-text search across dataset content
   - Semantic search using embeddings
   - Similar dataset recommendations
   - Advanced filtering (column types, data ranges)

6. **Notifications & Alerts**
   - Email notifications for dataset updates
   - Slack/Teams integration
   - Webhook support for custom integrations
   - RSS feeds for dataset changes

7. **Data Marketplace**
   - Public dataset marketplace
   - Dataset licensing and pricing
   - Dataset ratings and reviews
   - Featured datasets showcase

8. **Advanced Security**
   - Multi-factor authentication (MFA)
   - Single Sign-On (SSO) integration
   - IP whitelisting
   - Advanced audit logging with anomaly detection

---

## Out of Scope

The following features are explicitly **NOT** included in this project:

1. **Real-time Data Streaming**
   - Live data updates via WebSockets
   - Real-time query results
   - Streaming data ingestion

2. **Frontend UI Implementation** (Phase 1-6)
   - User interface will be developed in Phase 7
   - Initial focus is backend API only

3. **Machine Learning Model Hosting**
   - ML model training infrastructure
   - Model serving endpoints
   - AutoML capabilities

4. **Data Visualization Tools**
   - Chart/graph generation
   - Interactive dashboards
   - Business intelligence features

5. **Multi-tenancy**
   - Organization/tenant isolation
   - Separate databases per tenant
   - Tenant-specific branding

6. **Advanced Workflow Automation**
   - No-code/low-code workflow builder
   - Custom automation scripting
   - Integration with external automation tools

7. **Mobile Applications**
   - iOS/Android native apps
   - Mobile-optimized UI

8. **Data Science Notebooks**
   - Jupyter notebook integration
   - In-browser code execution
   - Collaborative coding environment

---

## Instructions for Developers

### Getting Started

1. **Clone Repository**
   ```bash
   git clone https://github.com/your-org/dataset-manager.git
   cd dataset-manager
   ```

2. **Set Up Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start Services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Initialize Cassandra Schema**
   ```bash
   python scripts/init_cassandra.py
   ```

5. **Run Backend**
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

6. **Run Tests**
   ```bash
   pytest tests/ -v --cov=app
   ```

### GitHub Copilot Usage

- **Use this PRD as authoritative guide** for all backend system code and architecture
- All Copilot completions for infrastructure, models, API, and tests must reflect the above requirements
- **Document assumptions and deviations inline** using standard Python docstrings and Markdown comments
- When in doubt, refer to the code examples provided in this document
- Use type hints throughout for better Copilot suggestions
- Follow the project structure defined above
- Adhere to error handling patterns and exception classes

### Code Standards

- **PEP 8**: Follow Python style guide
- **Type Hints**: Use throughout codebase
- **Docstrings**: Google-style docstrings for all functions/classes
- **Testing**: Write tests for all new features
- **Logging**: Use structured JSON logging
- **Error Handling**: Use custom exception classes
- **Security**: Never commit secrets, use environment variables

### Commit Message Format

```
type(scope): subject

body (optional)

footer (optional)
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Example**:
```
feat(api): add dataset download endpoint

Implement CSV, JSON, Parquet export with role-based masking.
Supports streaming for large files.

Closes #123
```

---

## References

- [GitHub Copilot Documentation](https://docs.github.com/copilot)
- [PRD Template - Spark Fabrik](https://playbook.sparkfabrik.com/guides/product-requirements-template)
- [Crowdbotics PRD-Driven Context](http://crowdbotics.com/posts/blog/how-the-crowdbotics-github-copilot-extension-delivers-more-accurate-code-with-prd-driven-context/)
- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)

---

## Changelog

| Version | Date | Changes | Author |Reviewer|
|---------|------|---------|--------|--------|
| 1.0 | 2025-12-30 | Initial PRD creation with complete specifications | System |Krishna Mohan|
| 2.0 | 2026-02-21 | Added Phase 7-10 features and updated code examples | System |Krishna Mohan|
| 3.0 | 2026-03-01 | Added batch ingestion, schema versioning, batch management endpoints, frontend batch/schema UI | System |Krishna Mohan|

---

**End of Product Requirements Document**
