"""
Database Manager - Clean, Reset, and Manage AIS Database
Complete database management utilities for presentations and testing
"""

import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")
ALERTS_COLLECTION = "anomaly_alerts"


def get_database():
    """Connects to MongoDB and returns database instance"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        db = client[DATABASE_NAME]
        return db
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def get_database_stats(db):
    """Gets current database statistics"""
    collection = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]
    
    total_signals = collection.count_documents({})
    simulation_signals = collection.count_documents({"simulation": True})
    real_signals = total_signals - simulation_signals
    
    unique_vessels = len(collection.distinct('mmsi'))
    total_alerts = alerts_collection.count_documents({})
    
    # Date range
    date_range = {"min": None, "max": None}
    if total_signals > 0:
        date_agg = list(collection.aggregate([
            {"$group": {
                "_id": None,
                "min_date": {"$min": "$created_at"},
                "max_date": {"$max": "$created_at"}
            }}
        ]))
        if date_agg:
            date_range["min"] = date_agg[0]["min_date"]
            date_range["max"] = date_agg[0]["max_date"]
    
    return {
        "total_signals": total_signals,
        "simulation_signals": simulation_signals,
        "real_signals": real_signals,
        "unique_vessels": unique_vessels,
        "total_alerts": total_alerts,
        "date_range": date_range
    }


def display_stats(db):
    """Displays current database statistics"""
    stats = get_database_stats(db)
    
    print("\n" + "="*70)
    print("📊 CURRENT DATABASE STATUS")
    print("="*70)
    print(f"Database: {DATABASE_NAME}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"\n📡 AIS Signals:")
    print(f"   Total Signals:      {stats['total_signals']:,}")
    print(f"   └─ Simulation Data: {stats['simulation_signals']:,}")
    print(f"   └─ Real Data:       {stats['real_signals']:,}")
    print(f"   Unique Vessels:     {stats['unique_vessels']:,}")
    
    if stats['date_range']['min'] and stats['date_range']['max']:
        print(f"\n📅 Data Date Range:")
        print(f"   From: {stats['date_range']['min'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   To:   {stats['date_range']['max'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n🚨 Alert History:")
    print(f"   Total Alerts: {stats['total_alerts']:,}")
    
    print("="*70 + "\n")


def clear_simulation_data(db):
    """Clears only simulation data, keeps real data"""
    collection = db[COLLECTION_NAME]
    
    count_before = collection.count_documents({"simulation": True})
    
    if count_before == 0:
        print("ℹ️  No simulation data found")
        return False
    
    print(f"\n⚠️  About to delete {count_before:,} simulation signals")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return False
    
    result = collection.delete_many({"simulation": True})
    print(f"✅ Deleted {result.deleted_count:,} simulation signals")
    return True


def clear_alert_history(db):
    """Clears alert history"""
    alerts_collection = db[ALERTS_COLLECTION]
    
    count_before = alerts_collection.count_documents({})
    
    if count_before == 0:
        print("ℹ️  No alert history found")
        return False
    
    print(f"\n⚠️  About to delete {count_before:,} alert records")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return False
    
    result = alerts_collection.delete_many({})
    print(f"✅ Deleted {result.deleted_count:,} alert records")
    return True


def clear_old_data(db, days):
    """Clears data older than specified days"""
    collection = db[COLLECTION_NAME]
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    count_before = collection.count_documents({
        "created_at": {"$lt": cutoff_date}
    })
    
    if count_before == 0:
        print(f"ℹ️  No data older than {days} days found")
        return False
    
    print(f"\n⚠️  About to delete {count_before:,} signals older than {days} days")
    print(f"   (Before: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')})")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return False
    
    result = collection.delete_many({
        "created_at": {"$lt": cutoff_date}
    })
    print(f"✅ Deleted {result.deleted_count:,} old signals")
    return True


def clear_all_data(db):
    """Clears ALL data (nuclear option)"""
    collection = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]
    
    signal_count = collection.count_documents({})
    alert_count = alerts_collection.count_documents({})
    
    if signal_count == 0 and alert_count == 0:
        print("ℹ️  Database is already empty")
        return False
    
    print(f"\n{'='*70}")
    print("⚠️  ⚠️  ⚠️  NUCLEAR OPTION - DELETE EVERYTHING ⚠️  ⚠️  ⚠️")
    print(f"{'='*70}")
    print(f"This will delete:")
    print(f"   • {signal_count:,} AIS signals (ALL data)")
    print(f"   • {alert_count:,} alert records")
    print(f"{'='*70}")
    
    confirm1 = input("Are you ABSOLUTELY sure? Type 'DELETE ALL': ").strip()
    
    if confirm1 != 'DELETE ALL':
        print("❌ Cancelled")
        return False
    
    confirm2 = input("Last chance! Type 'YES' to confirm: ").strip().upper()
    
    if confirm2 != 'YES':
        print("❌ Cancelled")
        return False
    
    print("\n🗑️  Deleting all data...")
    
    result1 = collection.delete_many({})
    result2 = alerts_collection.delete_many({})
    
    print(f"✅ Deleted {result1.deleted_count:,} AIS signals")
    print(f"✅ Deleted {result2.deleted_count:,} alert records")
    print(f"✅ Database is now empty")
    
    return True


def clear_test_data(db):
    """Clears test case data (from seed_database.py)"""
    collection = db[COLLECTION_NAME]
    
    # Test data typically has MMSI in specific ranges
    test_mmsi_ranges = [
        {"mmsi": {"$gte": 111111111, "$lte": 111999999}},  # Test case range 1
        {"mmsi": {"$gte": 222222222, "$lte": 222999999}},  # Test case range 2
        {"mmsi": {"$gte": 900000000, "$lte": 900999999}},  # Noise vessels
    ]
    
    count_before = collection.count_documents({"$or": test_mmsi_ranges})
    
    if count_before == 0:
        print("ℹ️  No test case data found")
        return False
    
    print(f"\n⚠️  About to delete {count_before:,} test case signals")
    print("   (MMSI ranges: 111111xxx, 222222xxx, 900000xxx)")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return False
    
    result = collection.delete_many({"$or": test_mmsi_ranges})
    print(f"✅ Deleted {result.deleted_count:,} test case signals")
    return True


def presentation_ready_reset(db):
    """Complete reset for clean presentation"""
    print("\n" + "="*70)
    print("🎯 PRESENTATION READY RESET")
    print("="*70)
    print("This will:")
    print("  1. Clear all simulation data")
    print("  2. Clear all test case data")
    print("  3. Clear alert history")
    print("  4. Keep any real/production data intact")
    print("="*70)
    
    confirm = input("\nProceed with presentation reset? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("❌ Cancelled")
        return False
    
    print("\n🧹 Cleaning database for presentation...")
    
    # Clear simulation data
    print("\n1️⃣ Clearing simulation data...")
    collection = db[COLLECTION_NAME]
    result1 = collection.delete_many({"simulation": True})
    print(f"   ✅ Deleted {result1.deleted_count:,} simulation signals")
    
    # Clear test case data
    print("\n2️⃣ Clearing test case data...")
    test_mmsi_ranges = [
        {"mmsi": {"$gte": 111111111, "$lte": 111999999}},
        {"mmsi": {"$gte": 222222222, "$lte": 222999999}},
        {"mmsi": {"$gte": 900000000, "$lte": 900999999}},
    ]
    result2 = collection.delete_many({"$or": test_mmsi_ranges})
    print(f"   ✅ Deleted {result2.deleted_count:,} test case signals")
    
    # Clear alert history
    print("\n3️⃣ Clearing alert history...")
    alerts_collection = db[ALERTS_COLLECTION]
    result3 = alerts_collection.delete_many({})
    print(f"   ✅ Deleted {result3.deleted_count:,} alert records")
    
    print("\n" + "="*70)
    print("✅ PRESENTATION RESET COMPLETE!")
    print("="*70)
    print("Your database is now clean and ready for:")
    print("  • Fresh demonstrations")
    print("  • New simulations")
    print("  • Live presentations")
    print("="*70)
    
    return True


def backup_database(db):
    """Creates a backup of current database state"""
    import subprocess
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"backup_{timestamp}"
    
    print(f"\n📦 Creating database backup...")
    print(f"   Backup directory: {backup_dir}")
    
    try:
        # Use mongodump
        cmd = [
            "mongodump",
            "--uri", MONGODB_URI,
            "--db", DATABASE_NAME,
            "--out", backup_dir
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Backup created successfully: {backup_dir}")
        print(f"\nTo restore this backup:")
        print(f"   mongorestore --uri {MONGODB_URI} --db {DATABASE_NAME} {backup_dir}/{DATABASE_NAME}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Backup failed: {e}")
        return False
    except FileNotFoundError:
        print("❌ mongodump not found. Install MongoDB Database Tools:")
        print("   https://www.mongodb.com/docs/database-tools/installation/installation/")
        return False


def show_menu():
    """Displays main menu"""
    print("\n" + "="*70)
    print("🗄️  DATABASE MANAGER - Choose an action:")
    print("="*70)
    print("\n📊 Information:")
    print("  [1] Show Database Statistics")
    print("\n🧹 Clean Specific Data:")
    print("  [2] Clear Simulation Data Only")
    print("  [3] Clear Test Case Data Only")
    print("  [4] Clear Alert History Only")
    print("  [5] Clear Old Data (by date)")
    print("\n🎯 Quick Actions:")
    print("  [6] 🎯 Presentation Ready Reset (Recommended)")
    print("      └─ Clears simulation + test + alerts (keeps real data)")
    print("\n⚠️  Nuclear Options:")
    print("  [7] 💣 Clear ALL Data (Everything)")
    print("\n💾 Backup:")
    print("  [8] Create Database Backup")
    print("\n[Q] Quit")
    print("="*70)


def main():
    """Main execution function"""
    
    print("\n🗄️  AIS Transhipment - Database Manager")
    print("Manage and clean your database for presentations and testing\n")
    
    db = get_database()
    print(f"✅ Connected to: {DATABASE_NAME}")
    
    while True:
        show_menu()
        
        choice = input("\nSelect action (1-8 or Q): ").strip().upper()
        
        if choice == 'Q':
            print("\n👋 Exiting database manager...")
            break
        
        elif choice == '1':
            display_stats(db)
        
        elif choice == '2':
            print("\n🧹 CLEAR SIMULATION DATA")
            print("="*70)
            print("This will remove all data marked as 'simulation: true'")
            print("Real data will NOT be affected")
            print("="*70)
            clear_simulation_data(db)
            display_stats(db)
        
        elif choice == '3':
            print("\n🧹 CLEAR TEST CASE DATA")
            print("="*70)
            print("This will remove data from seed_database.py test scenarios")
            print("(MMSI ranges: 111111xxx, 222222xxx, 900000xxx)")
            print("="*70)
            clear_test_data(db)
            display_stats(db)
        
        elif choice == '4':
            print("\n🧹 CLEAR ALERT HISTORY")
            print("="*70)
            print("This will remove all alert records from anomaly_alerts collection")
            print("AIS signals will NOT be affected")
            print("="*70)
            clear_alert_history(db)
            display_stats(db)
        
        elif choice == '5':
            print("\n🧹 CLEAR OLD DATA")
            print("="*70)
            days = input("Delete data older than how many days? (e.g., 30): ").strip()
            try:
                days = int(days)
                clear_old_data(db, days)
                display_stats(db)
            except ValueError:
                print("❌ Invalid number")
        
        elif choice == '6':
            presentation_ready_reset(db)
            display_stats(db)
        
        elif choice == '7':
            print("\n💣 CLEAR ALL DATA")
            clear_all_data(db)
            display_stats(db)
        
        elif choice == '8':
            backup_database(db)
        
        else:
            print("❌ Invalid choice")
            continue
        
        # Ask if user wants to continue
        if choice != '1':  # Don't ask after just viewing stats
            another = input("\nPerform another action? (y/n): ").strip().lower()
            if another != 'y':
                break
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()