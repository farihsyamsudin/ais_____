"""
Seeder Database AIS - Batam/Singapore Area

Skema dokumen sesuai data produksi (contoh row nyata):
{
  "_id":        { "$oid": "65919f3c77ab59fa50baa3a6" },
  "valid":      true,
  "error_mesg": "",
  "aistype":    3,
  "channel":    "B",
  "msglen":     28,
  "immsi":      525101059,
  "mmsi":       "525101059",
  "class":      "A",
  "navstatus":  3,
  "lon":        104.00441666666667,
  "lat":        1.16170000000000,
  "rot":        -128,
  "sog":        0,
  "cog":        286.9,
  "hdg":        511,
  "utc":        0,
  "smi":        0,
  "created_at": { "$date": "2024-01-01T00:00:01.000Z" },
  "loc": {
    "type": "Point",
    "coordinates": [ 104.00441666666667, 1.16170000000000 ]
  },
  "original":     "!AIVDM,1,1,,B,37li`0kP00842CGsp3Ss=Ov025MS,0*48",
  "port_origin":  "4334",
  "callsign":     null
}

Notes:
- immsi  : integer MMSI (dipakai oleh anomaly_logic untuk komputasi)
- mmsi   : string MMSI (field asli dari AIS decoder)
- rot    : -128 = data tidak tersedia (AIS standard)
- hdg    : 511  = data tidak tersedia (AIS standard)
- utc    : detik (0-59) dari sinyal AIS, BUKAN timestamp — gunakan created_at
- loc    : GeoJSON Point [lon, lat] untuk 2dsphere index
"""

import random
import string
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI     = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DATABASE_NAME   = os.getenv("DATABASE_NAME", "ais_transhipment_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ais_signals")

# ==============================================================================
# MMSI Pools - Format Indonesia (525xxxxxx) dan Malaysia (533xxxxxx)
# dan kapal internasional umum di Selat Singapura
# ==============================================================================
MMSI_INDO  = [525101059, 525101200, 525014321, 525006781, 525019042,
              525030088, 525044417, 525055530, 525066123, 525077890]
MMSI_MY    = [533000100, 533001234, 533002345, 533003456, 533004567]
MMSI_SG    = [564000001, 564000002, 564000003, 564000004, 564000005]
MMSI_NOISE = [477001001, 477001002, 477001003,  # HK
              636000101, 636000102,              # Liberia
              311000201, 311000202]              # Bahamas

# Navstatus codes (AIS):
# 0=under way engine, 1=at anchor, 3=not under command,
# 5=moored, 7=engaged in fishing, 15=undefined
NAV_ANCHORED   = 1
NAV_UNDERWAY   = 0
NAV_MOORED     = 5

# Port origin codes (Batam area)
PORT_ORIGINS = ["4334", "4335", "4336", "4337", "4338"]


def make_callsign():
    prefix = random.choice(["YB", "YC", "YD", "9M", "S"])
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}{suffix}"


def make_ais_doc(mmsi_int, lat, lon, sog, cog, hdg, navstatus, created_at,
                 rot=-128, aistype=3, channel="B", simulation=False):
    """Membuat dokumen AIS dengan skema lengkap sesuai data produksi."""
    mmsi_str = str(mmsi_int)
    return {
        "valid": True,
        "error_mesg": "",
        "aistype": aistype,
        "channel": channel,
        "msglen": random.choice([26, 27, 28]),
        "immsi": mmsi_int,
        "mmsi": mmsi_str,
        "class": "A",
        "navstatus": navstatus,
        "lon": round(lon, 8),
        "lat": round(lat, 8),
        "rot": rot,
        "sog": round(sog, 1),
        "cog": round(cog, 1),
        "hdg": hdg,
        "utc": created_at.second,       # AIS UTC field = detik (0-59)
        "smi": 0,
        "created_at": created_at,
        "loc": {
            "type": "Point",
            "coordinates": [round(lon, 8), round(lat, 8)]
        },
        "original": f"!AIVDM,1,1,,{channel},SIMULATED_{mmsi_str},0*00",
        "port_origin": random.choice(PORT_ORIGINS),
        "callsign": make_callsign() if random.random() > 0.3 else None,
        **({"simulation": True} if simulation else {}),
    }


