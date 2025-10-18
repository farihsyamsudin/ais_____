# 🚢 AIS Transhipment Detection System - Web Based

Complete web-based implementation of illegal transhipment detection system using MongoDB and Flask API.

## 📁 Project Structure

```
ais-transhipment-web/
├── backend/
│   ├── app.py                  # Flask API server
│   ├── anomaly_logic.py        # Core detection algorithm
│   ├── seed_database.py        # MongoDB seeder script
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Environment variables
├── frontend/
│   ├── index.html             # Web interface
│   └── app.js                 # Frontend JavaScript
├── V3/                        # Original code (for reference)
│   ├── main.py
│   ├── anomaly_logic.py
│   └── generate_test_case.py
└── README.md                  # This file
```

## 🔧 Prerequisites

- **WSL Ubuntu** (or native Linux)
- **Python 3.8+**
- **MongoDB 7.0+**
- **Git** (optional)

## 📦 Step-by-Step Installation

### 1️⃣ Install MongoDB on WSL Ubuntu

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y wget curl gnupg2 software-properties-common apt-transport-https ca-certificates lsb-release

# Import MongoDB public GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update package list
sudo apt update

# Install MongoDB
sudo apt install -y mongodb-org

# Start MongoDB service
sudo systemctl start mongod

# Enable MongoDB to start on boot
sudo systemctl enable mongod

# Verify installation
sudo systemctl status mongod

# Test connection (should open MongoDB shell)
mongosh
```

**Common Issues & Solutions:**

```bash
# If mongod fails to start
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chown mongodb:mongodb /tmp/mongodb-27017.sock
sudo systemctl restart mongod

# Check logs
sudo tail -f /var/log/mongodb/mongod.log
```

### 2️⃣ Create Project Structure

```bash
# Create project directory
mkdir -p ~/ais-transhipment-web
cd ~/ais-transhipment-web

# Create subdirectories
mkdir -p backend frontend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### 3️⃣ Setup Backend

```bash
cd backend

# Create requirements.txt
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

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=ais_transhipment_db
COLLECTION_NAME=ais_signals
FLASK_ENV=development
PORT=5000
EOF
```

### 4️⃣ Copy Core Files

**Copy these files to `backend/` directory:**

1. **`anomaly_logic.py`** - Your existing core detection algorithm (from document 2)
2. **`app.py`** - Flask API server (from artifact above)
3. **`seed_database.py`** - MongoDB seeder (from artifact above)

```bash
# Verify files exist
ls -la backend/
# Should show: app.py, anomaly_logic.py, seed_database.py, requirements.txt, .env
```

### 5️⃣ Seed Database

```bash
cd ~/ais-transhipment-web/backend
source ../venv/bin/activate

# Run seeder
python seed_database.py

# When prompted, choose option:
# 1 = Test scenarios only (recommended for first run)
# 2 = Realistic data only
# 3 = Both

# Select option 1 for initial testing
```

**Expected Output:**
```
✅ Connected to MongoDB: ais_transhipment_db
✅ Indexes created
📦 Seeding test scenarios...
  ✅ valid: 80 documents
  ✅ valid_multi: 400 documents
  ...
✅ Total test documents inserted: 2880
```

### 6️⃣ Start Backend Server

```bash
# In backend directory with venv activated
python app.py
```

**Expected Output:**
```
============================================================
🚢 AIS Transhipment Detection API
============================================================
Server: http://localhost:5000
Database: ais_transhipment_db
Debug mode: True
============================================================
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

**Test API:**
```bash
# In another terminal
curl http://localhost:5000/health

# Expected response:
# {"database":"connected","status":"healthy","timestamp":"2024-..."}
```

### 7️⃣ Setup Frontend

```bash
cd ~/ais-transhipment-web/frontend

# Copy frontend files (index.html and app.js from artifacts above)
# Make sure both files are in the frontend/ directory

# Verify files
ls -la
# Should show: index.html, app.js
```

### 8️⃣ Start Frontend

```bash
# Simple Python HTTP server
cd ~/ais-transhipment-web/frontend
python3 -m http.server 8000
```

**Access the application:**
- Open browser: `http://localhost:8000`
- You should see the web interface

## 🎯 Usage Guide

### Running Detection

1. **Check Status**: Green dot in header = system ready
2. **Set Date Range**: 
   - Default is set to test data time range
   - For test scenarios: `2023-08-01 10:00` to `2023-08-01 12:00`
3. **Adjust Parameters** (optional):
   - Proximity: Distance threshold for vessel proximity
   - Duration: Minimum time for confirmed anomaly
   - SOG: Speed over ground threshold
   - Port Distance: Minimum distance from ports
