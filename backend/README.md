# DuckLake Backend

FastAPI-based backend service for DuckLake data platform with DuckDB, MinIO, and OpenLineage integration.

## 🚀 Quick Start

### Local Development with Docker Compose
```bash
# Build and run all services
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f ducklake-backend

# Stop services
docker-compose down
```

### Local Development with Python
```bash
# Install dependencies (from project root)
uv sync

# Run the application
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 Project Structure

```
backend/
├── app/                    # Application code
│   ├── main.py            # FastAPI application entry point
│   ├── config.py          # Configuration management
│   ├── lineage.py         # OpenLineage integration
│   ├── queue_worker.py    # Async queue processing
│   ├── exceptions.py      # Custom exception handling
│   ├── resilience.py      # Circuit breakers and retry logic
│   ├── config_monitor.py  # Configuration monitoring
│   ├── instrumentation/   # Memory and performance monitoring
│   │   ├── __init__.py
│   │   ├── memory.py      # Memory usage tracking
│   │   └── performance.py # Performance metrics
│   └── routers/           # API route modules
│       └── lineage.py     # Lineage-specific endpoints
├── Dockerfile             # Production Docker build
├── docker-compose.yml     # Local development stack
├── .dockerignore          # Docker build exclusions
├── build.sh              # Docker build script
└── README.md             # This file
```

## 🔧 Configuration

Configuration is managed via environment variables. See `.env.example` in the project root for all options.

### Key Environment Variables

#### Application
- `ENVIRONMENT`: `development`, `staging`, `production`
- `DEBUG`: `true` or `false`
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`

#### Database (PostgreSQL - DuckLake Catalog)
- `DB_POSTGRES_HOST`: PostgreSQL hostname
- `DB_POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `DB_POSTGRES_DB`: Database name
- `DB_POSTGRES_USER`: Database username
- `DB_POSTGRES_PASSWORD`: Database password

#### DuckLake Configuration
- `DB_DUCKLAKE_ENCRYPTED`: Enable encryption for data storage
- `DB_DUCKLAKE_DATA_INLINING_ROW_LIMIT`: Row limit for data inlining optimization
- `DB_DUCKLAKE_CONNECTION_RETRIES`: Number of connection retry attempts
- `DB_DUCKLAKE_CONNECTION_TIMEOUT`: Connection timeout in seconds

#### Storage (MinIO/S3 - DuckLake Data)
- `STORAGE_MINIO_ENDPOINT`: MinIO server endpoint
- `STORAGE_MINIO_ACCESS_KEY`: MinIO access key
- `STORAGE_MINIO_SECRET_KEY`: MinIO secret key
- `STORAGE_MINIO_SECURE`: Use HTTPS for MinIO connections
- `STORAGE_DEFAULT_BUCKET`: Default bucket for data storage

#### Feature Flags
- `FEATURE_ENABLE_MEMORY_MONITORING`: Enable memory monitoring
- `FEATURE_ENABLE_PERFORMANCE_TRACKING`: Enable performance tracking
- `FEATURE_ENABLE_PROMETHEUS_METRICS`: Enable Prometheus metrics
- `FEATURE_ENABLE_S3_ENCRYPTION`: Enable S3 encryption

## 🐳 Docker

### Build Image
```bash
# Using build script (recommended)
./build.sh v1.0.2

# Or manually
docker build -t ducklake-backend:v1.0.2 .
```

### Run Container
```bash
# Run with default configuration
docker run -p 8000:8000 ducklake-backend:v1.0.2

# Run with custom environment
docker run -p 8000:8000 \
  -e ENVIRONMENT=development \
  -e DB_POSTGRES_HOST=localhost \
  -e STORAGE_MINIO_ENDPOINT=localhost:9000 \
  ducklake-backend:v1.0.2
```

## ☸️ Kubernetes Deployment

### Prerequisites
- Kubernetes cluster
- PostgreSQL database
- MinIO/S3 storage
- Secrets configured

### Deploy to Kubernetes
```bash
# Apply secrets
kubectl apply -f ../k8s/postgres-credentials.yaml

# Deploy backend
kubectl apply -f ../k8s/backend-deployment.yaml
kubectl apply -f ../k8s/backend-service.yaml

