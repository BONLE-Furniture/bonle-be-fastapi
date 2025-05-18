from bson import ObjectId
from db.database import db

from fastapi import APIRouter, HTTPException, Depends

from router.crawling.price.price_crawling import get_all_info
from router.user.token import allow_admin

from datetime import datetime
from pytz import timezone

kst = timezone('Asia/Seoul')
router = APIRouter(
    prefix="/price",
    tags=["price CRUD"]
)

############
## price ###
############

# 특정 shop & product의 날짜별 price 조회 API
@router.get("/{product_id}/{shop_sld}/", tags=["price CRUD"])
async def get_price_specific_shop_wholeday(product_id: str, shop_sld: str):
    """
    특정 shop & product의 날짜별 price 조회 API

    input : product_id{str}, shop_sld

    output : prices [{date, price}...]
    """
    item = await db["bonre_prices"].find_one({"product_id": product_id, "shop_sld": shop_sld})
    prices = item["prices"]
    if prices:
        filtered_items = [
            {
                "date": item["date"],
                "price": item["price"],
            }
            for item in prices
        ]
    return filtered_items



# 특정 product의 모든 shop price 출력 (오늘)
@router.get("/price/{product_id}/", tags=["price CRUD"])
async def get_prices_per_shops_today(product_id: str):
    """
    특정 product의 모든 shop price 출력 (오늘 날짜만)

    input : product_id{object_id}

    output : prices [{date, price}...]
    """
    items = await db["bonre_prices"].find({"product_id": product_id}).to_list(1000)
    if items:
        filtered_items = [
            {
                "_id": str(item["_id"]),
                "product_id": item["product_id"],
                "shop_sld": item["shop_sld"],
                "shop_id": item["shop_id"],
                "price": item["prices"][-1]["price"] if item.get("prices") and len(item["prices"]) > 0 else None
            }
            for item in items
        ]
    ########### 지금은 [-1] 마지막 인덱스로 처리하지만, 후에는 날짜별로 처리해야함
    #"price": item["prices"][-1]["price"] if item.get("prices") and len(item["prices"]) > 0 and item["prices"][-1]["date"] == datetime.utcnow().date().isoformat() else None
    return filtered_items


##############
## Crawling ##
##############
# front API 수정

@router.post("/update_prices/one", tags=["price CRUD"])
async def update_prices_with_id(product_id: str):
    # 제품 정보 가져오기
    product_doc = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product_doc:
        raise HTTPException(status_code=404, detail="Product not found")

    shops_urls = product_doc.get("shop_urls", [])
    if not shops_urls:
        raise HTTPException(status_code=400, detail="No shops_url found for this product")

    current_date = datetime.now().strftime("%Y-%m-%d")
    price_records = []

    for dict in shops_urls:
        url = dict["url"]
        shop_id = dict["shop_id"]
        info = get_all_info(url)

        if not info:
            continue

        shop_sld = info["site"]
        price = info["price"]

        if price is None:
            continue

        price_records.append((shop_id, price))

        existing_price_doc = await db["bonre_prices"].find_one({"product_id": product_id, "shop_sld": shop_sld})
        if existing_price_doc:
            existing_price_date = existing_price_doc["prices"][-1]["date"]
            if existing_price_date != current_date:
                await db["bonre_prices"].update_one(
                    {"product_id": product_id, "shop_sld": shop_sld},
                    {"$push": {"prices": {"date": current_date, "price": price}}}
                )
                updated_count += 1
                price_records.append((shop_id, price))
            else: # 가격이 이미 업데이트된 경우
                continue
        else:
            new_doc = {
                "product_id": product_id,
                "shop_sld": shop_sld,
                "shop_id": shop_id,
                "prices": [{"date": current_date, "price": price}]
            }
            await db["bonre_prices"].insert_one(new_doc)

    # 최저가 업데이트
    if price_records:
        cheapest_shop = min(price_records, key=lambda x: int(str(x[1]).replace(",", "")))
        cheapest_price = cheapest_shop[1]
        cheapest_shop_id = cheapest_shop[0]

        await db["bonre_products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$push": {"cheapest": {"date": current_date, "price": cheapest_price, "shop_id": cheapest_shop_id}}}
        )
    return {"message": "Prices updated successfully"}

# front API 수정
@router.post("/update_prices/all", tags=["price CRUD"])
async def update_prices_all():
    # 제품 정보 가져오기
    product_cursor = db["bonre_products"].find({"shop_urls": {"$exists": True, "$ne": []}})
    products = await product_cursor.to_list(length=None)
    if not products:
        raise HTTPException(status_code=404, detail="No products found")

    updated_count = 0
    for product in products:
        product_id = str(product["_id"])
        shops_urls = product.get("shop_urls", [])
        if not shops_urls:
            continue  # Skip this product and move to the next one

        # UTC 시간을 KST로 변환
        current_date = datetime.now(kst).strftime("%Y-%m-%d")
        price_records = []

        for dict in shops_urls:
            url = dict["url"]
            shop_id = dict["shop_id"]
            info = get_all_info(url)

            if not info or info["price"] is None:
                continue

            shop_sld = info["site"]
            price = info["price"]

            existing_price_doc = await db["bonre_prices"].find_one({"product_id": product_id, "shop_sld": shop_sld})
            if existing_price_doc:
                existing_price_date = existing_price_doc["prices"][-1]["date"]
                if existing_price_date != current_date:
                    await db["bonre_prices"].update_one(
                        {"product_id": product_id, "shop_sld": shop_sld},
                        {"$push": {"prices": {"date": current_date, "price": price}}}
                    )
                    updated_count += 1
                    price_records.append((shop_id, price))
            else:
                new_doc = {
                    "product_id": product_id,
                    "shop_sld": shop_sld,
                    "shop_id": shop_id,
                    "prices": [{"date": current_date, "price": price}]
                }
                await db["bonre_prices"].insert_one(new_doc)
                updated_count += 1
                price_records.append((shop_id, price))

        # 최저가 업데이트
        if price_records:
            cheapest_shop = min(price_records, key=lambda x: int(str(x[1]).replace(",", "")))
            cheapest_price = cheapest_shop[1]
            cheapest_shop_id = cheapest_shop[0]

            await db["bonre_products"].update_one(
                {"_id": ObjectId(product_id)},
                {"$push": {"cheapest": {"date": current_date, "price": cheapest_price, "shop_id": cheapest_shop_id}}}
            )

    return {"message": f"Prices updated successfully for {updated_count} products"}
