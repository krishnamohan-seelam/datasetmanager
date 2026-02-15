
import sys
import os
import uuid
import json
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.dataset_service import DatasetService
from app.cassandra_client import CassandraClient
from app.core.config import settings

def verify_refactor():
    print("Starting verification of per-dataset table refactor...")
    
    service = DatasetService()
    db = CassandraClient([settings.CASSANDRA_HOST], settings.CASSANDRA_PORT)
    keyspace = settings.CASSANDRA_KEYSPACE
    
    # 1. Create a test dataset
    dataset_id = service.create_dataset(
        name="Verification Test Dataset",
        owner="admin@example.com",
        description="Dataset for refactor verification"
    )
    print(f"Created dataset with ID: {dataset_id}")
    
    # 2. Insert some rows
    rows = [
        {"id": 1, "name": "Alice", "city": "New York"},
        {"id": 2, "name": "Bob", "city": "San Francisco"},
        {"id": 3, "name": "Charlie", "city": "London"}
    ]
    
    inserted = service.insert_rows(dataset_id, rows)
    print(f"Inserted {inserted} rows")
    
    # 3. Verify specific table exists in Cassandra
    table_name = service._get_table_name(dataset_id)
    print(f"Checking for table: {table_name}")
    
    query = f"SELECT table_name FROM system_schema.tables WHERE keyspace_name = '{keyspace}' AND table_name = '{table_name}'"
    result = db.execute(query)
    if result.one():
        print(f"SUCCESS: Table {table_name} exists in Cassandra.")
    else:
        print(f"FAILURE: Table {table_name} NOT found in Cassandra.")
        return False
        
    # 4. Verify data can be retrieved
    retrieved_rows, total = service.get_rows(dataset_id, page=1, page_size=10, user_role="admin")
    print(f"Retrieved {len(retrieved_rows)} rows (total: {total})")
    
    if len(retrieved_rows) == 3 and retrieved_rows[0]["name"] == "Alice":
        print("SUCCESS: Data retrieved correctly from the dynamic table.")
    else:
        print("FAILURE: Data retrieval failed or incorrect.")
        return False
        
    # 5. Delete dataset and verify table is dropped
    print(f"Deleting dataset {dataset_id}...")
    service.delete_dataset(dataset_id)
    
    result = db.execute(query)
    if not result.one():
        print(f"SUCCESS: Table {table_name} has been dropped.")
    else:
        print(f"FAILURE: Table {table_name} still exists after deletion.")
        return False
        
    print("\nVERIFICATION COMPLETE: All tests passed!")
    return True

if __name__ == "__main__":
    try:
        if verify_refactor():
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"An error occurred during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