4. **Click "Run Detection"**
5. **View Results**:
   - Map shows red (confirmed) and yellow (candidate) markers
   - Tables show detailed information
   - Click table rows to focus on map

### Expected Test Results

With default test data, you should see:

| Scenario | Expected Result |
|----------|----------------|
| `valid` | ✅ Confirmed anomaly detected |
| `valid_multi` | ✅ Multiple confirmed anomalies |
| `short_duration` | ⚠️ Candidate or rejected |
| `far_proximity` | ❌ Rejected (too far apart) |
| `high_speed` | ❌ Rejected (speed too high) |
| `near_port` | ❌ Rejected (near port) |

## 🔍 Verification Commands

### Check MongoDB Data

```bash
mongosh

use ais_transhipment_db

// Count total signals
db.ais_signals.countDocuments()

// Count unique vessels
db.ais_signals.distinct("mmsi").length

// View sample data
db.ais_signals.findOne()

// Check date range
db.ais_signals.aggregate([
  {$group: {
    _id: null,
    min: {$min: "$created_at"},
    max: {$max: "$created_at"}
  }}
])

// Count signals by MMSI
db.ais_signals.aggregate([
  {$group: {_id: "$mmsi", count: {$sum: 1}}},
  {$sort: {count: -1}}
])
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:5000/health

# Get stats
curl http://localhost:5000/api/stats

# Get vessels
curl http://localhost:5000/api/vessels

# Run detection (example)
curl -X POST http://localhost:5000/api/detect \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2023-08-01T10:00:00",
    "end_date": "2023-08-01T12:00:00",
    "parameters": {
      "proximity_km": 0.2,
      "duration_min": 30,
      "sog_threshold": 0.5,
      "port_distance_km": 10
    }
  }'
```

## 🐛 Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Restart MongoDB
sudo systemctl restart mongod

# Check logs
sudo tail -f /var/log/mongodb/mongod.log
```

### Backend Issues

```bash
# Check if port 5000 is in use
lsof -i :5000

# Kill process if needed
kill -9 <PID>

# Check Python dependencies
pip list | grep -E "Flask|pymongo|pandas"
```

### Frontend Issues

```bash
# Check if port 8000 is in use
lsof -i :8000

# Try different port
python3 -m http.server 8080

# Check browser console for errors
# Press F12 in browser, check Console tab
```

### CORS Issues

If you see CORS errors in browser:
1. Verify `flask-cors` is installed: `pip show flask-cors`
2. Check backend is running on port 5000
3. Verify frontend API_BASE_URL in `app.js` is correct

### No Anomalies Detected

1. **Check date range**: Must have data in that range
2. **Verify data in MongoDB**: Run verification commands above
3. **Adjust parameters**: Try lowering duration threshold
4. **Check logs**: Backend terminal shows processing details

## 📊 Adding Real Data

When you get access to real MongoDB database:

### Option 1: Direct Connection

```bash
# Update backend/.env
MONGODB_URI=mongodb://your-real-server:27017/
DATABASE_NAME=your_real_database
COLLECTION_NAME=your_real_collection
```

### Option 2: Data Migration

```bash
# Export from real DB
mongodump --uri="mongodb://real-server/real_db" \
  --collection=ais_signals \
  --out=./dump

# Import to local DB
mongorestore --uri="mongodb://localhost:27017/ais_transhipment_db" \
  --collection=ais_signals \
  ./dump/real_db/ais_signals.bson
```

## 🚀 Production Deployment

### Using Gunicorn

```bash
cd backend

# Install gunicorn (already in requirements.txt)
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Docker (Optional)

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 📈 Performance Tips

1. **Database Indexing**: Already configured in seeder
2. **Data Sampling**: For large datasets, use date ranges
3. **Pagination**: For frontend tables (future enhancement)
4. **Caching**: Consider Redis for frequent queries

## 🔐 Security Notes

For production:
- Use environment variables for sensitive data
- Enable MongoDB authentication
- Use HTTPS for API
- Implement rate limiting
- Add user authentication

## 📝 Next Steps

1. ✅ Setup complete system
2. ✅ Test with seeded data
3. ⏳ Connect to real database
4. ⏳ Fine-tune detection parameters
5. ⏳ Add export functionality (CSV, PDF reports)
6. ⏳ Implement user authentication
7. ⏳ Add real-time monitoring

## 💡 Tips

- Keep backend and frontend terminals open to monitor logs
- Use browser DevTools (F12) to debug frontend issues
- Test with small date ranges first
- Adjust parameters based on your specific needs

## 📞 Support

If you encounter issues:
1. Check troubleshooting section
2. Review terminal logs (backend and frontend)
3. Verify all files are in correct locations
4. Ensure MongoDB is running

---

**Good luck with your transhipment detection system! 🚢⚓**