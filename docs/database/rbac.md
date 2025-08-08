# PostgreSQL RBAC Implementation Plan for Direct Read-Only Access

## Executive Summary

This plan implements role-based access control (RBAC) to allow users direct read-only access to DuckLake data through PostgreSQL, while maintaining full backend privileges and ensuring encrypted communication.

## Security Architecture

### Encryption & Communication Security

**SSL/TLS Encryption (REQUIRED)**
- All connections MUST use SSL/TLS encryption
- PostgreSQL configured with `ssl = on`
- Client certificates for enhanced security
- No plain text communication allowed

**Connection Security Configuration:**
```ini
# postgresql.conf
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
ssl_ca_file = 'ca.crt'
ssl_crl_file = 'root.crl'
ssl_prefer_server_ciphers = on
ssl_ciphers = 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384'
```

## Phase 1: Database Schema & Role Setup

### 1.1 Create Analytics Schema Structure

**Schema Design:**
```sql
-- Create dedicated schemas for different access levels
CREATE SCHEMA analytics;           -- Public analytical data
CREATE SCHEMA reporting;           -- Business reporting views
CREATE SCHEMA monitoring;          -- System metrics (limited access)

-- Set proper ownership
ALTER SCHEMA analytics OWNER TO postgres;
ALTER SCHEMA reporting OWNER TO postgres;
ALTER SCHEMA monitoring OWNER TO postgres;
```

**Data Organization:**
- `analytics`: Aggregated, non-sensitive data tables
- `reporting`: Pre-built business intelligence views
- `monitoring`: Queue metrics, job statistics
- `public`: Maintain existing application tables (backend-only access)

### 1.2 Implement Role Hierarchy

**Base Roles:**
```sql
-- Base read-only role (no direct assignment)
CREATE ROLE db_readonly;
GRANT CONNECT ON DATABASE ducklakedb TO db_readonly;

-- Analytics access role
CREATE ROLE data_analyst;
GRANT db_readonly TO data_analyst;
GRANT USAGE ON SCHEMA analytics TO data_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO data_analyst;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO data_analyst;

-- Business user role (limited views only)
CREATE ROLE business_user;
GRANT db_readonly TO business_user;
GRANT USAGE ON SCHEMA reporting TO business_user;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO business_user;

-- Power user role (broader access)
CREATE ROLE power_analyst;
GRANT data_analyst TO power_analyst;
GRANT USAGE ON SCHEMA monitoring TO power_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO power_analyst;

-- Individual user accounts
CREATE USER analyst1 PASSWORD 'secure_password';
GRANT data_analyst TO analyst1;

CREATE USER business1 PASSWORD 'secure_password';
GRANT business_user TO business1;
```

### 1.3 Row-Level Security (RLS) Implementation

**Tenant Isolation:**
```sql
-- Enable RLS on analytics tables
ALTER TABLE analytics.customer_data ENABLE ROW LEVEL SECURITY;

-- Create policies for multi-tenant access
CREATE POLICY tenant_isolation ON analytics.customer_data
FOR SELECT TO data_analyst
USING (tenant_id = current_setting('app.current_tenant', true));

-- Set tenant context in connection
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_name text)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant', tenant_name, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execution to roles
GRANT EXECUTE ON FUNCTION set_tenant_context(text) TO data_analyst;
```

**Time-Based Access Control:**
```sql
-- Restrict access to recent data for certain roles
CREATE POLICY recent_data_only ON analytics.transactions
FOR SELECT TO business_user
USING (created_at >= CURRENT_DATE - INTERVAL '30 days');
```

## Phase 2: Connection Management & Pooling

### 2.1 PgBouncer Configuration

**PgBouncer Setup:**
```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
# Read-only pool for analytics
analytics_db = host=localhost port=5432 dbname=ducklakedb user=pool_readonly
# Backend pool for application
backend_db = host=localhost port=5432 dbname=ducklakedb user=pool_backend

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction

# Connection limits per pool
max_client_conn = 200
default_pool_size = 25

# Read-only pool optimization
server_idle_timeout = 600
client_idle_timeout = 0
```

**Connection Pool Users:**
```txt
# /etc/pgbouncer/userlist.txt
"pool_readonly" "md5_hashed_password"
"pool_backend" "md5_hashed_password"
```

### 2.2 Connection Strings & Client Configuration

**Read-Only Connection String:**
```
postgresql://analyst1:password@pgbouncer:6432/analytics_db?sslmode=require&sslcert=client.crt&sslkey=client.key&sslrootcert=ca.crt
```

**Backend Connection String (existing):**
```
postgresql://backend_user:password@postgres:5432/ducklakedb?sslmode=require
```

### 2.3 Load Balancing (Optional)

**HAProxy Configuration:**
```
# /etc/haproxy/haproxy.cfg
global
    daemon

defaults
    mode tcp
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend postgres_frontend
    bind *:5433
    default_backend postgres_backend

backend postgres_backend
    balance roundrobin
    server pgbouncer1 localhost:6432 check
```

