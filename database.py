# database.py
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import certifi


load_dotenv()

# 환경 변수로부터 MongoDB URI 불러오기
db_uri = os.getenv("MONGODB_URI")

# MongoDB 클라이언트 설정
client = AsyncIOMotorClient(db_uri, tlsCAFile=certifi.where())
db = client.bonre
# product_collection = db.get_collection("bonre_products")

