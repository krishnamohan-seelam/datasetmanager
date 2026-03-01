"""
Datasets router — CRUD, schema, masking, and batch endpoints.
"""

import math
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, Form

from app.core.security import get_current_user
from app.core.exceptions import DatasetNotFoundException, InvalidFileFormatException
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


# ── Upload ───────────────────────────────────────────────────────────────

@router.post("", response_model=dict)
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
    except InvalidFileFormatException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


# ── List / Get ───────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedResponse[DatasetListResponse])
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List datasets with pagination"""
    try:
        raw_datasets, _ = dataset_service.list_datasets(page=1, page_size=1000, search=search)

        accessible_datasets = []
        for ds in raw_datasets:
            if isinstance(ds.get("tags"), str):
                ds["tags"] = [t.strip() for t in ds["tags"].split(",") if t.strip()]
            elif ds.get("tags") is None:
                ds["tags"] = []

            if (
                ds.get("is_public")
                or ds.get("owner") == current_user["email"]
                or current_user.get("role") == "admin"
            ):
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
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to list datasets")


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get dataset metadata"""
    try:
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
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dataset")


# ── Schema endpoints ─────────────────────────────────────────────────────

@router.get("/{dataset_id}/schema", response_model=List[dict])
async def get_dataset_schema(
    dataset_id: uuid.UUID,
    version: Optional[int] = Query(None, description="Schema version (latest if omitted)"),
    current_user: dict = Depends(get_current_user),
):
    """Get dataset schema columns. Optionally specify a version."""
    try:
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
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schema")


@router.get("/{dataset_id}/schema/history", response_model=List[dict])
async def get_schema_history(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get schema version history for a dataset."""
    try:
        dataset = dataset_service.get_dataset(dataset_id)
        if not permission_service.is_dataset_accessible(
            dataset_id,
            current_user["email"],
            dataset["owner"],
            dataset["is_public"],
            current_user["role"],
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        history = schema_service.get_schema_history(dataset_id)
        return history
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to get schema history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schema history")


@router.patch("/{dataset_id}/schema/{column_name}/masking")
async def update_masking_rule(
    dataset_id: uuid.UUID,
    column_name: str,
    mask_rule: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Update masking rule for a column"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)
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


# ── Batch endpoints ──────────────────────────────────────────────────────

@router.get("/{dataset_id}/batches", response_model=PaginatedResponse[BatchResponse])
async def list_batches(
    dataset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List all batches for a dataset"""
    try:
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
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to list batches: {e}")
        raise HTTPException(status_code=500, detail="Failed to list batches")


@router.delete("/{dataset_id}/batches/{batch_id}")
async def delete_batch(
    dataset_id: uuid.UUID,
    batch_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Delete a specific batch from a dataset"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)
        if (
            dataset["owner"] != current_user["email"]
            and current_user["role"] != "admin"
        ):
            raise HTTPException(status_code=403, detail="Permission denied")

        deleted = batch_service.delete_batch(dataset_id, batch_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Batch not found")

        return {"message": "Batch deleted successfully", "batch_id": str(batch_id)}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to delete batch: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete batch")


# ── Metadata update & delete ─────────────────────────────────────────────

@router.patch("/{dataset_id}/meta", response_model=DatasetResponse)
async def update_dataset_metadata(
    dataset_id: uuid.UUID,
    update: DatasetMetadataUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update dataset metadata"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)

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


@router.delete("/{dataset_id}")
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
