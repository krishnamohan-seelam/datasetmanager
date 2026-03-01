"""
Rows router — data retrieval and download endpoints.
"""

import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.core.exceptions import DatasetNotFoundException
from app.schemas.common import RowsResponse
from app.api.dependencies import dataset_service, permission_service, logger

router = APIRouter(prefix="/api/v1/datasets", tags=["Rows & Data"])


@router.get("/{dataset_id}/rows", response_model=RowsResponse)
async def get_dataset_rows(
    dataset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    columns: Optional[str] = Query(None, description="Comma-separated column names to select"),
    batch_id: Optional[uuid.UUID] = Query(None, description="Filter by specific batch"),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated rows from dataset. Optionally filter by batch_id."""
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

        # Parse columns parameter
        column_list = None
        if columns:
            column_list = [c.strip() for c in columns.split(",") if c.strip()]

        rows, total = dataset_service.get_rows(
            dataset_id,
            page,
            page_size,
            current_user["role"],
            columns=column_list,
            batch_id=batch_id,
        )

        pages = (total + page_size - 1) // page_size if total > 0 else 1

        return RowsResponse(
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            items=rows,
        )
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to get rows: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rows")


@router.get("/{dataset_id}/download")
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
            dataset_id,
            current_user["email"],
            dataset["owner"],
            dataset["is_public"],
            current_user["role"],
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
