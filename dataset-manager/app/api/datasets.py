"""
Datasets router — CRUD, schema, and masking endpoints.
"""

import math
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, Form

from app.core.security import get_current_user
from app.core.exceptions import DatasetNotFoundException, InvalidFileFormatException
from app.schemas.common import (
    DatasetResponse,
    DatasetListResponse,
    DatasetMetadataUpdate,
    PaginatedResponse,
)
from app.api.dependencies import dataset_service, permission_service, parse_file_content, logger

router = APIRouter(prefix="/api/v1/datasets", tags=["Datasets"])


@router.post("", response_model=dict)
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
            file_format=file_ext[1:],
            size_bytes=len(content),
            status="ready",
        )

        # Parse and insert rows
        rows = parse_file_content(content, file_ext)
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


@router.get("", response_model=PaginatedResponse[DatasetListResponse])
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
            if (
                ds["is_public"]
                or ds["owner"] == current_user["email"]
                or current_user["role"] == "admin"
            ):
                accessible_datasets.append(DatasetListResponse(**ds))
            else:
                # Check explicit permissions
                permission = permission_service.get_user_permission(
                    ds["id"], current_user["email"]
                )
                if permission:
                    accessible_datasets.append(DatasetListResponse(**ds))

        total_accessible = len(accessible_datasets)
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


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get dataset metadata"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)

        # Check access
        if not permission_service.is_dataset_accessible(
            dataset_id,
            current_user["email"],
            dataset["owner"],
            dataset["is_public"],
            current_user["role"],
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        # Fetch schema
        schema = dataset_service.get_dataset_schema(dataset_id)
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


@router.get("/{dataset_id}/schema", response_model=List[dict])
async def get_dataset_schema(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """Get dataset schema and masking rules"""
    try:
        dataset = dataset_service.get_dataset(dataset_id)
        # Check access
        if not permission_service.is_dataset_accessible(
            dataset_id,
            current_user["email"],
            dataset["owner"],
            dataset["is_public"],
            current_user["role"],
        ):
            raise HTTPException(status_code=403, detail="Access denied")

        schema = dataset_service.get_dataset_schema(dataset_id)
        return schema
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schema")


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


@router.patch("/{dataset_id}/meta", response_model=DatasetResponse)
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
