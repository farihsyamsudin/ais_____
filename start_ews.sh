#!/bin/bash
# start_ews.sh - Complete Early Warning System Starter

echo "=========================================="
echo "🚨 Early Warning System Starter"
echo "=========================================="
echo ""

# Check if in correct directory
if [ ! -d "backend" ] || [ ! -d "venv" ]; then
    echo "❌ Error: Must run from project root (ais-transhipment-web/)"
    echo "   Current directory: $(pwd)"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Menu
echo "Select action:"
echo ""
echo "1. 🧪 Test Email Configuration"
echo "2. 🎮 Run Anomaly Simulator (Interactive)"
echo "3. 🔍 Single Detection Check (Manual)"
echo "4. ⏰ Start Continuous Monitoring"
echo "5. 📜 View Alert History"
echo "6. 🛠️  Setup Email Config (.env)"
echo "7. 🗄️  Database Manager (Clean/Reset)"
echo "8. 🧹 Quick: Presentation Ready Reset"
echo "Q. Quit"
echo ""
read -p "Enter choice (1-8 or Q): " choice

case $choice in
    1)
        echo ""
        echo "=========================================="
        echo "🧪 Testing Email Configuration"
        echo "=========================================="
        cd backend
        python email_config.py
        ;;
    
    2)
        echo ""
        echo "=========================================="
        echo "🎮 Anomaly Simulator"
        echo "=========================================="
        cd backend
        python simulate_anomaly.py
        ;;
    
    3)
        echo ""
        echo "=========================================="
        echo "🔍 Running Single Detection Check"
        echo "=========================================="
        cd backend
        python early_warning_monitor.py --check-now
        echo ""
        echo "Check complete! See results above."
        ;;
    
    4)
        echo ""
        echo "=========================================="
        echo "⏰ Starting Continuous Monitoring"
        echo "=========================================="
        echo "Press Ctrl+C to stop monitoring"
        echo ""
        cd backend
        python early_warning_monitor.py
        ;;
    
    5)
        echo ""
        echo "=========================================="
        echo "📜 Alert History"
        echo "=========================================="
        read -p "How many alerts to show? (default: 10): " limit
        limit=${limit:-10}
        cd backend
        python early_warning_monitor.py --mode history --history-limit $limit
        ;;
    
    6)
        echo ""
        echo "=========================================="
        echo "🛠️  Email Configuration Setup"
        echo "=========================================="
        echo ""
        echo "Edit backend/.env file with your settings:"
        echo ""
        echo "For Gmail:"
        echo "1. Enable 2-Factor Authentication"
        echo "2. Generate App Password: https://myaccount.google.com/apppasswords"
        echo "3. Add to .env:"
        echo ""
        echo "SENDER_EMAIL=your_email@gmail.com"
        echo "SENDER_PASSWORD=your_16_char_app_password"
        echo "RECIPIENT_EMAILS=recipient@example.com"
        echo ""
        read -p "Press Enter to edit .env now, or Ctrl+C to cancel..."
        ${EDITOR:-nano} backend/.env
        ;;
    
    7)
        echo ""
        echo "=========================================="
        echo "🗄️  Database Manager"
        echo "=========================================="
        cd backend
        python manage_database.py
        ;;
    
    8)
        echo ""
        echo "=========================================="
        echo "🎯 Quick Presentation Ready Reset"
        echo "=========================================="
        echo ""
        echo "This will clean:"
        echo "  ✓ All simulation data"
        echo "  ✓ All test case data"
        echo "  ✓ Alert history"
        echo "  ✓ Keeps real/production data"
        echo ""
        read -p "Continue? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            cd backend
            python -c "
from manage_database import get_database, presentation_ready_reset
db = get_database()
presentation_ready_reset(db)
"
            echo ""
            echo "✅ Database is presentation-ready!"
        else
            echo "❌ Cancelled"
        fi
        ;;
    
    [Qq])
        echo "👋 Exiting..."
        exit 0
        ;;
    
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="

# ==========================================
# test_ews.sh - Complete EWS Testing Script
# ==========================================
# Save as: test_ews.sh

cat > test_ews.sh << 'EOFTEST'
#!/bin/bash

echo "=========================================="
echo "🧪 Early Warning System - Full Test"
echo "=========================================="
echo ""

cd ~/ais-transhipment-web
source venv/bin/activate
cd backend

PASSED=0
FAILED=0

test_step() {
    echo ""
    echo "▶ $1"
}

pass() {
    echo "  ✅ $1"
    ((PASSED++))
}

fail() {
    echo "  ❌ $1"
    ((FAILED++))
}

# Test 1: Email Config
test_step "Test 1: Email Configuration"
if python -c "from email_config import EMAIL_CONFIG; assert EMAIL_CONFIG['sender_email'], 'No sender email'" 2>/dev/null; then
    pass "Email configuration loaded"
else
    fail "Email configuration missing or invalid"
fi

# Test 2: Email Test
test_step "Test 2: Send Test Email"
echo "   Attempting to send test email..."
if timeout 30 python email_config.py 2>&1 | grep -q "Email alert sent successfully"; then
    pass "Test email sent successfully"
    echo "   📬 Check your inbox!"
else
    fail "Failed to send test email"
fi

# Test 3: Database Connection
test_step "Test 3: Database Connection"
if python -c "from early_warning_monitor import get_database; db = get_database(); print('OK')" 2>/dev/null | grep -q "OK"; then
    pass "MongoDB connection successful"
else
    fail "MongoDB connection failed"
fi

# Test 4: Run Simulator (Fast Mode)
test_step "Test 4: Simulate Anomaly Data"
echo "   Inserting test anomaly data..."
if timeout 60 python simulate_anomaly.py <<EOF 2>&1 | grep -q "Simulation complete"
5
F
y
n
EOF
then
    pass "Simulation data inserted"
else
    fail "Simulation failed"
fi

# Test 5: Detection Check
test_step "Test 5: Anomaly Detection"
echo "   Running detection on simulated data..."
if timeout 60 python early_warning_monitor.py --check-now 2>&1 | grep -q "confirmed anomaly"; then
    pass "Anomaly detected successfully"
else
    fail "No anomalies detected (this might be OK if data is old)"
fi

# Test 6: Alert History
test_step "Test 6: Alert History"
if python early_warning_monitor.py --mode history --history-limit 1 2>&1 | grep -q "RECENT ALERT HISTORY"; then
    pass "Alert history accessible"
else
    fail "Alert history not accessible"
fi

# Summary
echo ""
echo "=========================================="
echo "📊 Test Summary"
echo "=========================================="
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ All tests passed! EWS is fully functional."
    exit 0
else
    echo "⚠️  Some tests failed. Check errors above."
    exit 1
fi
EOFTEST

chmod +x test_ews.sh

echo ""
echo "Created test_ews.sh - Run complete EWS test suite"

# ==========================================
# monitor_daemon.sh - Run as Background Service
# ==========================================

cat > monitor_daemon.sh << 'EOFDAEMON'
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
EOFDAEMON

chmod +x monitor_daemon.sh

echo "Created monitor_daemon.sh - Background monitoring control"
echo ""
echo "Usage:"
echo "  ./monitor_daemon.sh start   - Start monitoring in background"
echo "  ./monitor_daemon.sh stop    - Stop monitoring"
echo "  ./monitor_daemon.sh status  - Check if running"
echo "  ./monitor_daemon.sh logs    - View live logs"