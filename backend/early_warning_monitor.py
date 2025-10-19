"""
Early Warning System - Continuous Monitoring Service
Monitors AIS data for anomalies and sends real-time email alerts
"""

import pymongo
from pymongo import MongoClient
from datetime import datetime, timedelta
import pandas as pd
import time
import sys
import argparse
from anomaly_logic import detect_anomalies
from email_config import send_email_alert
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")
ALERTS_COLLECTION = "anomaly_alerts"  # Separate collection for alert history

# Detection parameters
PORTS = [
    {"name": "Pelabuhan Merak", "lat": -5.8933, "lon": 106.0086},
    {"name": "Pelabuhan Ciwandan", "lat": -5.9525, "lon": 106.0358},
    {"name": "Pelabuhan Bojonegara", "lat": -5.8995, "lon": 106.0657},
    {"name": "Pelabuhan Bakauheni", "lat": -5.8711, "lon": 105.7421},
    {"name": "Pelabuhan Panjang", "lat": -5.4558, "lon": 105.3134},
]

DETECTION_PARAMS = {
    'proximity_km': float(os.getenv('MONITOR_PROXIMITY_KM', '0.2')),
    'duration_min': int(os.getenv('MONITOR_DURATION_MIN', '30')),
    'candidate_duration_min': int(os.getenv('MONITOR_CANDIDATE_DURATION_MIN', '22')),
    'sog_threshold': float(os.getenv('MONITOR_SOG_THRESHOLD', '0.5')),
    'port_distance_km': float(os.getenv('MONITOR_PORT_DISTANCE_KM', '10.0')),
    'time_gap_min': int(os.getenv('MONITOR_TIME_GAP_MIN', '10'))
}

# Monitoring configuration
MONITOR_CONFIG = {
    'check_interval_minutes': int(os.getenv('MONITOR_CHECK_INTERVAL', '5')),  # Check every 5 minutes
    'lookback_window_minutes': int(os.getenv('MONITOR_LOOKBACK_WINDOW', '60')),  # Look back 60 minutes
    'send_email_alerts': os.getenv('MONITOR_SEND_EMAIL', 'true').lower() == 'true'
}


