# 🔄 Migration Guide: From Pickle to MongoDB Web-Based System

## 📋 Overview

This guide helps you understand the differences between your original system and the new web-based implementation, and how to migrate when you get access to the real MongoDB database.

## 🔍 System Comparison

### Original System (V3)

```
Input:  PKL files (pandas pickle)
Process: Python script (command line)
Output: CSV, PNG, HTML files
Usage:  python V3/main.py [test_case|real_case]
```

### New Web-Based System

```
Input:  MongoDB database
Process: Flask API + Web Interface
Output: Interactive web dashboard
Usage:  Web browser (http://localhost:8000)
```

## 📊 Feature Comparison

| Feature | Original | Web-Based |
|---------|----------|-----------|
| Data Source | `.pkl` files | MongoDB database |
| Interface | Command line | Web browser |
| Visualization | Static PNG/HTML | Interactive map |
| Parameters | Hardcoded | Adjustable UI |
| Real-time | No | Yes |
| Multi-user | No | Yes (potential) |
| Results Storage | Files | Database + Memory |
| Deployment | Local only | Web deployable |

## 🔧 Core Algorithm

**Good news**: The core detection algorithm (`anomaly_logic.py`) is **exactly the same**! No changes to the detection logic.

### Unchanged Components:
- ✅ Proximity detection algorithm
- ✅ Duration thresholds
- ✅ SOG filtering
- ✅ Port distance checking
- ✅ Time gap handling
- ✅ BallTree spatial indexing

### What Changed:
- 🔄 Data input: From `pd.read_pickle()` → MongoDB queries
- 🔄 Output format: From files → JSON API responses
- ➕ Added: REST API layer
- ➕ Added: Web interface
- ➕ Added: Real-time parameter adjustment

## 🗄️ Data Structure Mapping

### Original PKL Data (from test_case generator)

```python
{
    'mmsi': 111111111,
    'lat': -6.0,
    'lon': 105.5,
    'sog': 0.3,
    'created_at': datetime(2023, 8, 1, 10, 0, 0)
}
```

### MongoDB Document Structure

```javascript
{
    "_id": ObjectId("..."),
    "mmsi": 111111111,           // int32
    "lat": -6.0,                 // float32
    "lon": 105.5,                // float32
    "sog": 0.3,                  // float32
    "created_at": ISODate("..."), // datetime
    "cog": 180.5,                // optional
    "heading": 180,              // optional
    "vessel_type": "Cargo",      // optional
    "vessel_name": "Ship Name"   // optional
}
```

**Key Points:**
- Core fields are identical
- Additional optional fields for enrichment
- MongoDB handles datetime natively
- Efficient indexing for queries

## 🔄 Migration Scenarios

### Scenario 1: Using Test Data (Current)

**Status**: ✅ Already working

You're using the seeded test data that mimics the structure of `test_case/*.pkl` files.

```bash
# What you did
python seed_database.py
# Selected option 1 (test scenarios)
```

**Result**: Database populated with test scenarios matching your original test cases.

### Scenario 2: Connecting to Real MongoDB (Future)

**When**: You get access to the production MongoDB

**Steps**:

1. **Get connection details** from your team:
   ```
   Host: mongodb://production-server:27017/
   Database: your_database_name
   Collection: ais_collection_name
   Username: (if authentication enabled)
   Password: (if authentication enabled)
   ```

2. **Update backend/.env**:
   ```bash
   # OLD (test)
   MONGODB_URI=mongodb://localhost:27017/
   DATABASE_NAME=ais_transhipment_db
   COLLECTION_NAME=ais_signals
   
   # NEW (production)
   MONGODB_URI=mongodb://username:password@prod-server:27017/
   DATABASE_NAME=real_database_name
   COLLECTION_NAME=real_collection_name
   ```

3. **Verify data structure**:
   ```bash
   mongosh "mongodb://prod-server/real_database"
   
   # Check collection
   use real_database_name
   db.real_collection_name.findOne()
   
   # Verify required fields exist
   db.real_collection_name.findOne({}, {mmsi:1, lat:1, lon:1, sog:1, created_at:1})
   ```

4. **Restart backend**:
   ```bash
   ./stop_all.sh
   ./start_all.sh
   ```

### Scenario 3: Migrating PKL Files to MongoDB

**When**: You have `.pkl` files but want to use the web system

**Option A: One-time migration script**

```python
# migrate_pkl_to_mongo.py
import pandas as pd
from pymongo import MongoClient
import glob

client = MongoClient("mongodb://localhost:27017/")
db = client["ais_transhipment_db"]
collection = db["ais_signals"]

# Clear existing data (optional)
collection.delete_many({})

# Process all PKL files
for pkl_file in glob.glob("data/*.pkl"):
    print(f"Processing {pkl_file}...")
    df = pd.read_pickle(pkl_file)
    
    # Convert to records
    records = df.to_dict('records')
    
    # Insert to MongoDB
    if records:
        collection.insert_many(records)
        print(f"  Inserted {len(records)} documents")

print("Migration complete!")
```

**Option B: Continuous sync (if PKL files update regularly)**

```python
# watch_and_sync.py
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class PKLHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.pkl'):
            sync_file_to_mongo(event.src_path)

# Setup file watcher
observer = Observer()
observer.schedule(PKLHandler(), path='data/', recursive=False)
observer.start()
```

