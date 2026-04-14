# cek_index.py
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"), serverSelectionTimeoutMS=5000)
db = client[os.getenv("DATABASE_NAME")]
collection = db[os.getenv("COLLECTION_NAME")]

print("📋 Indexes yang ada:")
for idx in collection.list_indexes():
    print(f"  - {idx['name']}: {idx['key']}")