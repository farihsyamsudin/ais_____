import pandas as pd
import numpy as np
from haversine import haversine, Unit
from sklearn.neighbors import BallTree

def is_far_from_ports(lat, lon, ports, min_distance_km):
    """Checks if a coordinate is far from any port in the list."""
    for port in ports:
        dist = haversine((lat, lon), (port['lat'], port['lon']), unit=Unit.KILOMETERS)
        if dist < min_distance_km:
            return False
    return True


def detect_anomalies(df, proximity_km, duration_min, candidate_duration_min,
                     sog_threshold, port_dist_km, time_gap_min, ports):
    """
    Optimized core logic for detecting transhipment anomalies in AIS data.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: (confirmed_anomalies, candidate_anomalies).
    """

    # ============================
    # 0. Pre-optimisation step
    # ============================
    # Downsample per MMSI tiap menit → kurangi duplikat
    df = (
        df.sort_values('utc')
          .groupby(['mmsi', pd.Grouper(key='utc', freq='1min')])
          .first()
          .reset_index()
    )

    # Pastikan tipe data hemat RAM
    df['mmsi'] = df['mmsi'].astype('int32')
    df['lat'] = df['lat'].astype('float32')
    df['lon'] = df['lon'].astype('float32')
    df['sog'] = df['sog'].astype('float32')

    # Pakai window lebih lebar biar group lebih sedikit
    df['utc_rounded'] = df['utc'].dt.floor('5min')

    potential_interactions = []

    # ============================
    # 1. Proximity Detection
    # ============================
    for time, group in df.groupby('utc_rounded'):
        if len(group) < 2:
            continue

        coords = np.radians(group[['lat', 'lon']].values)
        tree = BallTree(coords, metric='haversine')

        # Ambil tetangga unik, tanpa nested loop kuadrat
        indices = tree.query_radius(coords, r=proximity_km / 6371.0)

        for i, neighbors in enumerate(indices):
            row_i = group.iloc[i]
            if row_i['sog'] >= sog_threshold:
                continue

            for j in neighbors:
                if j <= i:  # skip self & duplikat
                    continue

                row_j = group.iloc[j]
                if row_j['sog'] >= sog_threshold:
                    continue

                potential_interactions.append({
                    'mmsi_1': min(row_i['mmsi'], row_j['mmsi']),
                    'mmsi_2': max(row_i['mmsi'], row_j['mmsi']),
                    'utc': time,
                    'lat': (row_i['lat'] + row_j['lat']) / 2,
                    'lon': (row_i['lon'] + row_j['lon']) / 2,
                })

    if not potential_interactions:
        return pd.DataFrame(), pd.DataFrame()

    # ============================
    # 2. Session Aggregation
    # ============================
    anom_df = pd.DataFrame(potential_interactions)
    final_anomalies = []
    candidate_anomalies = []

    for (m1, m2), group in anom_df.groupby(['mmsi_1', 'mmsi_2']):
        group = group.sort_values('utc')
        group['time_diff'] = group['utc'].diff().fillna(pd.Timedelta(seconds=0))
        group['gap'] = (group['time_diff'] > pd.Timedelta(minutes=time_gap_min)).cumsum()

        for _, session in group.groupby('gap'):
            lat_mean = session['lat'].mean()
            lon_mean = session['lon'].mean()

            # Check port distance
            if is_far_from_ports(lat_mean, lon_mean, ports, port_dist_km):
                duration_minutes = (session['utc'].max() - session['utc'].min()).total_seconds() / 60
                anomaly_record = {
                    'mmsi_1': m1,
                    'mmsi_2': m2,
                    'start_time': session['utc'].min(),
                    'end_time': session['utc'].max(),
                    'duration_min': round(duration_minutes, 2),
                    'lat': lat_mean,
                    'lon': lon_mean,
                }

                # Filtering based on duration
                if duration_minutes >= duration_min:
                    final_anomalies.append(anomaly_record)
                elif duration_minutes >= candidate_duration_min:
                    candidate_anomalies.append(anomaly_record)

    return pd.DataFrame(final_anomalies), pd.DataFrame(candidate_anomalies)