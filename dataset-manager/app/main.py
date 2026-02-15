"""
FastAPI application entry point for Dataset Manager 
"""

from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Query, Form, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
import logging
import json
from typing import Optional, List
import uuid
from datetime import datetime
import io
from app.utils.log_formatter import JsonFormatter, app_logger   
from app.core.config import settings
from fastapi.middleware.cors import CORSMiddleware



# Import modules
from .auth_utils import User, create_access_token, decode_access_token
from .cassandra_client import CassandraClient
from .core.security import get_current_user, require_role
from .core.exceptions import (
    DatasetNotFoundException,
    InsufficientPermissionsException,
    InvalidFileFormatException,
    DatabaseException,
)
from .schemas.common import (
    DatasetCreate,
    DatasetResponse,
    DatasetListResponse,
    DatasetMetadataUpdate,
    PaginatedResponse,
    AuthResponse,
    RowsResponse,
    PermissionResponse,
    ErrorResponse,
    RegisterRequest,
    LoginRequest,
    UserBase,
)
from .services.dataset_service import DatasetService
from .services.permission_service import PermissionService

# Configure logging
logger = app_logger
from scripts.init_cassandra import initialize_schema

# Create FastAPI app
app = FastAPI(title="Dataset Manager API", version="1.0.0")

@app.on_event("startup")
def startup_event():
    # Initialize database schema
    initialize_schema()

# Initialize services
dataset_service = DatasetService()
permission_service = PermissionService()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": str(exc.status_code),
                "message": str(exc.detail),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )
db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
origins = ["*"]
    

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================