## Phase 3: Data Exposure Strategy

### 3.1 Analytics-Friendly Views

**Performance-Optimized Views:**
```sql
-- Create materialized views for heavy analytics
CREATE MATERIALIZED VIEW analytics.daily_metrics AS
SELECT 
    DATE_TRUNC('day', created_at) as day,
    tenant_id,
    COUNT(*) as total_transactions,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount
FROM public.transactions
GROUP BY DATE_TRUNC('day', created_at), tenant_id;

-- Create indexes on materialized views
CREATE INDEX idx_daily_metrics_day ON analytics.daily_metrics(day);
CREATE INDEX idx_daily_metrics_tenant ON analytics.daily_metrics(tenant_id);

-- Grant access to analytics role
GRANT SELECT ON analytics.daily_metrics TO data_analyst;

-- Refresh materialized view regularly (via cron job)
-- Refresh handled by backend application
```

**Real-Time Views:**
```sql
-- Live views for current data
CREATE VIEW analytics.live_queue_status AS
SELECT 
    queue_name,
    COUNT(*) as pending_messages,
    MAX(created_at) as last_message_time
FROM pgmq.q_lineage_events
GROUP BY queue_name;

GRANT SELECT ON analytics.live_queue_status TO power_analyst;
```

### 3.2 DuckDB Integration

**Foreign Data Wrapper Setup:**
```sql
-- Install and configure DuckDB FDW (requires extension)
CREATE EXTENSION IF NOT EXISTS duckdb_fdw;

-- Create foreign server
CREATE SERVER duckdb_analytics
FOREIGN DATA WRAPPER duckdb_fdw
OPTIONS (
    database '/data/analytics.duckdb',
    read_only 'true'
);

-- Create foreign tables
CREATE FOREIGN TABLE analytics.large_dataset (
    id BIGINT,
    timestamp TIMESTAMPTZ,
    data JSONB,
    metrics NUMERIC[]
) SERVER duckdb_analytics
OPTIONS (table 'processed_data');

-- Grant access
GRANT SELECT ON analytics.large_dataset TO data_analyst;
```

### 3.3 Performance Optimization

**Index Strategy:**
```sql
-- BRIN indexes for time-series data
CREATE INDEX CONCURRENTLY idx_transactions_time_brin 
ON public.transactions USING BRIN(created_at);

-- Partial indexes for analytical queries
CREATE INDEX CONCURRENTLY idx_active_transactions 
ON public.transactions(tenant_id, status) 
WHERE status IN ('completed', 'processed');

-- Expression indexes for common queries
CREATE INDEX CONCURRENTLY idx_daily_revenue 
ON public.transactions(DATE_TRUNC('day', created_at), tenant_id)
WHERE amount > 0;
```

## Phase 4: Security & Monitoring

### 4.1 Enhanced Access Control

**IP-Based Restrictions:**
```sql
# pg_hba.conf
# Backend connections (local/container network)
host    ducklakedb    backend_user    10.0.0.0/8         md5
host    ducklakedb    postgres        127.0.0.1/32       md5

# Read-only connections (specific IP ranges)
hostssl ducklakedb    data_analyst    192.168.1.0/24     md5 clientcert=1
hostssl ducklakedb    business_user   192.168.1.0/24     md5 clientcert=1
hostssl ducklakedb    power_analyst   10.10.0.0/16       md5 clientcert=1

# Deny all others
host    all           all             0.0.0.0/0           reject
```

**Certificate-Based Authentication:**
```bash
# Generate client certificates
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -out client.crt -days 365
```

### 4.2 Comprehensive Monitoring

**PostgreSQL Configuration:**
```ini
# Enhanced logging for read-only access
log_connections = on
log_disconnections = on
log_min_duration_statement = 1000
log_statement = 'all'
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

# Enable pgAudit for detailed tracking
shared_preload_libraries = 'pgaudit,pg_stat_statements'
pgaudit.log = 'read,write,function,role,ddl,misc'
pgaudit.log_catalog = off
pgaudit.log_parameter = on
```

**Query Monitoring:**
```sql
-- Monitor read-only user activity
CREATE VIEW monitoring.readonly_activity AS
SELECT 
    usename,
    datname,
    state,
    query_start,
    state_change,
    LEFT(query, 100) as query_preview
FROM pg_stat_activity 
WHERE usename IN ('analyst1', 'business1', 'power1');

GRANT SELECT ON monitoring.readonly_activity TO power_analyst;
```

### 4.3 Resource Limits & Query Timeouts

**Role-Based Limits:**
```sql
-- Set connection limits per role
ALTER ROLE data_analyst CONNECTION LIMIT 10;
ALTER ROLE business_user CONNECTION LIMIT 5;
ALTER ROLE power_analyst CONNECTION LIMIT 15;

-- Set statement timeout for analytical queries
ALTER ROLE data_analyst SET statement_timeout = '5min';
ALTER ROLE business_user SET statement_timeout = '2min';

-- Memory limits for complex queries
ALTER ROLE data_analyst SET work_mem = '256MB';
ALTER ROLE business_user SET work_mem = '64MB';
```

