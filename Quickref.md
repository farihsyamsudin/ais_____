# 📋 Quick Reference Card

## 🚀 Essential Commands

### System Control

```bash
# START everything (recommended)
./start_all.sh

# START separately
./start_backend.sh   # Terminal 1
./start_frontend.sh  # Terminal 2

# STOP everything
./stop_all.sh
# or press Ctrl+C in terminals

# TEST system
./test_system.sh
```

### MongoDB Commands

```bash
# Start/Stop MongoDB
sudo systemctl start mongod
sudo systemctl stop mongod
sudo systemctl restart mongod
sudo systemctl status mongod

# Connect to MongoDB shell
mongosh

# Inside mongosh:
use ais_transhipment_db              # Switch to database
db.ais_signals.countDocuments()      # Count total documents
db.ais_signals.distinct("mmsi")      # Get unique vessels
db.ais_signals.findOne()             # View one document
show collections                      # List collections
db.ais_signals.find().limit(5)       # View 5 documents
```

### Database Operations

```bash
# Seed database
cd backend
source ../venv/bin/activate
python seed_database.py

# Backup database
mongodump --db=ais_transhipment_db --out=./backup

# Restore database
mongorestore --db=ais_transhipment_db ./backup/ais_transhipment_db

# Clear database
mongosh --eval "use ais_transhipment_db; db.ais_signals.deleteMany({})"

# Export to JSON
mongoexport --db=ais_transhipment_db --collection=ais_signals --out=data.json

# Import from JSON
mongoimport --db=ais_transhipment_db --collection=ais_signals --file=data.json
```

### Python Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Deactivate
deactivate

# Install dependencies
pip install -r backend/requirements.txt

# Update dependencies
pip freeze > backend/requirements.txt

# Check installed packages
pip list
```

## 🌐 API Endpoints

Base URL: `http://localhost:5000`

### GET Endpoints

```bash
# Health check
curl http://localhost:5000/health

# Get statistics
curl http://localhost:5000/api/stats

# Get vessels list
curl http://localhost:5000/api/vessels

# Get vessel track
curl "http://localhost:5000/api/vessel/111111111?start_date=2023-08-01T10:00:00&end_date=2023-08-01T12:00:00"

# Get ports
curl http://localhost:5000/api/ports
```

### POST Endpoints

```bash
# Run detection
curl -X POST http://localhost:5000/api/detect \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2023-08-01T10:00:00",
    "end_date": "2023-08-01T12:00:00",
    "parameters": {
      "proximity_km": 0.2,
      "duration_min": 30,
      "sog_threshold": 0.5
    }
  }'
```

## 📊 Useful MongoDB Queries

```javascript
// Connect first
mongosh
use ais_transhipment_db

// Count documents by date
db.ais_signals.aggregate([
  {$group: {
    _id: {$dateToString: {format: "%Y-%m-%d", date: "$created_at"}},
    count: {$sum: 1}
  }},
  {$sort: {_id: 1}}
])

// Find vessels in specific area
db.ais_signals.find({
  lat: {$gte: -6.0, $lte: -5.5},
  lon: {$gte: 105.5, $lte: 106.0}
}).limit(10)

// Find slow vessels (potential transhipment)
db.ais_signals.find({
  sog: {$lt: 0.5}
}).limit(10)

// Count signals per vessel
db.ais_signals.aggregate([
  {$group: {_id: "$mmsi", count: {$sum: 1}}},
  {$sort: {count: -1}},
  {$limit: 10}
])

// Get date range
db.ais_signals.aggregate([
  {$group: {
    _id: null,
    min_date: {$min: "$created_at"},
    max_date: {$max: "$created_at"}
  }}
])

// Find vessels near each other
db.ais_signals.aggregate([
  {$match: {
    created_at: {
      $gte: ISODate("2023-08-01T10:00:00"),
      $lte: ISODate("2023-08-01T12:00:00")
    }
  }},
  {$group: {
    _id: {
      lat_bucket: {$floor: {$multiply: ["$lat", 100]}},
      lon_bucket: {$floor: {$multiply: ["$lon", 100]}}
    },
    vessels: {$addToSet: "$mmsi"},
    count: {$sum: 1}
  }},
  {$match: {count: {$gt: 1}}},
  {$sort: {count: -1}}
])
```

## 🐛 Troubleshooting

### MongoDB Issues

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Fix permissions
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chown mongodb:mongodb /tmp/mongodb-27017.sock

