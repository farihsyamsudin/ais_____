"""
========================================================
PROOF OF CONCEPT — AIS Anomaly Detection Validator
========================================================
Script ini membuktikan bahwa algoritma detect_anomalies()
bekerja dengan benar dengan cara:

  1. Inject data sintetis yang PASTI terdeteksi ke collection
     `ais_signal_test` (BUKAN ais_signals / production)
  2. Jalankan detect_anomalies() langsung
  3. Assert hasilnya sesuai ekspektasi
  4. Cetak laporan lengkap

Jalankan:
    python test_detection_proof.py

Requirement:
    pip install pymongo pandas numpy haversine scikit-learn python-dotenv
"""

import sys
import os
import time
from datetime import datetime, timedelta, timezone
import random

import pandas as pd
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv

# ── Pastikan anomaly_logic.py bisa diimport ─────────────────────────────────
# Sesuaikan path jika file ada di subfolder lain
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from anomaly_logic import detect_anomalies
except ImportError:
    print("❌  Tidak bisa import anomaly_logic.py")
    print("    Pastikan file anomaly_logic.py ada di folder yang sama dengan script ini.")
    sys.exit(1)

load_dotenv()

# ==============================
# CONFIG
# ==============================

MONGODB_URI    = os.getenv("MONGODB_URI",    "mongodb://localhost:27017/")
DATABASE_NAME  = os.getenv("DATABASE_NAME",  "ais_transhipment_db")
TEST_COLLECTION = "ais_signal_test"          # ← Tidak menyentuh production!

# Parameter deteksi — sama persis dengan DEFAULT_PARAMS di app.py
PARAMS = {
    "proximity_km":           0.5,
    "duration_min":           30,
    "candidate_duration_min": 15,
    "sog_threshold":          1.5,
    "port_distance_km":       10,
    "time_gap_min":           30,
}

# Port list minimal (sama dengan PORTS di app.py — cukup beberapa key port)
# Titik simulasi kita jauh dari semua ini, jadi tidak akan terfilter
PORTS = [
    {"name": "Batu Ampar",   "lat": 1.1617, "lon": 104.0047},
    {"name": "Kabil",        "lat": 1.1108, "lon": 104.1403},
    {"name": "Jurong Port",  "lat": 1.2604, "lon": 103.6888},
    {"name": "Keppel",       "lat": 1.2600, "lon": 103.8300},
    {"name": "PTP",          "lat": 1.3600, "lon": 103.5500},
]

# ==============================
# SCENARIO DEFINITIONS
# ==============================
# Setiap skenario mendefinisikan apa yang di-inject & apa yang diharapkan terdeteksi.
# Titik simulasi ada di tengah Selat Bangka — jauh dari port mana pun.

SCENARIOS = [
    {
        "id": "S1",
        "name": "Confirmed Anomaly — 35 menit",
        "description": "Dua kapal berdekatan (< 0.5 km), sog < 1.5, selama 35 menit",
        "mmsi_1": 111111001,
        "mmsi_2": 111111002,
        "duration_min": 35,      # > 30 → harus masuk confirmed
        "lat": -5.80,
        "lon": 105.50,
        "sog": 0.3,
        "offset_km": 0.08,       # jarak antar kapal ≈ 80 m (jauh di bawah threshold 500 m)
        "expect_confirmed": True,
        "expect_candidate": False,
    },
    {
        "id": "S2",
        "name": "Candidate Anomaly — 20 menit",
        "description": "Dua kapal berdekatan selama 20 menit (> 15, < 30 → candidate)",
        "mmsi_1": 222222001,
        "mmsi_2": 222222002,
        "duration_min": 20,
        "lat": -5.90,
        "lon": 105.60,
        "sog": 0.5,
        "offset_km": 0.08,
        "expect_confirmed": False,
        "expect_candidate": True,
    },
    {
        "id": "S3",
        "name": "NOT Detected — terlalu cepat (sog > threshold)",
        "description": "Dua kapal dekat tapi sog = 3.0 (> 1.5) → harus diabaikan",
        "mmsi_1": 333333001,
        "mmsi_2": 333333002,
        "duration_min": 35,
        "lat": -6.00,
        "lon": 105.70,
        "sog": 3.0,              # Ngebut → bukan transhipment
        "offset_km": 0.08,
        "expect_confirmed": False,
        "expect_candidate": False,
    },
    {
        "id": "S4",
        "name": "NOT Detected — terlalu singkat (10 menit)",
        "description": "Kapal berdekatan hanya 10 menit (< 15 min threshold)",
        "mmsi_1": 444444001,
        "mmsi_2": 444444002,
        "duration_min": 10,
        "lat": -6.10,
        "lon": 105.40,
        "sog": 0.4,
        "offset_km": 0.08,
        "expect_confirmed": False,
        "expect_candidate": False,
    },
    {
        "id": "S5",
        "name": "High Priority — 50 menit (Multi-pair)",
        "description": "Satu pasang kapal bertemu sangat lama, seharusnya jadi top confirmed",
        "mmsi_1": 555555001,
        "mmsi_2": 555555002,
        "duration_min": 50,
        "lat": -5.70,
        "lon": 105.45,
        "sog": 0.2,
        "offset_km": 0.05,
        "expect_confirmed": True,
        "expect_candidate": False,
    },
]


