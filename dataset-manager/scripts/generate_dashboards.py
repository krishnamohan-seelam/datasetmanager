import json
import os
import sys

# Add the app directory to sys.path to import monitoring.grafana_config
sys.path.append(os.path.join(os.getcwd(), 'app'))

try:
    from app.monitoring.grafana_config import (
        API_PERFORMANCE_DASHBOARD,
        INFRASTRUCTURE_DASHBOARD,
        ETL_PIPELINE_DASHBOARD
    )
except ImportError:
    # Fallback if pathing is different
    from monitoring.grafana_config import (
        API_PERFORMANCE_DASHBOARD,
        INFRASTRUCTURE_DASHBOARD,
        ETL_PIPELINE_DASHBOARD
    )

def save_dashboard(config, filename):
    path = os.path.join('monitoring', 'grafana', 'provisioning', 'dashboards', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        # The config in grafana_config.py is wrapped in a "dashboard" key
        json.dump(config['dashboard'], f, indent=2)
    print(f"Exported {filename}")

if __name__ == "__main__":
    save_dashboard(API_PERFORMANCE_DASHBOARD, 'api-performance.json')
    save_dashboard(INFRASTRUCTURE_DASHBOARD, 'infrastructure-health.json')
    save_dashboard(ETL_PIPELINE_DASHBOARD, 'etl-pipeline.json')
