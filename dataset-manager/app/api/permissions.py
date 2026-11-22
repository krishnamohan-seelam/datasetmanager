"""
Permissions router — grant, revoke, and list dataset permissions.
"""

from typing import List

from fastapi import APIRouter, Depends

from app.core.security import get_current_user, require_owner_or_admin
from app.core.exceptions import translate_domain_exceptions
from app.schemas.common import PermissionBase
from app.api.dependencies import permission_service, logger

router = APIRouter(prefix="/api/v1/datasets", tags=["Permissions"])


@router.get("/{dataset_id}/permissions", response_model=List[dict])
@translate_domain_exceptions
async def get_permissions(
    ctx: dict = Depends(require_owner_or_admin),
):
    """List all permissions for a dataset (owner or admin only)"""
    permissions = permission_service.list_dataset_permissions(ctx["dataset"]["id"])
    return permissions


@router.post("/{dataset_id}/permissions", response_model=dict)
@translate_domain_exceptions
async def grant_permission(
    grant: PermissionBase,
    ctx: dict = Depends(require_owner_or_admin),
):
    """Grant permission to user for dataset (owner or admin only)"""
    dataset_id = ctx["dataset"]["id"]
    permission_service.grant_permission(dataset_id, grant.user_email, grant.role.value)
    logger.info(f"Permission granted by {ctx['current_user']['email']} for {grant.user_email}")
    return {"message": "Permission granted successfully"}


@router.delete("/{dataset_id}/permissions/{user_email}")
@translate_domain_exceptions
async def revoke_permission(
    user_email: str,
    ctx: dict = Depends(require_owner_or_admin),
):
    """Revoke permission from user (owner or admin only)"""
    dataset_id = ctx["dataset"]["id"]
    permission_service.revoke_permission(dataset_id, user_email)
    logger.info(f"Permission revoked by {ctx['current_user']['email']} for {user_email}")
    return {"message": "Permission revoked successfully"}
