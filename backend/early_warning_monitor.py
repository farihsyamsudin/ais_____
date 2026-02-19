"""
Early Warning System (EWS) - AIS Transhipment Monitor
Monitors live/recent AIS data and sends alerts when anomalies are detected.
Source of truth: V4/main.py + V4/anomaly_logic.py
"""

import sys
import os
import time
import pymongo
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Pastikan bisa import dari folder yang sama
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anomaly_logic import detect_anomalies

# ==============================
# Configuration
# ==============================

MONGODB_URI    = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME  = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")
ALERTS_COLLECTION = os.getenv("ALERTS_COLLECTION", "ais_alerts")

# ==============================================================================
# KONFIGURASI PELABUHAN LENGKAP (BATAM, SG, JOHOR)
# Source of truth: V4/main.py
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

# Bounding box area Batam / Selat Singapura
GEO_FILTER = {
    "lat": {"$gte": 0.8, "$lte": 1.6},
    "lon": {"$gte": 103.4, "$lte": 104.5},
}

DETECTION_PARAMS = {
    "proximity_km": float(os.getenv('MONITOR_PROXIMITY_KM', '0.5')),
    "duration_min": float(os.getenv('MONITOR_DURATION_MIN', '30')),
    "candidate_duration_min": float(os.getenv('MONITOR_CANDIDATE_MIN', '15')),
    "sog_threshold": float(os.getenv('MONITOR_SOG_THRESHOLD', '2.0')),
    "port_dist_km": float(os.getenv('MONITOR_PORT_DIST_KM', '0.5')),
    "time_gap_min": float(os.getenv('MONITOR_TIME_GAP_MIN', '10')),
}

MONITOR_CONFIG = {
    'interval_minutes': int(os.getenv('MONITOR_INTERVAL', '5')),
    'lookback_minutes': int(os.getenv('MONITOR_LOOKBACK_WINDOW', '60')),
    'send_email_alerts': os.getenv('MONITOR_SEND_EMAIL', 'true').lower() == 'true'
}


def get_database():
    """Connects to MongoDB and returns database instance"""
    try:
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client[DATABASE_NAME]
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def fetch_recent_data(collection, minutes_back):
    """
    Fetches recent AIS data from MongoDB (area Batam/Singapore).
    Skema real: mmsi (string), immsi (int), created_at (datetime).
    """
    end_time   = datetime.utcnow()
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

    # Mapping field: gunakan immsi (int) sebagai kolom mmsi untuk algo
    if 'immsi' in df.columns:
        df['mmsi'] = df['immsi'].astype('int32')
    elif 'mmsi' in df.columns:
        df['mmsi'] = pd.to_numeric(df['mmsi'], errors='coerce').astype('int32')
    else:
        return pd.DataFrame()

    df['sog'] = df['sog'].astype('float32')
    df['lat'] = df['lat'].astype('float32')
    df['lon'] = df['lon'].astype('float32')

    # created_at sebagai timestamp (utc AIS field = detik 0-59, bukan timestamp)
    df['utc'] = pd.to_datetime(df['created_at'])

    return df[['mmsi', 'lat', 'lon', 'sog', 'utc', 'created_at']]


def check_if_already_alerted(alerts_collection, mmsi_1, mmsi_2, start_time):
    """
    Checks if this anomaly pair has already been alerted recently (deduplicate).
    """
    dedup_window = start_time - timedelta(hours=2)
    existing = alerts_collection.find_one({
        "mmsi_1": mmsi_1,
        "mmsi_2": mmsi_2,
        "start_time": {"$gte": dedup_window}
    })
    return existing is not None


def save_alert(alerts_collection, anomaly, alert_type="confirmed"):
    """Saves anomaly alert to MongoDB"""
    alert_doc = {
        "alert_type": alert_type,
        "mmsi_1": int(anomaly['mmsi_1']),
        "mmsi_2": int(anomaly['mmsi_2']),
        "start_time": anomaly['start_time'],
        "end_time": anomaly['end_time'],
        "duration_min": float(anomaly['duration_min']),
        "lat": float(anomaly['lat']),
        "lon": float(anomaly['lon']),
        "alerted_at": datetime.utcnow(),
    }
    alerts_collection.insert_one(alert_doc)
    return alert_doc


