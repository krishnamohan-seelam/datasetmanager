"""
FastAPI application entry point for Dataset Manager.
App configuration, middleware, exception handlers, and router registration.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.utils.log_formatter import app_logger
from app.api import all_routers
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


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
for router in all_routers:
    app.include_router(router)
