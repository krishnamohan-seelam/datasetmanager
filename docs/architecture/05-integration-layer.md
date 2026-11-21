# 05 — Integration Layer

`dataset-manager/app/integrations/` wraps every external system. Services in `app/services/` are
expected to go through these wrappers rather than talking to client libraries directly (the one
exception is `app/cassandra_client.py`, which lives outside this package — see the "Known gaps" note in
`README.md`).

## Object storage — factory + duck-typed backends

`storage_factory.get_storage_service()` reads `STORAGE_BACKEND` (`local` / `minio` / `aws`) and returns
either `LocalStorageService` (`local_storage.py`) or `S3StorageService` (`s3_storage.py`, used for both
MinIO and real AWS S3 — just constructed with different endpoint/credential args). Both classes expose
the same method set — `upload_file`, `download_file`, `delete_file`, `delete_dataset_files`,
`get_file_size`, `generate_presigned_url`, `archive_old_files` — but **this is enforced only by
convention, not by a shared `ABC`/`Protocol`**; nothing will catch a backend that drifts from this
interface except a runtime `AttributeError`. `archive_old_files` on `S3StorageService` additionally
demonstrates lifecycle logic (moving old objects to Glacier storage class) that `LocalStorageService`'s
version presumably can't replicate semantically — check both implementations before assuming behavior
parity beyond the method signatures.

Always obtain a backend through the factory (`get_storage_service()`), never by importing
`LocalStorageService`/`S3StorageService` directly in a service — that's what keeps storage swappable
per-environment via a single env var.

## Redis — two parallel services, not one

There are **two independent Redis-backed classes** with overlapping purpose:
- `RedisCacheService` (`redis_cache.py`) — general-purpose cache: dataset metadata, per-user dataset
  listings, arbitrary query-result caching (`get_query_result`/`set_query_result`), plus
  `get_stats`/`clear_all` (used by the admin `POST /cache/clear` endpoint).
- `PaginationCacheService` (`app/services/pagination_cache.py`, logically a service but Redis-backed) —
  purpose-built for paginated row reads, keyed by dataset+page+page_size+**role** (see
  `03-service-layer.md`).

They are not the same instance and not obviously coordinated — invalidating one does not invalidate the
other. Anyone adding new Redis-cached data should decide explicitly which of the two this belongs to
(or whether a third purpose-built cache key scheme, like pagination's, is warranted) rather than assuming
a single cache layer exists.

## Kafka — producer/consumer, two use cases

- `kafka_producer.py` (`KafkaEventProducer`, intended as a singleton via `_instance`, configured by
  `KAFKA_BOOTSTRAP_SERVERS`) publishes events for two purposes per its own docstring: **ETL pipeline
  triggers** and **audit logging**. `acks="all"`, `retries=3`,
  `max_in_flight_requests_per_connection=1` — configured for delivery reliability/ordering over
  throughput.
- `kafka_consumer.py` (`KafkaEventConsumer`) exposes `subscribe_to_uploads`, `subscribe_to_etl_triggers`,
  `subscribe_to_audit_events`, each taking a callback, plus ready-made handler factories
  (`create_upload_event_handler`, `create_etl_trigger_handler`, `create_audit_event_handler`) meant to be
  wired to an Airflow client / workflow executor (see `07-etl-orchestration.md`).
- **Neither Kafka nor a consumer process is started anywhere in `app/main.py`** or in
  `docker-compose.yml` — the producer/consumer code exists and is presumably exercised by
  tests/standalone scripts, but there is no wired-up "Kafka is running and consumed" path in the services
  that ship via Docker Compose. Treat Kafka as present-in-code, not present-in-the-default-runtime, until
  it's explicitly started.

## Cassandra client

`app/cassandra_client.py` (top-level, not under `integrations/`) is the shared session wrapper imported
by `app/api/dependencies.py` and presumably by the services. It is the one piece of integration code not
organized under `app/integrations/` — worth moving there for consistency if touching this area, but not
done as part of this blueprint since it's a structural change, not a documentation one.
