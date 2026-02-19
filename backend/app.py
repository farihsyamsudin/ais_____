"""
Flask Backend API for AIS Transhipment Detection
Source of truth: V4/main.py + V4/anomaly_logic.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from anomaly_logic import detect_anomalies
import os
from dotenv import load_dotenv

load_dotenv()

# ==============================
# Configuration
# ==============================

app = Flask(__name__)
CORS(app)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")

# ==============================================================================
# KONFIGURASI PELABUHAN LENGKAP (BATAM, SG, JOHOR)
# Source of truth: V4/main.py
# Filter ini krusial untuk membuang antrean legal di dermaga.
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

    # --- BINTAN (Sisi Timur) ---
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

DEFAULT_PARAMS = {
    "proximity_km": 0.5,
    "duration_min": 30,
    "candidate_duration_min": 15,
    "sog_threshold": 2.0,
    "port_distance_km": 0.5,
    "time_gap_min": 10
}

# ==============================
# Database Connection
# ==============================

def get_db():
    """Returns MongoDB database instance"""
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return client[DATABASE_NAME]

# ==============================
# Helper Functions
# ==============================

def fetch_ais_data(start_date, end_date, mmsi_filter=None):
    """
    Fetches AIS data from MongoDB within date range.
    Skema real: mmsi (string), immsi (int), created_at (datetime), utc (int AIS field).
    """
    db = get_db()
    collection = db[COLLECTION_NAME]

    query = {
        "created_at": {
            "$gte": start_date,
            "$lte": end_date
        },
        **GEO_FILTER
    }

    if mmsi_filter:
        # immsi adalah field integer, mmsi adalah string
        query["immsi"] = {"$in": [int(m) for m in mmsi_filter]}

    cursor = collection.find(query).sort("created_at", ASCENDING)

    data = list(cursor)
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Mapping field: gunakan immsi (int) sebagai kolom mmsi untuk algo
    if 'immsi' in df.columns:
        df['mmsi'] = df['immsi'].astype('int32')
    elif 'mmsi' in df.columns:
        # fallback: mmsi bisa string atau int
        df['mmsi'] = pd.to_numeric(df['mmsi'], errors='coerce').astype('int32')

    df['sog'] = df['sog'].astype('float32')
    df['lat'] = df['lat'].astype('float32')
    df['lon'] = df['lon'].astype('float32')

    # Field 'utc' di AIS = detik dalam menit (0-59), bukan timestamp.
    # Gunakan created_at sebagai timestamp sebenarnya.
    df['utc'] = pd.to_datetime(df['created_at'])

    return df[['mmsi', 'lat', 'lon', 'sog', 'utc', 'created_at']]


def format_anomaly_response(final_df, candidate_df):
    """Formats anomaly dataframes for API response"""

    confirmed = []
    if not final_df.empty:
        for _, row in final_df.iterrows():
            confirmed.append({
                "mmsi_1": int(row['mmsi_1']),
                "mmsi_2": int(row['mmsi_2']),
                "start_time": row['start_time'].isoformat() if hasattr(row['start_time'], 'isoformat') else str(row['start_time']),
                "end_time": row['end_time'].isoformat() if hasattr(row['end_time'], 'isoformat') else str(row['end_time']),
                "duration_min": float(row['duration_min']),
                "lat": float(row['lat']),
                "lon": float(row['lon'])
            })

    candidates = []
    if not candidate_df.empty:
        for _, row in candidate_df.iterrows():
            candidates.append({
                "mmsi_1": int(row['mmsi_1']),
                "mmsi_2": int(row['mmsi_2']),
                "start_time": row['start_time'].isoformat() if hasattr(row['start_time'], 'isoformat') else str(row['start_time']),
                "end_time": row['end_time'].isoformat() if hasattr(row['end_time'], 'isoformat') else str(row['end_time']),
                "duration_min": float(row['duration_min']),
                "lat": float(row['lat']),
                "lon": float(row['lon'])
            })

    return confirmed, candidates


# ==============================
# API Routes
# ==============================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        db = get_db()
        db.command('ping')
        count = db[COLLECTION_NAME].count_documents({})
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "collection": COLLECTION_NAME,
            "document_count": count,
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 503


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns database statistics"""
    try:
        db = get_db()
        collection = db[COLLECTION_NAME]

        total_docs = collection.count_documents({})
        unique_vessels = len(collection.distinct('immsi'))

        date_range = list(collection.aggregate([
            {"$group": {
                "_id": None,
                "min_date": {"$min": "$created_at"},
                "max_date": {"$max": "$created_at"}
            }}
        ]))

        stats = {
            "total_signals": total_docs,
            "unique_vessels": unique_vessels,
            "date_range": {
                "start": date_range[0]['min_date'].isoformat() if date_range else None,
                "end": date_range[0]['max_date'].isoformat() if date_range else None
            }
        }

        return jsonify(stats), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/vessels', methods=['GET'])
