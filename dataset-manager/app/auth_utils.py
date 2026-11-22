from typing import Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt

from app.core.config import settings

# Password hashing context - Switched to PBKDF2 to avoid bcrypt's 72-byte limit
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class User:
    def __init__(
        self,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
        role: str = "viewer",
        is_active: bool = True,
        created_at: Optional[datetime] = None,
    ):
        self.email = email
        self.hashed_password = hashed_password
        self.full_name = full_name
        self.role = role
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    def to_dict(self):
        return {
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


# JWT utility functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
