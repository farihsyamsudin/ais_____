"""
MongoDB Seeder for AIS Transhipment Detection System
Generates realistic test data similar to test_case generator
"""

import pymongo
from pymongo import MongoClient, ASCENDING
from datetime import datetime, timedelta
import random
import sys

# ==============================
# Configuration
# ==============================

MONGODB_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "ais_transhipment_db"
COLLECTION_NAME = "ais_signals"

# Port coordinates (same as your original code)
PORTS = [
    {"name": "Pelabuhan Merak", "lat": -5.8933, "lon": 106.0086},
    {"name": "Pelabuhan Ciwandan", "lat": -5.9525, "lon": 106.0358},
    {"name": "Pelabuhan Bojonegara", "lat": -5.8995, "lon": 106.0657},
    {"name": "Pelabuhan Bakauheni", "lat": -5.8711, "lon": 105.7421},
    {"name": "Pelabuhan Panjang", "lat": -5.4558, "lon": 105.3134},
]

# ==============================
# Database Connection
# ==============================

def get_database():
    """Connects to MongoDB and returns database instance"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        client.server_info()
        db = client[DATABASE_NAME]
        print(f"✅ Connected to MongoDB: {DATABASE_NAME}")
        return db
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

def setup_indexes(collection):
    """Creates indexes for optimized queries"""
    # Compound index for efficient querying
    collection.create_index([
        ("created_at", ASCENDING),
        ("mmsi", ASCENDING)
    ])
    collection.create_index([("lat", ASCENDING), ("lon", ASCENDING)])
    collection.create_index("mmsi")
    print("✅ Indexes created")

# ==============================
# Data Generation Functions
# ==============================

def generate_scenario(scenario_type, start_time, duration=40, num_pairs=1):
    """
    Generates AIS data for different test scenarios
    
    Args:
        scenario_type: Type of test scenario
        start_time: Starting datetime
        duration: Duration in minutes
        num_pairs: Number of vessel pairs
    
    Returns:
        List of document dictionaries
    """
    documents = []
    
    for i in range(duration):
        t = start_time + timedelta(minutes=i)
        
        # Apply gap for specific scenarios
        if "gap" in scenario_type and (10 <= i < 25):
            continue
        
        for k in range(num_pairs):
            # Unique MMSI for each pair
            mmsi1 = 111111111 + (k * 1000)
            mmsi2 = 222222222 + (k * 1000)
            
            # Different base coordinates for each pair
            base_lat = -6.0 - (k * 0.01)
            base_lon = 105.5 + (k * 0.01)
            
            # Default proximity (close ~40m)
            lat1, lon1 = base_lat, base_lon
            lat2, lon2 = base_lat + 0.0003, base_lon + 0.0003
            
            # Default speed (low)
            sog1 = sog2 = 0.3
            
            # Apply scenario-specific modifications
            if "far_proximity" in scenario_type:
                lat2, lon2 = base_lat + 0.02, base_lon + 0.02  # ~2.8 km
            
            if "near_port" in scenario_type:
                lat1, lon1 = -5.89 - (k * 0.001), 106.01 + (k * 0.001)
                if "far_proximity" in scenario_type:
                    lat2, lon2 = lat1 + 0.02, lon1 + 0.02
                else:
                    lat2, lon2 = lat1 + 0.0003, lon1 + 0.0003
            
            if "high_speed" in scenario_type:
                sog1 = sog2 = 1.2
            
            # Add vessel 1
            documents.append({
                "mmsi": mmsi1,
                "lat": round(lat1, 6),
                "lon": round(lon1, 6),
                "sog": round(sog1, 2),
                "created_at": t,
                "cog": round(random.uniform(0, 360), 1),
                "heading": random.randint(0, 359),
                "vessel_type": random.choice(["Cargo", "Tanker", "Fishing"]),
                "vessel_name": f"Vessel_{mmsi1}"
            })
            
            # Add vessel 2
            documents.append({
                "mmsi": mmsi2,
                "lat": round(lat2, 6),
                "lon": round(lon2, 6),
                "sog": round(sog2, 2),
                "created_at": t,
                "cog": round(random.uniform(0, 360), 1),
                "heading": random.randint(0, 359),
                "vessel_type": random.choice(["Cargo", "Tanker", "Fishing"]),
                "vessel_name": f"Vessel_{mmsi2}"
            })
    
    return documents

def add_noise_vessels(documents, start_time, duration=40, num_noise=3):
    """Adds random noise vessels to make data more realistic"""
    for i in range(duration):
        t = start_time + timedelta(minutes=i)
        
        for n in range(num_noise):
            mmsi_noise = 900000000 + n
            
            # Random position in Selat Sunda area
            lat_noise = random.uniform(-6.4, -5.6)
            lon_noise = random.uniform(105.1, 105.9)
            sog_noise = random.uniform(0.0, 15.0)
            
            documents.append({
                "mmsi": mmsi_noise,
                "lat": round(lat_noise, 6),
                "lon": round(lon_noise, 6),
                "sog": round(sog_noise, 2),
                "created_at": t,
                "cog": round(random.uniform(0, 360), 1),
                "heading": random.randint(0, 359),
                "vessel_type": random.choice(["Cargo", "Tanker", "Passenger", "Other"]),
                "vessel_name": f"Noise_Vessel_{mmsi_noise}"
            })
    
    return documents

# ==============================
# Seeding Functions
# ==============================

def seed_test_scenarios(collection):
    """Seeds all test scenarios similar to test_case generator"""
    
    scenarios = [
        # Valid anomalies
        {"type": "valid", "duration": 40, "pairs": 1},
        {"type": "valid_multi", "duration": 40, "pairs": 5},
        
        # Short duration (should be candidate or rejected)
        {"type": "short_duration", "duration": 20, "pairs": 1},
        {"type": "short_duration_multi", "duration": 20, "pairs": 5},
        
        # Far proximity (should be rejected)
        {"type": "far_proximity", "duration": 40, "pairs": 1},
        {"type": "far_proximity_multi", "duration": 40, "pairs": 5},
        
        # High speed (should be rejected)
        {"type": "high_speed", "duration": 40, "pairs": 1},
        {"type": "high_speed_multi", "duration": 40, "pairs": 5},
        
        # Near port (should be rejected)
        {"type": "near_port", "duration": 40, "pairs": 1},
        {"type": "near_port_multi", "duration": 40, "pairs": 5},
        
        # With gap (may split into multiple sessions)
        {"type": "gap", "duration": 40, "pairs": 1},
        {"type": "gap_multi", "duration": 40, "pairs": 5},
        
        # Borderline cases
        {"type": "borderline", "duration": 31, "pairs": 1},
        {"type": "borderline_multi", "duration": 31, "pairs": 5},
    ]
    
    base_time = datetime(2023, 8, 1, 10, 0, 0)
    time_offset = timedelta(days=0)
    
    print("\n📦 Seeding test scenarios...")
    total_docs = 0
    
    for scenario in scenarios:
        scenario_time = base_time + time_offset
        docs = generate_scenario(
            scenario["type"], 
            scenario_time, 
            scenario["duration"], 
            scenario["pairs"]
        )
        
        # Add noise for realism
        if "multi" in scenario["type"]:
            docs = add_noise_vessels(docs, scenario_time, scenario["duration"], num_noise=2)
        
        if docs:
            collection.insert_many(docs)
            total_docs += len(docs)
            print(f"  ✅ {scenario['type']}: {len(docs)} documents")
        
        # Offset time for next scenario (avoid overlap)
        time_offset += timedelta(hours=2)
    
    print(f"\n✅ Total test documents inserted: {total_docs}")

def seed_realistic_data(collection, days=7):
    """
    Seeds realistic continuous data for multiple days
    Simulates normal vessel traffic + some anomalies
    """
    print(f"\n📦 Seeding {days} days of realistic data...")
    
    start_date = datetime(2024, 1, 1, 0, 0, 0)
    documents = []
    
    # Normal traffic vessels (moving around)
    normal_vessels = list(range(300000000, 300000010))  # 10 normal vessels
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        # Generate normal traffic (1 signal per 5 minutes)
        for minute in range(0, 1440, 5):  # 24 hours
            t = current_date + timedelta(minutes=minute)
            
            for mmsi in normal_vessels:
                lat = random.uniform(-6.3, -5.7)
                lon = random.uniform(105.2, 105.8)
                sog = random.uniform(5.0, 12.0)  # Normal moving speed
                
                documents.append({
                    "mmsi": mmsi,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "sog": round(sog, 2),
                    "created_at": t,
                    "cog": round(random.uniform(0, 360), 1),
                    "heading": random.randint(0, 359),
                    "vessel_type": random.choice(["Cargo", "Tanker"]),
                    "vessel_name": f"Normal_Vessel_{mmsi}"
                })
        
        # Inject 1-2 potential anomalies per day
        num_anomalies = random.randint(1, 2)
        for _ in range(num_anomalies):
            anomaly_start = current_date + timedelta(hours=random.randint(8, 18))
            mmsi_pair = [400000000 + random.randint(0, 100), 500000000 + random.randint(0, 100)]
            
            # Generate 35-45 minutes of proximity
            duration = random.randint(35, 45)
            base_lat = random.uniform(-6.2, -5.8)
            base_lon = random.uniform(105.3, 105.7)
            
            for i in range(duration):
                t = anomaly_start + timedelta(minutes=i)
                
                for idx, mmsi in enumerate(mmsi_pair):
                    lat = base_lat + (idx * 0.0003) + random.uniform(-0.0001, 0.0001)
                    lon = base_lon + (idx * 0.0003) + random.uniform(-0.0001, 0.0001)
                    
                    documents.append({
                        "mmsi": mmsi,
                        "lat": round(lat, 6),
                        "lon": round(lon, 6),
                        "sog": round(random.uniform(0.1, 0.4), 2),
                        "created_at": t,
                        "cog": round(random.uniform(0, 360), 1),
                        "heading": random.randint(0, 359),
                        "vessel_type": random.choice(["Cargo", "Tanker", "Fishing"]),
                        "vessel_name": f"Suspicious_Vessel_{mmsi}"
                    })
    
    # Bulk insert for performance
    if documents:
        # Insert in batches of 10000
        batch_size = 10000
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i+batch_size]
            collection.insert_many(batch)
            print(f"  Inserted batch {i//batch_size + 1}: {len(batch)} documents")
        
        print(f"✅ Total realistic documents inserted: {len(documents)}")

# ==============================
# Main Execution
# ==============================

def main():
    print("=" * 60)
    print("🚢 AIS Transhipment DB Seeder")
    print("=" * 60)
    
    # Connect to database
    db = get_database()
    collection = db[COLLECTION_NAME]
    
    # Clear existing data
    print("\n🗑️  Clearing existing data...")
    result = collection.delete_many({})
    print(f"   Deleted {result.deleted_count} existing documents")
    
    # Setup indexes
    setup_indexes(collection)
    
    # Seed data
    print("\n" + "=" * 60)
    choice = input("Select seeding mode:\n1. Test scenarios only\n2. Realistic data only\n3. Both\nChoice (1/2/3): ")
    
    if choice in ["1", "3"]:
        seed_test_scenarios(collection)
    
    if choice in ["2", "3"]:
        days = int(input("How many days of realistic data? (default: 7): ") or "7")
        seed_realistic_data(collection, days)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Database Summary:")
    print(f"   Total documents: {collection.count_documents({})}")
    print(f"   Unique vessels: {len(collection.distinct('mmsi'))}")
    
    date_range = collection.aggregate([
        {"$group": {
            "_id": None,
            "min_date": {"$min": "$created_at"},
            "max_date": {"$max": "$created_at"}
        }}
    ])
    for doc in date_range:
        print(f"   Date range: {doc['min_date']} to {doc['max_date']}")
    
    print("=" * 60)
    print("✅ Seeding completed successfully!")

if __name__ == "__main__":
    main()