# Check deployment status
kubectl get pods -l app=ducklake-backend
kubectl logs -f deployment/ducklake-backend
```

### Kubernetes Configuration

The deployment includes:
- **3 replicas** for high availability
- **Resource limits**: 512Mi memory, 500m CPU
- **Security context**: Non-root user, restricted capabilities
- **Health checks**: Startup, liveness, and readiness probes
- **Pod anti-affinity**: Distributes pods across nodes
- **Volume mounts**: Logs and data directories

## 🔍 API Endpoints

### Health and Monitoring
- `GET /` - Root endpoint
- `GET /health` - Comprehensive health check
- `GET /metrics/memory` - Memory usage metrics
- `GET /metrics/performance` - Performance metrics
- `POST /metrics/gc` - Force garbage collection

### Configuration
- `GET /config/summary` - Configuration summary (without secrets)
- `GET /config/validate` - Validate current configuration
- `GET /config/features` - Feature flags status
- `GET /config/ducklake` - DuckLake configuration and status
- `POST /config/ducklake/reconnect` - Reconnect to DuckLake

### DuckLake Tables
- `POST /tables` - Create new table
- `GET /tables` - List all tables
- `GET /tables/{table_name}` - Get table schema
- `PUT /tables/{table_name}` - Append data to table
- `DELETE /tables/{table_name}` - Delete table
- `POST /tables/{table_name}/query` - Query table with content negotiation

### Data Storage (MinIO)
- `POST /datasets/{bucket_name}` - Create bucket
- `GET /datasets/{bucket_name}` - List objects in bucket
- `PUT /datasets/{bucket_name}/{object_name}` - Upload object
- `GET /datasets/{bucket_name}/{object_name}` - Download object
- `DELETE /datasets/{bucket_name}/{object_name}` - Delete object

### Job Lineage (OpenLineage)
- `POST /jobs` - Create job definition
- `GET /jobs` - List all jobs
- `GET /jobs/{job_name}` - Get job details
- `POST /jobs/{job_name}/runs` - Start job run
- `PUT /jobs/{job_name}/runs/{run_id}/complete` - Complete job run
- `GET /jobs/{job_name}/runs/{run_id}` - Get job run details

## 🔌 Server-Sent Events (SSE) Endpoints

Real-time event streaming for monitoring lineage processing, job status, queue metrics, and system events.

### Event Stream Endpoints

| Endpoint | Description | Event Types |
|----------|-------------|-------------|
| `GET /events/stream` | All events stream with optional filtering | All event types |
| `GET /events/lineage` | Lineage events only | `lineage_event`, `error` |
| `GET /events/jobs` | Job status events only | `job_status`, `error` |
| `GET /events/metrics` | System metrics and queue status | `system_metric`, `queue_status`, `error` |

### Event Types

- **`lineage_event`**: OpenLineage event processing (START, COMPLETE, FAIL)
- **`job_status`**: Job run status updates (starting, running, completed, failed)
- **`queue_status`**: Queue metrics and processing statistics
- **`system_metric`**: System performance and health metrics
- **`error`**: Error events from various components
- **`heartbeat`**: Connection keepalive events

### SSE Usage Examples

#### JavaScript Client
```javascript
// Connect to all events
const eventSource = new EventSource('/events/stream');

// Connect to specific event types
const eventSource = new EventSource('/events/stream?events=lineage_event,job_status');

// Listen for specific event types
eventSource.addEventListener('lineage_event', function(event) {
    const data = JSON.parse(event.data);
    console.log('Lineage event:', data);
});

eventSource.addEventListener('job_status', function(event) {
    const data = JSON.parse(event.data);
    console.log('Job status:', data);
});
```

#### cURL Example
```bash
# Stream all events
curl -N -H "Accept: text/event-stream" http://localhost:8000/events/stream

# Stream specific events
curl -N -H "Accept: text/event-stream" "http://localhost:8000/events/stream?events=lineage_event,job_status"
```

### SSE Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /events/stats` | GET | Get SSE connection statistics |
| `POST /events/broadcast` | POST | Broadcast custom event (testing) |
| `DELETE /events/clients/{client_id}` | DELETE | Disconnect specific client |
| `GET /events/zombies` | GET | Get zombie detection statistics |
| `POST /events/pong` | POST | Handle pong response from client |
| `POST /events/zombies/cleanup` | POST | Force cleanup of zombie clients |

### Zombie Client Detection

The SSE system includes comprehensive zombie client detection to identify and manage dead connections:

#### Detection Methods

1. **Write Detection**: Catches broken pipe errors when writing to disconnected clients
2. **Ping/Pong Mechanism**: Sends periodic ping events expecting pong responses
3. **Queue Health Monitoring**: Detects clients with consistently full queues
4. **Connection Timeout**: Basic timeout detection for inactive connections
5. **Missed Ping Tracking**: Counts consecutive missed ping responses

#### Detection Criteria

A client is marked as zombie when:
- **Write Errors**: More than 3 consecutive write failures
- **Missed Pings**: More than 3 consecutive missed ping responses
- **Queue Full**: Queue consistently full for 10+ events
- **Timeout**: No activity for 2+ minutes
- **No Pong Response**: No pong received within 90 seconds of first ping

#### Zombie Statistics

```json
{
  "current_zombies": 2,
  "total_detected": 15,
  "detection_reasons": {
    "write_errors": 5,
    "missed_pings": 3,
    "queue_consistently_full": 4,
    "timeout": 2,
    "no_pong_response": 1
  },
  "last_cleanup": 1647123456.789,
  "zombie_details": [...]
}
```

