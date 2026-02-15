"""
Security utilities for Dataset Manager
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.auth_utils import decode_access_token
from typing import Optional, List

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
