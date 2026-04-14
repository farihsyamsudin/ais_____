# test_connection.py
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

print(f"🔌 Connecting to: {MONGODB_URI[:30]}...")
print(f"📦 Database: {DATABASE_NAME}")
print(f"📋 Collection: {COLLECTION_NAME}")
print("-" * 40)

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    
    # Ping dulu
    client.admin.command('ping')
    print("✅ Ping berhasil! Koneksi OK")
    
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    
    # Estimated count (cepet, ga scan full)
    count = collection.estimated_document_count()
    print(f"✅ Collection '{COLLECTION_NAME}' ditemukan")
    print(f"📊 Estimasi total dokumen: {count:,}")
    
    # Sample 1 dokumen buat lihat strukturnya
    sample = collection.find_one()
    if sample:
        print(f"✅ Sample dokumen fields: {list(sample.keys())}")
    else:
        print("⚠️  Collection kosong!")

except Exception as e:
    print(f"❌ Gagal konek: {e}")