# ==============================================================================
# KOORDINAT AREA BATAM / SELAT SINGAPURA
# Hindari area pelabuhan (filter akan dilakukan oleh anomaly_logic)
# Open sea spots untuk inject anomali:
# - Tengah selat Batam-Singapore: lat ~1.18, lon ~103.98
# - Barat Batam: lat ~1.08, lon ~103.87
# - Timur Batam: lat ~1.15, lon ~104.12
# ==============================================================================
ANOMALY_SPOTS = [
    {"lat": 1.1800, "lon": 103.9800, "name": "Selat Batam Tengah"},
    {"lat": 1.0850, "lon": 103.8700, "name": "Barat Batam"},
    {"lat": 1.1500, "lon": 104.1200, "name": "Timur Batam"},
    {"lat": 1.2200, "lon": 103.9200, "name": "Selat Utara"},
    {"lat": 1.1000, "lon": 104.0500, "name": "Perairan Kabil"},
]


def generate_scenario(scenario_type, base_time, duration_min=40, num_pairs=1):
    """
    Generate test scenario sesuai tipe.
    Semua dokumen pakai skema AIS produksi penuh.
    """
    documents = []

    for k in range(num_pairs):
        spot = ANOMALY_SPOTS[k % len(ANOMALY_SPOTS)]
        base_lat = spot["lat"] + (k * 0.005)
        base_lon = spot["lon"] + (k * 0.005)

        # Pilih MMSI dari pool Indo/SG
        mmsi1 = MMSI_INDO[k % len(MMSI_INDO)]
        mmsi2 = MMSI_SG[k % len(MMSI_SG)]

        # Default: 2 kapal berdekatan ~50m
        lat1, lon1 = base_lat, base_lon
        lat2, lon2 = base_lat + 0.0004, base_lon + 0.0004  # ~50m

        sog1 = sog2 = 0.2
        nav1 = nav2 = NAV_ANCHORED

        # ---- Modifikasi sesuai scenario ----
        if "far_proximity" in scenario_type:
            lat2, lon2 = base_lat + 0.03, base_lon + 0.03  # ~4km

        if "near_port" in scenario_type:
            # Pindah ke dekat Batu Ampar
            lat1, lon1 = 1.1617, 104.0047
            lat2, lon2 = lat1 + 0.0004, lon1 + 0.0004

        if "high_speed" in scenario_type:
            sog1 = sog2 = 8.5
            nav1 = nav2 = NAV_UNDERWAY

        # ---- Generate sinyal per menit ----
        for minute in range(duration_min):
            t = base_time + timedelta(minutes=minute)
            cog1 = round(random.uniform(0, 360), 1)
            cog2 = round(random.uniform(0, 360), 1)
            hdg1 = random.randint(0, 359) if sog1 > 1 else 511
            hdg2 = random.randint(0, 359) if sog2 > 1 else 511

            documents.append(make_ais_doc(
                mmsi1, lat1 + random.uniform(-0.00005, 0.00005),
                lon1 + random.uniform(-0.00005, 0.00005),
                sog1, cog1, hdg1, nav1, t,
                simulation=True
            ))
            documents.append(make_ais_doc(
                mmsi2, lat2 + random.uniform(-0.00005, 0.00005),
                lon2 + random.uniform(-0.00005, 0.00005),
                sog2, cog2, hdg2, nav2, t,
                simulation=True
            ))

    return documents


