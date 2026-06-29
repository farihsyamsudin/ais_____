import sys
import os
import pymongo
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import random

# Load config
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
load_dotenv(os.path.join(backend_dir, '.env'))

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = "monitoring_ews"

def get_database():
    client = pymongo.MongoClient(MONGODB_URI)
    return client[DATABASE_NAME]

def insert_simulated_anomaly():
    db = get_database()
    collection = db[COLLECTION_NAME]
    
    # MMSI dummy
    mmsi_1 = 999111222
    mmsi_2 = 999333444
    
    print("==================================================")
    print(f"🎮 Menjalankan Simulator Anomali (MMSI: {mmsi_1} & {mmsi_2})")
    print(f"Target Collection: {COLLECTION_NAME}")
    print("==================================================")
    
    # Koordinat di tengah laut area Batam/Singapore (jauh dari pelabuhan)
    base_lat, base_lon = 1.1500, 103.8000
    
    # Durasi simulasi: 35 menit yang lalu sampai sekarang
    # (Syarat anomaly: > 30 menit)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=35)
    
    total_points = 8 # Titik dikirim kira2 tiap 5 menit
    
    records = []
    current_time = start_time
    
    for i in range(total_points):
        # Kapal berjalan sangat lambat / diam berdekatan (sog < 0.5)
        # Jarak kedua kapal < 0.5km (di setlat dan lon sangat mirip)
        
        offset_lat = random.uniform(-0.001, 0.001)
        offset_lon = random.uniform(-0.001, 0.001)
        
        rec1 = {
            "mmsi": mmsi_1,
            "immsi": mmsi_1,
            "lat": base_lat + offset_lat,
            "lon": base_lon + offset_lon,
            "sog": random.uniform(0.1, 0.4),
            "created_at": current_time
        }
        
        rec2 = {
            "mmsi": mmsi_2,
            "immsi": mmsi_2,
            "lat": base_lat + offset_lat + 0.0005, # Beda tipis banget
            "lon": base_lon + offset_lon + 0.0005,
            "sog": random.uniform(0.1, 0.4),
            "created_at": current_time
        }
        
        records.extend([rec1, rec2])
        
        # Maju 5 menit
        current_time += timedelta(minutes=5)
    
    print(f"Memasukkan {len(records)} data poin ke database...")
    collection.insert_many(records)
    print("✅ Berhasil! Data anomali telah disimulasikan.")
    print("EWS Monitor akan mendeteksinya dalam waktu kurang dari 3 detik.")

if __name__ == "__main__":
    insert_simulated_anomaly()
