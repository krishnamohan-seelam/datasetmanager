"""
Authentication router — register, login, and current user info.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.auth_utils import User, create_access_token
from app.core.security import get_current_user
from app.schemas.common import AuthResponse, RegisterRequest, LoginRequest, UserBase
from app.api.dependencies import db, logger

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse)
def register(user_data: RegisterRequest):
    """Register new user"""
    try:
        email = user_data.email
        password = user_data.password
        full_name = user_data.full_name
        role = user_data.role or "viewer"

        # Check if user exists
        query = "SELECT email FROM dataset_manager.users WHERE email = %s LIMIT 1;"
        result = db.execute(query, (email,))
        if result.one():
            raise HTTPException(status_code=400, detail="User already exists")

        # Create user with UUID
        user_id = uuid.uuid4()
        hashed_password = User.hash_password(password)
        is_active = True
        now = datetime.utcnow()

        prepared = db.prepare(
            """INSERT INTO dataset_manager.users 
            (user_id, email, password_hash, full_name, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        )

        db.execute(
            prepared,
            (user_id, email, hashed_password, full_name, role, is_active, now, now),
        )

        # Create JWT token for immediate login
        access_token = create_access_token({"sub": email, "role": role})

        logger.info(f"User {email} registered successfully")
        return AuthResponse(
            token=access_token,
            access_token=access_token,
            user=UserBase(email=email, full_name=full_name, role=role),
            message="User registered successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=AuthResponse)
def login(login_data: LoginRequest):
    """Login user and return JWT token"""
    try:
        email = login_data.email
        password = login_data.password

        # Get user
        query = "SELECT email, password_hash, role FROM dataset_manager.users WHERE email = %s LIMIT 1;"
        result = db.execute(query, (email,))
        row = result.one()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify password
        user = User(
            email=row.email,
            hashed_password=row.password_hash,
            role=row.role,
        )
        if not user.verify_password(password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create JWT token
        access_token = create_access_token({"sub": user.email, "role": user.role})

        logger.info(f"User {email} logged in successfully")
        return AuthResponse(
            token=access_token,
            access_token=access_token,
            user=UserBase(email=user.email, full_name=user.full_name, role=user.role),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return {"email": current_user["email"], "role": current_user["role"]}