# ==============================
# HELPERS
# ==============================

def connect_db():
    """Connect ke MongoDB dan return collection test."""
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    try:
        client.server_info()
    except Exception as e:
        print(f"❌  MongoDB tidak bisa dijangkau: {e}")
        sys.exit(1)
    db = client[DATABASE_NAME]
    return db[TEST_COLLECTION]


def km_to_deg_lat(km):
    """Konversi km ke derajat lintang (approx)."""
    return km / 111.32


def generate_scenario_docs(scenario, base_time):
    """
    Buat dokumen AIS sintetis untuk satu skenario.
    Format mengikuti skema real: immsi (int), mmsi (str), lat, lon, sog, created_at, utc
    """
    docs = []
    duration = scenario["duration_min"]
    lat_base  = scenario["lat"]
    lon_base  = scenario["lon"]
    sog       = scenario["sog"]
    offset    = km_to_deg_lat(scenario["offset_km"])

    for minute in range(duration + 1):   # +1 agar endpoint inklusif
        ts = base_time + timedelta(minutes=minute)

        # Kapal 1 — sedikit drift acak
        lat1 = lat_base + random.uniform(-0.0001, 0.0001)
        lon1 = lon_base + random.uniform(-0.0001, 0.0001)

        # Kapal 2 — dekat, offset kecil
        lat2 = lat1 + offset
        lon2 = lon1 + offset

        sog1 = sog + random.uniform(-0.05, 0.05)
        sog2 = sog + random.uniform(-0.05, 0.05)

        for mmsi_int, lat, lon, s in [
            (scenario["mmsi_1"], lat1, lon1, sog1),
            (scenario["mmsi_2"], lat2, lon2, sog2),
        ]:
            docs.append({
                "immsi":      mmsi_int,
                "mmsi":       str(mmsi_int),
                "lat":        round(lat, 6),
                "lon":        round(lon, 6),
                "sog":        round(max(0.0, s), 2),
                "created_at": ts,
                "cog":        round(random.uniform(0, 360), 1),
                "heading":    random.randint(0, 359),
                "navstatus":  0,
                "_test_scenario": scenario["id"],   # tag untuk mudah dibersihkan
            })

    return docs


def build_dataframe(collection, mmsi_list, start_dt, end_dt):
    """
    Ambil data dari MongoDB (format sama dengan fetch_ais_data di app.py),
    return DataFrame siap masuk detect_anomalies().
    """
    query = {
        "immsi": {"$in": mmsi_list},
        "created_at": {"$gte": start_dt, "$lte": end_dt},
    }
    data = list(collection.find(query).sort("created_at", 1))
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df["mmsi"] = df["immsi"].astype("int32")
    df["sog"]  = df["sog"].astype("float32")
    df["lat"]  = df["lat"].astype("float32")
    df["lon"]  = df["lon"].astype("float32")
    df["utc"]  = pd.to_datetime(df["created_at"])

    return df[["mmsi", "lat", "lon", "sog", "utc", "created_at"]]


def run_test(scenario, collection, base_time, end_time):
    """Jalankan satu skenario dan return (passed, detail_dict)."""
    mmsi_list = [scenario["mmsi_1"], scenario["mmsi_2"]]

    df = build_dataframe(collection, mmsi_list, base_time, end_time)
    if df.empty:
        return False, {"error": "Tidak ada data ditemukan di DB"}

    confirmed_df, candidate_df = detect_anomalies(
        df,
        PARAMS["proximity_km"],
        PARAMS["duration_min"],
        PARAMS["candidate_duration_min"],
        PARAMS["sog_threshold"],
        PARAMS["port_distance_km"],
        PARAMS["time_gap_min"],
        PORTS,
    )

    # Cek apakah pasangan kapal ini ada di hasil
    def pair_found(result_df):
        if result_df.empty:
            return False
        m1, m2 = min(mmsi_list), max(mmsi_list)
        mask = (
            (result_df["mmsi_1"] == m1) & (result_df["mmsi_2"] == m2)
        )
        return mask.any()

    got_confirmed  = pair_found(confirmed_df)
    got_candidate  = pair_found(candidate_df)

    exp_confirmed  = scenario["expect_confirmed"]
    exp_candidate  = scenario["expect_candidate"]

    passed = (got_confirmed == exp_confirmed) and (got_candidate == exp_candidate)

    # Detail durasi jika ada
    duration_found = None
    if got_confirmed and not confirmed_df.empty:
        m1, m2 = min(mmsi_list), max(mmsi_list)
        row = confirmed_df[(confirmed_df["mmsi_1"] == m1) & (confirmed_df["mmsi_2"] == m2)]
        if not row.empty:
            duration_found = float(row.iloc[0]["duration_min"])
    elif got_candidate and not candidate_df.empty:
        m1, m2 = min(mmsi_list), max(mmsi_list)
        row = candidate_df[(candidate_df["mmsi_1"] == m1) & (candidate_df["mmsi_2"] == m2)]
        if not row.empty:
            duration_found = float(row.iloc[0]["duration_min"])

    return passed, {
        "got_confirmed":  got_confirmed,
        "got_candidate":  got_candidate,
        "exp_confirmed":  exp_confirmed,
        "exp_candidate":  exp_candidate,
        "duration_found": duration_found,
        "data_points":    len(df),
    }


