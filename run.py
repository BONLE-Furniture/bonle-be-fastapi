from fastapi import FastAPI, HTTPException
from bson import ObjectId
from database import db
from datetime import datetime, timedelta
from models import Period

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}


# product 조회 API
@app.get("/product/{product_id}")
async def get_product(product_id: str):
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if product:
        product["_id"] = str(product["_id"])
        return product
    raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")



# 판매처 링크 조회 API
@app.get("/product/{product_id}/shop-urls")
async def get_shop_urls(product_id: str):

    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    shop_urls = product.get("shop_urls", [])
    if not shop_urls:
        raise HTTPException(status_code=404, detail="No shop URLs found for this product")

    # 반환할 데이터 정리
    result_data = [{"shop_id": shop["shop_id"], "url": shop["url"]} for shop in shop_urls]

    return  result_data


# 제품 내 가장 최근 최저가 정보 조회 API
#  TODO 현재 날짜 최저가 조회로 변경 해야함
@app.get("/product/{product_id}/cheapest")
async def get_cheapest(product_id: str):
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cheapest = product.get("cheapest", [])
    if not cheapest:
        raise HTTPException(status_code=404, detail="No cheapest price found for this product")

    # 최저가 정보 중 현재 날짜에서 가장 최근 정보 조회
    current_cheapest = sorted(cheapest, key=lambda x: x["date"], reverse=True)[0]

    return current_cheapest


# 최저가 그래프 조회 API
@app.get("/product/{product_id}/cheapest-graph")
async def get_cheapest_prices(product_id: str, period: Period):
    """
    기간별 최저가 데이터를 반환하는 엔드포인트.
    :param product_id: 제품 ID
    :param period: 선택된 기간 (1주일, 1달, 1년, 전체)
    """
    # MongoDB에서 제품 데이터 조회
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # `cheapest` 필드 확인
    cheapest = product.get("cheapest", [])
    if not cheapest:
        raise HTTPException(status_code=404, detail="No cheapest data found for this product")

    # 현재 날짜
    now = datetime.now()

    # 기간별 시작 날짜 계산
    if period == Period.one_week:
        start_date = now - timedelta(weeks=1)
    elif period == Period.one_month:
        start_date = now - timedelta(days=30)
    elif period == Period.one_year:
        start_date = now - timedelta(days=365)
    elif period == Period.all_time:
        start_date = None  # 전체 데이터는 필터링하지 않음

    # 기간 내 데이터 필터링
    filtered_data = []
    for entry in cheapest:
        entry_date = entry["date"]  # 이미 datetime 객체임
        if start_date is None or entry_date >= start_date:
            filtered_data.append({"date": entry_date.date().isoformat(), "price": entry["price"]})

    if not filtered_data:
        raise HTTPException(status_code=404, detail=f"No cheapest data available for period: {period}")

    # 날짜별 최저가 계산
    daily_prices = {}
    for entry in filtered_data:
        date_key = entry["date"]
        price = entry["price"]
        if date_key not in daily_prices or price < daily_prices[date_key]:
            daily_prices[date_key] = price

    # 결과 정렬 및 반환
    sorted_prices = [{"date": date, "price": price} for date, price in sorted(daily_prices.items())]
    return {"period": period.value, "data": sorted_prices}


################hyundong#####################

def sanitize_data(data):
    sanitized_data = []
    for item in data:
        sanitized_item = {}
        for key, value in item.items():
            if isinstance(value, ObjectId):
                sanitized_item[key] = str(value)
            elif isinstance(value, float):
                if value == float('inf') or value == float('-inf') or value != value:
                    sanitized_item[key] = None
                else:
                    sanitized_item[key] = value
            elif isinstance(value, dict): 
                sanitized_item[key] = sanitize_data([value])[0]
            elif isinstance(value, list): 
                sanitized_item[key] = [
                    str(v) if isinstance(v, ObjectId)
                    else sanitize_data([v])[0] if isinstance(v, dict)
                    else v
                    for v in value
                ]
            else:
                sanitized_item[key] = value
        sanitized_data.append(sanitized_item)
    return sanitized_data

"""
FAST API 연결, MongoDB 연결 테스트
"""
@app.get("/")
async def read_root():
    return {"message": "welcome to bonle"}

@app.get("/check_connection")
async def get_bonre_brands():
    collections = await database.list_collection_names()
    return collections

"""
제품 페이지 브랜드 API
"""
# test : /brands/get_bonre_brand_by_id/brand_andtrandition
# brand_id를 받아서 해당 브랜드 정보를 반환하는 API
@app.get("/brands/get_bonre_brand_by_id/{brand_id}")
async def get_bonre_brand_by_id(brand_id: str):
    item = await database["bonre_brands"].find_one({"_id": brand_id})
    if item is not None:
        return item
    raise HTTPException(status_code=404, detail="Item not found")

# test : http://127.0.0.1:8000/brands/get_bonre_products_by_brandId/brand_andtrandition
# brand_id를 받아서 해당 브랜드의 상품 정보를 반환하는 API
@app.get('/brands/get_bonre_products_by_brandId/{brand_id}')
async def get_bonre_products_by_brandId(brand_id: str):
    items = await database["bonre_products"].find({"brand": brand_id}).to_list(1000)
    if items:
        filtered_items = [
            {
                "_id": str(item["_id"]),
                "name_kr": item["name_kr"],
                "name": item["name"],
                "brand": item["brand"],
                "main_image_url": item["main_image_url"],
                # "cheapest": str(item["cheapest"][-1])
                "cheapest": str(item["cheapest"][-1]["price"] if item.get("cheapest") and len(item["cheapest"]) > 0 else None)
            }
            for item in items
        ]
        return filtered_items
    raise HTTPException(status_code=404, detail="Items not found")

# test : /home/products/?page=3&limit=2
@app.get("/home/products/")
async def get_products(page: int = 1, limit: int = 2):
    skip = (page - 1) * limit
    total_count = await database["bonre_products"].count_documents({})
    
    cursor = database["bonre_products"].find().skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    
    sanitized_items = sanitize_data(items)
    
    return {
        "items": sanitized_items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": ceil(total_count / limit)
    }

"""
모든 정보 반환 API
"""
# bonre_brands 컬렉션에 있는 모든 브랜드 정보를 반환하는 API
@app.get("/brands/get_bonre_brands")
async def get_bonre_brands():
    collections = await database.list_collection_names()
    if "bonre_brands" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await database["bonre_brands"].find().to_list(1000)
    sanitized_items = sanitize_data(items)
    return sanitized_items

# bonre_brands 컬렉션에 있는 모든 상품 정보를 반환하는 API
@app.get("/brands/get_bonre_products")
async def get_bonre_products():
    collections = await database.list_collection_names()
    if "bonre_products" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    items = await database["bonre_products"].find().to_list(1000)
    sanitized_items = sanitize_data(items)
    return sanitized_items

"""
CRUD API
"""

#  test in : http://localhost:8000/docs
@app.post("/brands/create_bonre_brand")
async def create_bonre_brand(brand: Bonre_brand):
    brand_dict = brand.dict(by_alias=True)
    await database["bonre_brands"].insert_one(brand_dict)
    return brand_dict

@app.patch("/brands/update_bonre_brand/{brand_id}")
async def update_bonre_brand(brand_id: str, brand: Bonre_brand_update):
    brand_dict = brand.dict(exclude_unset=True)
    brand_dict["_id"] = brand_id
    if not brand_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    await database["bonre_brands"].update_one({"_id": brand_id}, {"$set": brand_dict})
    return {"message": "Brand updated successfully"}