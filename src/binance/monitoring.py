from prometheus_client import Counter, Gauge, Histogram

# Kafka Metrics
price_updates = Counter(
    'kafka_price_updates_total',
    'Total messages processed in price_updates topic',
    ['topic']
)

signals = Counter(
    'kafka_signals_total',
    'Total messages processed in signals topic',
    ['topic']
)

# System Metrics
latency = Histogram(
    'app_latency_seconds',
    'Latency of key operations',
    ['operation']
)

errors = Counter(
    'app_errors_total',
    'Total errors encountered',
    ['type']
)

# Resource Metrics
cpu_usage = Gauge(
    'app_cpu_usage_percent',
    'Current CPU usage percentage'
)

memory_usage = Gauge(
    'app_memory_usage_bytes',
    'Current memory usage in bytes'
)