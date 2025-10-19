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
