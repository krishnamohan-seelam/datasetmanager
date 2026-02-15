"""
Kafka Producer for Dataset Manager
Publishes events for ETL pipeline triggers and audit logging
"""

import json
import logging
from typing import Any, Dict, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class KafkaEventProducer:
    """Singleton Kafka producer for publishing events"""

    _instance: Optional["KafkaEventProducer"] = None

    def __init__(
        self, bootstrap_servers: str = None, topic_prefix: str = "dataset-manager"
    ):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.topic_prefix = topic_prefix
        self.producer = None
        self._connect()

    def _connect(self):
        """Establish Kafka connection"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
                max_in_flight_requests_per_connection=1,
            )
            logger.info(f"Connected to Kafka: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            raise

    @classmethod
    def get_instance(cls) -> "KafkaEventProducer":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish_dataset_uploaded(
        self,
        dataset_id: str,
        dataset_name: str,
        owner: str,
        file_path: str,
        file_format: str,
        row_count: int,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """Publish dataset uploaded event"""
        event = {
            "event_type": "dataset.uploaded",
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "owner": owner,
            "file_path": file_path,
            "file_format": file_format,
            "row_count": row_count,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        return self._publish(f"{self.topic_prefix}.dataset.uploads", event)

    def publish_dataset_deleted(
        self, dataset_id: str, dataset_name: str, owner: str
    ) -> bool:
        """Publish dataset deleted event"""
        event = {
            "event_type": "dataset.deleted",
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "owner": owner,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return self._publish(f"{self.topic_prefix}.dataset.deletions", event)

    def publish_audit_event(
        self,
        user_email: str,
        action: str,
        resource_type: str,
        resource_id: str,
        status: str = "success",
        details: Dict[str, Any] = None,
    ) -> bool:
        """Publish audit log event"""
        event = {
            "user_email": user_email,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {},
        }
        return self._publish(f"{self.topic_prefix}.audit", event)

    def publish_etl_trigger(
        self,
        dataset_id: str,
        job_id: str,
        stage: str,
        validation_rules: Dict[str, Any] = None,
        transformation_config: Dict[str, Any] = None,
    ) -> bool:
        """Publish ETL job trigger event"""
        event = {
            "event_type": "etl.trigger",
            "dataset_id": dataset_id,
            "job_id": job_id,
            "stage": stage,  # 'validation', 'transformation', 'loading'
            "validation_rules": validation_rules or {},
            "transformation_config": transformation_config or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        return self._publish(f"{self.topic_prefix}.etl.triggers", event)

    def publish_performance_metric(
        self, metric_name: str, metric_value: float, labels: Dict[str, str] = None
    ) -> bool:
        """Publish performance metric"""
        event = {
            "metric_name": metric_name,
            "metric_value": metric_value,
            "labels": labels or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        return self._publish(f"{self.topic_prefix}.metrics", event)

    def _publish(self, topic: str, event: Dict[str, Any]) -> bool:
        """Publish event to topic"""
        try:
            future = self.producer.send(topic, value=event)
            future.get(timeout=10)
            logger.debug(
                f"Published event to {topic}: {event.get('event_type', 'unknown')}"
            )
            return True
        except KafkaError as e:
            logger.error(f"Failed to publish event to {topic}: {str(e)}")
            return False

    def close(self):
        """Close Kafka connection"""
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer closed")
