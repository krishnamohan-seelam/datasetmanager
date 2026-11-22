"""
Security utilities for Dataset Manager
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.auth_utils import decode_access_token
from app.schemas.common import Role
from typing import Any, Dict, Optional, List

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency to get current user from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    return {
        "email": email,
        "role": payload.get("role", "viewer"),
        "scopes": payload.get("scopes", []),
    }


def require_role(allowed_roles: List[str]):
    """
    Decorator to require specific user roles

    Usage:
        @router.get("/admin")
        async def admin_endpoint(current_user = Depends(require_role(["admin"]))):
            ...
    """

    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {allowed_roles}",
            )
        return current_user

    return role_checker


def require_owner_or_admin(
    dataset_id: uuid.UUID, current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Single owner-or-admin accessibility/ownership check, shared by every
    route that previously re-implemented
    `dataset["owner"] != current_user["email"] and current_user["role"] != "admin"`
    at its own call site.

    `current_user` must come from `get_current_user` (a server-verified JWT),
    never from client-supplied input — it is resolved via FastAPI's dependency
    injection here, so callers can't pass an arbitrary role.

    Returns both pieces callers typically need, so most route handlers don't
    need a second `get_dataset()` call:
        {"current_user": <dict>, "dataset": <dict>}
    """
    # Local import avoids a circular import: app.api.dependencies imports
    # services that sit above app.core, so app.core can't import it at
    # module load time.
    from app.api.dependencies import dataset_service

    dataset = dataset_service.get_dataset(dataset_id)
    if dataset["owner"] != current_user["email"] and current_user["role"] != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return {"current_user": current_user, "dataset": dataset}
