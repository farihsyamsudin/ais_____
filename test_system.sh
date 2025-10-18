#!/bin/bash

# System Test Script for AIS Transhipment Detection
# Tests all components and verifies setup

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

print_test() {
    echo -e "${YELLOW}▶ Testing: $1${NC}"
}

print_pass() {
    echo -e "${GREEN}  ✅ PASS: $1${NC}"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}  ❌ FAIL: $1${NC}"
    ((FAILED++))
}

echo "=========================================="
echo "🧪 AIS Transhipment System Test Suite"
echo "=========================================="
echo ""

# Test 1: MongoDB
print_test "MongoDB Service"
if sudo systemctl is-active --quiet mongod; then
    print_pass "MongoDB is running"
else
    print_fail "MongoDB is not running"
    echo "       Fix: sudo systemctl start mongod"
fi

# Test 2: MongoDB Connection
print_test "MongoDB Connection"
if mongosh --eval "db.version()" --quiet > /dev/null 2>&1; then
    print_pass "Can connect to MongoDB"
else
    print_fail "Cannot connect to MongoDB"
fi

# Test 3: Database Exists
print_test "Database & Collection"
DB_COUNT=$(mongosh --eval "use ais_transhipment_db; db.ais_signals.countDocuments()" --quiet 2>/dev/null | tail -1)
if [ ! -z "$DB_COUNT" ] && [ "$DB_COUNT" -gt 0 ]; then
    print_pass "Database has $DB_COUNT documents"
else
    print_fail "Database is empty or doesn't exist"
    echo "       Fix: python backend/seed_database.py"
fi

# Test 4: Python Virtual Environment
print_test "Python Virtual Environment"
if [ -d "venv" ]; then
    print_pass "Virtual environment exists"
else
    print_fail "Virtual environment not found"
    echo "       Fix: python3 -m venv venv"
fi

# Test 5: Backend Files
print_test "Backend Files"
BACKEND_FILES=("backend/app.py" "backend/anomaly_logic.py" "backend/seed_database.py" "backend/requirements.txt" "backend/.env")
ALL_BACKEND_PRESENT=true

for file in "${BACKEND_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_fail "Missing: $file"
        ALL_BACKEND_PRESENT=false
    fi
done

if [ "$ALL_BACKEND_PRESENT" = true ]; then
    print_pass "All backend files present"
fi

# Test 6: Frontend Files
print_test "Frontend Files"
FRONTEND_FILES=("frontend/index.html" "frontend/app.js")
ALL_FRONTEND_PRESENT=true

for file in "${FRONTEND_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_fail "Missing: $file"
        ALL_FRONTEND_PRESENT=false
    fi
done

if [ "$ALL_FRONTEND_PRESENT" = true ]; then
    print_pass "All frontend files present"
fi

# Test 7: Python Dependencies
print_test "Python Dependencies"
source venv/bin/activate 2>/dev/null || true

REQUIRED_PACKAGES=("flask" "pymongo" "pandas" "numpy" "haversine")
ALL_PACKAGES_INSTALLED=true

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! pip show "$package" > /dev/null 2>&1; then
        print_fail "Missing package: $package"
        ALL_PACKAGES_INSTALLED=false
    fi
done

if [ "$ALL_PACKAGES_INSTALLED" = true ]; then
    print_pass "All Python packages installed"
fi

# Test 8: Backend API (if running)
print_test "Backend API"
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:5000/health | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    if [ "$HEALTH" = "healthy" ]; then
        print_pass "Backend API is healthy"
    else
        print_fail "Backend API unhealthy"
    fi
else
    print_fail "Backend API not responding (may not be running)"
    echo "       Info: This is OK if not started yet"
    echo "       Fix: ./start_backend.sh"
fi

# Test 9: Frontend Server (if running)
print_test "Frontend Server"
if curl -s http://localhost:8000 > /dev/null 2>&1; then
    print_pass "Frontend server is running"
else
    print_fail "Frontend server not responding (may not be running)"
    echo "       Info: This is OK if not started yet"
    echo "       Fix: ./start_frontend.sh"
fi

# Test 10: Port Availability
print_test "Port Availability"
if ! lsof -Pi :5000 -sTCP:LISTEN -t > /dev/null 2>&1; then
    print_pass "Port 5000 is available"
else
    PID=$(lsof -Pi :5000 -sTCP:LISTEN -t)
    print_fail "Port 5000 is in use (PID: $PID)"
    echo "       Fix: kill $PID"
fi

if ! lsof -Pi :8000 -sTCP:LISTEN -t > /dev/null 2>&1; then
    print_pass "Port 8000 is available"
else
    PID=$(lsof -Pi :8000 -sTCP:LISTEN -t)
    print_fail "Port 8000 is in use (PID: $PID)"
    echo "       Fix: kill $PID"
fi

# Test 11: Startup Scripts
print_test "Startup Scripts"
SCRIPTS=("start_backend.sh" "start_frontend.sh" "start_all.sh" "stop_all.sh")
ALL_SCRIPTS_PRESENT=true

for script in "${SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        print_fail "Missing: $script"
        ALL_SCRIPTS_PRESENT=false
    elif [ ! -x "$script" ]; then
        print_fail "Not executable: $script"
        echo "       Fix: chmod +x $script"
        ALL_SCRIPTS_PRESENT=false
    fi
done

if [ "$ALL_SCRIPTS_PRESENT" = true ]; then
    print_pass "All startup scripts present and executable"
fi

# Test 12: Sample Data Query
print_test "Sample Data Query"
if [ ! -z "$DB_COUNT" ] && [ "$DB_COUNT" -gt 0 ]; then
    UNIQUE_VESSELS=$(mongosh --eval "use ais_transhipment_db; db.ais_signals.distinct('mmsi').length" --quiet 2>/dev/null | tail -1)
    if [ ! -z "$UNIQUE_VESSELS" ] && [ "$UNIQUE_VESSELS" -gt 0 ]; then
        print_pass "Found $UNIQUE_VESSELS unique vessels"
        
        # Get date range
        DATE_RANGE=$(mongosh --eval "use ais_transhipment_db; db.ais_signals.aggregate([{\$group:{_id:null,min:{\$min:'\$created_at'},max:{\$max:'\$created_at'}}}])" --quiet 2>/dev/null | grep -A2 "min:" | tail -2)
        if [ ! -z "$DATE_RANGE" ]; then
            echo "       Date range available for testing"
        fi
    else
        print_fail "No vessels found in database"
    fi
else
    print_fail "Cannot query sample data"
fi

# Summary
echo ""
echo "=========================================="
echo "📊 Test Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed! System is ready.${NC}"
    echo ""
    echo "🚀 You can now start the system:"
    echo "   ./start_all.sh"
    echo ""
    echo "🌐 Then open: http://localhost:8000"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please fix the issues above.${NC}"
    echo ""
    echo "💡 Common fixes:"
    echo "   - Start MongoDB: sudo systemctl start mongod"
    echo "   - Seed database: python backend/seed_database.py"
    echo "   - Install deps: pip install -r backend/requirements.txt"
    exit 1
fi