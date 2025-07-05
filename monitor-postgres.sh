#!/bin/bash

# PostgreSQL Monitoring Script with Loki Integration
# Provides real-time monitoring of PostgreSQL performance and PGMQ queue operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/bin:$PATH"
export LOKI_ADDR=http://localhost:3100

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if Loki is accessible
check_loki() {
    if ! curl -s "$LOKI_ADDR/ready" | grep -q "ready"; then
        log_error "Loki is not accessible at $LOKI_ADDR"
        log_info "Please run './setup-logs.sh' first to establish port forwarding"
        exit 1
    fi
}

# Monitor PostgreSQL performance in real-time
monitor_postgres_performance() {
    log_info "Monitoring PostgreSQL performance metrics..."
    echo ""
    
    while true; do
        echo "=== PostgreSQL Performance Dashboard ($(date)) ==="
        echo ""
        
        # Recent errors
        echo -e "${RED}Recent Errors (last 5 minutes):${NC}"
        logcli query --since=5m '{container="postgresql"} |~ "(?i)(error|fatal|panic)"' --limit=5 2>/dev/null || echo "No errors found"
        echo ""
        
        # Slow queries
        echo -e "${YELLOW}Slow Queries (>1s, last 10 minutes):${NC}"
        logcli query --since=10m '{container="postgresql"} |~ "duration:"' --limit=5 2>/dev/null || echo "No slow queries found"
        echo ""
        
        # Autovacuum activity
        echo -e "${BLUE}Recent Autovacuum Activity (last 15 minutes):${NC}"
        logcli query --since=15m '{container="postgresql"} |~ "automatic (vacuum|analyze)"' --limit=3 2>/dev/null || echo "No autovacuum activity"
        echo ""
        
        # Connection activity
        echo -e "${GREEN}Connection Activity (last 5 minutes):${NC}"
        logcli query --since=5m '{container="postgresql"} |~ "(connection|disconnect)"' --limit=3 2>/dev/null || echo "No connection activity"
        echo ""
        
        echo "Press Ctrl+C to exit, refreshing in 30 seconds..."
        sleep 30
        clear
    done
}

# Monitor PGMQ queue operations
monitor_pgmq_queues() {
    log_info "Monitoring PGMQ queue operations..."
    echo ""
    
    while true; do
        echo "=== PGMQ Queue Operations Dashboard ($(date)) ==="
        echo ""
        
        # PGMQ operations
        echo -e "${BLUE}PGMQ Queue Operations (last 10 minutes):${NC}"
        logcli query --since=10m '{container="postgresql"} |~ "pgmq"' --limit=10 2>/dev/null || echo "No PGMQ operations found"
        echo ""
        
        # Queue errors
        echo -e "${RED}Queue Processing Errors (last 15 minutes):${NC}"
        logcli query --since=15m '{} |~ "(?i)(queue.*error|pgmq.*error)"' --limit=5 2>/dev/null || echo "No queue errors found"
        echo ""
        
        echo "Press Ctrl+C to exit, refreshing in 20 seconds..."
        sleep 20
        clear
    done
}

# Monitor OpenLineage event processing
monitor_lineage_processing() {
    log_info "Monitoring OpenLineage event processing..."
    echo ""
    
    while true; do
        echo "=== OpenLineage Processing Dashboard ($(date)) ==="
        echo ""
        
        # Lineage events
        echo -e "${GREEN}OpenLineage Event Processing (last 10 minutes):${NC}"
        logcli query --since=10m '{} |~ "(lineage|openlineage)"' --limit=10 2>/dev/null || echo "No lineage events found"
        echo ""
        
        # Processing errors
        echo -e "${RED}Lineage Processing Errors (last 15 minutes):${NC}"
        logcli query --since=15m '{} |~ "(?i)(lineage.*error|openlineage.*error)"' --limit=5 2>/dev/null || echo "No lineage errors found"
        echo ""
        
        echo "Press Ctrl+C to exit, refreshing in 20 seconds..."
        sleep 20
        clear
    done
}

