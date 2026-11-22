"""
Datasets router — CRUD, schema, masking, and batch endpoints.
"""

import math
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, Form

from app.core.config import settings
from app.core.security import get_current_user, require_owner_or_admin
from app.core.exceptions import (
    InvalidFileFormatException,
    translate_domain_exceptions,
)
from app.schemas.common import (
    DatasetResponse,
    DatasetListResponse,
    DatasetMetadataUpdate,
    PaginatedResponse,
    BatchResponse,
    SchemaVersionResponse,
)
from app.api.dependencies import (
    dataset_service,
    permission_service,
    schema_service,
    batch_service,
    parse_file_content,
    logger,
)

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])

# Non-admin dataset listing can't push permission filtering into Cassandra
# (no index on accessibility), so it still scans a bounded window and
# filters in Python. Raised well past the old hardcoded 1000 so the common
# case stops silently truncating; a table larger than this per non-admin
# search is a known remaining limitation, not a silent bug — see
# docs/code_review1_fix_spec.md Module 4.
_NON_ADMIN_LIST_SCAN_LIMIT = 5000


# ── Upload ───────────────────────────────────────────────────────────────

@router.post("", response_model=dict)
@translate_domain_exceptions
async def upload_dataset(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    batch_frequency: str = Form("once"),
    batch_date: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a new dataset (or a new batch for an existing dataset)"""
    # Validate file format — filename may be None or lack a dot; check
    # explicitly instead of letting an AttributeError/IndexError fall through
    # to a generic 500.
    allowed_formats = [".csv", ".json", ".parquet"]
    if not file.filename or "." not in file.filename:
        raise InvalidFileFormatException(
            f"File must have an extension; one of: {', '.join(allowed_formats)}"
        )
    file_ext = f".{file.filename.rsplit('.', 1)[-1].lower()}"
    if file_ext not in allowed_formats:
        raise InvalidFileFormatException(
            f"File format must be one of: {', '.join(allowed_formats)}"
        )

    # Reject oversized uploads before reading the whole file into memory.
    # UploadFile.size is populated by Starlette from the multipart stream as
    # it's read; file.file also exposes the underlying SpooledTemporaryFile
    # for a belt-and-suspenders check.
    if file.size is not None and file.size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise InvalidFileFormatException(
            f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_BYTES} bytes"
        )

    # Read file content
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise InvalidFileFormatException(
            f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_BYTES} bytes"
        )

    # Parse batch_date
    parsed_batch_date = None
    if batch_date:
        try:
            parsed_batch_date = datetime.fromisoformat(batch_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid batch_date format. Use ISO 8601.")

    # Create dataset metadata
    dataset_id = dataset_service.create_dataset(
        name=name,
        owner=current_user["email"],
        description=description,
        tags=tags,
        is_public=is_public,
        file_format=file_ext[1:],
        size_bytes=len(content),
        status="ready",
        batch_frequency=batch_frequency,
    )

    # Parse and insert rows (creates batch + evolves schema automatically)
    rows = parse_file_content(content, file_ext)
    row_count = dataset_service.insert_rows(
        dataset_id,
        rows,
        batch_date=parsed_batch_date,
        uploaded_by=current_user["email"],
        file_format=file_ext[1:],
        size_bytes=len(content),
    )

    logger.info(f"Dataset {dataset_id} uploaded by {current_user['email']}")
    return {
        "id": str(dataset_id),
        "name": name,
        "row_count": row_count,
        "status": "ready",
        "batch_frequency": batch_frequency,
    }


# ── List / Get ───────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[DatasetListResponse])
@translate_domain_exceptions
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List datasets with pagination.

    Admins (and the public/global-visibility case) are paged directly by
    Cassandra via dataset_service — real page/page_size, not a hardcoded
    page=1,page_size=1000 that silently truncated beyond 1000 datasets
    (Mandatory #10). Non-admins still need per-row permission checks that
    Cassandra can't push down without a secondary index, so that path scans
    a bounded (but much larger, and documented) window and paginates in
    Python — see _NON_ADMIN_LIST_SCAN_LIMIT above.
    """
    if current_user.get("role") == "admin":
        raw_datasets, total = dataset_service.list_datasets(
            page=page, page_size=page_size, search=search
        )
        items = [DatasetListResponse(**ds) for ds in raw_datasets]
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return PaginatedResponse(
            total=total, page=page, page_size=page_size, pages=total_pages, items=items
        )

    raw_datasets, _ = dataset_service.list_datasets(
        page=1, page_size=_NON_ADMIN_LIST_SCAN_LIMIT, search=search
    )

    accessible_datasets = []
    for ds in raw_datasets:
        if ds.get("is_public") or ds.get("owner") == current_user["email"]:
            accessible_datasets.append(DatasetListResponse(**ds))
        else:
            permission = permission_service.get_user_permission(
                ds["id"], current_user["email"]
            )
            if permission:
                accessible_datasets.append(DatasetListResponse(**ds))

    total_accessible = len(accessible_datasets)
    offset = (page - 1) * page_size
    paginated_items = accessible_datasets[offset : offset + page_size]
    total_pages = math.ceil(total_accessible / page_size) if page_size > 0 else 0

    return PaginatedResponse(
        total=total_accessible,
        page=page,
        page_size=page_size,
        pages=total_pages,
        items=paginated_items,
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
@translate_domain_exceptions
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get dataset metadata"""
    dataset = dataset_service.get_dataset(dataset_id)

    if not permission_service.is_dataset_accessible(
        dataset_id,
        current_user["email"],
        dataset["owner"],
        dataset["is_public"],
        current_user["role"],
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    # Fetch schema (tolerant of old table format)
    try:
        schema = schema_service.get_schema(dataset_id)
    except Exception:
        schema = []
    dataset["schema"] = schema

    dataset["statistics"] = {}
    dataset["permissions"] = {
        "admins": [dataset["owner"]],
        "contributors": [],
        "viewers": [],
    }

    return DatasetResponse(**dataset)


# ── Schema endpoints ─────────────────────────────────────────────────────

@router.get("/{dataset_id}/schema", response_model=List[dict])
@translate_domain_exceptions
async def get_dataset_schema(
    dataset_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Schema version (latest if omitted)"),
    current_user: dict = Depends(get_current_user),
):
    """Get dataset schema columns. Optionally specify a version."""
    dataset = dataset_service.get_dataset(dataset_id)
    if not permission_service.is_dataset_accessible(
        dataset_id,
        current_user["email"],
        dataset["owner"],
        dataset["is_public"],
        current_user["role"],
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        schema = schema_service.get_schema(dataset_id, version=version)
    except Exception:
        schema = []
    return schema


@router.get("/{dataset_id}/schema/history", response_model=List[dict])
@translate_domain_exceptions
async def get_schema_history(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get schema version history for a dataset."""
    dataset = dataset_service.get_dataset(dataset_id)
    if not permission_service.is_dataset_accessible(
        dataset_id,
        current_user["email"],
        dataset["owner"],
        dataset["is_public"],
        current_user["role"],
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    return schema_service.get_schema_history(dataset_id)


@router.patch("/{dataset_id}/schema/{column_name}/masking")
@translate_domain_exceptions
async def update_masking_rule(
    column_name: str,
    mask_rule: Optional[str] = Query(None),
    ctx: dict = Depends(require_owner_or_admin),
):
    """Update masking rule for a column (owner or admin only)"""
    dataset_service.update_masking_rule(ctx["dataset"]["id"], column_name, mask_rule)
    return {"message": "Masking rule updated successfully"}


# ── Batch endpoints ──────────────────────────────────────────────────────

@router.get("/{dataset_id}/batches", response_model=PaginatedResponse[BatchResponse])
@translate_domain_exceptions
async def list_batches(
    dataset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List all batches for a dataset"""
    dataset = dataset_service.get_dataset(dataset_id)
    if not permission_service.is_dataset_accessible(
        dataset_id,
        current_user["email"],
        dataset["owner"],
        dataset["is_public"],
        current_user["role"],
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    batches, total = batch_service.list_batches(dataset_id, page, page_size)
    total_pages = math.ceil(total / page_size) if page_size > 0 else 0

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
        items=[BatchResponse(**b) for b in batches],
    )


@router.delete("/{dataset_id}/batches/{batch_id}")
@translate_domain_exceptions
async def delete_batch(
    batch_id: uuid.UUID,
    ctx: dict = Depends(require_owner_or_admin),
):
    """Delete a specific batch from a dataset (owner or admin only)"""
    deleted = batch_service.delete_batch(ctx["dataset"]["id"], batch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Batch not found")

    return {"message": "Batch deleted successfully", "batch_id": str(batch_id)}


# ── Metadata update & delete ─────────────────────────────────────────────

@router.patch("/{dataset_id}/meta", response_model=DatasetResponse)
@translate_domain_exceptions
async def update_dataset_metadata(
    update: DatasetMetadataUpdate,
    ctx: dict = Depends(require_owner_or_admin),
):
    """Update dataset metadata (owner or admin only)"""
    dataset_id = ctx["dataset"]["id"]
    update_data = update.dict(exclude_unset=True)
    updated = dataset_service.update_dataset(dataset_id, **update_data)

    logger.info(f"Dataset {dataset_id} updated by {ctx['current_user']['email']}")
    return DatasetResponse(**updated)


@router.delete("/{dataset_id}")
@translate_domain_exceptions
async def delete_dataset(
    confirm: bool = False,
    ctx: dict = Depends(require_owner_or_admin),
):
    """Delete dataset (owner or admin only)"""
    if not confirm:
        raise HTTPException(status_code=400, detail="Missing confirm=true")

    dataset_id = ctx["dataset"]["id"]
    dataset_service.delete_dataset(dataset_id)

    logger.info(f"Dataset {dataset_id} deleted by {ctx['current_user']['email']}")
    return {"id": str(dataset_id), "message": "Dataset deleted successfully"}
