"""
Custom exceptions for Dataset Manager
"""


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
