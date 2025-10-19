#!/bin/bash
# monitor_daemon.sh - Run monitoring as daemon

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/monitor.pid"
LOG_FILE="$PROJECT_DIR/monitor.log"

start_monitor() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "❌ Monitor already running (PID: $PID)"
            exit 1
        fi
    fi
    
    echo "🚀 Starting EWS monitor in background..."
    cd "$PROJECT_DIR"
    source venv/bin/activate
    cd backend
    
    nohup python early_warning_monitor.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    echo "✅ Monitor started (PID: $(cat $PID_FILE))"
    echo "   Logs: $LOG_FILE"
}

stop_monitor() {
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ Monitor not running (no PID file)"
        exit 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "🛑 Stopping monitor (PID: $PID)..."
        kill $PID
        sleep 2
        
        if ps -p $PID > /dev/null 2>&1; then
            echo "   Force killing..."
            kill -9 $PID
        fi
        
        rm "$PID_FILE"
        echo "✅ Monitor stopped"
    else
        echo "❌ Monitor not running (stale PID file)"
        rm "$PID_FILE"
    fi
}

status_monitor() {
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ Monitor not running"
        exit 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Monitor running (PID: $PID)"
        echo ""
        echo "Recent logs:"
        tail -20 "$LOG_FILE"
    else
        echo "❌ Monitor not running (stale PID file)"
        rm "$PID_FILE"
        exit 1
    fi
}

case "$1" in
    start)
        start_monitor
        ;;
    stop)
        stop_monitor
        ;;
    restart)
        stop_monitor
        sleep 2
        start_monitor
        ;;
    status)
        status_monitor
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