# Restart MongoDB
sudo systemctl restart mongod
```

### Port Issues

```bash
# Check what's using port 5000
lsof -i :5000

# Check what's using port 8000
lsof -i :8000

# Kill process on port
kill -9 $(lsof -t -i:5000)
kill -9 $(lsof -t -i:8000)

# Or use specific PID
kill -9 <PID>
```

### Backend Issues

```bash
# Check logs (in terminal running backend)
# Look for error messages

# Verify MongoDB connection
python -c "from pymongo import MongoClient; print(MongoClient('mongodb://localhost:27017/').server_info())"

# Check if Flask is installed
pip show Flask

# Reinstall dependencies
pip install -r backend/requirements.txt --force-reinstall
```

### Frontend Issues

```bash
# Check if index.html exists
ls -la frontend/

# Test frontend locally
cd frontend
python3 -m http.server 8080

# Check browser console
# Open browser → F12 → Console tab

# Clear browser cache
# Ctrl+Shift+R (hard refresh)
```

## 📁 Important Files & Locations

```
Project Root: ~/ais-transhipment-web/

Configuration:
  backend/.env                 # Environment variables
  backend/requirements.txt     # Python dependencies

Code:
  backend/app.py              # Flask API server
  backend/anomaly_logic.py    # Detection algorithm
  backend/seed_database.py    # Database seeder
  frontend/index.html         # Web interface
  frontend/app.js             # Frontend logic

Scripts:
  start_all.sh                # Start everything
  start_backend.sh            # Start backend only
  start_frontend.sh           # Start frontend only
  stop_all.sh                 # Stop all services
  test_system.sh              # Run system tests
  setup.sh                    # Initial setup

Logs:
  /var/log/mongodb/mongod.log # MongoDB logs
  Terminal output             # Flask logs
```

## 🎯 Common Tasks

### Change Database Connection

```bash
# Edit backend/.env
nano backend/.env

# Update these lines:
MONGODB_URI=mongodb://new-server:27017/
DATABASE_NAME=new_database
COLLECTION_NAME=new_collection

# Restart backend
./stop_all.sh
./start_all.sh
```

### Add New Test Data

```python
# Edit backend/seed_database.py
# Add new scenario in seed_test_scenarios()

scenarios.append({
    "type": "my_custom_test",
    "duration": 40,
    "pairs": 3
})

# Run seeder
python backend/seed_database.py
```

### Export Results

```bash
# From MongoDB
mongoexport --db=ais_transhipment_db \
  --collection=ais_signals \
  --query='{"created_at": {"$gte": {"$date": "2023-08-01T00:00:00Z"}}}' \
  --out=results.json

# Convert JSON to CSV
python -c "
import pandas as pd
df = pd.read_json('results.json')
df.to_csv('results.csv', index=False)
"
```

### Update Detection Parameters

```javascript
// In frontend (browser)
// Adjust sliders in web interface

// Or via API
fetch('http://localhost:5000/api/detect', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    start_date: '2023-08-01T10:00:00',
    end_date: '2023-08-01T12:00:00',
    parameters: {
      proximity_km: 0.3,      // Increase for more detections
      duration_min: 25,       // Decrease for more detections
      sog_threshold: 1.0,     // Increase for more detections
      port_distance_km: 15    // Increase for more detections
    }
  })
})
```

## 🔑 Keyboard Shortcuts

### Browser

- `F12` - Open Developer Tools
- `Ctrl+Shift+R` - Hard refresh (clear cache)
- `Ctrl+Shift+I` - Open Inspector
- `Ctrl+Shift+C` - Element picker

### Terminal

- `Ctrl+C` - Stop running process
- `Ctrl+Z` - Suspend process
- `Ctrl+L` - Clear screen
- `Ctrl+R` - Search command history

## 📞 Quick Links

- Frontend: http://localhost:8000
- Backend API: http://localhost:5000
- Health Check: http://localhost:5000/health
- API Stats: http://localhost:5000/api/stats

## 💡 Pro Tips

1. **Always activate venv** before running Python commands
2. **Check MongoDB first** if backend fails
3. **Use test_system.sh** to diagnose issues
4. **Keep terminals open** to see logs
5. **Backup database** before major changes
6. **Use small date ranges** for faster testing
7. **Check browser console** for frontend errors
8. **Monitor system resources** (RAM, CPU) for large datasets

---

**Print this and keep it handy!** 📌