def get_database():
    """Connects to MongoDB and returns database instance"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        return client[DATABASE_NAME]
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)


def fetch_recent_data(collection, minutes_back):
    """
    Fetches recent AIS data from MongoDB
    
    Args:
        collection: MongoDB collection
        minutes_back: How many minutes back to look
    
    Returns:
        pandas DataFrame
    """
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=minutes_back)
    
    query = {
        "created_at": {
            "$gte": start_time,
            "$lte": end_time
        },
        "lat": {"$gte": -6.5, "$lte": -5.5},
        "lon": {"$gte": 105.0, "$lte": 106.0}
    }
    
    cursor = collection.find(query).sort("created_at", pymongo.ASCENDING)
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


def check_if_already_alerted(alerts_collection, mmsi_1, mmsi_2, start_time):
    """
    Checks if this anomaly has already been alerted
    
    Args:
        alerts_collection: MongoDB collection for alerts
        mmsi_1: First vessel MMSI
        mmsi_2: Second vessel MMSI
        start_time: Start time of anomaly
    
    Returns:
        bool: True if already alerted
    """
    
    # Check if we've already alerted for this pair within last 24 hours
    recent_threshold = datetime.utcnow() - timedelta(hours=24)
    
    existing_alert = alerts_collection.find_one({
        'mmsi_1': mmsi_1,
        'mmsi_2': mmsi_2,
        'start_time': start_time,
        'alert_sent_at': {'$gte': recent_threshold}
    })
    
    return existing_alert is not None


def record_alert(alerts_collection, anomalies, email_sent):
    """
    Records alert in database for tracking
    
    Args:
        alerts_collection: MongoDB collection
        anomalies: List of detected anomalies
        email_sent: Whether email was successfully sent
    """
    
    alert_record = {
        'detected_at': datetime.utcnow(),
        'anomaly_count': len(anomalies),
        'anomalies': anomalies,
        'email_sent': email_sent,
        'detection_params': DETECTION_PARAMS
    }
    
    alerts_collection.insert_one(alert_record)


def format_anomaly_for_email(anomaly_row):
    """Formats anomaly row for email"""
    return {
        'mmsi_1': int(anomaly_row['mmsi_1']),
        'mmsi_2': int(anomaly_row['mmsi_2']),
        'duration_min': float(anomaly_row['duration_min']),
        'start_time': anomaly_row['start_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(anomaly_row['start_time'], datetime) else str(anomaly_row['start_time']),
        'end_time': anomaly_row['end_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(anomaly_row['end_time'], datetime) else str(anomaly_row['end_time']),
        'lat': float(anomaly_row['lat']),
        'lon': float(anomaly_row['lon'])
    }


def check_for_anomalies(db, send_alerts=True):
    """
    Main function to check for anomalies and send alerts
    
    Args:
        db: MongoDB database instance
        send_alerts: Whether to send email alerts
    
    Returns:
        tuple: (confirmed_count, candidate_count, email_sent)
    """
    
    collection = db[COLLECTION_NAME]
    alerts_collection = db[ALERTS_COLLECTION]
    
    # Fetch recent data
    lookback = MONITOR_CONFIG['lookback_window_minutes']
    print(f"🔍 Checking data from last {lookback} minutes...")
    
    df = fetch_recent_data(collection, lookback)
    
    if df.empty:
        print("   ℹ️  No data found in the specified time window")
        return 0, 0, False
    
    print(f"   📊 Found {len(df)} AIS signals from {len(df['mmsi'].unique())} vessels")
    
    # Run anomaly detection
    print(f"   🔬 Running anomaly detection...")
    final_df, candidate_df = detect_anomalies(
        df,
        DETECTION_PARAMS['proximity_km'],
        DETECTION_PARAMS['duration_min'],
        DETECTION_PARAMS['candidate_duration_min'],
        DETECTION_PARAMS['sog_threshold'],
        DETECTION_PARAMS['port_distance_km'],
        DETECTION_PARAMS['time_gap_min'],
        PORTS
    )
    
    confirmed_count = len(final_df)
    candidate_count = len(candidate_df)
    
    print(f"   ✅ Detection complete: {confirmed_count} confirmed, {candidate_count} candidates")
    
    email_sent = False
    
    # Process confirmed anomalies
    if confirmed_count > 0:
        print(f"\n🚨 ALERT: {confirmed_count} confirmed anomaly(ies) detected!")
        
        # Filter out already-alerted anomalies
        new_anomalies = []
        for _, row in final_df.iterrows():
            if not check_if_already_alerted(alerts_collection, row['mmsi_1'], row['mmsi_2'], row['start_time']):
                new_anomalies.append(row)
        
        if not new_anomalies:
            print("   ℹ️  All anomalies have already been alerted. Skipping email.")
        elif send_alerts and MONITOR_CONFIG['send_email_alerts']:
            # Format anomalies for email
            anomalies_for_email = [format_anomaly_for_email(row) for row in new_anomalies]
            
            # Send email alert
            print(f"\n📧 Sending email alert for {len(anomalies_for_email)} new anomaly(ies)...")
            email_sent = send_email_alert(anomalies_for_email)
            
            # Record all anomalies (both new and already alerted)
            all_anomalies_for_record = [format_anomaly_for_email(row) for _, row in final_df.iterrows()]
            record_alert(alerts_collection, all_anomalies_for_record, email_sent)
            
            if email_sent:
                print("   ✅ Email alert sent and recorded")
            else:
                print("   ⚠️  Email failed but alert recorded")
        else:
            print("   ℹ️  Email alerts disabled (send_alerts=False or MONITOR_SEND_EMAIL=false)")
            all_anomalies_for_record = [format_anomaly_for_email(row) for _, row in final_df.iterrows()]
            record_alert(alerts_collection, all_anomalies_for_record, False)
        
        # Display anomalies
        print("\n📋 Detected Anomalies:")
        for idx, row in final_df.iterrows():
            print(f"   • MMSI {row['mmsi_1']} ↔ {row['mmsi_2']}: {row['duration_min']:.1f} min at ({row['lat']:.4f}, {row['lon']:.4f})")
    
    if candidate_count > 0:
        print(f"\n⚠️  {candidate_count} candidate anomaly(ies) detected (below duration threshold)")
    
    return confirmed_count, candidate_count, email_sent


def continuous_monitoring():
    """
    Runs continuous monitoring loop
    """
    
    print("=" * 80)
    print("🚢 AIS TRANSHIPMENT - EARLY WARNING SYSTEM")
    print("=" * 80)
    print(f"Database: {DATABASE_NAME}")
    print(f"Check Interval: Every {MONITOR_CONFIG['check_interval_minutes']} minutes")
    print(f"Lookback Window: {MONITOR_CONFIG['lookback_window_minutes']} minutes")
    print(f"Email Alerts: {'Enabled' if MONITOR_CONFIG['send_email_alerts'] else 'Disabled'}")
    print(f"\nDetection Parameters:")
    for key, value in DETECTION_PARAMS.items():
        print(f"  • {key}: {value}")
    print("=" * 80)
    print("\n⏰ Starting monitoring... (Press Ctrl+C to stop)\n")
    
    db = get_database()
    check_count = 0
    
    try:
        while True:
            check_count += 1
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            print(f"\n{'='*80}")
            print(f"🔄 Check #{check_count} - {timestamp}")
            print(f"{'='*80}")
            
            try:
                confirmed, candidates, email_sent = check_for_anomalies(db, send_alerts=True)
                
                if confirmed == 0 and candidates == 0:
                    print("✅ No anomalies detected - All clear")
                
            except Exception as e:
                print(f"❌ Error during check: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # Wait for next check
            wait_seconds = MONITOR_CONFIG['check_interval_minutes'] * 60
            print(f"\n⏳ Next check in {MONITOR_CONFIG['check_interval_minutes']} minutes...")
            time.sleep(wait_seconds)
    
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped by user")
        print(f"Total checks performed: {check_count}")


def single_check():
    """
    Performs a single anomaly check (for manual/scheduled runs)
    """
    
    print("=" * 80)
    print("🔍 SINGLE CHECK MODE")
    print("=" * 80)
    
    db = get_database()
    
    try:
        confirmed, candidates, email_sent = check_for_anomalies(db, send_alerts=True)
        
        print("\n" + "=" * 80)
        print("📊 CHECK SUMMARY")
        print("=" * 80)
        print(f"Confirmed Anomalies: {confirmed}")
        print(f"Candidate Anomalies: {candidates}")
        print(f"Email Sent: {'Yes' if email_sent else 'No'}")
        print("=" * 80)
        
        return confirmed > 0
    
    except Exception as e:
        print(f"\n❌ Error during check: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def view_alert_history(db, limit=10):
    """
    Views recent alert history
    
    Args:
        db: MongoDB database
        limit: Number of recent alerts to show
    """
    
    alerts_collection = db[ALERTS_COLLECTION]
    
    print("\n" + "=" * 80)
    print(f"📜 RECENT ALERT HISTORY (Last {limit} alerts)")
    print("=" * 80)
    
    alerts = list(alerts_collection.find().sort('detected_at', pymongo.DESCENDING).limit(limit))
    
    if not alerts:
        print("No alerts found in history")
        return
    
    for idx, alert in enumerate(alerts, 1):
        detected_at = alert['detected_at'].strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{idx}] {detected_at}")
        print(f"    Anomalies: {alert['anomaly_count']}")
        print(f"    Email Sent: {'✅ Yes' if alert.get('email_sent', False) else '❌ No'}")
        
        if alert['anomaly_count'] > 0 and 'anomalies' in alert:
            for anomaly in alert['anomalies'][:3]:  # Show first 3
                print(f"      • MMSI {anomaly['mmsi_1']} ↔ {anomaly['mmsi_2']}: {anomaly['duration_min']:.1f} min")
            
            if alert['anomaly_count'] > 3:
                print(f"      ... and {alert['anomaly_count'] - 3} more")
    
    print("\n" + "=" * 80)


def main():
    """Main entry point with argument parsing"""
    
    parser = argparse.ArgumentParser(
        description="Early Warning System for AIS Transhipment Detection",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--mode',
        choices=['monitor', 'check', 'history'],
        default='monitor',
        help="Execution mode:\n"
             "  monitor - Continuous monitoring (default)\n"
             "  check   - Single check (for cron/scheduled tasks)\n"
             "  history - View alert history"
    )
    
    parser.add_argument(
        '--check-now',
        action='store_true',
        help="Shortcut for --mode check"
    )
    
    parser.add_argument(
        '--history-limit',
        type=int,
        default=10,
        help="Number of alerts to show in history mode (default: 10)"
    )
    
    parser.add_argument(
        '--no-email',
        action='store_true',
        help="Disable email alerts (detection only)"
    )
    
    args = parser.parse_args()
    
    # Override email setting if --no-email
    if args.no_email:
        MONITOR_CONFIG['send_email_alerts'] = False
    
    # Handle --check-now shortcut
    if args.check_now:
        args.mode = 'check'
    
    # Execute based on mode
    db = get_database()
    
    if args.mode == 'monitor':
        continuous_monitoring()
    elif args.mode == 'check':
        sys.exit(0 if single_check() else 1)
    elif args.mode == 'history':
        view_alert_history(db, args.history_limit)


if __name__ == "__main__":
    main()