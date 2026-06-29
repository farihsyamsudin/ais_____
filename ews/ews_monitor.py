import sys
import os
import time
import pymongo
import pandas as pd
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Tambahkan folder backend ke path agar bisa import anomaly_logic & email_config
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, '.env'))

from anomaly_logic import detect_anomalies
from email_config import send_email_alert

# ==============================
# Configuration
# ==============================
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = "monitoring_ews"  # Collection khusus untuk EWS yang baru
ALERTS_COLLECTION = "monitoring_ews_alerts"  # Collection alert khusus

# Interval waktu ais menangkap dan memproses data yang baru masuk selama: 3 detik.
# Sehingga ketika simulasi dijalankan, monitor akan "langsung" menangkapnya
POLL_INTERVAL_SEC = 3
LOOKBACK_MINUTES = 60

# ==============================================================================
# KONFIGURASI PELABUHAN
# ==============================================================================
PORTS = [
    # --- BATAM, INDONESIA ---
    {"name": "Batu Ampar (Cargo)", "lat": 1.1617, "lon": 104.0047},
    {"name": "Kabil (Citranusa/Oil)", "lat": 1.1108, "lon": 104.1403},
    {"name": "Sekupang (Ferry/Intl)", "lat": 1.1261, "lon": 103.9278},
    {"name": "Tanjung Uncang (Shipyard)", "lat": 1.0750, "lon": 103.9050},
    {"name": "Nongsa Pura", "lat": 1.1960, "lon": 104.0830},
    {"name": "Telaga Punggur", "lat": 1.0370, "lon": 104.1480},
    {"name": "Batam Centre", "lat": 1.1320, "lon": 104.0520},
    {"name": "Harbour Bay", "lat": 1.1550, "lon": 103.9950},

    # --- BINTAN ---
    {"name": "Tanjung Uban (Oil)", "lat": 1.0713, "lon": 104.2209},

    # --- SINGAPURA ---
    {"name": "Jurong Port", "lat": 1.2604, "lon": 103.6888},
    {"name": "Pasir Panjang", "lat": 1.2761, "lon": 103.7914},
    {"name": "Keppel Terminal", "lat": 1.2600, "lon": 103.8300},
    {"name": "Brani Terminal", "lat": 1.2630, "lon": 103.8350},
    {"name": "Tanjong Pagar", "lat": 1.2670, "lon": 103.8450},
    {"name": "Marina South Pier", "lat": 1.2700, "lon": 103.8640},
    {"name": "Changi Naval Base", "lat": 1.3200, "lon": 104.0200},
    {"name": "Changi Cargo", "lat": 1.3500, "lon": 104.0300},
    {"name": "Tuas Mega Port", "lat": 1.2900, "lon": 103.6200},
    {"name": "Sembawang", "lat": 1.4550, "lon": 103.8250},

    # --- JOHOR, MALAYSIA ---
    {"name": "Tanjung Pelepas (PTP)", "lat": 1.3600, "lon": 103.5500},
    {"name": "Tanjung Bin (Power/Coal)", "lat": 1.3300, "lon": 103.5400},
    {"name": "Kukup Anchorage", "lat": 1.3200, "lon": 103.4500},
    {"name": "Johor Port (Pasir Gudang)", "lat": 1.4300, "lon": 103.9000},
    {"name": "Tanjung Langsat", "lat": 1.4500, "lon": 104.0100},
]

GEO_FILTER = {
    "lat": {"$gte": 0.8, "$lte": 1.6},
    "lon": {"$gte": 103.4, "$lte": 104.5},
}

DETECTION_PARAMS = {
    "proximity_km": 0.5,
    "duration_min": 30,
    "candidate_duration_min": 15,
    "sog_threshold": 2.0,
    "port_dist_km": 0.5,
    "time_gap_min": 10,
}

def get_database():
    try:
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client[DATABASE_NAME]
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