@app.get("/health")
def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    cassandra_status = "unhealthy"
    try:
        client = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        client.execute("SELECT now() FROM system.local;")
        cassandra_status = "healthy"
    except Exception as e:
        logger.error(f"Cassandra health check failed: {e}")

    return {
        "status": "healthy",
        "cassandra": cassandra_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================


@app.post("/api/v1/auth/register", response_model=AuthResponse)
def register(user_data: RegisterRequest):
    """Register new user"""
    try:
        email = user_data.email
        password = user_data.password
        full_name = user_data.full_name
        role = user_data.role or "viewer"

        # Check if user exists
        query = "SELECT email FROM dataset_manager.users WHERE email = %s LIMIT 1;"
        result = db.execute(query, (email,))
        if result.one():
            raise HTTPException(status_code=400, detail="User already exists")

        # Create user with UUID
        user_id = uuid.uuid4()
        hashed_password = User.hash_password(password)
        is_active = True
        now = datetime.utcnow()

        prepared = db.prepare("""INSERT INTO dataset_manager.users 
                        (user_id, email, password_hash, full_name, role, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """)

        db.execute(prepared, (user_id, email, hashed_password, full_name, role, is_active, now, now))

        # Create JWT token for immediate login
        access_token = create_access_token({"sub": email, "role": role})

        logger.info(f"User {email} registered successfully")
        return AuthResponse(
            token=access_token,
            access_token=access_token,
            user=UserBase(email=email, full_name=full_name, role=role),
            message="User registered successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(login_data: LoginRequest):
    """Login user and return JWT token"""
    try:
        email = login_data.email
        password = login_data.password

        # Get user
        query = "SELECT email, password_hash, role FROM dataset_manager.users WHERE email = %s LIMIT 1;"
        result = db.execute(query, (email,))
        row = result.one()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify password
        user = User(
            email=row.email,
            hashed_password=row.password_hash,
            role=row.role,
        )
        if not user.verify_password(password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create JWT token
        access_token = create_access_token({"sub": user.email, "role": user.role})

        logger.info(f"User {email} logged in successfully")
        return AuthResponse(
            token=access_token,
            access_token=access_token,
            user=UserBase(email=user.email, full_name=user.full_name, role=user.role)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.get("/api/v1/auth/me", response_model=dict)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {"email": current_user["email"], "role": current_user["role"]}


# ============================================================================
# DATASET ENDPOINTS
# ============================================================================


@app.post("/api/v1/datasets", response_model=dict)
async def upload_dataset(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a new dataset"""
    try:
        # Validate file format
        allowed_formats = [".csv", ".json", ".parquet"]
        file_ext = f".{file.filename.split('.')[-1].lower()}"
        if file_ext not in allowed_formats:
            raise InvalidFileFormatException(
                f"File format must be one of: {', '.join(allowed_formats)}"
            )

        # Read file content
        content = await file.read()

        # Create dataset metadata
        dataset_id = dataset_service.create_dataset(
            name=name,
            owner=current_user["email"],
            description=description,
            tags=tags,
            is_public=is_public,
            file_format=file_ext[1:],  # Remove dot
            size_bytes=len(content),
            status="ready",
        )
        
        # Parse and insert rows
        rows = _parse_file_content(content, file_ext)
        row_count = dataset_service.insert_rows(dataset_id, rows)

        logger.info(f"Dataset {dataset_id} uploaded by {current_user['email']}")
        return {
            "id": str(dataset_id),
            "name": name,
            "row_count": row_count,
            "status": "ready",
        }
    except InvalidFileFormatException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


@app.get("/api/v1/datasets", response_model=PaginatedResponse[DatasetListResponse])
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List datasets with pagination"""
    try:
        datasets, total = dataset_service.list_datasets(page, page_size, search)

        # Filter datasets based on permissions
        accessible_datasets = []
        for ds in datasets:
            # Prepare tags (ensure it's a list)
            if isinstance(ds.get("tags"), str):
                ds["tags"] = [t.strip() for t in ds["tags"].split(",") if t.strip()]
            elif ds.get("tags") is None:
                ds["tags"] = []

            # Always include public datasets, owner's datasets, and global admins
            if ds["is_public"] or ds["owner"] == current_user["email"] or current_user["role"] == "admin":
                accessible_datasets.append(DatasetListResponse(**ds))
            else:
                # Check explicit permissions
                permission = permission_service.get_user_permission(
                    ds["id"], current_user["email"]
                )
                if permission:
                    accessible_datasets.append(DatasetListResponse(**ds))

        total_accessible = len(accessible_datasets)
        import math
        total_pages = math.ceil(total_accessible / page_size) if page_size > 0 else 0

        return PaginatedResponse(
            total=total_accessible,
            page=page,
            page_size=page_size,
            pages=total_pages,
            items=accessible_datasets,
        )
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to list datasets")


@app.get("/api/v1/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get dataset metadata"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)

        # Check access
        if not permission_service.is_dataset_accessible(
            dataset_id, current_user["email"], dataset["owner"], dataset["is_public"], current_user["role"]
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        # Fetch schema
        schema = dataset_service.get_dataset_schema(dataset_id)
        dataset["schema"] = schema

        # Optional: Fetch statistics and permissions if needed
        # For now, we use defaults as defined in Pydantic models
        dataset["statistics"] = {}
        dataset["permissions"] = {
            "admins": [dataset["owner"]],
            "contributors": [],
            "viewers": []
        }

        return DatasetResponse(**dataset)
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dataset")


@app.get("/api/v1/datasets/{dataset_id}/schema", response_model=List[dict])
async def get_dataset_schema(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get dataset schema and masking rules"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)
        # Check access
        if not permission_service.is_dataset_accessible(
            dataset_id, current_user["email"], dataset["owner"], dataset["is_public"], current_user["role"]
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        schema = dataset_service.get_dataset_schema(dataset_id)
        return schema
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schema")


@app.patch("/api/v1/datasets/{dataset_id}/schema/{column_name}/masking")
async def update_masking_rule(
    dataset_id: uuid.UUID,
    column_name: str,
    mask_rule: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Update masking rule for a column"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)
        # Check permission (only owner and admins)
        if (
            dataset["owner"] != current_user["email"]
            and current_user["role"] != "admin"
        ):
            raise HTTPException(status_code=403, detail="Permission denied")

        dataset_service.update_masking_rule(dataset_id, column_name, mask_rule)
        return {"message": "Masking rule updated successfully"}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to update masking rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to update masking rule")


@app.patch("/api/v1/datasets/{dataset_id}/meta", response_model=DatasetResponse)
async def update_dataset_metadata(
    dataset_id: uuid.UUID,
    update: DatasetMetadataUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update dataset metadata"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)

        # Check permission (only owner and admins)
        if (
            dataset["owner"] != current_user["email"]
            and current_user["role"] != "admin"
        ):
            raise HTTPException(status_code=403, detail="Permission denied")

        update_data = update.dict(exclude_unset=True)
        updated = dataset_service.update_dataset(dataset_id, **update_data)

        logger.info(f"Dataset {dataset_id} updated by {current_user['email']}")
        return DatasetResponse(**updated)
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to update dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to update dataset")


@app.delete("/api/v1/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: uuid.UUID,
    confirm: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Delete dataset"""
    try:
        if not confirm:
            raise HTTPException(status_code=400, detail="Missing confirm=true")

        dataset = dataset_service.get_dataset(dataset_id)

        # Check permission (only owner and admins)
        if (
            dataset["owner"] != current_user["email"]
            and current_user["role"] != "admin"
        ):
            raise HTTPException(status_code=403, detail="Permission denied")

        dataset_service.delete_dataset(dataset_id)

        logger.info(f"Dataset {dataset_id} deleted by {current_user['email']}")
        return {"id": str(dataset_id), "message": "Dataset deleted successfully"}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete dataset")


# ============================================================================
# ROW/DATA ENDPOINTS
# ============================================================================


@app.get("/api/v1/datasets/{dataset_id}/rows", response_model=RowsResponse)
async def get_dataset_rows(
    dataset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated rows from dataset"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)

        # Check access
        if not permission_service.is_dataset_accessible(
            dataset_id, current_user["email"], dataset["owner"], dataset["is_public"], current_user["role"]
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        rows, total = dataset_service.get_rows(
            dataset_id, page, page_size, current_user["role"]
        )

        return RowsResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=rows,
        )
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to get rows: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rows")


@app.get("/api/v1/datasets/{dataset_id}/download")
async def download_dataset(
    dataset_id: uuid.UUID,
    format: str = Query("csv", regex="^(csv|json|parquet)$"),
    current_user: dict = Depends(get_current_user),
):
    """Download dataset in specified format"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)

        # Check access
        if not permission_service.is_dataset_accessible(
            dataset_id, current_user["email"], dataset["owner"], dataset["is_public"], current_user["role"]
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        file_content = dataset_service.export_dataset(
            dataset_id, format=format, user_role=current_user["role"]
        )

        logger.info(f"Dataset {dataset_id} downloaded by {current_user['email']}")

        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=dataset_{dataset_id}.{format}"
            },
        )
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to download dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to download dataset")


# ============================================================================
# PERMISSION ENDPOINTS
# ============================================================================


@app.get("/api/v1/datasets/{dataset_id}/permissions", response_model=List[dict])
async def get_permissions(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """List all permissions for a dataset"""
    try:
        # Check access (must be owner or admin)
        dataset = dataset_service.get_dataset(dataset_id)
        if dataset["owner"] != current_user["email"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to view permissions")
            
        permissions = permission_service.list_dataset_permissions(dataset_id)
        return permissions
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list permissions")


@app.post("/api/v1/datasets/{dataset_id}/permissions", response_model=dict)
async def grant_permission(
    dataset_id: uuid.UUID,
    user_email: str,
    role: str,
    current_user: dict = Depends(get_current_user),
):
    """Grant permission to user for dataset"""
    try:
        # Check access (must be owner or admin)
        dataset = dataset_service.get_dataset(dataset_id)
        if dataset["owner"] != current_user["email"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to manage permissions")

        permission_service.grant_permission(dataset_id, user_email, role)
        logger.info(f"Permission granted by {current_user['email']} for {user_email}")
        return {"message": "Permission granted successfully"}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to grant permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant permission")


@app.delete("/api/v1/datasets/{dataset_id}/permissions/{user_email}")
async def revoke_permission(
    dataset_id: uuid.UUID,
    user_email: str,
    current_user: dict = Depends(get_current_user),
):
    """Revoke permission from user"""
    try:
        # Check access (must be owner or admin)
        dataset = dataset_service.get_dataset(dataset_id)
        if dataset["owner"] != current_user["email"] and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Not authorized to manage permissions")

        permission_service.revoke_permission(dataset_id, user_email)
        logger.info(f"Permission revoked by {current_user['email']} for {user_email}")
        return {"message": "Permission revoked successfully"}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to revoke permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke permission")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _parse_file_content(content: bytes, file_ext: str) -> List[dict]:
    """Parse file content based on format"""
    import csv
    import pandas as pd

    try:
        if file_ext == ".csv":
            text = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)
        elif file_ext == ".json":
            text = content.decode("utf-8")
            data = json.loads(text)
            return data if isinstance(data, list) else [data]
        elif file_ext == ".parquet":
            # For parquet, use pandas
            df = pd.read_parquet(io.BytesIO(content))
            return df.to_dict("records")
        else:
            raise InvalidFileFormatException(f"Unsupported format: {file_ext}")
    except Exception as e:
        raise InvalidFileFormatException(f"Failed to parse file: {str(e)}")
