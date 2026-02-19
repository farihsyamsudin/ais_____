"""
Database Manager - Clean, Reset, and Manage AIS Database
Complete database management utilities for presentations and testing.

Skema real: immsi (int), mmsi (str), simulation (bool, seeder only)
"""

import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGODB_URI       = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME     = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME   = os.getenv("COLLECTION_NAME", "ais_signals")
ALERTS_COLLECTION = os.getenv("ALERTS_COLLECTION", "ais_alerts")


def get_database():
    """Connects to MongoDB and returns database instance"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client[DATABASE_NAME]
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def get_database_stats(db):
    """Gets current database statistics"""
    collection        = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]

    total_signals      = collection.count_documents({})
    simulation_signals = collection.count_documents({"simulation": True})
    real_signals       = total_signals - simulation_signals

    # Gunakan immsi (int) untuk hitung unique vessels — bukan mmsi (string)
    unique_vessels = len(collection.distinct('immsi'))
    total_alerts   = alerts_collection.count_documents({})

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
        "total_signals":      total_signals,
        "simulation_signals": simulation_signals,
        "real_signals":       real_signals,
        "unique_vessels":     unique_vessels,
        "total_alerts":       total_alerts,
        "date_range":         date_range
    }


def display_stats(db):
    """Displays current database statistics"""
    stats = get_database_stats(db)

    print("\n" + "="*70)
    print("📊 CURRENT DATABASE STATUS")
    print("="*70)
    print(f"  Database   : {DATABASE_NAME}")
    print(f"  Collection : {COLLECTION_NAME}")
    print(f"  Area       : Batam / Singapore / Johor")
    print("-"*70)
    print(f"  Total signals      : {stats['total_signals']:,}")
    print(f"  ├─ Real/Production : {stats['real_signals']:,}")
    print(f"  └─ Simulation/Seed : {stats['simulation_signals']:,}")
    print(f"  Unique vessels     : {stats['unique_vessels']:,}  (via immsi)")
    print(f"  Alert records      : {stats['total_alerts']:,}")

    if stats['date_range']['min']:
        print(f"  Date range : {stats['date_range']['min'].strftime('%Y-%m-%d %H:%M')} "
              f"→ {stats['date_range']['max'].strftime('%Y-%m-%d %H:%M')} UTC")
    else:
        print("  Date range : (empty)")
    print("="*70)


def clear_simulation_data(db):
    """
    Clears all data marked with simulation=True.
    Data produksi real TIDAK akan tersentuh.
    """
    collection = db[COLLECTION_NAME]

    count = collection.count_documents({"simulation": True})
    if count == 0:
        print("ℹ️  No simulation data found.")
        return False

    print(f"\n⚠️  About to delete {count:,} simulation signals")
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return False

    result = collection.delete_many({"simulation": True})
    print(f"✅ Deleted {result.deleted_count:,} simulation signals")
    return True


def clear_test_data(db):
    """
    Clears test/seed data.
    Menggunakan flag 'simulation: true' — AMAN untuk data produksi.
    
    CATATAN: Tidak lagi pakai MMSI range (111111xxx, dll) karena seeder baru
    menggunakan MMSI real (525xxxxxx, 564xxxxxx, dll) yang bisa overlap
    dengan data produksi. Flag simulation=True adalah satu-satunya cara aman.
    """
    collection = db[COLLECTION_NAME]

    count = collection.count_documents({"simulation": True})
    if count == 0:
        print("ℹ️  No seeded/simulation test data found.")
        return False

    print(f"\n⚠️  About to delete {count:,} seeded test signals (simulation=True)")
    print("   Data produksi real TIDAK akan tersentuh.")
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return False

    result = collection.delete_many({"simulation": True})
    print(f"✅ Deleted {result.deleted_count:,} test signals")
    return True


def clear_alert_history(db):
    """Clears all alert records"""
    alerts_collection = db[ALERTS_COLLECTION]

    count = alerts_collection.count_documents({})
    if count == 0:
        print("ℹ️  No alert records found.")
        return False

    print(f"\n⚠️  About to delete {count:,} alert records")
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return False

    result = alerts_collection.delete_many({})
    print(f"✅ Deleted {result.deleted_count:,} alert records")
    return True


def clear_old_data(db, days_old):
    """Clears data older than specified number of days"""
    collection  = db[COLLECTION_NAME]
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    count = collection.count_documents({"created_at": {"$lt": cutoff_date}})
    if count == 0:
        print(f"ℹ️  No data older than {days_old} days found.")
        return False

    print(f"\n⚠️  About to delete {count:,} signals older than {cutoff_date.strftime('%Y-%m-%d')}")
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return False

    result = collection.delete_many({"created_at": {"$lt": cutoff_date}})
    print(f"✅ Deleted {result.deleted_count:,} old signals")
    return True


def clear_all_data(db):
    """Clears ALL data — nuclear option"""
    collection        = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]

    signal_count = collection.count_documents({})
    alert_count  = alerts_collection.count_documents({})

    if signal_count == 0 and alert_count == 0:
        print("ℹ️  Database is already empty.")
        return False

    print(f"\n{'='*70}")
    print("⚠️  ⚠️  ⚠️  NUCLEAR OPTION - DELETE EVERYTHING ⚠️  ⚠️  ⚠️")
    print(f"{'='*70}")
    print(f"  This will delete:")
    print(f"  • {signal_count:,} AIS signals (ALL — termasuk data produksi real!)")
    print(f"  • {alert_count:,} alert records")
    print(f"{'='*70}")

    confirm1 = input("Are you ABSOLUTELY sure? Type 'DELETE ALL': ").strip()
    if confirm1 != 'DELETE ALL':
        print("❌ Cancelled")
        return False

    confirm2 = input("Last chance! Type 'YES' to confirm: ").strip().upper()
    if confirm2 != 'YES':
        print("❌ Cancelled")
        return False

    result1 = collection.delete_many({})
    result2 = alerts_collection.delete_many({})
    print(f"✅ Deleted {result1.deleted_count:,} AIS signals")
    print(f"✅ Deleted {result2.deleted_count:,} alert records")
    print("✅ Database is now empty")
    return True


def presentation_ready_reset(db):
    """
    Complete reset for clean presentation.
    Hapus semua simulation/seed data + alert history.
    Data produksi real TIDAK tersentuh.
    """
    print("\n" + "="*70)
    print("🎯 PRESENTATION READY RESET")
    print("="*70)
    print("This will:")
    print("  1. Clear all simulation/seed data  (simulation=True)")
    print("  2. Clear all alert history")
    print("  3. Keep real/production data intact")
    print("="*70)

    confirm = input("\nProceed? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cancelled")
        return False

    collection        = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]

    print("\n🧹 Cleaning database...")

    # 1. Clear simulation/seed data — pakai flag, BUKAN MMSI range
    print("\n1️⃣  Clearing simulation/seed data...")
    result1 = collection.delete_many({"simulation": True})
    print(f"   ✅ Deleted {result1.deleted_count:,} simulation signals")

    # 2. Clear alert history
    print("\n2️⃣  Clearing alert history...")
    result2 = alerts_collection.delete_many({})
    print(f"   ✅ Deleted {result2.deleted_count:,} alert records")

    print("\n" + "="*70)
    print("✅ PRESENTATION RESET COMPLETE!")
    print("="*70)
    print("Database is now clean and ready for:")
    print("  • Fresh demonstrations")
    print("  • New simulations")
    print("  • Live presentations")
    print("="*70)
    return True


def backup_database(db):
    """Creates a backup of current database via mongodump"""
    import subprocess

    timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"backup_{timestamp}"

    print(f"\n📦 Creating database backup → {backup_dir}/")

    try:
        cmd = [
            "mongodump",
            "--uri", MONGODB_URI,
            "--db", DATABASE_NAME,
            "--out", backup_dir
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Backup created: {backup_dir}/")
        print(f"\nTo restore:")
        print(f"   mongorestore --uri {MONGODB_URI} --db {DATABASE_NAME} {backup_dir}/{DATABASE_NAME}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Backup failed: {e}")
        return False
    except FileNotFoundError:
        print("❌ mongodump not found.")
        print("   Install: https://www.mongodb.com/docs/database-tools/installation/")
        return False


def show_menu():
    """Displays main menu"""
    print("\n" + "="*70)
    print("🗄️  DATABASE MANAGER - Choose an action:")
    print("="*70)
    print("\n📊 Information:")
    print("  [1] Show Database Statistics")
    print("\n🧹 Clean Specific Data:")
    print("  [2] Clear Simulation/Seed Data Only  (simulation=True)")
    print("  [3] Clear Test Case Data Only        (same as option 2)")
    print("  [4] Clear Alert History Only")
    print("  [5] Clear Old Data (by date)")
    print("\n🎯 Quick Actions:")
    print("  [6] 🎯 Presentation Ready Reset      (Recommended)")
    print("      └─ Clears simulation + alerts, keeps real data")
    print("\n⚠️  Nuclear Options:")
    print("  [7] 💣 Clear ALL Data (Everything including real data!)")
    print("\n💾 Backup:")
    print("  [8] Create Database Backup (mongodump)")
    print("\n[Q] Quit")
    print("="*70)


def main():
    """Main execution function"""
    print("\n🗄️  AIS Transhipment - Database Manager")
    print("   Area: Batam / Singapore / Johor\n")

    db = get_database()
    print(f"✅ Connected to: {DATABASE_NAME}")
    display_stats(db)

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
            print("Menghapus semua data dengan flag simulation=True")
            print("Data produksi real TIDAK akan tersentuh.")
            print("="*70)
            clear_simulation_data(db)
            display_stats(db)

        elif choice == '3':
            print("\n🧹 CLEAR TEST CASE DATA")
            print("="*70)
            print("Menghapus semua data seed/test (simulation=True)")
            print("CATATAN: Tidak pakai MMSI range — pakai flag simulation=True")
            print("Data produksi real TIDAK akan tersentuh.")
            print("="*70)
            clear_test_data(db)
            display_stats(db)

        elif choice == '4':
            print("\n🧹 CLEAR ALERT HISTORY")
            print("="*70)
            print("Menghapus semua alert records dari collection ais_alerts")
            print("AIS signals TIDAK akan tersentuh.")
            print("="*70)
            clear_alert_history(db)
            display_stats(db)

        elif choice == '5':
            print("\n🧹 CLEAR OLD DATA")
            print("="*70)
            days = input("Delete data older than how many days? (e.g., 30): ").strip()
            try:
                clear_old_data(db, int(days))
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

        if choice != '1':
            another = input("\nPerform another action? (y/n): ").strip().lower()
            if another != 'y':
                break

    print("\n✅ Done!")


if __name__ == "__main__":
    main()