## Phase 5: Integration with Existing Systems

### 5.1 PGMQ Integration

**Queue Metrics Exposure:**
```sql
-- Create read-only access to queue archive data
CREATE VIEW analytics.queue_performance AS
SELECT 
    queue_name,
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as messages_processed,
    AVG(EXTRACT(EPOCH FROM (archived_at - created_at))) as avg_processing_time
FROM pgmq.a_lineage_events  -- Archive table
GROUP BY queue_name, DATE_TRUNC('hour', created_at);

GRANT SELECT ON analytics.queue_performance TO data_analyst;
```

### 5.2 OpenLineage Integration

**Lineage Queries for Analytics:**
```sql
-- Expose lineage graph for analytical queries
CREATE VIEW analytics.data_lineage AS
SELECT 
    j.name as job_name,
    r.run_id,
    r.state,
    d.name as dataset_name,
    lg.direction,
    r.started_at,
    r.ended_at
FROM openlineage.jobs j
JOIN openlineage.runs r ON j.id = r.job_id
JOIN openlineage.lineage_graph lg ON r.run_id = lg.run_id
JOIN openlineage.datasets d ON lg.dataset_id = d.id
WHERE r.state = 'COMPLETE';

GRANT SELECT ON analytics.data_lineage TO data_analyst;
```

### 5.3 Logging Integration

**Enhanced Log Queries:**
```sql
-- Create view for analyzing query patterns
CREATE VIEW monitoring.query_analytics AS
SELECT 
    usename,
    DATE_TRUNC('hour', query_start) as hour,
    COUNT(*) as query_count,
    AVG(EXTRACT(EPOCH FROM (now() - query_start))) as avg_duration,
    COUNT(CASE WHEN state = 'active' THEN 1 END) as active_queries
FROM pg_stat_activity 
WHERE usename LIKE '%analyst%' OR usename LIKE '%business%'
GROUP BY usename, DATE_TRUNC('hour', query_start);
```

## Implementation Timeline

### Week 1: Infrastructure Setup
- [ ] Configure SSL/TLS certificates
- [ ] Set up PgBouncer with connection pooling
- [ ] Create basic role hierarchy
- [ ] Implement IP-based access controls

### Week 2: Schema & Security
- [ ] Create analytics, reporting, monitoring schemas
- [ ] Implement Row-Level Security policies
- [ ] Set up comprehensive logging and monitoring
- [ ] Create initial analytics views

### Week 3: Data Exposure
- [ ] Migrate/copy appropriate data to analytics schema
- [ ] Create materialized views for performance
- [ ] Set up DuckDB Foreign Data Wrapper
- [ ] Implement query optimization indexes

### Week 4: Testing & Documentation
- [ ] Test all access scenarios and permissions
- [ ] Performance testing with analytical workloads
- [ ] Document connection procedures for users
- [ ] Create monitoring dashboards

## Security Considerations

### Encryption Status: **FULLY ENCRYPTED**
- All connections use SSL/TLS encryption
- Client certificate authentication
- Encrypted password storage (md5/scram-sha-256)
- No plain text communication

### Access Controls
- Role-based permissions with principle of least privilege
- Row-level security for multi-tenant isolation
- IP-based connection restrictions
- Connection limits and query timeouts

### Monitoring & Auditing
- Comprehensive connection and query logging
- pgAudit for detailed access tracking
- Real-time monitoring of read-only user activity
- Alert mechanisms for suspicious activity

## Maintenance Procedures

### Daily Tasks
- Monitor connection counts and query performance
- Check for failed authentication attempts
- Review slow query logs

### Weekly Tasks
- Refresh materialized views
- Analyze query patterns and optimize indexes
- Review access logs for anomalies

### Monthly Tasks
- Rotate SSL certificates if needed
- Review and update role permissions
- Performance tuning based on usage patterns

## Client Connection Examples

### Python (psycopg2/asyncpg)
```python
import asyncpg

# Encrypted connection with certificate
conn = await asyncpg.connect(
    host='pgbouncer.ducklake.local',
    port=6432,
    database='analytics_db',
    user='analyst1',
    password='secure_password',
    ssl='require',
    server_settings={
        'application_name': 'data_analysis_tool'
    }
)

# Set tenant context
await conn.execute("SELECT set_tenant_context('tenant_123')")

# Execute analytical query
result = await conn.fetch("""
    SELECT day, total_amount 
    FROM analytics.daily_metrics 
    WHERE day >= CURRENT_DATE - INTERVAL '30 days'
""")
```

### BI Tools (Tableau, PowerBI, etc.)
```
Connection Type: PostgreSQL
Server: pgbouncer.ducklake.local
Port: 6432
Database: analytics_db
Username: business1
Password: [encrypted]
SSL Mode: Require
```

This plan ensures secure, encrypted, direct access to analytical data while maintaining strict security boundaries and optimal performance.