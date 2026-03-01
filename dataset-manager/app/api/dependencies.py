"""
Shared dependencies for API routers.
Centralizes service singletons and helper functions.
"""

import csv
import io
import json
import logging
from typing import List

import pandas as pd

from app.auth_utils import User, create_access_token, decode_access_token
from app.cassandra_client import CassandraClient
from app.core.config import settings
from app.core.exceptions import InvalidFileFormatException
from app.services.dataset_service import DatasetService
from app.services.permission_service import PermissionService
from app.services.schema_service import SchemaService
from app.services.batch_service import BatchService
from app.utils.log_formatter import app_logger

# Logger
logger = app_logger

# Service singletons
dataset_service = DatasetService()
permission_service = PermissionService()
schema_service = SchemaService()
batch_service = BatchService()

# Database client (used directly for auth queries)
db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)


def parse_file_content(content: bytes, file_ext: str) -> List[dict]:
    """Parse file content based on format"""
    try:
        if file_ext == ".csv":
            text = content.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)
        elif file_ext == ".json":
            text = content.decode("utf-8")
            data = json.loads(text)
            return data if isinstance(data, list) else [data]
        elif file_ext == ".parquet":
            df = pd.read_parquet(io.BytesIO(content))
            return df.to_dict("records")
        else:
            raise InvalidFileFormatException(f"Unsupported format: {file_ext}")
    except InvalidFileFormatException:
        raise
    except Exception as e:
        raise InvalidFileFormatException(f"Failed to parse file: {str(e)}")
