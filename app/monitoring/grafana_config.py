"""
Grafana Dashboard Configurations for Release 2
API Performance, Infrastructure, and Business Metrics
"""

import json


# Grafana Dashboard: API Performance Monitoring
API_PERFORMANCE_DASHBOARD = {
    "dashboard": {
        "title": "Dataset Manager - API Performance",
        "description": "Real-time API performance and endpoint metrics",
        "timezone": "UTC",
        "refresh": "30s",
        "panels": [
            {
                "id": 1,
                "title": "Request Rate",
                "targets": [
                    {
                        "expr": "rate(http_requests_total[5m])",
                        "legendFormat": "{{method}} {{path}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
            },
            {
                "id": 2,
                "title": "Response Time (p95)",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)",
                        "legendFormat": "{{path}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
            },
            {
                "id": 3,
                "title": "Error Rate",
                "targets": [
                    {
                        "expr": 'rate(http_requests_total{status=~"5.."}[5m])',
                        "legendFormat": "{{path}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
            },
            {
                "id": 4,
                "title": "Active Requests",
                "targets": [
                    {"expr": "http_requests_in_progress", "legendFormat": "{{path}}"}
                ],
                "type": "graph",
                "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
            },
            {
                "id": 5,
                "title": "Dataset Upload Size Distribution",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, dataset_upload_bytes_bucket)",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 16, "w": 12, "h": 8},
            },
            {
                "id": 6,
                "title": "Top 10 Slowest Endpoints",
                "targets": [
                    {
                        "expr": "topk(10, histogram_quantile(0.95, http_request_duration_seconds_bucket))",
                        "legendFormat": "{{path}}",
                    }
                ],
                "type": "table",
                "gridPos": {"x": 12, "y": 16, "w": 12, "h": 8},
            },
        ],
    }
}

# Grafana Dashboard: Infrastructure Health
INFRASTRUCTURE_DASHBOARD = {
    "dashboard": {
        "title": "Dataset Manager - Infrastructure Health",
        "description": "Database, Cache, Storage, and Message Queue health",
        "timezone": "UTC",
        "refresh": "30s",
        "panels": [
            {
                "id": 1,
                "title": "Cassandra Connection Pool",
                "targets": [
                    {
                        "expr": "cassandra_connection_pool_size",
                        "legendFormat": "{{pool_name}}",
                    },
                    {
                        "expr": "cassandra_connection_active",
                        "legendFormat": "Active - {{pool_name}}",
                    },
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
            },
            {
                "id": 2,
                "title": "Redis Connection Status",
                "targets": [
                    {
                        "expr": "redis_connected_clients",
                        "legendFormat": "Connected Clients",
                    },
                    {"expr": "redis_used_memory_bytes", "legendFormat": "Memory Used"},
                ],
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
            },
            {
                "id": 3,
                "title": "Cache Hit Ratio",
                "targets": [
                    {
                        "expr": "cache_hits / (cache_hits + cache_misses)",
                        "legendFormat": "Hit Ratio",
                    }
                ],
                "type": "stat",
                "gridPos": {"x": 0, "y": 8, "w": 8, "h": 6},
            },
            {
                "id": 4,
                "title": "S3/MinIO Operations",
                "targets": [
                    {
                        "expr": "rate(s3_operations_total[5m])",
                        "legendFormat": "{{operation}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 8, "y": 8, "w": 16, "h": 8},
            },
            {
                "id": 5,
                "title": "Kafka Consumer Lag",
                "targets": [
                    {
                        "expr": "kafka_consumer_lag",
                        "legendFormat": "{{topic}} - {{partition}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 16, "w": 12, "h": 8},
            },
            {
                "id": 6,
                "title": "Kafka Message Throughput",
                "targets": [
                    {
                        "expr": "rate(kafka_messages_total[5m])",
                        "legendFormat": "{{topic}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 12, "y": 16, "w": 12, "h": 8},
            },
        ],
    }
}

# Grafana Dashboard: ETL Pipeline Monitoring
ETL_PIPELINE_DASHBOARD = {
    "dashboard": {
        "title": "Dataset Manager - ETL Pipeline",
        "description": "ETL job execution, throughput, and failure tracking",
        "timezone": "UTC",
        "refresh": "30s",
        "panels": [
            {
                "id": 1,
                "title": "Active ETL Jobs",
                "targets": [{"expr": "etl_jobs_active", "legendFormat": "{{dag_id}}"}],
                "type": "stat",
                "gridPos": {"x": 0, "y": 0, "w": 6, "h": 6},
            },
            {
                "id": 2,
                "title": "ETL Success Rate",
                "targets": [
                    {
                        "expr": "100 * (etl_jobs_success / etl_jobs_total)",
                        "legendFormat": "Success Rate",
                    }
                ],
                "type": "gauge",
                "gridPos": {"x": 6, "y": 0, "w": 6, "h": 6},
            },
            {
                "id": 3,
                "title": "ETL Job Duration",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, etl_duration_seconds_bucket)",
                        "legendFormat": "p95 - {{dag_id}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
            },
            {
                "id": 4,
                "title": "Rows Processed Per Minute",
                "targets": [
                    {
                        "expr": "rate(etl_rows_processed[1m])",
                        "legendFormat": "{{dag_id}}",
                    }
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
            },
            {
                "id": 5,
                "title": "ETL Failure Breakdown",
                "targets": [{"expr": "etl_jobs_failed", "legendFormat": "{{reason}}"}],
                "type": "piechart",
                "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
            },
            {
                "id": 6,
                "title": "Data Quality Score",
                "targets": [
                    {"expr": "etl_data_quality_score", "legendFormat": "{{dataset_id}}"}
                ],
                "type": "graph",
                "gridPos": {"x": 0, "y": 16, "w": 24, "h": 8},
            },
        ],
    }
}

# Alert Rules
ALERT_RULES = {
    "groups": [
        {
            "name": "api_alerts",
            "interval": "30s",
            "rules": [
                {
                    "alert": "HighAPIErrorRate",
                    "expr": 'rate(http_requests_total{status=~"5.."}[5m]) > 0.05',
                    "for": "5m",
                    "annotations": {
                        "summary": "High API error rate",
                        "description": "Error rate exceeds 5% for more than 5 minutes",
                    },
                },
                {
                    "alert": "HighResponseLatency",
                    "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket) > 0.5",
                    "for": "5m",
                    "annotations": {
                        "summary": "High API response latency",
                        "description": "p95 latency exceeds 500ms",
                    },
                },
                {
                    "alert": "RateLimiterExceeded",
                    "expr": "increase(rate_limit_exceeded_total[5m]) > 100",
                    "for": "2m",
                    "annotations": {
                        "summary": "Rate limiter frequently exceeded",
                        "description": "More than 100 rate limit violations in 5 minutes",
                    },
                },
            ],
        },
        {
            "name": "infrastructure_alerts",
            "interval": "30s",
            "rules": [
                {
                    "alert": "CassandraConnectionPoolExhausted",
                    "expr": "cassandra_connection_available == 0",
                    "for": "2m",
                    "annotations": {
                        "summary": "Cassandra connection pool exhausted",
                        "description": "All connections in pool are in use",
                    },
                },
                {
                    "alert": "RedisHighMemory",
                    "expr": "redis_used_memory_bytes / redis_max_memory_bytes > 0.9",
                    "for": "5m",
                    "annotations": {
                        "summary": "Redis memory usage critical",
                        "description": "Redis memory usage exceeds 90%",
                    },
                },
                {
                    "alert": "CacheLowHitRatio",
                    "expr": "(cache_hits / (cache_hits + cache_misses)) < 0.7",
                    "for": "10m",
                    "annotations": {
                        "summary": "Cache hit ratio below target",
                        "description": "Cache hit ratio below 70%",
                    },
                },
                {
                    "alert": "KafkaConsumerLagHigh",
                    "expr": "kafka_consumer_lag > 10000",
                    "for": "5m",
                    "annotations": {
                        "summary": "High Kafka consumer lag",
                        "description": "Consumer lag exceeds 10,000 messages",
                    },
                },
            ],
        },
        {
            "name": "etl_alerts",
            "interval": "30s",
            "rules": [
                {
                    "alert": "ETLJobFailure",
                    "expr": "increase(etl_jobs_failed[10m]) > 0",
                    "for": "1m",
                    "annotations": {
                        "summary": "ETL job failed",
                        "description": "One or more ETL jobs have failed",
                    },
                },
                {
                    "alert": "ETLLowThroughput",
                    "expr": "rate(etl_rows_processed[5m]) < 100000",
                    "for": "10m",
                    "annotations": {
                        "summary": "ETL throughput below target",
                        "description": "ETL processing rate below 100k rows/min",
                    },
                },
                {
                    "alert": "ETLDataQualityIssue",
                    "expr": "etl_data_quality_score < 0.8",
                    "for": "5m",
                    "annotations": {
                        "summary": "Data quality issues detected",
                        "description": "Data quality score below 80%",
                    },
                },
            ],
        },
    ]
}


def export_dashboard_json(dashboard_config: dict, filename: str):
    """Export dashboard configuration to JSON file"""
    with open(filename, "w") as f:
        json.dump(dashboard_config, f, indent=2)
    print(f"Dashboard exported to {filename}")


def export_alert_rules_yaml(alert_rules: dict, filename: str):
    """Export alert rules to YAML format"""
    import yaml

    with open(filename, "w") as f:
        yaml.dump(alert_rules, f, default_flow_style=False)
    print(f"Alert rules exported to {filename}")


# Generate setup instructions
GRAFANA_SETUP_INSTRUCTIONS = """
# Grafana Setup Instructions for Release 2

## 1. Add Prometheus Datasource

1. Open Grafana: http://localhost:3000
2. Login: admin / admin
3. Go to Configuration → Datasources
4. Click "Add Datasource"
5. Select "Prometheus"
6. URL: http://prometheus:9090
7. Click "Save & Test"

## 2. Import Dashboards

### API Performance Dashboard
```bash
# Export dashboard JSON
python -c "from monitoring.grafana_config import API_PERFORMANCE_DASHBOARD; \
from monitoring.grafana_config import export_dashboard_json; \
export_dashboard_json(API_PERFORMANCE_DASHBOARD, 'api-dashboard.json')"
```

1. Grafana → Create → Import
2. Upload api-dashboard.json
3. Select Prometheus datasource
4. Click "Import"

### Infrastructure Dashboard
```bash
python -c "from monitoring.grafana_config import INFRASTRUCTURE_DASHBOARD; \
from monitoring.grafana_config import export_dashboard_json; \
export_dashboard_json(INFRASTRUCTURE_DASHBOARD, 'infra-dashboard.json')"
```

### ETL Pipeline Dashboard
```bash
python -c "from monitoring.grafana_config import ETL_PIPELINE_DASHBOARD; \
from monitoring.grafana_config import export_dashboard_json; \
export_dashboard_json(ETL_PIPELINE_DASHBOARD, 'etl-dashboard.json')"
```

## 3. Configure Alert Rules

1. Save alert rules: alerts.yaml
2. Update Prometheus config to include:
   ```yaml
   rule_files:
     - "alerts.yaml"
   ```
3. Restart Prometheus
4. Verify rules in Prometheus UI: http://localhost:9090/alerts

## 4. Setup Alert Notifications

1. Grafana → Alerting → Notification Channels
2. Create notification channel (Email, Slack, PagerDuty, etc.)
3. Test notification
4. Assign to alert policies

## Expected Metrics in Prometheus

### API Metrics
- http_requests_total
- http_request_duration_seconds
- http_requests_in_progress
- dataset_upload_bytes

### Infrastructure Metrics
- cassandra_connection_pool_size
- redis_connected_clients
- cache_hits, cache_misses
- s3_operations_total

### ETL Metrics
- etl_jobs_active
- etl_jobs_success
- etl_jobs_failed
- etl_rows_processed
- etl_duration_seconds
- etl_data_quality_score

### Kafka Metrics
- kafka_consumer_lag
- kafka_messages_total

## Quick Test

```bash
# Check if metrics are being collected
curl http://localhost:9090/api/v1/query?query=http_requests_total

# View alert status
curl http://localhost:9090/api/v1/alerts
```

## Troubleshooting

- Metrics not showing? Check prometheus scrape config
- Dashboard empty? Verify Prometheus datasource connection
- Alerts not firing? Check alert rule syntax in Prometheus UI
"""


if __name__ == "__main__":
    print(GRAFANA_SETUP_INSTRUCTIONS)
