#!/bin/bash

# Quick Setup Script for AIS Transhipment Detection System
# Usage: bash setup.sh

set -e  # Exit on error

echo "=========================================="
echo "🚢 AIS Transhipment Setup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check if running in WSL
if ! grep -q Microsoft /proc/version; then
    print_info "Not detected as WSL. This script is optimized for WSL Ubuntu."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 1. Check MongoDB
echo ""
echo "Step 1: Checking MongoDB..."
if ! command -v mongod &> /dev/null; then
    print_error "MongoDB not found. Installing..."
    
    # Install MongoDB
    sudo apt update
    sudo apt install -y wget curl gnupg2 software-properties-common apt-transport-https ca-certificates lsb-release
    
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
      sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
    
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | \
      sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    
    sudo apt update
    sudo apt install -y mongodb-org
    
    sudo systemctl start mongod
    sudo systemctl enable mongod
    
    print_success "MongoDB installed and started"
else
    print_success "MongoDB already installed"
    
    # Check if MongoDB is running
    if sudo systemctl is-active --quiet mongod; then
        print_success "MongoDB is running"
    else
        print_info "Starting MongoDB..."
        sudo systemctl start mongod
        print_success "MongoDB started"
    fi
fi

# 2. Create project structure
echo ""
echo "Step 2: Creating project structure..."
PROJECT_DIR="$HOME/ais-transhipment-web"

if [ -d "$PROJECT_DIR" ]; then
    print_info "Project directory exists. Using existing directory."
else
    mkdir -p "$PROJECT_DIR"
    print_success "Created project directory: $PROJECT_DIR"
fi

cd "$PROJECT_DIR"
mkdir -p backend frontend

# 3. Setup Python virtual environment
echo ""
echo "Step 3: Setting up Python environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

source venv/bin/activate
print_success "Virtual environment activated"

# 4. Install Python dependencies
echo ""
echo "Step 4: Installing Python dependencies..."

cd backend

cat > requirements.txt << 'EOF'
Flask==3.0.0
flask-cors==4.0.0
pymongo==4.6.1
pandas==2.1.4
numpy==1.26.2
haversine==2.8.1
scikit-learn==1.3.2
python-dotenv==1.0.0
gunicorn==21.2.0
EOF

pip install --upgrade pip
pip install -r requirements.txt
print_success "Python dependencies installed"

# 5. Create .env file
echo ""
echo "Step 5: Creating environment configuration..."

if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=ais_transhipment_db
COLLECTION_NAME=ais_signals
FLASK_ENV=development
PORT=5000
EOF
    print_success ".env file created"
else
    print_info ".env file already exists"
fi

# 6. Check required files
echo ""
echo "Step 6: Checking required files..."

REQUIRED_FILES=("app.py" "anomaly_logic.py" "seed_database.py")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    print_success "All required backend files present"
else
    print_error "Missing backend files: ${MISSING_FILES[*]}"
    echo ""
    echo "Please copy these files to: $PROJECT_DIR/backend/"
    echo "Files needed:"
    echo "  - app.py (Flask API server)"
    echo "  - anomaly_logic.py (Detection algorithm)"
    echo "  - seed_database.py (Database seeder)"
    echo ""
    read -p "Press Enter after copying files to continue, or Ctrl+C to exit..."
fi

# 7. Check frontend files
cd ../frontend

FRONTEND_FILES=("index.html" "app.js")
MISSING_FRONTEND=()

for file in "${FRONTEND_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FRONTEND+=("$file")
    fi
done

if [ ${#MISSING_FRONTEND[@]} -eq 0 ]; then
    print_success "All required frontend files present"
else
    print_error "Missing frontend files: ${MISSING_FRONTEND[*]}"
    echo ""
    echo "Please copy these files to: $PROJECT_DIR/frontend/"
    echo ""
    read -p "Press Enter after copying files to continue, or Ctrl+C to exit..."
fi

# 8. Seed database
echo ""
echo "Step 7: Database seeding..."
cd ../backend

print_info "Do you want to seed the database now?"
echo "Options:"
echo "  1) Test scenarios only (recommended for first run)"
echo "  2) Realistic data (7 days)"
echo "  3) Both"
echo "  4) Skip for now"
read -p "Enter choice (1-4): " SEED_CHOICE

if [ "$SEED_CHOICE" != "4" ]; then
    python seed_database.py <<< "$SEED_CHOICE"
    print_success "Database seeded"
else
    print_info "Skipping database seeding. Run 'python seed_database.py' manually later."
fi

# 9. Create startup scripts
echo ""
echo "Step 8: Creating startup scripts..."

cd "$PROJECT_DIR"

# Backend start script
cat > start_backend.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/backend"
source ../venv/bin/activate
echo "🚀 Starting Flask backend on http://localhost:5000"
python app.py
EOF
chmod +x start_backend.sh
print_success "Created start_backend.sh"

# Frontend start script
cat > start_frontend.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/frontend"
echo "🌐 Starting frontend on http://localhost:8000"
python3 -m http.server 8000
EOF
chmod +x start_frontend.sh
print_success "Created start_frontend.sh"

# Combined start script
cat > start_all.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

echo "=========================================="
echo "🚢 AIS Transhipment Detection System"
echo "=========================================="
echo ""

# Check MongoDB
if ! sudo systemctl is-active --quiet mongod; then
    echo "Starting MongoDB..."
    sudo systemctl start mongod
    sleep 2
fi

# Start backend in background
echo "Starting backend..."
./start_backend.sh &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend in background
echo "Starting frontend..."
./start_frontend.sh &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "✅ System started successfully!"
echo "=========================================="
echo ""
echo "Backend:  http://localhost:5000"
echo "Frontend: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Trap Ctrl+C to kill both processes
trap "echo ''; echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT

# Wait for both processes
wait
EOF
chmod +x start_all.sh
print_success "Created start_all.sh"

# 10. Create stop script
cat > stop_all.sh << 'EOF'
#!/bin/bash
echo "Stopping all services..."
pkill -f "python app.py"
pkill -f "python3 -m http.server 8000"
echo "✅ All services stopped"
EOF
chmod +x stop_all.sh
print_success "Created stop_all.sh"

# Final summary
echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📁 Project location: $PROJECT_DIR"
echo ""
echo "🚀 Quick Start Commands:"
echo ""
echo "  # Start everything:"
echo "  cd $PROJECT_DIR"
echo "  ./start_all.sh"
echo ""
echo "  # Or start separately:"
echo "  ./start_backend.sh   # Terminal 1"
echo "  ./start_frontend.sh  # Terminal 2"
echo ""
echo "  # Stop everything:"
echo "  ./stop_all.sh"
echo ""
echo "🌐 URLs:"
echo "  Backend API:  http://localhost:5000"
echo "  Frontend Web: http://localhost:8000"
echo ""
echo "📚 Next steps:"
echo "  1. Run: ./start_all.sh"
echo "  2. Open browser: http://localhost:8000"
echo "  3. Set date range: 2023-08-01 10:00 to 12:00"
echo "  4. Click 'Run Detection'"
echo ""
echo "📖 Full documentation: README.md"
echo "=========================================="
echo ""