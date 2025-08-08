# 🌊 DuckLake API Organization & Synthwave Theme

## 📋 Overview

The DuckLake API has been reorganized into logical groups with custom Synthwave theming that matches your frontend. The API documentation now features a retro cyberpunk aesthetic with neon colors and smooth animations.

## 🎯 API Organization

### 1. **🔧 Admin** (`/admin/*`)
**Router**: `app/routers/admin.py`
**Purpose**: System administration, health checks, and configuration

**Key Endpoints:**
- `GET /admin/health` - 🩺 System Health Check
- `GET /admin/metrics/memory` - Memory usage metrics
- `GET /admin/metrics/performance` - Performance statistics
- `POST /admin/metrics/gc` - Force garbage collection
- `GET /admin/config/summary` - Configuration summary
- `GET /admin/config/validate` - Validate configuration
- `GET /admin/config/features` - Feature flags status
- `GET /admin/config/ducklake` - DuckLake configuration
- `POST /admin/config/ducklake/reconnect` - Reconnect to DuckLake

### 2. **🚀 Jobs & Events** (`/events/*`)
**Router**: `app/routers/jobs_events.py`
**Purpose**: Job management, real-time events, and lineage tracking

**Key Endpoints:**
- `GET /events/stream` - 📡 Stream Real-time Events (SSE)
- `GET /events/lineage` - Stream lineage events
- `GET /events/jobs` - Stream job status events
- `GET /events/metrics` - Stream system metrics
- `POST /events/jobs` - ⚙️ Create Job Definition
- `POST /events/jobs/{job_name}/runs` - Start job run
- `PUT /events/jobs/{job_name}/runs/{run_id}/complete` - Complete job run
- `GET /events/jobs/{job_name}` - Get job metadata
- `POST /events/broadcast` - Broadcast custom events
- `GET /events/zombies` - Zombie client statistics

### 3. **📊 Tables & Datasets** (`/data/*`)
**Router**: `app/routers/tables_datasets.py`
**Purpose**: DuckLake table operations, MinIO datasets, and query execution

**Key Endpoints:**
- `GET /data/tables` - 📋 List DuckLake Tables
- `POST /data/tables` - 🆕 Create DuckLake Table
- `GET /data/tables/{table_name}` - Get table schema
- `PUT /data/tables/{table_name}` - Append data to table
- `DELETE /data/tables/{table_name}` - Delete table
- `POST /data/tables/{table_name}/query` - 🔍 Query DuckLake Table
- `GET /data/datasets/{bucket_name}` - List MinIO objects
- `POST /data/datasets/{bucket_name}` - Create MinIO bucket
- `PUT /data/datasets/{bucket_name}/{object_name}` - Upload object
- `GET /data/datasets/{bucket_name}/{object_name}` - Download object
- `DELETE /data/datasets/{bucket_name}/{object_name}` - Delete object

**Detached Mode Endpoints:**
- `GET /data/v1/tables` - List detached tables
- `GET /data/v1/tables/{table_name}/snapshots/latest` - Get latest snapshot
- `POST /data/v1/jobs/register-snapshot` - Register snapshot

### 4. **🔄 Lineage** (`/lineage/*`)
**Router**: `app/routers/lineage.py`
**Purpose**: OpenLineage integration and data lineage tracking

## 🎨 Synthwave Theme Implementation

### Color Palette
The OpenAPI documentation uses your frontend's Synthwave color scheme:

```css
--synthwave-deep: #0a0a0f      /* Deepest dark */
--synthwave-dark: #1a0b2e      /* Main background */
--synthwave-darker: #16213e    /* Secondary dark */
--synthwave-purple: #240046    /* UI element background */
--synthwave-indigo: #3c096c    /* Accent background */
--synthwave-pink: #ff006e      /* Primary accent */
--synthwave-cyan: #00f5ff      /* Secondary accent */
--synthwave-green: #39ff14     /* Success/online */
--synthwave-orange: #ff9500    /* Warning states */
--synthwave-yellow: #ffff00    /* Attention/pending */
--synthwave-violet: #7209b7    /* Subtle accent */
--synthwave-blue: #560bad      /* Link states */
--synthwave-teal: #277da1      /* Alternative accent */
```

### Theme Features
- **Neon glow effects** on titles and interactive elements
- **Gradient backgrounds** matching your frontend
- **Cyberpunk typography** using Orbitron and JetBrains Mono fonts
- **Animated pulsing** on the main title
- **Color-coded HTTP methods** (GET=green, POST=pink, PUT=orange, DELETE=yellow)
- **Glass morphism effects** on cards and containers
- **Custom scrollbars** with neon gradients
- **Retro terminal aesthetic** for code blocks

### Custom Documentation
- **Custom Swagger UI** at `/docs` with full Synthwave theme
- **Enhanced descriptions** with emoji icons and detailed explanations
- **Organized sections** with clear visual hierarchy
- **Interactive examples** with themed buttons and inputs

## 🚀 Getting Started

1. **Start the API server**:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. **View the themed documentation**:
   - Main docs: `http://localhost:8000/docs`
   - API root: `http://localhost:8000/`
   - Health check: `http://localhost:8000/admin/health`

3. **Test the organization**:
   - Admin endpoints: `http://localhost:8000/admin/*`
   - Job/Event streams: `http://localhost:8000/events/*`
   - Table operations: `http://localhost:8000/data/*`

## 🔧 Configuration

The API automatically includes:
- **Router organization** with proper prefixes and tags
- **Custom OpenAPI schema** with enhanced descriptions
- **Synthwave theme CSS** injected into Swagger UI
- **Emoji-enhanced endpoints** for better visual organization
- **Consistent error handling** across all routers

## 📈 Benefits

1. **Better Organization**: Clear separation of concerns
2. **Enhanced UX**: Matching frontend theme creates cohesive experience
3. **Improved Documentation**: Rich descriptions and visual hierarchy
4. **Developer Experience**: Easy to navigate and understand
5. **Brand Consistency**: Synthwave theme reinforces your platform identity

## 🎯 Future Enhancements

- Add more detailed response models
- Implement request/response examples
- Add authentication documentation
- Include rate limiting information
- Add webhook documentation for SSE events

Your API now has a professional, organized structure with a stunning Synthwave theme that matches your frontend perfectly! 🌟