#### Client Health Monitoring

Each client tracks:
- **Connection Health**: Overall health status
- **Ping/Pong Counters**: Communication statistics
- **Error Tracking**: Write errors and queue issues
- **Zombie Status**: Detection timestamp and reason

### Event Format

All SSE events follow this format:
```
id: <unique-event-id>
event: <event-type>
data: {"timestamp": <unix-timestamp>, "data": <event-data>}
```

### Testing SSE

1. **HTML Test Page**: Open `sse_test.html` in a browser for interactive testing
2. **Command Line**: Use cURL to stream events
3. **Custom Scripts**: Use the `/events/broadcast` endpoint to send test events

### Real-time Monitoring

The SSE implementation provides real-time monitoring for:

- **Lineage Processing**: Track OpenLineage events as they're processed
- **Job Execution**: Monitor job runs from start to completion
- **Queue Health**: Watch queue processing metrics and backlogs
- **System Performance**: Stream system metrics and health data
- **Error Tracking**: Immediate notification of processing errors

## 🛠️ Development

### Prerequisites
- Python 3.10+
- uv package manager
- Docker & Docker Compose
- PostgreSQL (for local development)
- MinIO (for local development)

### Setup Development Environment
```bash
# From project root
uv sync

# Start dependencies
cd backend
docker-compose up postgres minio -d

# Run application
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Code Quality
```bash
# Run linting
uv run ruff check app/

# Run type checking
uv run mypy app/

# Format code
uv run ruff format app/

# Run tests (when added)
uv run pytest
```

### Testing
```bash
# Run unit tests
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=app tests/
```

## 📊 Monitoring and Observability

### Structured Logging
- JSON formatted logs with loguru
- Request IDs for tracing
- Structured context in all log messages

### Memory Monitoring
- Real-time memory usage tracking
- Garbage collection metrics
- Memory leak detection
- Component-specific allocations

### Performance Tracking
- Request timing middleware
- Database query performance
- MinIO operation latency
- Throughput calculations (RPS)

### Prometheus Metrics
- HTTP request metrics
- Database operation metrics
- Memory usage metrics
- Custom business metrics

## 🚨 Troubleshooting

### Common Issues

#### DuckLake Connection Failed
```bash
# Check PostgreSQL connectivity
curl http://localhost:8000/config/ducklake

# Reconnect to DuckLake
curl -X POST http://localhost:8000/config/ducklake/reconnect
```

#### MinIO Access Issues
```bash
# Check MinIO credentials
kubectl get secret minio-credentials -o yaml

# Verify MinIO connectivity
kubectl exec -it deployment/ducklake-backend -- curl -f http://minio-service:9000/minio/health/live
```

#### Performance Issues
```bash
# Check memory usage
curl http://localhost:8000/metrics/memory

# Check performance metrics
curl http://localhost:8000/metrics/performance

# Force garbage collection
curl -X POST http://localhost:8000/metrics/gc
```

### Log Analysis
```bash
# View application logs
kubectl logs -f deployment/ducklake-backend

# Filter for errors
kubectl logs deployment/ducklake-backend | grep ERROR

# Follow logs with timestamps
kubectl logs -f deployment/ducklake-backend --timestamps=true
```

## 🔐 Security

### Production Security Checklist
- [ ] Change default passwords in secrets
- [ ] Enable TLS for all external connections
- [ ] Use strong, unique passwords
- [ ] Enable S3 encryption
- [ ] Configure network policies
- [ ] Regular security updates
- [ ] Audit logging enabled

### Secret Management
```bash
# Create production secrets
kubectl create secret generic postgres-credentials \
  --from-literal=username=postgres \
  --from-literal=password='your-strong-password'

kubectl create secret generic minio-credentials \
  --from-literal=accesskey='your-access-key' \
  --from-literal=secretkey='your-secret-key'
```

## 📈 Scaling

### Horizontal Scaling
```bash
# Scale deployment
kubectl scale deployment ducklake-backend --replicas=5

# Check scaling status
kubectl get pods -l app=ducklake-backend
```

### Vertical Scaling
```yaml
# Update resources in deployment
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

## 🔄 Updates and Deployment

### Rolling Updates
```bash
# Update image
kubectl set image deployment/ducklake-backend ducklake-backend=ducklake-backend:v1.0.3

# Check rollout status
kubectl rollout status deployment/ducklake-backend

# Rollback if needed
kubectl rollout undo deployment/ducklake-backend
```

### Blue-Green Deployment
```bash
# Deploy new version alongside old
kubectl apply -f backend-deployment-v2.yaml

# Switch traffic
kubectl patch service ducklake-backend-service -p '{"spec":{"selector":{"version":"v1.0.3"}}}'
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckLake Documentation](https://ducklake.select/docs/)
- [MinIO Documentation](https://docs.min.io/)
- [OpenLineage Documentation](https://openlineage.io/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/) 