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
        raise HTTPException(status_code=404, detail=f"{period}간 해당 품목의 최저가 정보가 없습니다.")

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


# 북마크 수 업데이트 API
@app.post("/product/{product_id}/bookmark")
async def add_bookmark(product_id: str):
    """
    특정 상품의 bookmark_counts를 1 증가시키는 엔드포인트.
    :param product_id: 제품 ID
    """
    # ObjectId로 변환 가능한지 확인
    try:
        obj_id = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID format")

    # 해당 상품 조회
    product = await db["bonre_products"].find_one({"_id": obj_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 기존 북마크 카운트 가져오기 (기본값 0)
    current_count = product.get("bookmark_counts", 0)

    # bookmark_counts 필드를 +1 증가
    result = await db["bonre_products"].update_one(
        {"_id": obj_id},
        {"$set": {"bookmark_counts": current_count + 1}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update bookmark count")

    return {"product_id": product_id, "bookmark_counts": current_count + 1}