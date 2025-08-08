# PGMQ Performance Configuration Guide

This guide outlines the PostgreSQL configuration optimizations for PGMQ (PostgreSQL Message Queue) in the DuckLake project, designed to achieve high-throughput message processing.

## Performance Targets

- **Development**: 1,000-5,000 messages/second
- **Production**: 30,000+ messages/second
- **Latency**: Sub-second event processing
- **Reliability**: Exactly-once delivery with retry capability

## Configuration Overview

### Memory Configuration

#### Development (3-4GB memory)
```ini
shared_buffers = '2GB'          # 75% of available memory (aggressive for MQ)
work_mem = '64MB'               # Per operation memory
maintenance_work_mem = '512MB'  # Vacuum/index operations
effective_cache_size = '2GB'    # OS cache assumption
```

#### Production (16GB memory)
```ini
shared_buffers = '12GB'         # 75% of available memory (3x typical)
work_mem = '128MB'              # Higher per operation memory
maintenance_work_mem = '2GB'    # Large vacuum/index operations
effective_cache_size = '12GB'   # Aggressive OS cache assumption
temp_buffers = '32MB'           # Temporary table buffers
```

### Autovacuum Configuration

**Critical for PGMQ Performance** - Message queues create high table churn requiring aggressive cleanup:

#### Development
```ini
autovacuum_vacuum_scale_factor = 0.01    # Very aggressive (vs 0.2 default)
autovacuum_analyze_scale_factor = 0.005  # Very aggressive (vs 0.1 default)
autovacuum_vacuum_threshold = 25         # Vacuum after 25 dead tuples
autovacuum_naptime = '15s'               # Check more frequently
```

#### Production
```ini
autovacuum_vacuum_scale_factor = 0.005   # Ultra aggressive
autovacuum_analyze_scale_factor = 0.002  # Ultra aggressive
autovacuum_vacuum_threshold = 10         # Vacuum after 10 dead tuples
autovacuum_naptime = '10s'               # Very frequent checks
autovacuum_max_workers = 12              # Scale with high workload
autovacuum_work_mem = '1GB'              # Large memory for autovacuum
```

### I/O Optimization

#### SSD-Optimized Settings
```ini
random_page_cost = 1.0                   # High-performance SSD
seq_page_cost = 1.0                      # Sequential scan baseline
effective_io_concurrency = 1000          # High-end SSD concurrent I/O
maintenance_io_concurrency = 100         # Maintenance operation I/O
```

### WAL and Checkpoint Tuning

#### Write-Heavy Workload Optimization
```ini
wal_buffers = '256MB'                    # Large WAL buffer (production)
max_wal_size = '8GB'                     # Large WAL size (production)
checkpoint_completion_target = 0.9       # Spread checkpoint I/O
synchronous_commit = off                 # Async commit for performance
wal_compression = on                     # Compress WAL records
```

## PGMQ-Specific Configuration

### Required Extensions
```sql
-- Essential for PGMQ partition management
shared_preload_libraries = 'pg_partman_bgw,pg_stat_statements'
pg_partman_bgw.interval = 60
pg_partman_bgw.role = 'postgres'
pg_partman_bgw.dbname = 'ducklakedb'
```

### Queue-Specific Table Tuning
```sql
-- Ultra-aggressive autovacuum for queue tables
ALTER TABLE pgmq.q_lineage_events SET (
    autovacuum_vacuum_scale_factor = 0.001,
    autovacuum_analyze_scale_factor = 0.0005,
    autovacuum_vacuum_threshold = 5,
    autovacuum_vacuum_cost_limit = 10000
);
```

## Performance Monitoring

### Key Metrics to Monitor

#### Queue Performance
```sql
-- Queue depth and processing rate
SELECT queue_name, queue_length, total_messages 
FROM pgmq.metrics_all();

-- Dead letter queue monitoring
SELECT msg_id, message, enqueued_at 
FROM pgmq.q_lineage_events_dlq 
ORDER BY enqueued_at DESC LIMIT 10;
```

#### Database Performance
```sql
-- Autovacuum activity monitoring
SELECT schemaname, tablename, last_vacuum, last_autovacuum,
       n_dead_tup, n_live_tup
FROM pg_stat_user_tables 
WHERE schemaname IN ('pgmq', 'openlineage')
ORDER BY n_dead_tup DESC;

-- Top slow queries
SELECT query, calls, total_time, mean_time, rows
FROM pg_stat_statements 
ORDER BY total_time DESC LIMIT 10;
```

