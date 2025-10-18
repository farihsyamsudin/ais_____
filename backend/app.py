"""
Flask Backend API for AIS Transhipment Detection
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
CORS(app)  # Enable CORS for frontend

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")

# Detection parameters (same as your original code)
PORTS = [
    {"name": "Pelabuhan Merak", "lat": -5.8933, "lon": 106.0086},
    {"name": "Pelabuhan Ciwandan", "lat": -5.9525, "lon": 106.0358},
    {"name": "Pelabuhan Bojonegara", "lat": -5.8995, "lon": 106.0657},
    {"name": "Pelabuhan Bakauheni", "lat": -5.8711, "lon": 105.7421},
    {"name": "Pelabuhan Panjang", "lat": -5.4558, "lon": 105.3134},
    {"name": "Pelabuhan Ciwandan 2", "lat": -6.02147, "lon": 105.95485},
    {"name": "Labuan", "lat": -6.395829, "lon": 105.807895},
    {"name": "Citeureup", "lat": -6.491586, "lon": 105.725007},
    {"name": "Tarahan", "lat": -5.565000, "lon": 105.372998},
]

DEFAULT_PARAMS = {
    "proximity_km": 0.2,
    "duration_min": 30,
    "candidate_duration_min": 22,
    "sog_threshold": 0.5,
    "port_distance_km": 10.0,
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
    Fetches AIS data from MongoDB within date range
    
    Args:
        start_date: Start datetime
        end_date: End datetime
        mmsi_filter: List of MMSI to filter (optional)
    
    Returns:
        pandas DataFrame
    """
    db = get_db()
    collection = db[COLLECTION_NAME]
    
    query = {
        "created_at": {
            "$gte": start_date,
            "$lte": end_date
        },
        "lat": {"$gte": -6.5, "$lte": -5.5},
        "lon": {"$gte": 105.0, "$lte": 106.0}
    }
    
    if mmsi_filter:
        query["mmsi"] = {"$in": mmsi_filter}
    
    # Fetch data
    cursor = collection.find(query).sort("created_at", ASCENDING)
    
    # Convert to DataFrame
    data = list(cursor)
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Data type optimization
    df['mmsi'] = df['mmsi'].astype('int32')
    df['sog'] = df['sog'].astype('float32')
    df['lat'] = df['lat'].astype('float32')
    df['lon'] = df['lon'].astype('float32')
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
                "start_time": row['start_time'].isoformat() if isinstance(row['start_time'], datetime) else str(row['start_time']),
                "end_time": row['end_time'].isoformat() if isinstance(row['end_time'], datetime) else str(row['end_time']),
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
                "start_time": row['start_time'].isoformat() if isinstance(row['start_time'], datetime) else str(row['start_time']),
                "end_time": row['end_time'].isoformat() if isinstance(row['end_time'], datetime) else str(row['end_time']),
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
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Returns database statistics"""
    try:
        db = get_db()
        collection = db[COLLECTION_NAME]
        
        total_signals = collection.count_documents({})
        unique_vessels = len(collection.distinct('mmsi'))
        
        # Date range
        date_agg = list(collection.aggregate([
            {"$group": {
                "_id": None,
                "min_date": {"$min": "$created_at"},
                "max_date": {"$max": "$created_at"}
            }}
        ]))
        
        date_range = {}
        if date_agg:
            date_range = {
                "min": date_agg[0]['min_date'].isoformat(),
                "max": date_agg[0]['max_date'].isoformat()
            }
        
        return jsonify({
            "total_signals": total_signals,
            "unique_vessels": unique_vessels,
            "date_range": date_range
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/detect', methods=['POST'])
def detect_anomalies_endpoint():
    """
    Main endpoint for anomaly detection
    
    Request body:
    {
        "start_date": "2023-08-01T00:00:00",
        "end_date": "2023-08-02T00:00:00",
        "parameters": {
            "proximity_km": 0.2,
            "duration_min": 30,
            ...
        },
        "mmsi_filter": [111111111, 222222222]  // optional
    }
    """
    try:
        data = request.json
        
        # Parse dates
        start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
        
        # Get parameters (use defaults if not provided)
        params = data.get('parameters', {})
        proximity_km = params.get('proximity_km', DEFAULT_PARAMS['proximity_km'])
        duration_min = params.get('duration_min', DEFAULT_PARAMS['duration_min'])
        candidate_duration_min = params.get('candidate_duration_min', DEFAULT_PARAMS['candidate_duration_min'])
        sog_threshold = params.get('sog_threshold', DEFAULT_PARAMS['sog_threshold'])
        port_distance_km = params.get('port_distance_km', DEFAULT_PARAMS['port_distance_km'])
        time_gap_min = params.get('time_gap_min', DEFAULT_PARAMS['time_gap_min'])
        
        mmsi_filter = data.get('mmsi_filter')
        
        # Fetch data from MongoDB
        print(f"Fetching data from {start_date} to {end_date}...")
        df = fetch_ais_data(start_date, end_date, mmsi_filter)
        
        if df.empty:
            return jsonify({
                "message": "No data found for the specified date range",
                "confirmed_anomalies": [],
                "candidate_anomalies": [],
                "data_points": 0
            }), 200
        
        print(f"Data fetched: {len(df)} records")
        
        # Run anomaly detection
        print("Running anomaly detection...")
        final_df, candidate_df = detect_anomalies(
            df, proximity_km, duration_min, candidate_duration_min,
            sog_threshold, port_distance_km, time_gap_min, PORTS
        )
        
        # Format response
        confirmed, candidates = format_anomaly_response(final_df, candidate_df)
        
        return jsonify({
            "message": "Detection completed successfully",
            "confirmed_anomalies": confirmed,
            "candidate_anomalies": candidates,
            "data_points": len(df),
            "parameters_used": {
                "proximity_km": proximity_km,
                "duration_min": duration_min,
                "candidate_duration_min": candidate_duration_min,
                "sog_threshold": sog_threshold,
                "port_distance_km": port_distance_km,
                "time_gap_min": time_gap_min
            }
        }), 200
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/vessels', methods=['GET'])
def get_vessels():
    """Returns list of vessels in database"""
    try:
        db = get_db()
        collection = db[COLLECTION_NAME]
        
        # Get unique vessels with their info
        pipeline = [
            {"$group": {
                "_id": "$mmsi",
                "vessel_name": {"$first": "$vessel_name"},
                "vessel_type": {"$first": "$vessel_type"},
                "signal_count": {"$sum": 1}
            }},
            {"$sort": {"signal_count": -1}},
            {"$limit": 100}  # Limit to top 100 vessels
        ]
        
        vessels = list(collection.aggregate(pipeline))
        
        result = []
        for v in vessels:
            result.append({
                "mmsi": v['_id'],
                "vessel_name": v.get('vessel_name', 'Unknown'),
                "vessel_type": v.get('vessel_type', 'Unknown'),
                "signal_count": v['signal_count']
            })
        
        return jsonify({"vessels": result}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vessel/<int:mmsi>', methods=['GET'])
def get_vessel_track(mmsi):
    """
    Returns track data for a specific vessel
    Query params: start_date, end_date
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        db = get_db()
        collection = db[COLLECTION_NAME]
        
        query = {
            "mmsi": mmsi,
            "created_at": {"$gte": start_date, "$lte": end_date}
        }
        
        cursor = collection.find(query).sort("created_at", ASCENDING).limit(1000)
        tracks = []
        
        for doc in cursor:
            tracks.append({
                "lat": float(doc['lat']),
                "lon": float(doc['lon']),
                "sog": float(doc['sog']),
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
    print(f"Server: http://localhost:{port}")
    print(f"Database: {DATABASE_NAME}")
    print(f"Debug mode: {debug}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=debug)