# Generate comprehensive log report
generate_log_report() {
    local hours=${1:-1}
    local output_file="postgres-report-$(date +%Y%m%d-%H%M%S).txt"
    
    log_info "Generating PostgreSQL log report for the last $hours hour(s)..."
    
    {
        echo "PostgreSQL Performance and PGMQ Report"
        echo "Generated: $(date)"
        echo "Time Range: Last $hours hour(s)"
        echo "============================================="
        echo ""
        
        echo "=== PostgreSQL Errors ==="
        logcli query --since="${hours}h" '{container="postgresql"} |~ "(?i)(error|fatal|panic)"' 2>/dev/null || echo "No errors found"
        echo ""
        
        echo "=== Slow Queries (>1s) ==="
        logcli query --since="${hours}h" '{container="postgresql"} |~ "duration:"' 2>/dev/null || echo "No slow queries found"
        echo ""
        
        echo "=== Autovacuum Activity ==="
        logcli query --since="${hours}h" '{container="postgresql"} |~ "automatic (vacuum|analyze)"' 2>/dev/null || echo "No autovacuum activity"
        echo ""
        
        echo "=== PGMQ Operations ==="
        logcli query --since="${hours}h" '{container="postgresql"} |~ "pgmq"' 2>/dev/null || echo "No PGMQ operations"
        echo ""
        
        echo "=== OpenLineage Events ==="
        logcli query --since="${hours}h" '{} |~ "(lineage|openlineage)"' 2>/dev/null || echo "No lineage events"
        echo ""
        
        echo "=== Connection Activity ==="
        logcli query --since="${hours}h" '{container="postgresql"} |~ "(connection|disconnect)"' 2>/dev/null || echo "No connection activity"
        echo ""
        
    } > "$output_file"
    
    log_success "Report generated: $output_file"
}

# Real-time tail of all PostgreSQL logs
tail_postgres_logs() {
    log_info "Tailing PostgreSQL logs in real-time..."
    log_info "Press Ctrl+C to exit"
    echo ""
    
    logcli tail --follow '{container="postgresql"}'
}

# Check PostgreSQL health via logs
check_postgres_health() {
    log_info "Checking PostgreSQL health via logs..."
    
    # Check for recent errors
    local recent_errors=$(logcli query --since=5m '{container="postgresql"} |~ "(?i)(error|fatal|panic)"' --quiet 2>/dev/null | wc -l)
    
    if [ "$recent_errors" -gt 0 ]; then
        log_warn "Found $recent_errors error(s) in the last 5 minutes"
        logcli query --since=5m '{container="postgresql"} |~ "(?i)(error|fatal|panic)"' --limit=3
    else
        log_success "No errors found in the last 5 minutes"
    fi
    
    # Check for connection issues
    local connection_errors=$(logcli query --since=10m '{container="postgresql"} |~ "(?i)(connection.*failed|could not connect)"' --quiet 2>/dev/null | wc -l)
    
    if [ "$connection_errors" -gt 0 ]; then
        log_warn "Found $connection_errors connection issue(s) in the last 10 minutes"
    else
        log_success "No connection issues in the last 10 minutes"
    fi
    
    # Check autovacuum activity
    local vacuum_activity=$(logcli query --since=30m '{container="postgresql"} |~ "automatic vacuum"' --quiet 2>/dev/null | wc -l)
    
    if [ "$vacuum_activity" -gt 0 ]; then
        log_success "Autovacuum is active ($vacuum_activity operations in last 30 minutes)"
    else
        log_warn "No autovacuum activity in the last 30 minutes"
    fi
}

# Main function
main() {
    check_loki
    
    case "$1" in
        "performance"|"perf")
            monitor_postgres_performance
            ;;
        "queues"|"pgmq")
            monitor_pgmq_queues
            ;;
        "lineage")
            monitor_lineage_processing
            ;;
        "report")
            generate_log_report "${2:-1}"
            ;;
        "tail")
            tail_postgres_logs
            ;;
        "health")
            check_postgres_health
            ;;
        "help"|*)
            echo "PostgreSQL Monitoring Script with Loki Integration"
            echo "Usage: $0 [command] [options]"
            echo ""
            echo "Commands:"
            echo "  performance, perf    - Monitor PostgreSQL performance in real-time"
            echo "  queues, pgmq        - Monitor PGMQ queue operations"
            echo "  lineage             - Monitor OpenLineage event processing"
            echo "  report [hours]      - Generate comprehensive log report (default: 1 hour)"
            echo "  tail                - Tail PostgreSQL logs in real-time"
            echo "  health              - Check PostgreSQL health via logs"
            echo "  help                - Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 performance       # Monitor performance metrics"
            echo "  $0 report 4          # Generate 4-hour report"
            echo "  $0 queues            # Monitor queue operations"
            echo ""
            echo "Prerequisites:"
            echo "  - Run './setup-logs.sh' first to establish port forwarding"
            echo "  - Ensure Loki is accessible at $LOKI_ADDR"
            ;;
    esac
}

# Run main function with all arguments
main "$@"