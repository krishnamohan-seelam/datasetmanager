"""
Rows router — data retrieval and download endpoints.
"""

import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.core.exceptions import translate_domain_exceptions
from app.schemas.common import RowsResponse
from app.services.pagination_cache import PageRequest
from app.api.dependencies import dataset_service, permission_service, logger

router = APIRouter(prefix="/api/v1/datasets", tags=["Rows & Data"])


def _ensure_readable(dataset_id: uuid.UUID, current_user: dict) -> None:
    """Read-accessibility check (owner, public, admin, or explicit grant)."""
    dataset = dataset_service.get_dataset(dataset_id)
    if not permission_service.is_dataset_accessible(
        dataset_id,
        current_user["email"],
        dataset["owner"],
        dataset["is_public"],
        current_user["role"],
    ):
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{dataset_id}/rows", response_model=RowsResponse)
@translate_domain_exceptions
async def get_dataset_rows(
    dataset_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    columns: Optional[str] = Query(None, description="Comma-separated column names to select"),
    batch_id: Optional[uuid.UUID] = Query(None, description="Filter by specific batch"),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated rows from dataset. Optionally filter by batch_id."""
    _ensure_readable(dataset_id, current_user)

    column_list = None
    if columns:
        column_list = tuple(c.strip() for c in columns.split(",") if c.strip()) or None

    rows, total = dataset_service.get_rows(
        PageRequest(
            dataset_id=dataset_id,
            page=page,
            page_size=page_size,
            user_role=current_user["role"],
            columns=column_list,
            batch_id=batch_id,
        )
    )

    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return RowsResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=rows,
    )


@router.get("/{dataset_id}/download")
@translate_domain_exceptions
async def download_dataset(
    dataset_id: uuid.UUID,
    format: str = Query("csv", regex="^(csv|json|parquet)$"),
    current_user: dict = Depends(get_current_user),
):
    """Download dataset in specified format"""
    _ensure_readable(dataset_id, current_user)

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
