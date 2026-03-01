"""
Migration script: Migrate from legacy dataset_schema (unversioned) to
versioned schema tables (dataset_schema v2 + dataset_schema_versions).

Also backfills batch entries for existing datasets.

Safe to re-run — uses IF NOT EXISTS and idempotent inserts.
"""

import sys
sys.path.insert(0, ".")

from uuid import uuid4
from datetime import datetime
from cassandra.cluster import Cluster
from app.core.config import settings

KEYSPACE = settings.CASSANDRA_KEYSPACE


def migrate():
    cluster = Cluster(
        [settings.CASSANDRA_HOST], port=settings.CASSANDRA_PORT, protocol_version=5
    )
    session = cluster.connect(KEYSPACE)

    # ── 1. Ensure new tables exist ───────────────────────────────────
    print("[1/5] Ensuring new tables exist...")

    session.execute(f"""
        CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_batches (
            dataset_id UUID, batch_id UUID, batch_date TIMESTAMP,
            schema_version INT, row_count BIGINT, size_bytes BIGINT,
            file_format TEXT, status TEXT, uploaded_by TEXT, created_at TIMESTAMP,
            PRIMARY KEY ((dataset_id), batch_date, batch_id)
        ) WITH CLUSTERING ORDER BY (batch_date DESC, batch_id DESC);
    """)

    session.execute(f"""
        CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema_versions (
            dataset_id UUID, version INT, batch_id UUID,
            created_at TIMESTAMP, column_count INT, change_summary TEXT,
            PRIMARY KEY ((dataset_id), version)
        ) WITH CLUSTERING ORDER BY (version DESC);
    """)

    # Check if versioned schema table already exists with new columns
    cols_result = session.execute(
        f"SELECT column_name FROM system_schema.columns "
        f"WHERE keyspace_name = '{KEYSPACE}' AND table_name = 'dataset_schema'"
    )
    existing_cols = {r.column_name for r in cols_result}

    needs_migration = "version" not in existing_cols
    if not needs_migration:
        print("  Schema table already has 'version' column — skipping DDL migration")
    else:
        print("  Legacy schema table detected — will migrate data")

        # Create the new table
        session.execute(f"""
            CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema_v2 (
                dataset_id UUID, version INT, column_name TEXT,
                column_type TEXT, position INT, masking_rule TEXT,
                is_active BOOLEAN, added_at TIMESTAMP, removed_at TIMESTAMP,
                PRIMARY KEY ((dataset_id), version, position)
            ) WITH CLUSTERING ORDER BY (version DESC, position ASC);
        """)

        # ── 2. Migrate existing schema rows ──────────────────────────
        print("[2/5] Migrating legacy schema rows...")
        legacy_rows = list(session.execute(
            f"SELECT dataset_id, column_name, column_type, masking_rule FROM {KEYSPACE}.dataset_schema"
        ))

        # Group by dataset_id
        datasets = {}
        for row in legacy_rows:
            datasets.setdefault(row.dataset_id, []).append(row)

        now = datetime.utcnow()
        for ds_id, cols in datasets.items():
            for pos, col in enumerate(cols):
                session.execute(
                    f"""INSERT INTO {KEYSPACE}.dataset_schema_v2
                        (dataset_id, version, column_name, column_type, position,
                         masking_rule, is_active, added_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    [ds_id, 1, col.column_name, col.column_type, pos,
                     col.masking_rule, True, now],
                )

            # Register version
            session.execute(
                f"""INSERT INTO {KEYSPACE}.dataset_schema_versions
                    (dataset_id, version, created_at, column_count, change_summary)
                    VALUES (%s, %s, %s, %s, %s)""",
                [ds_id, 1, now, len(cols), "Migrated from legacy schema"],
            )
            print(f"  Migrated schema for {ds_id} ({len(cols)} columns)")

        # Rename tables
        print("[3/5] Swapping tables...")
        try:
            session.execute(f"ALTER TABLE {KEYSPACE}.dataset_schema RENAME TO {KEYSPACE}.dataset_schema_legacy")
        except Exception:
            # ALTER TABLE RENAME not supported in all Cassandra versions
            # Fall back to dropping and keeping v2
            session.execute(f"DROP TABLE IF EXISTS {KEYSPACE}.dataset_schema")

        try:
            session.execute(f"ALTER TABLE {KEYSPACE}.dataset_schema_v2 RENAME TO {KEYSPACE}.dataset_schema")
        except Exception:
            # If rename not supported, recreate
            print("  RENAME not supported, recreating table...")
            session.execute(f"""
                CREATE TABLE IF NOT EXISTS {KEYSPACE}.dataset_schema (
                    dataset_id UUID, version INT, column_name TEXT,
                    column_type TEXT, position INT, masking_rule TEXT,
                    is_active BOOLEAN, added_at TIMESTAMP, removed_at TIMESTAMP,
                    PRIMARY KEY ((dataset_id), version, position)
                ) WITH CLUSTERING ORDER BY (version DESC, position ASC);
            """)
            # Copy data
            v2_rows = list(session.execute(f"SELECT * FROM {KEYSPACE}.dataset_schema_v2"))
            for r in v2_rows:
                session.execute(
                    f"""INSERT INTO {KEYSPACE}.dataset_schema
                        (dataset_id, version, column_name, column_type, position,
                         masking_rule, is_active, added_at, removed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [r.dataset_id, r.version, r.column_name, r.column_type,
                     r.position, r.masking_rule, r.is_active, r.added_at, r.removed_at],
                )
            session.execute(f"DROP TABLE IF EXISTS {KEYSPACE}.dataset_schema_v2")

    # ── 4. Backfill batch entries for existing datasets ───────────────
    print("[4/5] Backfilling batch entries for existing datasets...")
    datasets_rows = list(session.execute(
        f"SELECT dataset_id, name, owner, row_count, size_bytes, file_format, created_at "
        f"FROM {KEYSPACE}.datasets"
    ))

    for ds in datasets_rows:
        # Check if batch already exists
        existing = session.execute(
            f"SELECT batch_id FROM {KEYSPACE}.dataset_batches WHERE dataset_id = %s LIMIT 1",
            [ds.dataset_id],
        ).one()

        if existing:
            continue

        batch_id = uuid4()
        batch_date = ds.created_at or datetime.utcnow()

        session.execute(
            f"""INSERT INTO {KEYSPACE}.dataset_batches
                (dataset_id, batch_id, batch_date, schema_version, row_count,
                 size_bytes, file_format, status, uploaded_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [ds.dataset_id, batch_id, batch_date, 1,
             ds.row_count or 0, ds.size_bytes or 0,
             ds.file_format or "csv", "ready",
             ds.owner or "", batch_date],
        )

        # Update dataset with batch metadata
        session.execute(
            f"""UPDATE {KEYSPACE}.datasets
                SET latest_batch_id = %s, latest_batch_date = %s,
                    total_batches = %s, schema_version = %s,
                    batch_frequency = %s
                WHERE dataset_id = %s""",
            [batch_id, batch_date, 1, 1, "once", ds.dataset_id],
        )
        print(f"  Backfilled batch for {ds.dataset_id} (name={ds.name!r})")

    # ── 5. Add new columns to datasets if missing ────────────────────
    print("[5/5] Ensuring datasets table has batch columns...")
    alter_stmts = [
        f"ALTER TABLE {KEYSPACE}.datasets ADD batch_frequency TEXT;",
        f"ALTER TABLE {KEYSPACE}.datasets ADD latest_batch_id UUID;",
        f"ALTER TABLE {KEYSPACE}.datasets ADD latest_batch_date TIMESTAMP;",
        f"ALTER TABLE {KEYSPACE}.datasets ADD total_batches INT;",
        f"ALTER TABLE {KEYSPACE}.datasets ADD schema_version INT;",
    ]
    for stmt in alter_stmts:
        try:
            session.execute(stmt)
        except Exception:
            pass  # Column already exists

    cluster.shutdown()
    print("\nMigration complete!")


if __name__ == "__main__":
    print("=" * 60)
    print(" DATASET MANAGER — Schema Migration v3")
    print("=" * 60)
    migrate()
