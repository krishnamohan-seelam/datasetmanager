# 07 — ETL Orchestration (Airflow)

`dataset-manager/airflow/dags/dataset_etl_pipeline.py` defines one DAG, `dataset_etl_pipeline`,
`schedule_interval=None` — it only ever runs when triggered with a `conf` payload (manually or, per
design intent, from `create_etl_trigger_handler` in `app/integrations/kafka_consumer.py` reacting to a
Kafka event), never on a cron schedule. `retries=2`, 5-minute retry delay, email-on-failure configured
but email delivery itself isn't configured elsewhere in this repo.

## Task graph

Four `PythonOperator` tasks, strictly linear:

```
validate_dataset >> transform_dataset >> load_to_cassandra >> publish_completion
```

- `validate_dataset` — reads `dataset_id`/`job_id`/`validation_rules` from `dag_run.conf` (the Kafka
  trigger's payload), runs data-quality/schema-compliance/duplicate checks, returns a results dict
  (schema compliance flag, null counts per column, etc.) via XCom for the next task.
- `transform_dataset` — pulls `validate_dataset`'s XCom result and applies transformations.
- `load_to_cassandra` — writes the transformed batch into the dataset's per-dataset Cassandra table
  (`04-data-layer.md`) — this is Airflow's own write path into the same tables the API writes to via
  `DatasetService`/`BatchService`, so both the DAG and the API are producers against the same schema;
  anything changed in the per-dataset table shape in `DatasetService` must stay compatible with what
  this task expects to write.
- `publish_completion` — presumably publishes a completion event back via Kafka (`KafkaEventProducer`),
  closing the loop that started with the upload/ETL-trigger event.

## Relationship to the rest of the system

This DAG is **decoupled from the request/response cycle** — a dataset upload via `POST /datasets` is not
required to wait on this pipeline; validation/transformation/loading can happen asynchronously after the
initial ingestion. This is the intended place for anything too slow or too failure-prone to run inline in
an API request handler.

However: Airflow is not part of `docker-compose.yml` (`01-system-overview.md`), and neither is a Kafka
broker, so **this DAG cannot currently run end-to-end from the default `docker-compose up` stack** —
running it requires standing up Airflow (scheduler + webserver, with this DAG on its `dags/` path) and a
Kafka broker separately, then wiring `create_etl_trigger_handler`'s consumer to actually trigger it. Don't
assume uploads trigger this pipeline in the shipped Docker setup.
