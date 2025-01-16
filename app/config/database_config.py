import os
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
import certifi

load_dotenv()
uri = os.environ.get('MONGODB_URI')
client = MongoClient(uri, tlsCAFile=certifi.where())

try:
    client.admin.command("ping")
    print("Connected to MongoDB")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")