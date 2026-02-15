"""
Permission management service
"""

import logging
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime

from ..cassandra_client import CassandraClient
from ..core.exceptions import DatabaseException
from ..core.config import settings

logger = logging.getLogger(__name__)


class PermissionService:
    """Service for managing dataset permissions"""

    def __init__(self):
        self.db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
        self.keyspace = settings.CASSANDRA_KEYSPACE

    def grant_permission(self, dataset_id: UUID, user_email: str, role: str) -> bool:
        """Grant permission to user for dataset"""
        try:
            query = f"""
                INSERT INTO {self.keyspace}.dataset_permissions
                (dataset_id, user_email, role, granted_at)
                VALUES (%s, %s, %s, %s)
            """

            self.db.execute(query, [dataset_id, user_email, role, datetime.utcnow()])

            logger.info(
                f"Granted {role} permission to {user_email} for dataset {dataset_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to grant permission: {e}")
            raise DatabaseException(f"Failed to grant permission: {str(e)}")

    def revoke_permission(self, dataset_id: UUID, user_email: str) -> bool:
        """Revoke permission from user for dataset"""
        try:
            query = f"""
                DELETE FROM {self.keyspace}.dataset_permissions
                WHERE dataset_id = %s AND user_email = %s
            """

            self.db.execute(query, [dataset_id, user_email])

            logger.info(f"Revoked permission for {user_email} on dataset {dataset_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke permission: {e}")
            raise DatabaseException(f"Failed to revoke permission: {str(e)}")

    def get_user_permission(self, dataset_id: UUID, user_email: str) -> Dict[str, Any]:
        """Get user's permission for dataset"""
        try:
            query = f"""
                SELECT dataset_id, user_email, role, granted_at
                FROM {self.keyspace}.dataset_permissions
                WHERE dataset_id = %s AND user_email = %s
            """

            result = self.db.execute(query, [dataset_id, user_email])
            row = result.one()

            if row:
                return {
                    "dataset_id": row.dataset_id,
                    "user_email": row.user_email,
                    "role": row.role,
                    "granted_at": row.granted_at,
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get permission: {e}")
            raise DatabaseException(f"Failed to get permission: {str(e)}")

    def list_dataset_permissions(self, dataset_id: UUID) -> List[Dict[str, Any]]:
        """List all permissions for a dataset"""
        try:
            query = f"""
                SELECT user_email, role, granted_at
                FROM {self.keyspace}.dataset_permissions
                WHERE dataset_id = %s
            """

            result = self.db.execute(query, [dataset_id])
            permissions = [
                {
                    "user_email": row.user_email,
                    "role": row.role,
                    "granted_at": row.granted_at,
                }
                for row in result
            ]

            return permissions
        except Exception as e:
            logger.error(f"Failed to list permissions: {e}")
            raise DatabaseException(f"Failed to list permissions: {str(e)}")

    def check_permission(
        self, dataset_id: UUID, user_email: str, dataset_owner: str, is_public: bool, user_role: str = None
    ) -> str:
        """
        Check user's permission level for dataset

        Returns: role ('admin', 'contributor', 'viewer', or None if denied)
        """
        # Global admin always has access
        if user_role == "admin":
            return "admin"

        # Owner always has admin access
        if user_email == dataset_owner:
            return "admin"

        # Public datasets are visible to all as viewers
        if is_public:
            return "viewer"

        # Check explicit permissions
        permission = self.get_user_permission(dataset_id, user_email)
        if permission:
            return permission["role"]

        # No permission
        return None

    def is_dataset_accessible(
        self, dataset_id: UUID, user_email: str, dataset_owner: str, is_public: bool, user_role: str = None
    ) -> bool:
        """Check if user can access dataset"""
        return (
            self.check_permission(dataset_id, user_email, dataset_owner, is_public, user_role)
            is not None
        )
