"""
Pydantic models for request/response validation
"""

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List, Optional, Any, Dict
from datetime import datetime
from uuid import UUID

T = TypeVar("T")


# Pagination
class PaginationParams(BaseModel):
    """Reusable pagination parameters"""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=100, ge=1, le=1000, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Reusable paginated response wrapper"""

    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Items per page")
    pages: int = Field(default=0, description="Total number of pages")
    items: List[T] = Field(description="Items in current page")


# User
class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: str = "viewer"


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    created_at: datetime
    is_active: bool


# Dataset
class DatasetBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[str] = None
    is_public: bool = False


class DatasetCreate(DatasetBase):
    masking_config: Optional[Dict[str, str]] = None


class DatasetMetadataUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    masking_config: Optional[Dict[str, str]] = None


class DatasetColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True
    masked: bool = False
    mask_rule: Optional[str] = None
    position: int = 0


class DatasetStatistics(BaseModel):
    total_rows: int = 0
    total_columns: int = 0
    null_count: int = 0
    duplicate_rows: int = 0


class DatasetPermissions(BaseModel):
    admins: List[str] = []
    contributors: List[str] = []
    viewers: List[str] = []


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = ""
    owner: str
    created_at: datetime
    updated_at: datetime
    row_count: int
    size_bytes: int = 0
    file_format: str = "csv"
    status: str = "ready"
    storage_path: Optional[str] = ""
    version: int = 1
    tags: List[str] = []
    is_public: bool = False
    schema: Optional[List[DatasetColumn]] = None
    statistics: Optional[DatasetStatistics] = None
    permissions: Optional[DatasetPermissions] = None


class DatasetListResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = ""
    owner: str
    created_at: datetime
    row_count: int
    size_bytes: int = 0
    file_format: str = "csv"
    is_public: bool
    status: str = "ready"
    tags: List[str] = []


# Rows/Data
class RowsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Dict[str, Any]]


class RowsQuery(BaseModel):
    page: int = 1
    page_size: int = 100
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[str] = None
    masked: bool = True


# Permissions
class PermissionBase(BaseModel):
    user_email: str
    role: str = Field(default="viewer", pattern="^(admin|contributor|viewer)$")


class PermissionResponse(PermissionBase):
    dataset_id: UUID
    granted_at: datetime


# Auth
class AuthResponse(BaseModel):
    token: str
    access_token: str  # For OAuth2 compatibility
    token_type: str = "bearer"
    user: UserBase
    message: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "viewer"


# ETL Job
class ETLJobResponse(BaseModel):
    job_id: UUID
    dataset_id: UUID
    status: str
    progress: float = 0.0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# Standard error response
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
