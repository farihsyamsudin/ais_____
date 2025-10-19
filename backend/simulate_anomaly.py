"""
Anomaly Simulator - Real-time Data Injection
Simulates live vessel data that will trigger anomaly detection and email alerts
"""

import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta
import random
import time
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")

# Scenario configurations
SCENARIOS = {
    '1': {
        'name': 'Single Transhipment (30+ min)',
        'pairs': 1,
        'duration': 35,
        'location': (-6.0, 105.5),
        'description': 'Simulates one vessel pair meeting for 35 minutes'
    },
    '2': {
        'name': 'High Priority Alert (45+ min)',
        'pairs': 1,
        'duration': 50,
        'location': (-6.1, 105.6),
        'description': 'Simulates extended transhipment (50 min) - triggers HIGH PRIORITY alert'
    },
    '3': {
        'name': 'Multiple Simultaneous Transhipments',
        'pairs': 3,
        'duration': 40,
        'location': (-6.05, 105.55),
        'description': 'Simulates 3 vessel pairs conducting transhipment at same time'
    },
    '4': {
        'name': 'Borderline Case (30 min exactly)',
        'pairs': 1,
        'duration': 30,
        'location': (-5.95, 105.45),
        'description': 'Exactly at threshold - tests edge case detection'
    },
    '5': {
        'name': 'Quick Test (Fast insertion)',
        'pairs': 1,
        'duration': 35,
        'location': (-6.02, 105.52),
        'description': 'Same as scenario 1 but inserts data quickly for testing'
    }
}


