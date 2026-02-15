"""
CassandraClient singleton for connection pooling
"""

from cassandra.cluster import Cluster, Session,NoHostAvailable
from cassandra.policies import RoundRobinPolicy
from threading import Lock
import time

class CassandraClient:
    _instance = None
    _lock = Lock()

    def __new__(cls, contact_points=None, port=9042):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(contact_points, port)
            return cls._instance

    def _init(self, contact_points, port):


        # Ensure contact_points don't have http:// prefix
        cleaned_points = [p.replace("http://", "").replace("https://", "").split(":")[0] for p in (contact_points or ["localhost"])]
        
        self.cluster = Cluster(
            cleaned_points,
            port=port,
            protocol_version=5,  # Explicitly set protocol version for Cassandra 4.x
            load_balancing_policy=RoundRobinPolicy(),
        )
        
        # Retry connection until successful
        max_retries = 30
        retry_interval = 5
        
        for i in range(max_retries):
            try:
                self.session: Session = self.cluster.connect()
                print(f"Successfully connected to Cassandra at {cleaned_points}:{port}")
                return
            except NoHostAvailable as e:
                print(f"Waiting for Cassandra... ({i+1}/{max_retries})")
                time.sleep(retry_interval)
            except Exception as e:
                print(f"Unexpected error connecting to Cassandra: {e}")
                time.sleep(retry_interval)
        
        raise Exception("Could not connect to Cassandra after multiple retries")

    def execute(self, query, parameters=None):
        return self.session.execute(query, parameters)

    def prepare(self, query):
        return self.session.prepare(query)

    def shutdown(self):
        self.cluster.shutdown()


# Usage:
# client = CassandraClient(["localhost"], 9042)
# result = client.execute("SELECT * FROM dataset_manager.datasets LIMIT 1;")