def add_noise_vessels(documents, start_time, duration=40, num_noise=3):
    """Tambahkan kapal bergerak (noise) agar data lebih realistis."""
    noise_mmsi_pool = MMSI_NOISE + MMSI_MY
    for i in range(duration):
        t = start_time + timedelta(minutes=i)
        for j in range(num_noise):
            mmsi = noise_mmsi_pool[j % len(noise_mmsi_pool)]
            lat = random.uniform(1.05, 1.45)
            lon = random.uniform(103.55, 104.30)
            sog = round(random.uniform(6.0, 14.0), 1)
            cog = round(random.uniform(0, 360), 1)
            hdg = random.randint(0, 359)
            documents.append(make_ais_doc(
                mmsi, lat, lon, sog, cog, hdg, NAV_UNDERWAY, t,
                simulation=True
            ))
    return documents


def seed_test_scenarios(collection):
    """Seed test scenarios untuk validasi algoritma."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    time_offset = timedelta(hours=0)

    scenarios = [
        # Format: (type, duration_menit, num_pairs)
        # Valid: harus ketemu sebagai confirmed
        {"type": "valid",               "duration": 40, "pairs": 1},
        {"type": "valid_multi",         "duration": 40, "pairs": 3},

        # Candidate: durasi terlalu pendek untuk confirmed
        {"type": "short_duration",      "duration": 18, "pairs": 1},

        # Harus di-reject oleh algo
        {"type": "far_proximity",       "duration": 40, "pairs": 1},
        {"type": "high_speed",          "duration": 40, "pairs": 1},
        {"type": "near_port",           "duration": 40, "pairs": 1},
    ]

    print("\n📦 Seeding test scenarios (area Batam/Singapore)...")
    total_docs = 0

    for scenario in scenarios:
        scenario_time = base_time + time_offset
        docs = generate_scenario(
            scenario["type"],
            scenario_time,
            scenario["duration"],
            scenario["pairs"]
        )

        # Tambah noise untuk multi-pair biar realistis
        if "multi" in scenario["type"] or "valid" in scenario["type"]:
            docs = add_noise_vessels(docs, scenario_time, scenario["duration"], num_noise=2)

        if docs:
            collection.insert_many(docs)
            total_docs += len(docs)
            print(f"  ✅ [{scenario['type']}]: {len(docs)} dokumen @ {scenario_time.strftime('%H:%M')}")

        time_offset += timedelta(hours=2)

    print(f"\n✅ Total test documents: {total_docs}")
    print(f"   Time range: {base_time} → {base_time + time_offset}")


def seed_realistic_data(collection, days=7):
    """
    Seed data realistis multi-hari: lalu lintas normal + anomali inject.
    Koordinat area Batam/Selat Singapura.
    """
    print(f"\n📦 Seeding {days} days of realistic data (Batam/SG area)...")

    start_date = datetime(2024, 1, 1, 0, 0, 0)
    documents  = []

    # Normal traffic: kapal bergerak di selat
    normal_mmsi = MMSI_INDO[:5] + MMSI_SG[:3] + MMSI_MY[:2]

    for day in range(days):
        current_date = start_date + timedelta(days=day)

        # Normal traffic tiap 5 menit
        for minute in range(0, 1440, 5):
            t = current_date + timedelta(minutes=minute)
            for mmsi in normal_mmsi:
                lat = round(random.uniform(1.05, 1.45), 6)
                lon = round(random.uniform(103.55, 104.30), 6)
                sog = round(random.uniform(5.0, 13.0), 1)
                cog = round(random.uniform(0, 360), 1)
                hdg = random.randint(0, 359)
                documents.append(make_ais_doc(
                    mmsi, lat, lon, sog, cog, hdg, NAV_UNDERWAY, t
                ))

        # Inject 1-2 anomali per hari
        num_anomalies = random.randint(1, 2)
        for _ in range(num_anomalies):
            anomaly_minute = random.randint(60, 1380)
            anomaly_time   = current_date + timedelta(minutes=anomaly_minute)
            spot           = random.choice(ANOMALY_SPOTS)

            mmsi_a = random.choice(MMSI_INDO)
            mmsi_b = random.choice(MMSI_SG)
            lat_a, lon_a = spot["lat"], spot["lon"]
            lat_b = lat_a + random.uniform(0.0002, 0.0005)
            lon_b = lon_a + random.uniform(0.0002, 0.0005)

            # Anomali berlangsung 35-50 menit
            dur = random.randint(35, 50)
            for m in range(dur):
                t = anomaly_time + timedelta(minutes=m)
                cog_ab = round(random.uniform(0, 360), 1)
                documents.append(make_ais_doc(
                    mmsi_a, lat_a + random.uniform(-0.00005, 0.00005),
                    lon_a + random.uniform(-0.00005, 0.00005),
                    round(random.uniform(0.0, 0.3), 1), cog_ab, 511, NAV_ANCHORED, t
                ))
                documents.append(make_ais_doc(
                    mmsi_b, lat_b + random.uniform(-0.00005, 0.00005),
                    lon_b + random.uniform(-0.00005, 0.00005),
                    round(random.uniform(0.0, 0.3), 1), cog_ab, 511, NAV_ANCHORED, t
                ))

        # Batch insert per hari
        if documents:
            collection.insert_many(documents)
            print(f"  ✅ Day {day+1} ({current_date.date()}): {len(documents)} documents")
            documents = []

    print(f"✅ Realistic data seeded: {days} days")


def create_indexes(collection):
    """Create indexes untuk performa query."""
    collection.create_index([("created_at", ASCENDING)])
    collection.create_index([("immsi", ASCENDING)])
    collection.create_index([("mmsi", ASCENDING)])
    collection.create_index([("loc", "2dsphere")])  # Geospatial index
    print("✅ Indexes created (created_at, immsi, mmsi, loc 2dsphere)")


def main():
    print("=" * 60)
    print("🌊 AIS Database Seeder - Batam/Singapore Area")
    print("=" * 60)
    print(f"  MongoDB   : {MONGODB_URI}")
    print(f"  Database  : {DATABASE_NAME}")
    print(f"  Collection: {COLLECTION_NAME}")
    print("=" * 60)

    client     = MongoClient(MONGODB_URI)
    db         = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    # Cek existing data
    existing = collection.count_documents({})
    if existing > 0:
        print(f"\n⚠️  Collection sudah berisi {existing:,} dokumen.")
        action = input("Drop & reseed? (yes/no): ").strip().lower()
        if action == "yes":
            collection.drop()
            print("🗑️  Collection dropped.")
        else:
            print("Append ke data existing.")

    # Create indexes dulu
    create_indexes(collection)

    # Pilih tipe seed
    print("\nPilih data yang mau di-seed:")
    print("  1. Test scenarios only")
    print("  2. Realistic data only")
    print("  3. Both (recommended)")
    choice = input("Choice (1/2/3): ").strip()

    if choice in ["1", "3"]:
        seed_test_scenarios(collection)

    if choice in ["2", "3"]:
        days = int(input("Berapa hari data realistis? (default: 7): ").strip() or "7")
        seed_realistic_data(collection, days)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Database Summary:")
    print(f"   Total documents : {collection.count_documents({}):,}")
    print(f"   Unique vessels  : {len(collection.distinct('immsi'))}")

    date_range = list(collection.aggregate([
        {"$group": {
            "_id": None,
            "min_date": {"$min": "$created_at"},
            "max_date": {"$max": "$created_at"}
        }}
    ]))
    if date_range:
        print(f"   Date range      : {date_range[0]['min_date']} → {date_range[0]['max_date']}")

    print("=" * 60)
    print("✅ Seeding completed!")
    print()
    print("💡 Untuk test detection, gunakan:")
    print("   Start: 2024-01-01T10:00:00")
    print("   End  : 2024-01-01T22:00:00")
    print("   Params default (proximity 0.5km, duration 30min, SOG 2.0kn)")


if __name__ == "__main__":
    main()