def send_email_alert(anomaly, alert_type="confirmed"):
    """Sends email alert (delegate to email_config if available)"""
    try:
        from email_config import send_anomaly_alert
        send_anomaly_alert(anomaly, alert_type)
    except ImportError:
        print("   [EWS] email_config tidak ditemukan, skip email.")
    except Exception as e:
        print(f"   [EWS] Gagal kirim email: {e}")


def run_monitoring_cycle(db):
    """Runs a single monitoring cycle"""
    collection        = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]

    lookback = MONITOR_CONFIG['lookback_minutes']
    print(f"\n{'='*60}")
    print(f"[EWS] Cycle @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"[EWS] Fetching data from last {lookback} minutes...")

    df = fetch_recent_data(collection, lookback)

    if df.empty:
        print("[EWS] No data found in time window.")
        return

    print(f"[EWS] {len(df)} records fetched. Running detection...")

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

    new_confirmed  = 0
    new_candidates = 0

    # Process confirmed anomalies
    if not final_df.empty:
        for _, row in final_df.iterrows():
            if not check_if_already_alerted(alerts_collection, int(row['mmsi_1']), int(row['mmsi_2']), row['start_time']):
                alert = save_alert(alerts_collection, row, "confirmed")
                new_confirmed += 1
                print(f"   🚨 CONFIRMED: MMSI {row['mmsi_1']} ↔ {row['mmsi_2']} | {row['duration_min']:.1f} min @ ({row['lat']:.4f}, {row['lon']:.4f})")
                if MONITOR_CONFIG['send_email_alerts']:
                    send_email_alert(alert, "confirmed")

    # Process candidate anomalies
    if not candidate_df.empty:
        for _, row in candidate_df.iterrows():
            if not check_if_already_alerted(alerts_collection, int(row['mmsi_1']), int(row['mmsi_2']), row['start_time']):
                alert = save_alert(alerts_collection, row, "candidate")
                new_candidates += 1
                print(f"   ⚠️  CANDIDATE: MMSI {row['mmsi_1']} ↔ {row['mmsi_2']} | {row['duration_min']:.1f} min @ ({row['lat']:.4f}, {row['lon']:.4f})")
                if MONITOR_CONFIG['send_email_alerts']:
                    send_email_alert(alert, "candidate")

    if new_confirmed == 0 and new_candidates == 0:
        print("[EWS] No new anomalies detected.")

    print(f"[EWS] Cycle done. +{new_confirmed} confirmed, +{new_candidates} candidates.")


def main():
    print("=" * 60)
    print("🚨 AIS Early Warning System - Batam/Singapore Area")
    print("=" * 60)
    print(f"  Interval    : {MONITOR_CONFIG['interval_minutes']} min")
    print(f"  Lookback    : {MONITOR_CONFIG['lookback_minutes']} min")
    print(f"  Proximity   : {DETECTION_PARAMS['proximity_km']} km")
    print(f"  SOG thresh  : {DETECTION_PARAMS['sog_threshold']} knots")
    print(f"  Port buffer : {DETECTION_PARAMS['port_dist_km']} km")
    print(f"  Email alerts: {MONITOR_CONFIG['send_email_alerts']}")
    print("=" * 60)

    db = get_database()

    while True:
        try:
            run_monitoring_cycle(db)
        except Exception as e:
            print(f"[EWS] ❌ Error in cycle: {e}")

        interval_sec = MONITOR_CONFIG['interval_minutes'] * 60
        print(f"[EWS] Next cycle in {MONITOR_CONFIG['interval_minutes']} min...")
        time.sleep(interval_sec)


if __name__ == '__main__':
    main()