def get_vessels():
    """Returns list of unique vessels"""
    try:
        db = get_db()
        collection = db[COLLECTION_NAME]

        pipeline = [
            {"$group": {
                "_id": "$immsi",
                "mmsi_str": {"$first": "$mmsi"},
                "signal_count": {"$sum": 1},
                "last_seen": {"$max": "$created_at"},
                "last_lat": {"$last": "$lat"},
                "last_lon": {"$last": "$lon"},
                "last_sog": {"$last": "$sog"},
                "navstatus": {"$last": "$navstatus"},
            }},
            {"$sort": {"signal_count": -1}},
            {"$limit": 100}
        ]

        vessels = []
        for doc in collection.aggregate(pipeline):
            vessels.append({
                "mmsi": doc['_id'],         # int
                "mmsi_str": doc.get('mmsi_str', str(doc['_id'])),
                "signal_count": doc['signal_count'],
                "last_seen": doc['last_seen'].isoformat() if doc.get('last_seen') else None,
                "last_lat": float(doc['last_lat']) if doc.get('last_lat') is not None else None,
                "last_lon": float(doc['last_lon']) if doc.get('last_lon') is not None else None,
                "last_sog": float(doc['last_sog']) if doc.get('last_sog') is not None else None,
                "navstatus": doc.get('navstatus'),
            })

        return jsonify({"vessels": vessels, "count": len(vessels)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/detect', methods=['POST'])
def detect():
    """
    Runs anomaly detection on specified date range.
    Body:
    {
        "start_date": "2024-01-01T00:00:00",
        "end_date":   "2024-01-02T00:00:00",
        "parameters": {
            "proximity_km": 0.5,
            "duration_min": 30,
            "sog_threshold": 2.0,
            "port_distance_km": 0.5
        },
        "mmsi_filter": [525101059, 525101060]  // optional
    }
    """
    try:
        data = request.json

        # Parse dates
        start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))

        # Get parameters (use defaults if not provided)
        params = data.get('parameters', {})
        proximity_km          = float(params.get('proximity_km',          DEFAULT_PARAMS['proximity_km']))
        duration_min          = float(params.get('duration_min',          DEFAULT_PARAMS['duration_min']))
        candidate_duration_min = float(params.get('candidate_duration_min', DEFAULT_PARAMS['candidate_duration_min']))
        sog_threshold         = float(params.get('sog_threshold',         DEFAULT_PARAMS['sog_threshold']))
        port_distance_km      = float(params.get('port_distance_km',      DEFAULT_PARAMS['port_distance_km']))
        time_gap_min          = float(params.get('time_gap_min',          DEFAULT_PARAMS['time_gap_min']))

        mmsi_filter = data.get('mmsi_filter')

        # Fetch data from MongoDB
        print(f"[API] Fetching data {start_date} → {end_date}...")
        df = fetch_ais_data(start_date, end_date, mmsi_filter)

        if df.empty:
            return jsonify({
                "message": "No data found for the specified date range",
                "confirmed_anomalies": [],
                "candidate_anomalies": [],
                "data_points": 0
            }), 200

        print(f"[API] Data fetched: {len(df)} records")

        # Run anomaly detection
        print("[API] Running anomaly detection...")
        final_df, candidate_df = detect_anomalies(
            df, proximity_km, duration_min, candidate_duration_min,
            sog_threshold, port_distance_km, time_gap_min, PORTS
        )

        confirmed, candidates = format_anomaly_response(final_df, candidate_df)

        return jsonify({
            "confirmed_anomalies": confirmed,
            "candidate_anomalies": candidates,
            "data_points": len(df),
            "summary": {
                "confirmed_count": len(confirmed),
                "candidate_count": len(candidates),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
        }), 200

    except KeyError as e:
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except Exception as e:
        print(f"[API] Error during detection: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/vessel/<int:mmsi>', methods=['GET'])
def get_vessel_track(mmsi):
    """Returns vessel track for a given MMSI (int)"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required"}), 400

        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        db = get_db()
        collection = db[COLLECTION_NAME]

        # Gunakan immsi (int) untuk query
        query = {
            "immsi": mmsi,
            "created_at": {"$gte": start_date, "$lte": end_date}
        }

        cursor = collection.find(query).sort("created_at", ASCENDING).limit(2000)
        tracks = []

        for doc in cursor:
            tracks.append({
                "lat": float(doc['lat']),
                "lon": float(doc['lon']),
                "sog": float(doc['sog']),
                "cog": float(doc.get('cog', 0)),
                "navstatus": doc.get('navstatus'),
                "timestamp": doc['created_at'].isoformat()
            })

        return jsonify({
            "mmsi": mmsi,
            "track": tracks,
            "points": len(tracks)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/ports', methods=['GET'])
def get_ports():
    """Returns list of ports"""
    return jsonify({"ports": PORTS}), 200


# ==============================
# Error Handlers
# ==============================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


# ==============================
# Main Entry Point
# ==============================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'

    print("=" * 60)
    print("🚢 AIS Transhipment Detection API")
    print("=" * 60)
    print(f"  Server   : http://localhost:{port}")
    print(f"  Database : {DATABASE_NAME}")
    print(f"  Area     : Batam / Singapore / Johor")
    print(f"  Debug    : {debug}")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=debug)