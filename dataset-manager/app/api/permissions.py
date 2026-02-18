"""
Permissions router — grant, revoke, and list dataset permissions.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.core.exceptions import DatasetNotFoundException
from app.api.dependencies import dataset_service, permission_service, logger

router = APIRouter(prefix="/api/v1/datasets", tags=["Permissions"])


@router.get("/{dataset_id}/permissions", response_model=List[dict])
async def get_permissions(
    dataset_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
):
    """List all permissions for a dataset"""
    try:
        # Check access (must be owner or admin)
        dataset = dataset_service.get_dataset(dataset_id)
        if dataset["owner"] != current_user["email"] and current_user["role"] != "admin":
            raise HTTPException(
                status_code=403, detail="Not authorized to view permissions"
            )

        permissions = permission_service.list_dataset_permissions(dataset_id)
        return permissions
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list permissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list permissions")


@router.post("/{dataset_id}/permissions", response_model=dict)
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
            raise HTTPException(
                status_code=403, detail="Not authorized to manage permissions"
            )

        permission_service.grant_permission(dataset_id, user_email, role)
        logger.info(f"Permission granted by {current_user['email']} for {user_email}")
        return {"message": "Permission granted successfully"}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to grant permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to grant permission")


@router.delete("/{dataset_id}/permissions/{user_email}")
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
            raise HTTPException(
                status_code=403, detail="Not authorized to manage permissions"
            )

        permission_service.revoke_permission(dataset_id, user_email)
        logger.info(f"Permission revoked by {current_user['email']} for {user_email}")
        return {"message": "Permission revoked successfully"}
    except DatasetNotFoundException:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        logger.error(f"Failed to revoke permission: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke permission")