def fetch_recent_data(collection, minutes_back):
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=minutes_back)

    query = {
        "created_at": {"$gte": start_time, "$lte": end_time},
        **GEO_FILTER
    }

    cursor = collection.find(query).sort("created_at", pymongo.ASCENDING)
    data = list(cursor)

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if 'immsi' in df.columns:
        df['mmsi'] = df['immsi'].astype('int32')
    elif 'mmsi' in df.columns:
        df['mmsi'] = pd.to_numeric(df['mmsi'], errors='coerce').astype('int32')
    else:
        return pd.DataFrame()

    df['sog'] = df['sog'].astype('float32')
    df['lat'] = df['lat'].astype('float32')
    df['lon'] = df['lon'].astype('float32')
    df['utc'] = pd.to_datetime(df['created_at'])

    return df[['mmsi', 'lat', 'lon', 'sog', 'utc', 'created_at']]

def check_if_already_alerted(alerts_collection, mmsi_1, mmsi_2, start_time):
    dedup_window = start_time - timedelta(hours=2)
    existing = alerts_collection.find_one({
        "mmsi_1": mmsi_1,
        "mmsi_2": mmsi_2,
        "start_time": {"$gte": dedup_window}
    })
    return existing is not None

def save_alert(alerts_collection, anomaly, alert_type="confirmed"):
    alert_doc = {
        "alert_type": alert_type,
        "mmsi_1": int(anomaly['mmsi_1']),
        "mmsi_2": int(anomaly['mmsi_2']),
        "start_time": anomaly['start_time'],
        "end_time": anomaly['end_time'],
        "duration_min": float(anomaly['duration_min']),
        "lat": float(anomaly['lat']),
        "lon": float(anomaly['lon']),
        "alerted_at": datetime.now(timezone.utc),
    }
    alerts_collection.insert_one(alert_doc)
    return alert_doc

def run_monitoring_cycle(db):
    collection = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]

    df = fetch_recent_data(collection, LOOKBACK_MINUTES)
    if df.empty:
        return

    final_df, candidate_df = detect_anomalies(
        df,
        proximity_km=DETECTION_PARAMS['proximity_km'],
        duration_min=DETECTION_PARAMS['duration_min'],
        candidate_duration_min=DETECTION_PARAMS['candidate_duration_min'],
        sog_threshold=DETECTION_PARAMS['sog_threshold'],
        port_dist_km=DETECTION_PARAMS['port_dist_km'],
        time_gap_min=DETECTION_PARAMS['time_gap_min'],
        ports=PORTS
    )

    if not final_df.empty:
        for _, row in final_df.iterrows():
            m1, m2 = int(row['mmsi_1']), int(row['mmsi_2'])
            if not check_if_already_alerted(alerts_collection, m1, m2, row['start_time']):
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] 🚨 ANOMALY DETECTED! MMSI {m1} ↔ {m2} ({row['duration_min']:.1f} mins)")
                alert_doc = save_alert(alerts_collection, row, "confirmed")
                
                # Format anomali untuk dimasukkan ke email
                anomaly_for_email = [{
                    'mmsi_1': m1,
                    'mmsi_2': m2,
                    'duration_min': row['duration_min'],
                    'start_time': row['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': row['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'lat': row['lat'],
                    'lon': row['lon']
                }]
                print("📧 Mengirimkan email alert...")
                success = send_email_alert(anomaly_for_email)
                if success:
                    print("✅ Email berhasil dikirim!\n")
                else:
                    print("❌ Gagal mengirim email.\n")

def main():
    print("==================================================")
    print("🚨 EWS Monitor Berjalan")
    print(f"Memantau collection '{COLLECTION_NAME}'")
    print(f"Polling interval: {POLL_INTERVAL_SEC} detik")
    print("==================================================\n")

    db = get_database()
    
    # Pastikan collection ada dan memiliki index
    if COLLECTION_NAME not in db.list_collection_names():
        db.create_collection(COLLECTION_NAME)
        print(f"ℹ️ Collection '{COLLECTION_NAME}' dibuat.")
        db[COLLECTION_NAME].create_index("created_at")

    while True:
        try:
            run_monitoring_cycle(db)
        except Exception as e:
            print(f"❌ Error in cycle: {e}")
        
        # Sleep sebentar (POLL_INTERVAL_SEC detik) agar respon "langsung" (instant)
        time.sleep(POLL_INTERVAL_SEC)

if __name__ == '__main__':
    main()