#### System Resource Usage
```sql
-- Connection and memory usage
SELECT count(*) as active_connections,
       sum(CASE WHEN state = 'active' THEN 1 ELSE 0 END) as active_queries
FROM pg_stat_activity;

-- Buffer cache hit ratio (should be >99%)
SELECT round(
  100.0 * sum(blks_hit) / sum(blks_hit + blks_read), 2
) as cache_hit_ratio
FROM pg_stat_database;
```

## Hardware Recommendations

### Development Environment
- **Memory**: 3-4GB minimum
- **CPU**: 2-4 cores
- **Storage**: SSD with 1000+ IOPS
- **Network**: 1Gbps

### Production Environment
- **Memory**: 16GB+ (to support 12GB shared_buffers)
- **CPU**: 8+ cores (for parallel processing)
- **Storage**: High-performance SSD with 3000+ IOPS
- **Network**: 10Gbps for high-throughput

## Troubleshooting Common Issues

### High Queue Depth
```sql
-- Check for stuck messages
SELECT msg_id, enqueued_at, read_ct 
FROM pgmq.q_lineage_events 
WHERE read_ct > 5 
ORDER BY enqueued_at;

-- Monitor worker processing
SELECT count(*) as processing_workers
FROM pg_stat_activity 
WHERE query LIKE '%pgmq.read%';
```

### Table Bloat
```sql
-- Check table bloat ratio
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
       n_dead_tup, n_live_tup,
       round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2) as dead_ratio
FROM pg_stat_user_tables 
WHERE n_live_tup > 0
ORDER BY dead_ratio DESC;
```

### Performance Degradation
```sql
-- Check for lock contention
SELECT locktype, database, relation, mode, granted
FROM pg_locks 
WHERE NOT granted;

-- Monitor checkpoint frequency
SELECT checkpoint_timed, checkpoint_req, checkpoint_write_time, checkpoint_sync_time
FROM pg_stat_bgwriter;
```

## Deployment Configuration

### Local Development
Use the standard `postgres-values.yaml` with development-optimized settings:
```bash
make deploy-kind
```

### Production
Use the production configuration with higher resource allocation:
```bash
PROD_CONTEXT=production-cluster make deploy-prod
```

## Performance Testing

### Message Throughput Test
```python
import asyncio
import time
from app.lineage import lineage_manager

async def test_throughput():
    start_time = time.time()
    tasks = []
    
    for i in range(10000):
        event = await lineage_manager.create_job_start_event(
            job_name=f"test-job-{i % 100}",
            run_id=uuid.uuid4()
        )
        tasks.append(lineage_manager.enqueue_event(event))
    
    await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    throughput = 10000 / duration
    print(f"Throughput: {throughput:.0f} messages/second")

# Run: python -c "import asyncio; asyncio.run(test_throughput())"
```

### Load Testing with Queue Workers
```bash
# Monitor queue processing during load test
watch -n 1 "psql -c \"SELECT queue_name, queue_length FROM pgmq.metrics_all()\""

# Monitor system resources
htop
iostat -x 1
```

## Best Practices

1. **Memory Sizing**: Allocate 75% of available RAM to shared_buffers for queue workloads
2. **Autovacuum**: Use ultra-aggressive settings (10-100x more frequent than default)
3. **Storage**: Use high-IOPS SSD storage with at least 3000 provisioned IOPS
4. **Monitoring**: Set up continuous monitoring of queue depth and processing rates
5. **Scaling**: Scale horizontally with multiple queue workers rather than vertical scaling
6. **Retention**: Configure appropriate queue retention policies to prevent unbounded growth
7. **Dead Letter Queues**: Monitor and alert on DLQ accumulation for error detection

## Configuration Files

- **Development**: `/k8s/postgres-values.yaml`
- **Production**: `/k8s/prod/postgres-values.yaml`
- **Monitoring**: Use Loki/Promtail for log aggregation and analysis

For questions or issues, refer to the [PGMQ GitHub repository](https://github.com/pgmq/pgmq) or the [Tembo PGMQ documentation](https://tembo.io/pgmq/).