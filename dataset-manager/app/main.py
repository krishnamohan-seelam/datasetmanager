"""
FastAPI application entry point for Dataset Manager.
App configuration, middleware, exception handlers, and router registration.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.log_formatter import app_logger
from app.api import all_routers
from app.middleware.rate_limit_audit import (
    RateLimiter,
    rate_limit_middleware,
    audit_logging_middleware,
)
from scripts.init_cassandra import initialize_schema

# Configure logging
logger = app_logger

# Create FastAPI app
app = FastAPI(title="Dataset Manager API", version="1.0.0")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    """Initialize database schema on startup"""
    initialize_schema()


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit logging middleware — logs all API requests
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_logging_middleware)

# Rate limiting (uncomment for production; may interfere with dev testing)
# rate_limiter = RateLimiter(requests_per_minute=60)
# async def _rate_limit_dispatch(request, call_next):
#     return await rate_limit_middleware(request, call_next, rate_limiter)
# app.add_middleware(BaseHTTPMiddleware, dispatch=_rate_limit_dispatch)


from prometheus_client import make_asgi_app
from app.monitoring.metrics import registry

# Register routers
for router in all_routers:
    app.include_router(router)

# Add prometheus metrics endpoint
metrics_app = make_asgi_app(registry=registry)
app.mount("/metrics", metrics_app)