def get_database():
    """Connects to MongoDB and returns database instance"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        db = client[DATABASE_NAME]
        print(f"✅ Connected to MongoDB: {DATABASE_NAME}")
        return db
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def generate_realistic_anomaly_data(scenario_config, base_time=None, fast_mode=False):
    """
    Generates realistic AIS data that will trigger anomaly detection
    
    Args:
        scenario_config: Configuration dictionary for scenario
        base_time: Base timestamp (defaults to now)
        fast_mode: If True, inserts data quickly without real-time delays
    
    Returns:
        List of documents to insert
    """
    
    if base_time is None:
        base_time = datetime.utcnow()
    
    documents = []
    duration = scenario_config['duration']
    num_pairs = scenario_config['pairs']
    base_lat, base_lon = scenario_config['location']
    
    print(f"\n📝 Generating {duration} minutes of data for {num_pairs} vessel pair(s)...")
    
    for minute in range(duration):
        timestamp = base_time + timedelta(minutes=minute)
        
        for pair_idx in range(num_pairs):
            # Generate unique MMSI pairs
            mmsi_1 = 100000000 + (pair_idx * 100) + random.randint(0, 99)
            mmsi_2 = 200000000 + (pair_idx * 100) + random.randint(0, 99)
            
            # Different base location for each pair
            pair_lat = base_lat - (pair_idx * 0.01)
            pair_lon = base_lon + (pair_idx * 0.01)
            
            # Add slight random movement (vessels drift slightly)
            lat_1 = pair_lat + random.uniform(-0.0001, 0.0001)
            lon_1 = pair_lon + random.uniform(-0.0001, 0.0001)
            
            # Second vessel very close (within 200m)
            lat_2 = lat_1 + 0.0003 + random.uniform(-0.0001, 0.0001)
            lon_2 = lon_1 + 0.0003 + random.uniform(-0.0001, 0.0001)
            
            # Very low speed (stationary/drifting)
            sog_1 = random.uniform(0.1, 0.4)
            sog_2 = random.uniform(0.1, 0.4)
            
            # Vessel 1
            documents.append({
                'mmsi': mmsi_1,
                'lat': round(lat_1, 6),
                'lon': round(lon_1, 6),
                'sog': round(sog_1, 2),
                'created_at': timestamp,
                'cog': round(random.uniform(0, 360), 1),
                'heading': random.randint(0, 359),
                'vessel_type': random.choice(['Cargo', 'Tanker', 'Fishing']),
                'vessel_name': f'SIM_VESSEL_{mmsi_1}',
                'simulation': True  # Mark as simulated data
            })
            
            # Vessel 2
            documents.append({
                'mmsi': mmsi_2,
                'lat': round(lat_2, 6),
                'lon': round(lon_2, 6),
                'sog': round(sog_2, 2),
                'created_at': timestamp,
                'cog': round(random.uniform(0, 360), 1),
                'heading': random.randint(0, 359),
                'vessel_type': random.choice(['Cargo', 'Tanker', 'Fishing']),
                'vessel_name': f'SIM_VESSEL_{mmsi_2}',
                'simulation': True
            })
    
    return documents


def insert_data_realtime(collection, documents, fast_mode=False):
    """
    Inserts data in real-time or batch mode
    
    Args:
        collection: MongoDB collection
        documents: List of documents to insert
        fast_mode: If True, insert all at once. If False, insert minute by minute
    """
    
    if fast_mode:
        print("⚡ Fast mode: Inserting all data at once...")
        collection.insert_many(documents)
        print(f"✅ Inserted {len(documents)} documents instantly")
        return
    
    # Real-time insertion (minute by minute)
    print("🕐 Real-time mode: Inserting data minute by minute...")
    print("   (This simulates actual live vessel tracking)")
    
    # Group documents by minute
    from itertools import groupby
    documents_sorted = sorted(documents, key=lambda x: x['created_at'])
    
    for created_at, group in groupby(documents_sorted, key=lambda x: x['created_at']):
        batch = list(group)
        collection.insert_many(batch)
        
        minute_str = created_at.strftime('%H:%M')
        print(f"   ⏰ {minute_str} - Inserted {len(batch)} signals", end='\r')
        
        # Wait 1 second per minute (simulated time compression)
        time.sleep(1)
    
    print(f"\n✅ Completed real-time insertion of {len(documents)} documents")


def run_simulation(scenario_key, fast_mode=False):
    """
    Runs the complete simulation for a scenario
    
    Args:
        scenario_key: Key of scenario to run
        fast_mode: Whether to use fast insertion mode
    """
    
    if scenario_key not in SCENARIOS:
        print(f"❌ Invalid scenario. Choose from: {', '.join(SCENARIOS.keys())}")
        return
    
    scenario = SCENARIOS[scenario_key]
    
    print("=" * 70)
    print(f"🚢 ANOMALY SIMULATION: {scenario['name']}")
    print("=" * 70)
    print(f"Description: {scenario['description']}")
    print(f"Duration: {scenario['duration']} minutes")
    print(f"Vessel Pairs: {scenario['pairs']}")
    print(f"Location: {scenario['location']}")
    print(f"Mode: {'⚡ Fast' if fast_mode else '🕐 Real-time'}")
    print("=" * 70)
    
    # Connect to database
    db = get_database()
    collection = db[COLLECTION_NAME]
    
    # Generate data
    base_time = datetime.utcnow()
    documents = generate_realistic_anomaly_data(scenario, base_time, fast_mode)
    
    # Insert data
    print(f"\n📡 Starting data insertion...")
    insert_data_realtime(collection, documents, fast_mode)
    
    print(f"\n✅ Simulation complete!")
    print(f"\n📊 Summary:")
    print(f"   • Total signals inserted: {len(documents)}")
    print(f"   • Time range: {base_time.strftime('%H:%M')} - {(base_time + timedelta(minutes=scenario['duration'])).strftime('%H:%M')}")
    print(f"   • Unique vessels: {scenario['pairs'] * 2}")
    
    # Show detection info
    print(f"\n🔍 Next Steps:")
    print(f"   1. The monitoring service should detect this anomaly")
    print(f"   2. An email alert will be sent automatically")
    print(f"   3. Check your email inbox for the alert")
    print(f"\n   OR manually trigger detection:")
    print(f"   python early_warning_monitor.py --check-now")
    
    return base_time


def show_menu():
    """Displays scenario selection menu"""
    
    print("\n" + "=" * 70)
    print("🎯 ANOMALY SIMULATOR - Choose a scenario:")
    print("=" * 70)
    
    for key, scenario in SCENARIOS.items():
        print(f"\n[{key}] {scenario['name']}")
        print(f"    {scenario['description']}")
        print(f"    Duration: {scenario['duration']} min | Pairs: {scenario['pairs']}")
    
    print("\n[Q] Quit")
    print("=" * 70)


def main():
    """Main execution function"""
    
    print("\n🚢 AIS Transhipment - Anomaly Simulator")
    print("This tool simulates vessel data that triggers anomaly detection\n")
    
    while True:
        show_menu()
        
        choice = input("\nSelect scenario (1-5) or Q to quit: ").strip().upper()
        
        if choice == 'Q':
            print("👋 Exiting simulator...")
            break
        
        if choice not in SCENARIOS:
            print("❌ Invalid choice. Please select 1-5 or Q")
            continue
        
        # Ask for mode
        mode_choice = input("\nChoose insertion mode:\n  [F] Fast (instant)\n  [R] Real-time (1 sec per minute)\nChoice (F/R): ").strip().upper()
        
        fast_mode = mode_choice == 'F'
        
        # Confirm
        confirm = input(f"\n⚠️  This will insert simulated data into the database. Continue? (y/n): ").strip().lower()
        
        if confirm == 'y':
            run_simulation(choice, fast_mode)
            
            another = input("\n\nRun another simulation? (y/n): ").strip().lower()
            if another != 'y':
                break
        else:
            print("❌ Simulation cancelled")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()