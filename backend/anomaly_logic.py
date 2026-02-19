import pandas as pd
import numpy as np
from haversine import haversine, Unit
from sklearn.neighbors import BallTree
import time


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
    Logic deteksi anomali transhipment (Optimized for Batam/Singapore).
    Source of truth: V4/anomaly_logic.py
    """
    start_time = time.time()

    # ============================
    # 0. Pre-processing (Downsample)
    # ============================
    print("   [Logic] Downsampling data per menit per kapal...")
    # Downsample per MMSI tiap 1 menit untuk mengurangi beban komputasi
    # tapi tetap menjaga akurasi waktu
    df = (
        df.sort_values('utc')
          .groupby(['mmsi', pd.Grouper(key='utc', freq='1min')])
          .first()
          .reset_index()
    )

    # Hemat Memori
    df['mmsi'] = df['mmsi'].astype('int32')
    df['lat'] = df['lat'].astype('float32')
    df['lon'] = df['lon'].astype('float32')
    df['sog'] = df['sog'].astype('float32')

    print(f"   [Logic] Data siap diproses: {len(df)} titik data.")

    potential_interactions = []

    # ============================
    # 1. Proximity Detection (Spatial Indexing)
    # ============================
    # Loop per 'utc' (per menit) biar akurat
    unique_times = df['utc'].unique()
    total_steps = len(unique_times)

    print(f"   [Logic] Memindai kedekatan kapal pada {total_steps} timestamp...")

    # Loop ini cepat karena pakai BallTree
    for step, (timestamp, group) in enumerate(df.groupby('utc')):
        if len(group) < 2:
            continue

        # Konversi ke radian untuk BallTree
        coords = np.radians(group[['lat', 'lon']].values)

        # Bangun Tree (Spatial Index)
        tree = BallTree(coords, metric='haversine')

        # Cari tetangga dalam radius (radius harus dalam radian: km / 6371)
        indices = tree.query_radius(coords, r=proximity_km / 6371.0)

        for i, neighbors in enumerate(indices):
            # Jika kapal i sendiri ngebut, skip (bukan transhipment)
            if group.iloc[i]['sog'] > sog_threshold:
                continue

            for j in neighbors:
                if j <= i:  # Hindari duplikat (A-B dan B-A) & diri sendiri (A-A)
                    continue

                # Jika kapal j ngebut, skip
                if group.iloc[j]['sog'] > sog_threshold:
                    continue

                # DAPAT PASANGAN!
                # (Keduanya dekat & pelan/diam)
                row_i = group.iloc[i]
                row_j = group.iloc[j]

                potential_interactions.append({
                    'mmsi_1': min(row_i['mmsi'], row_j['mmsi']),
                    'mmsi_2': max(row_i['mmsi'], row_j['mmsi']),
                    'utc': timestamp,  # Waktu presisi (menit)
                    'lat': (row_i['lat'] + row_j['lat']) / 2,  # Titik tengah
                    'lon': (row_i['lon'] + row_j['lon']) / 2,
                })

        # Print progress tiap 10% biar gak dikira hang
        if total_steps > 10 and step % (max(1, total_steps // 10)) == 0:
            print(f"      ... Progress scan: {int(step/total_steps*100)}%")

    if not potential_interactions:
        print("   [Logic] Tidak ada pasangan kapal yang berdekatan.")
        return pd.DataFrame(), pd.DataFrame()

    print(f"   [Logic] Ditemukan {len(potential_interactions)} titik interaksi mentah. Menganalisis durasi...")

    # ============================
    # 2. Session Aggregation (Gabungkan Waktu)
    # ============================
    anom_df = pd.DataFrame(potential_interactions)
    final_anomalies = []
    candidate_anomalies = []

    # Grouping per Pasangan Kapal
    for (m1, m2), group in anom_df.groupby(['mmsi_1', 'mmsi_2']):
        group = group.sort_values('utc')

        # Hitung selisih waktu antar titik
        group['time_diff'] = group['utc'].diff().fillna(pd.Timedelta(seconds=0))

        # Jika putus > time_gap_min (misal 10 menit), anggap sesi baru
        group['gap'] = (group['time_diff'] > pd.Timedelta(minutes=time_gap_min)).cumsum()

        for _, session in group.groupby('gap'):
            # Hitung rata-rata lokasi sesi ini
            lat_mean = session['lat'].mean()
            lon_mean = session['lon'].mean()

            # FILTER: Jarak dari Pelabuhan
            if is_far_from_ports(lat_mean, lon_mean, ports, port_dist_km):

                # Hitung Durasi Real
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

                # Klasifikasi Anomali
                if duration_minutes >= duration_min:
                    final_anomalies.append(anomaly_record)
                elif duration_minutes >= candidate_duration_min:
                    candidate_anomalies.append(anomaly_record)

    elapsed = round(time.time() - start_time, 2)
    print(f"   [Logic] Selesai dalam {elapsed}s. {len(final_anomalies)} Confirmed, {len(candidate_anomalies)} Candidates.")

    return pd.DataFrame(final_anomalies), pd.DataFrame(candidate_anomalies)