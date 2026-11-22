"""
Custom exceptions for Dataset Manager
"""

import asyncio
import functools
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)


class DatasetManagerException(Exception):
    """Base exception for dataset manager"""

    pass


class DatasetNotFoundException(DatasetManagerException):
    """Raised when dataset is not found"""

    pass


class InsufficientPermissionsException(DatasetManagerException):
    """Raised when user lacks required permissions"""

    pass


class InvalidFileFormatException(DatasetManagerException):
    """Raised when uploaded file format is invalid"""

    pass


class DatasetAlreadyExistsException(DatasetManagerException):
    """Raised when dataset with same name already exists"""

    pass


class UploadFailedException(DatasetManagerException):
    """Raised when file upload fails"""

    pass


class DatabaseException(DatasetManagerException):
    """Raised when database operation fails"""

    pass


# Maps each known domain exception to the HTTP status it should surface as.
# Anything not listed here (including a bare DatasetManagerException) falls
# back to 500 in translate_domain_exceptions below.
_EXCEPTION_STATUS_MAP = {
    DatasetNotFoundException: 404,
    InsufficientPermissionsException: 403,
    InvalidFileFormatException: 400,
    DatasetAlreadyExistsException: 409,
    UploadFailedException: 500,
    DatabaseException: 500,
}


def translate_domain_exceptions(func):
    """Route-handler decorator: lets a deliberately-raised HTTPException pass
    through untouched, and maps DatasetManagerException subtypes to their HTTP
    status in one place — instead of each handler re-implementing
    `except HTTPException: raise` before a generic `except Exception` (whose
    absence lets HTTPException get swallowed and rewritten as a 500, since
    HTTPException is itself an Exception).
    """

    def _status_for(exc: DatasetManagerException) -> int:
        return _EXCEPTION_STATUS_MAP.get(type(exc), 500)

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except DatasetManagerException as exc:
            logger.error(f"{func.__name__} failed: {exc}")
            raise HTTPException(status_code=_status_for(exc), detail=str(exc))
        except Exception as exc:
            logger.error(f"{func.__name__} failed: {exc}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise
        except DatasetManagerException as exc:
            logger.error(f"{func.__name__} failed: {exc}")
            raise HTTPException(status_code=_status_for(exc), detail=str(exc))
        except Exception as exc:
            logger.error(f"{func.__name__} failed: {exc}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