### Scenario 4: Hybrid Approach

**When**: You want to use both systems temporarily

```bash
# Original system for batch processing
python V3/main.py real_case

# New system for interactive analysis
./start_all.sh
```

## 📈 Performance Considerations

### Original System Performance

- **Pros**: 
  - Fast for single file processing
  - No network overhead
  - Simple deployment

- **Cons**:
  - Loads entire dataset into memory
  - No concurrent access
  - Results not persistent

### Web System Performance

- **Pros**:
  - Query only date ranges needed
  - Database indexes for speed
  - Persistent results
  - Multiple users

- **Cons**:
  - Network latency (if remote DB)
  - Initial setup complexity

### Optimization Tips

1. **Date Range Queries**:
   ```javascript
   // Good: Specific range
   start: "2023-08-01T00:00:00"
   end: "2023-08-02T00:00:00"
   
   // Bad: Very large range
   start: "2023-01-01T00:00:00"
   end: "2023-12-31T23:59:59"
   ```

2. **Indexes** (already configured):
   ```javascript
   db.ais_signals.createIndex({created_at: 1, mmsi: 1})
   db.ais_signals.createIndex({lat: 1, lon: 1})
   db.ais_signals.createIndex({mmsi: 1})
   ```

3. **Data Sampling**:
   - For large datasets, the backend already samples (1-minute intervals)
   - Original code does the same: `df.groupby(['mmsi', pd.Grouper(key='utc', freq='1min')])`

## 🧪 Testing Migration

### 1. Test with Known Results

Use your original test cases to verify consistency:

```bash
# Original system
cd V3
python main.py test_case

# Check results
cat results/ais_test_case_valid_anomali.csv

# New system
cd ../ais-transhipment-web
./start_all.sh
# Use web interface with same date range
# Compare results
```

### 2. Compare Outputs

```python
# compare_results.py
import pandas as pd

# Load original results
original = pd.read_csv("V3/results/ais_test_case_valid_anomali.csv")

# Load web system results (from API or exported CSV)
web = pd.read_csv("web_results.csv")

# Compare
print("Original anomalies:", len(original))
print("Web anomalies:", len(web))

# Check for matches
merged = original.merge(
    web, 
    on=['mmsi_1', 'mmsi_2'], 
    suffixes=('_orig', '_web')
)
print("Matching anomalies:", len(merged))
```

## 🔧 Troubleshooting Migration

### Issue: Different Results

**Possible causes**:
1. Date/time timezone differences
2. Data sampling differences
3. Parameter differences

**Solution**:
```python
# Check timezones
df['created_at'] = pd.to_datetime(df['created_at'], utc=True)

# Check parameters match
print("Original params:", {
    'proximity_km': 0.2,
    'duration_min': 30,
    # ... etc
})
```

### Issue: Missing Data

**Check**:
```bash
# MongoDB data count
mongosh --eval "db.ais_signals.countDocuments()"

# PKL file size
wc -l data/maritim_selat_sunda.pkl
```

### Issue: Performance Degradation

**Solutions**:
1. Add more indexes
2. Use smaller date ranges
3. Enable MongoDB caching
4. Increase server resources

## 📝 Migration Checklist

- [ ] Backup original PKL files
- [ ] Document current system parameters
- [ ] Run full test suite on original system
- [ ] Setup MongoDB (local or connect to prod)
- [ ] Migrate/sync data to MongoDB
- [ ] Verify data structure matches
- [ ] Run test detection on web system
- [ ] Compare results with original
- [ ] Document any differences
- [ ] Train users on new interface
- [ ] Setup monitoring/logging
- [ ] Plan rollback strategy (if needed)

## 🎯 Recommended Migration Path

### Phase 1: Parallel Testing (Week 1-2)
- Run both systems simultaneously
- Compare results daily
- Fix any discrepancies

### Phase 2: Gradual Transition (Week 3-4)
- Use web system for new analyses
- Keep original system as backup
- Train users

### Phase 3: Full Migration (Week 5+)
- Primary: Web system
- Backup: Original system (for verification)
- Archive PKL files

## 💡 Best Practices

1. **Keep Original System**:
   - Don't delete V3 code
   - Useful for batch processing
   - Good for verification

2. **Version Control**:
   ```bash
   git init
   git add .
   git commit -m "Initial web migration"
   ```

3. **Documentation**:
   - Document parameter changes
   - Record migration decisions
   - Keep change logs

4. **Monitoring**:
   - Log all detections
   - Track API performance
   - Monitor database size

5. **Backup Strategy**:
   ```bash
   # Regular MongoDB backups
   mongodump --db=ais_transhipment_db --out=./backup_$(date +%Y%m%d)
   ```

## 🚀 Future Enhancements

After successful migration, consider:

1. **Real-time Processing**: Stream AIS data directly to MongoDB
2. **Historical Analysis**: Trends over time
3. **Alerts**: Email/SMS notifications for anomalies
4. **Reporting**: Automated PDF/Excel reports
5. **API Integration**: Connect with other systems
6. **Machine Learning**: Enhance detection with ML models

## 📞 Need Help?

- Review logs: `tail -f /var/log/mongodb/mongod.log`
- Check backend logs: Terminal running Flask
- Browser console: F12 → Console tab
- Compare with test cases: Use known scenarios

---

**Remember**: The core algorithm is identical. Migration is mainly about changing data source and adding web interface! 🎉