# ==============================
# MAIN
# ==============================

def main():
    random.seed(42)

    print()
    print("=" * 65)
    print("  AIS ANOMALY DETECTION — PROOF OF CONCEPT TEST")
    print("=" * 65)
    print(f"  DB         : {DATABASE_NAME}")
    print(f"  Collection : {TEST_COLLECTION}  (test only, bukan production)")
    print(f"  Params     : proximity={PARAMS['proximity_km']}km | "
          f"duration>={PARAMS['duration_min']}min | "
          f"sog<={PARAMS['sog_threshold']} kt")
    print("=" * 65)

    # ── Connect ──────────────────────────────────────────────────────────────
    print("\n🔌  Menghubungkan ke MongoDB...")
    collection = connect_db()
    print(f"✅  Terhubung ke collection: {TEST_COLLECTION}")

    # ── Cleanup data lama dari run sebelumnya ─────────────────────────────
    deleted = collection.delete_many({"_test_scenario": {"$exists": True}})
    if deleted.deleted_count:
        print(f"🗑️   Membersihkan {deleted.deleted_count} dokumen test lama")

    # ── Tentukan window waktu ─────────────────────────────────────────────
    # Buat semua skenario mulai dari 1 jam yang lalu, biar masuk window EWS
    base_time = datetime.utcnow() - timedelta(hours=1)
    end_time  = datetime.utcnow() + timedelta(minutes=5)

    # ── Inject data ───────────────────────────────────────────────────────
    print(f"\n📥  Menginjeksi data sintetis ke `{TEST_COLLECTION}`...")
    total_docs = 0
    for sc in SCENARIOS:
        docs = generate_scenario_docs(sc, base_time)
        collection.insert_many(docs)
        total_docs += len(docs)
        print(f"   [{sc['id']}] {sc['name'][:45]:<45} → {len(docs):>4} dokumen")

    print(f"\n   Total injeksi: {total_docs} dokumen")

    # ── Jalankan test per skenario ─────────────────────────────────────────
    print("\n🔍  Menjalankan deteksi per skenario...\n")
    print("-" * 65)

    results = []
    for sc in SCENARIOS:
        print(f"[{sc['id']}] {sc['name']}")
        print(f"    {sc['description']}")

        t0 = time.time()
        passed, detail = run_test(sc, collection, base_time, end_time)
        elapsed = round(time.time() - t0, 2)

        status = "✅ PASS" if passed else "❌ FAIL"
        results.append({"scenario": sc, "passed": passed, "detail": detail})

        print(f"    Status  : {status}  ({elapsed}s)")
        print(f"    Expected: confirmed={detail['exp_confirmed']}  candidate={detail['exp_candidate']}")
        print(f"    Got     : confirmed={detail['got_confirmed']}  candidate={detail['got_candidate']}", end="")
        if detail.get("duration_found") is not None:
            print(f"  (durasi terdeteksi: {detail['duration_found']:.1f} menit)", end="")
        print()
        print(f"    Data pts: {detail['data_points']}")
        print("-" * 65)

    # ── Summary ───────────────────────────────────────────────────────────
    passed_count = sum(1 for r in results if r["passed"])
    total_count  = len(results)

    print()
    print("=" * 65)
    print(f"  HASIL: {passed_count}/{total_count} skenario PASSED")
    print("=" * 65)

    for r in results:
        sc   = r["scenario"]
        icon = "✅" if r["passed"] else "❌"
        print(f"  {icon} [{sc['id']}] {sc['name']}")

    print()
    if passed_count == total_count:
        print("🎉  Semua skenario PASSED! Algoritma deteksi bekerja dengan benar.")
    else:
        failed = [r["scenario"]["id"] for r in results if not r["passed"]]
        print(f"⚠️   {len(failed)} skenario GAGAL: {', '.join(failed)}")
        print("    Periksa parameter deteksi atau logika inject data.")

    # ── Optional: cleanup setelah test ────────────────────────────────────
    print()
    cleanup = input("Hapus data test dari MongoDB sekarang? (y/n) [n]: ").strip().lower()
    if cleanup == "y":
        del_result = collection.delete_many({"_test_scenario": {"$exists": True}})
        print(f"🗑️   {del_result.deleted_count} dokumen test dihapus.")
    else:
        print(f"ℹ️   Data test dibiarkan di collection `{TEST_COLLECTION}`.")

    print("\n✅  Selesai.\n")
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())