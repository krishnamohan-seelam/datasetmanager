"""
Initialize Cassandra keyspace and tables for Dataset Manager
"""

from cassandra.cluster import Cluster
from app.core.config import settings

KEYSPACE = settings.CASSANDRA_KEYSPACE

TABLES = [
    # Keyspace - use RF=1 for local dev
    f"""
    CREATE KEYSPACE IF NOT EXISTS {KEYSPACE}
    WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}};
    """,
    # Datasets metadata
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
        masking_config TEXT
    );
    """,
    # Column metadata and masking rules
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema (
        dataset_id UUID,
        column_name TEXT,
        column_type TEXT,
        masking_rule TEXT,
        PRIMARY KEY (dataset_id, column_name)
    );
    """,
    # Column metadata and masking rules
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema (
        dataset_id UUID,
        column_name TEXT,
        column_type TEXT,
        masking_rule TEXT,
        PRIMARY KEY (dataset_id, column_name)
    );
    """,
    # Dataset level permissions
    f"""
    CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_permissions (
        dataset_id UUID,
        user_email TEXT,
        role TEXT,
        granted_at TIMESTAMP,
        PRIMARY KEY ((dataset_id), user_email)
    );
    """,
    # Audit log for actions
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
    # Users table
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
    # Indexes
    f"CREATE INDEX IF NOT EXISTS datasets_name_idx ON {KEYSPACE}.datasets (name);",
    f"CREATE INDEX IF NOT EXISTS users_email_idx ON {KEYSPACE}.users (email);",
    # Migrations for existing tables
    f"ALTER TABLE {KEYSPACE}.datasets ADD size_bytes BIGINT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD file_format TEXT;",
    f"ALTER TABLE {KEYSPACE}.datasets ADD status TEXT;",
]


def initialize_schema():
    print(f"Connecting to Cassandra at {settings.CASSANDRA_HOST}:{settings.CASSANDRA_PORT}...")
    
    # We use the same connection logic as CassandraClient to benefit from retries if we integrated it,
    # but for schema init we can just use a simple cluster object here as well.
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
