
from cassandra.cluster import Cluster
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    KEYSPACE = settings.CASSANDRA_KEYSPACE
    logger.info(f"Connecting to Cassandra at {settings.CASSANDRA_HOST}:{settings.CASSANDRA_PORT}...")
    
    cluster = Cluster([settings.CASSANDRA_HOST], port=settings.CASSANDRA_PORT, protocol_version=5)
    session = cluster.connect()
    
    # List of columns to add
    columns_to_add = [
        ("size_bytes", "BIGINT"),
        ("file_format", "TEXT"),
        ("status", "TEXT")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            logger.info(f"Adding column {col_name} to {KEYSPACE}.datasets...")
            query = f"ALTER TABLE {KEYSPACE}.datasets ADD {col_name} {col_type};"
            session.execute(query)
            logger.info(f"Successfully added {col_name}.")
        except Exception as e:
            if "already has a column" in str(e) or "Conflicting column" in str(e):
                logger.info(f"Column {col_name} already exists, skipping.")
            else:
                logger.error(f"Failed to add {col_name}: {e}")
                
    logger.info("Migration complete.")
    cluster.shutdown()

if __name__ == "__main__":
    migrate()
