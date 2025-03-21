# import redis
# import os
# from dotenv import load_dotenv
# import certifi
#
# load_dotenv()
#
# try:
#     redis_client = redis.StrictRedis(
#         host=os.getenv("REDIS_HOST"),
#         port=int(os.getenv("REDIS_PORT", 6380)),
#         password=os.getenv("REDIS_PASSWORD"),
#         ssl = True,
#         ssl_ca_certs=certifi.where(),
#         decode_responses=True
#     )
#     redis_client.ping()
#     print("Redis 연결 성공")
# except redis.ConnectionError as e:
#     print(f"Redis 연결 실패: {e}")

