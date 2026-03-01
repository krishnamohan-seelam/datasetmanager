"""
Initialize Cassandra keyspace and tables for Dataset Manager.

Tables:
  - datasets         : Dataset metadata (with batch tracking columns)
  - dataset_schema   : Versioned column metadata per dataset
  - dataset_schema_versions : Schema version registry
  - dataset_batches  : Batch registry per dataset
  - dataset_permissions : ACL
  - audit_log        : Action audit trail
  - users            : User accounts
"""

from cassandra.cluster import Cluster
from app.core.config import settings

KEYSPACE = settings.CASSANDRA_KEYSPACE

TABLES = [
    # ── Keyspace ─────────────────────────────────────────────────────
    f"""
    CREATE KEYSPACE IF NOT EXISTS {KEYSPACE}
    WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}};
    """,

    # ── Datasets metadata ────────────────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.datasets (
        dataset_id UUID PRIMARY KEY,
        name TEXT,
        description TEXT,
        owner TEXT,
        tags TEXT,
        is_public BOOLEAN,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        row_count BIGINT,
        size_bytes BIGINT,
        file_format TEXT,
        status TEXT,
        masking_config TEXT,
        batch_frequency TEXT,
        latest_batch_id UUID,
        latest_batch_date TIMESTAMP,
        total_batches INT,
        schema_version INT
    );
    """,

    # ── Dataset batches ──────────────────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_batches (
        dataset_id     UUID,
        batch_id       UUID,
        batch_date     TIMESTAMP,
        schema_version INT,
        row_count      BIGINT,
        size_bytes     BIGINT,
        file_format    TEXT,
        status         TEXT,
        uploaded_by    TEXT,
        created_at     TIMESTAMP,
        PRIMARY KEY ((dataset_id), batch_date, batch_id)
    ) WITH CLUSTERING ORDER BY (batch_date DESC, batch_id DESC);
    """,

    # ── Versioned schema per dataset ─────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema (
        dataset_id   UUID,
        version      INT,
        column_name  TEXT,
        column_type  TEXT,
        position     INT,
        masking_rule TEXT,
        is_active    BOOLEAN,
        added_at     TIMESTAMP,
        removed_at   TIMESTAMP,
        PRIMARY KEY ((dataset_id), version, position)
    ) WITH CLUSTERING ORDER BY (version DESC, position ASC);
    """,

    # ── Schema version metadata ──────────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema_versions (
        dataset_id     UUID,
        version        INT,
        batch_id       UUID,
        created_at     TIMESTAMP,
        column_count   INT,
        change_summary TEXT,
        PRIMARY KEY ((dataset_id), version)
    ) WITH CLUSTERING ORDER BY (version DESC);
    """,

    # ── Dataset permissions ──────────────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_permissions (
        dataset_id UUID,
        user_email TEXT,
        role TEXT,
        granted_at TIMESTAMP,
        PRIMARY KEY ((dataset_id), user_email)
    );
    """,

    # ── Audit log ────────────────────────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.audit_log (
        dataset_id UUID,
        log_id TIMEUUID,
        user_email TEXT,
        action TEXT,
        timestamp TIMESTAMP,
        ip_address TEXT,
        details TEXT,
        PRIMARY KEY ((dataset_id), log_id)
    ) WITH CLUSTERING ORDER BY (log_id DESC);
    """,

    # ── Users ────────────────────────────────────────────────────────
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.users (
        user_id UUID,
        email TEXT,
        password_hash TEXT,
        full_name TEXT,
        role TEXT,
        is_active BOOLEAN,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        PRIMARY KEY (user_id)
    );
    """,

    # ── Indexes ──────────────────────────────────────────────────────
    f"CREATE INDEX IF NOT EXISTS datasets_name_idx ON {KEYSPACE}.datasets (name);",
    f"CREATE INDEX IF NOT EXISTS users_email_idx ON {KEYSPACE}.users (email);",

    # ── Migrations for existing tables (safe to re-run) ──────────────
    f"ALTER TABLE {KEYSPACE}.datasets ADD size_bytes BIGINT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD file_format TEXT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD status TEXT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD batch_frequency TEXT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD latest_batch_id UUID;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD latest_batch_date TIMESTAMP;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD total_batches INT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD schema_version INT;",
]


def initialize_schema():
    print(f"Connecting to Cassandra at {settings.CASSANDRA_HOST}:{settings.CASSANDRA_PORT}...")

    cluster = Cluster([settings.CASSANDRA_HOST], port=settings.CASSANDRA_PORT, protocol_version=5)
    session = cluster.connect()

    for stmt in TABLES:
        try:
            session.execute(stmt)
            print(f"Executed: {stmt.strip().splitlines()[0]}...")
        except Exception as e:
            print(f"Error executing statement: {e}")

    print("Cassandra keyspace and tables initialization complete.")
    cluster.shutdown()


if __name__ == "__main__":
    initialize_schema()
