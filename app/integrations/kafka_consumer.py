"""
Kafka Consumer for ETL trigger events
Consumes events from Kafka topics and triggers ETL jobs
"""

import json
import logging
from typing import Callable, Optional
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import os
import threading

logger = logging.getLogger(__name__)


class KafkaEventConsumer:
    """Kafka consumer for event processing"""

    def __init__(
        self,
        bootstrap_servers: str = None,
        group_id: str = "dataset-manager-etl",
        topic_prefix: str = "dataset-manager",
    ):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.group_id = group_id
        self.topic_prefix = topic_prefix
        self.consumer = None
        self.running = False
        self._connect()

    def _connect(self):
        """Establish Kafka connection"""
        try:
            self.consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                max_poll_records=100,
            )
            logger.info(f"Connected to Kafka: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {str(e)}")
            raise

    def subscribe_to_uploads(self, callback: Callable):
        """Subscribe to dataset upload events"""
        topic = f"{self.topic_prefix}.dataset.uploads"
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to topic: {topic}")
        self._consume(callback)

    def subscribe_to_etl_triggers(self, callback: Callable):
        """Subscribe to ETL trigger events"""
        topic = f"{self.topic_prefix}.etl.triggers"
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to topic: {topic}")
        self._consume(callback)

    def subscribe_to_audit_events(self, callback: Callable):
        """Subscribe to audit events"""
        topic = f"{self.topic_prefix}.audit"
        self.consumer.subscribe([topic])
        logger.info(f"Subscribed to topic: {topic}")
        self._consume(callback)

    def _consume(self, callback: Callable):
        """Start consuming messages"""
        self.running = True
        try:
            logger.info("Consumer started")
            for message in self.consumer:
                if not self.running:
                    break

                try:
                    logger.debug(f"Received message: {message.value}")
                    callback(message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
        except KafkaError as e:
            logger.error(f"Kafka consumer error: {str(e)}")
        finally:
            self.consumer.close()
            logger.info("Consumer stopped")

    def stop(self):
        """Stop consuming"""
        self.running = False


def create_upload_event_handler(airflow_client: Optional[object] = None) -> Callable:
    """Create handler for dataset upload events"""

    def handle_upload_event(event: dict):
        dataset_id = event.get("dataset_id")
        dataset_name = event.get("dataset_name")
        file_format = event.get("file_format")

        logger.info(f"Processing upload event for {dataset_name} ({dataset_id})")

        if airflow_client:
            # Trigger Airflow DAG
            job_id = airflow_client.trigger_dag(
                dag_id="dataset_etl_pipeline",
                conf={
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name,
                    "file_format": file_format,
                    "validation_rules": {},
                },
            )
            logger.info(f"Triggered Airflow DAG: {job_id}")

    return handle_upload_event


def create_etl_trigger_handler(workflow_executor: Optional[object] = None) -> Callable:
    """Create handler for ETL trigger events"""

    def handle_etl_trigger(event: dict):
        dataset_id = event.get("dataset_id")
        job_id = event.get("job_id")
        stage = event.get("stage")

        logger.info(f"Processing ETL trigger for {dataset_id}, stage: {stage}")

        if workflow_executor:
            workflow_executor.execute_stage(
                job_id=job_id, dataset_id=dataset_id, stage=stage
            )

    return handle_etl_trigger


def create_audit_event_handler() -> Callable:
    """Create handler for audit events"""

    def handle_audit_event(event: dict):
        user_email = event.get("user_email")
        action = event.get("action")
        resource_type = event.get("resource_type")

        logger.info(f"Audit: {user_email} performed {action} on {resource_type}")
        # Store in audit database/log

    return handle_audit_event
