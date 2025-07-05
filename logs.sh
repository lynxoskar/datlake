#!/bin/bash

# Loki Logs Helper Script
export PATH="$HOME/bin:$PATH"
export LOKI_ADDR=http://localhost:3100

case "$1" in
  "tail")
    echo "Tailing all logs..."
    logcli tail --follow '{}'
    ;;
  "ducklake")
    echo "Showing ducklake-backend logs..."
    logcli query --since=1h '{app="ducklake-backend"}'
    ;;
  "tail-ducklake")
    echo "Tailing ducklake-backend logs..."
    logcli tail --follow '{app="ducklake-backend"}'
    ;;
  "postgres")
    echo "Showing PostgreSQL logs..."
    logcli query --since=1h '{container="postgresql"}'
    ;;
  "tail-postgres")
    echo "Tailing PostgreSQL logs..."
    logcli tail --follow '{container="postgresql"}'
    ;;
  "postgres-errors")
    echo "Showing PostgreSQL error logs..."
    logcli query --since=1h '{container="postgresql"} |~ "(?i)(error|fatal|panic)"'
    ;;
  "postgres-slow")
    echo "Showing PostgreSQL slow queries..."
    logcli query --since=1h '{container="postgresql"} |~ "duration:"'
    ;;
  "postgres-autovacuum")
    echo "Showing PostgreSQL autovacuum activity..."
    logcli query --since=1h '{container="postgresql"} |~ "automatic (vacuum|analyze)"'
    ;;
  "postgres-connections")
    echo "Showing PostgreSQL connection activity..."
    logcli query --since=1h '{container="postgresql"} |~ "(connection|disconnect)"'
    ;;
  "pgmq")
    echo "Showing PGMQ queue operations..."
    logcli query --since=1h '{container="postgresql"} |~ "pgmq"'
    ;;
  "lineage")
    echo "Showing OpenLineage processing logs..."
    logcli query --since=1h '{} |~ "(lineage|openlineage)"'
    ;;
  "errors")
    echo "Showing error logs from all services..."
    logcli query --since=1h '{} |~ "(?i)error"'
    ;;
  "namespace")
    if [ -z "$2" ]; then
      echo "Usage: $0 namespace <namespace_name>"
      exit 1
    fi
    echo "Showing logs from namespace: $2"
    logcli query --since=1h "{namespace=\"$2\"}"
    ;;
  "labels")
    echo "Available labels in Loki:"
    logcli labels
    ;;
  "help"|*)
    echo "Loki Logs Helper"
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  tail             - Tail all logs in real-time"
    echo "  ducklake         - Show ducklake-backend logs"
    echo "  tail-ducklake    - Tail ducklake-backend logs in real-time"
    echo "  postgres         - Show PostgreSQL logs"
    echo "  tail-postgres    - Tail PostgreSQL logs in real-time"
    echo "  postgres-errors  - Show PostgreSQL error logs"
    echo "  postgres-slow    - Show PostgreSQL slow queries (>1s)"
    echo "  postgres-autovacuum - Show PostgreSQL autovacuum activity"
    echo "  postgres-connections - Show PostgreSQL connection activity"
    echo "  pgmq             - Show PGMQ queue operations"
    echo "  lineage          - Show OpenLineage processing logs"
    echo "  errors           - Show error logs from all services"
    echo "  namespace <name> - Show logs from specific namespace"
    echo "  labels           - Show available labels"
    echo "  help             - Show this help"
    echo ""
    echo "Direct logcli usage:"
    echo "  export LOKI_ADDR=http://localhost:3100"
    echo "  logcli query '{app=\"ducklake-backend\"}'"
    echo "  logcli tail --follow '{namespace=\"default\"}'"
    ;;
esac