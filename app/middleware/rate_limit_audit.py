"""
Middleware for rate limiting, audit logging, and CORS configuration
"""

import logging
import time
from typing import Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)  # IP -> list of timestamps

    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if ts > cutoff
        ]

        # Check if limit exceeded
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return False

        # Add current request
        self.requests[client_ip].append(now)
        return True

    def get_remaining(self, client_ip: str) -> int:
        """Get remaining requests for this minute"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if ts > cutoff
        ]

        return max(0, self.requests_per_minute - len(self.requests[client_ip]))


class AuditLogger:
    """Audit logging for all requests"""

    @staticmethod
    def log_request(
        user_email: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        ip_address: str,
    ):
        """Log API request"""
        audit_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_email": user_email,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "ip_address": ip_address,
        }
        logger.info(f"API_AUDIT: {audit_record}")

    @staticmethod
    def log_data_access(
        user_email: str,
        dataset_id: str,
        action: str,
        row_count: int = 0,
        masked: bool = False,
    ):
        """Log data access"""
        access_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_email": user_email,
            "dataset_id": dataset_id,
            "action": action,
            "row_count": row_count,
            "masked": masked,
        }
        logger.info(f"DATA_ACCESS: {access_record}")

    @staticmethod
    def log_permission_change(
        admin_email: str,
        dataset_id: str,
        target_user: str,
        permission_level: str,
        action: str,
    ):
        """Log permission changes"""
        permission_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "admin_email": admin_email,
            "dataset_id": dataset_id,
            "target_user": target_user,
            "permission_level": permission_level,
            "action": action,
        }
        logger.info(f"PERMISSION_CHANGE: {permission_record}")


async def rate_limit_middleware(
    request: Request, call_next: Callable, limiter: RateLimiter
) -> JSONResponse:
    """Rate limiting middleware"""
    client_ip = request.client.host if request.client else "unknown"

    if not limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Maximum 60 requests per minute.",
                    "retry_after_seconds": 60,
                }
            },
        )

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Add rate limit headers
    remaining = limiter.get_remaining(client_ip)
    response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(
        int((datetime.utcnow() + timedelta(minutes=1)).timestamp())
    )
    response.headers["X-Response-Time"] = str(duration_ms)

    return response


async def audit_logging_middleware(
    request: Request, call_next: Callable
) -> JSONResponse:
    """Audit logging middleware"""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"

    # Get user from request (if authenticated)
    user_email = request.headers.get("X-User-Email", "anonymous")

    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Log the request
    AuditLogger.log_request(
        user_email=user_email,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        ip_address=client_ip,
    )

    return response


def cors_headers(
    allow_origins: list = None,
    allow_methods: list = None,
    allow_headers: list = None,
    allow_credentials: bool = True,
    max_age: int = 3600,
) -> dict:
    """Generate CORS headers"""
    return {
        "Access-Control-Allow-Origin": ", ".join(allow_origins or ["*"]),
        "Access-Control-Allow-Methods": ", ".join(
            allow_methods or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        ),
        "Access-Control-Allow-Headers": ", ".join(
            allow_headers or ["Content-Type", "Authorization", "X-User-Email"]
        ),
        "Access-Control-Allow-Credentials": str(allow_credentials).lower(),
        "Access-Control-Max-Age": str(max_age),
    }
