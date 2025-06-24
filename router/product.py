import os
from math import ceil
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, FastAPI

from db.database import db
from db.models import Product, ProductUpdate, Product_Period, sanitize_data

from db.storage import delete_blob_by_url, upload_imgFile_to_blob
from router.user.token import allow_admin
from utils.product_search import search_products

router = APIRouter(
    prefix="/product",
    tags=["product CRUD"]
)

router_total = APIRouter(
    prefix="/product-all",
    tags=["Detail Page"]
)

#############
### Total ###
#############

@router_total.get("")
async def get_total(product_id: str):
    """
    product_id, designer_id, brand_id, shop_id를 받아서 해당 정보를 반환하는 API

    input : product_id{str}, designer_id{str}, brand_id{str}, shop_id{str}

    output : product, designer, brand, shop info
    """
## redis 주석처리
    # cached_data = redis_client.get(f"product_{product_id}")
    #
    # if cached_data:
    #     cached_data = json.loads(cached_data)
    #     return {"cached": True, "data": cached_data}


    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if product:
        product = sanitize_data([product])[0]
    designer = await db["bonre_designers"].find_one({"_id": product['designer'][0]}) if product['designer'] else None
    if not designer:
        designer = None
    brand = await db["bonre_brands"].find_one({"_id": product['brand']}) if product['brand'] else None
    if not brand:
        brand = None
    products = await db["bonre_products"].find({"brand": product['brand'],"upload": True}).sort({"name":1,"subname":1}).to_list(10) if product['brand'] else None
    prices = await db["bonre_prices"].find({"product_id": product_id}).to_list(1000) if product['brand'] else None
    if products:
        filtered_products = [
            {
                "_id": str(item["_id"]),
                "name_kr": item["name_kr"],
                "name": item["name"],
                "subname": item["subname"],
                "subname_kr": item["subname_kr"],
                "brand": item["brand"],
                "main_image_url": item["main_image_url"],
                "cheapest": str(
                    item["cheapest"][-1]["price"] if item.get("cheapest") and len(item["cheapest"]) > 0 else None)
            }
            for item in products
        ]
    else:
        products = None
        
    if prices:
        filtered_prices = [
            {
                "_id": str(item["_id"]),
                "product_id": item["product_id"],
                "shop_sld": item["shop_sld"],
                "shop_id": item["shop_id"],
                "price": item["prices"][-1]["price"] if item.get("prices") and len(item["prices"]) > 0 else None
            }
            for item in prices
        ]   
    else:
        prices = None

## redis 주석처리
    # redis_client.setex(f"product_{product_id}", 3600, json.dumps({
    #     "product": product,
    #     "designer": designer,
    #     "brand": brand,
    #     "brand_products": filtered_products,
    #     "prices": filtered_prices
    # }))

    return {"product": product, "designer": designer, "brand": brand, "brand_products": filtered_products, "prices": filtered_prices}
        
        
#############
## product ##
#############

# bonre_products 컬렉션에 있는 모든 상품 정보를 반환하는 API
@router.get("")
async def get_all_products():
    collections = await db.list_collection_names()
    if "bonre_products" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")

    items = await db["bonre_products"].find().to_list(1000)
    sanitized_items = sanitize_data(items)
    return sanitized_items

@router.get("/home")
async def get_products_list_in_page(
    page: int = 1,
    limit: int = 20,
    category_id: Optional[str] = Query(None, description="카테고리 ID"),
    query: Optional[str] = Query(None, description="검색어")
):
    return await search_products(page, limit, category_id, query)

@router.get("/duplicate-check")
async def check_product_duplicate(product_name: str = Query(..., description="제품명"), product_sub_name: str = Query(None, description="제품 서브네임")):
    """
    제품명과 서브네임으로 중복 검사를 수행하는 API
    
    Args:
        product_name (str): 제품명
        product_sub_name (str, optional): 제품 서브네임
        
    Returns:
        dict: 중복 여부와 중복된 제품 정보
    """
    # 검색 조건 구성
    query = {
        "name_kr": product_name,
        "upload": True
    }
    
    # 서브네임이 제공된 경우에만 조건에 추가
    if product_sub_name:
        query["subname_kr"] = product_sub_name
    
    # DB에서 제품 검색
    products = await db["bonre_products"].find(query).to_list(1000)
    
    if products:
        formatted_products = []
        for product in products:
            formatted_product = {
                "name_kr": product["name_kr"],
                "subname_kr": product.get("subname_kr"),
            }
            formatted_products.append(formatted_product)
        
        return {
            "is_duplicate": True,
            "products": formatted_products
        }
    else:
        return {
            "is_duplicate": False,
            "products": []
        }

# product 조회 API
@router.get("/{product_id}")
async def get_product(product_id: str):
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if product:
        sanitized_data = sanitize_data([product])[0]
        return sanitized_data
    raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")


# 판매처 링크 조회 API
@router.get("/{product_id}/shop-urls")
async def get_shop_urls(product_id: str):
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    shop_urls = product.get("shop_urls", [])
    if not shop_urls:
        raise HTTPException(status_code=404, detail="No shop URLs found for this product")

    # 반환할 데이터 정리
    result_data = [{"shop_id": shop["shop_id"], "url": shop["url"]} for shop in shop_urls]
    
    return result_data


# 제품 내 가장 최근 최저가 정보 조회 API
@router.get("/{product_id}/cheapest")
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
@router.get("/{product_id}/cheapest-graph")
async def get_cheapest_prices(product_id: str, period: Product_Period):
    """
    기간별 최저가 데이터를 반환하는 엔드포인트.

    param product_id: 제품 ID

    param period: 선택된 기간 (1주일, 1달, 1년, 전체)
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
    if period == Product_Period.one_week:
        start_date = now - timedelta(weeks=1)
    elif period == Product_Period.one_month:
        start_date = now - timedelta(days=30)
    elif period == Product_Period.one_year:
        start_date = now - timedelta(days=365)
    elif period == Product_Period.all_time:
        start_date = None  # 전체 데이터는 필터링하지 않음

    # 기간 내 데이터 필터링
    filtered_data = []
    for entry in cheapest:
        # 날짜 데이터 datetime으로 맞춰주기
        try:
            if not isinstance(entry["date"], datetime):
                entry_date = datetime.fromisoformat(entry["date"])
            else:
                entry_date = entry["date"]
        except (ValueError, TypeError):
            continue

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


@router.post("/create-product", dependencies=[Depends(allow_admin)])
async def create_product(product: Product):
    """
    product 생성 API

    input : 

    필수 (type str & int)
    name_kr, name, subname, subname_kr, brand ,color, brand_kr 

    주의 

    size: Product_Size {width,height,depth,length}

    shop_urls: List[Product_ShopUrl]  {shop_id, url, priceCC(price crawling care)} # 만약 priceCC가 True이면 크롤링 과정에서 추가 처리 필요. 

    선택 (type str & int)

    designer, description, material, filter, category, bookmark_counts

    ## 주의

    ### main_image_url : json과 다른 방식으로 upload를 해야해서, 임의로 이미지 업로드 API를 분리했음. /product/upload-image/{product_id}로 업로드, 업데이트 수행

    cheapest: List[Product_Cheapest]

    upload : bool = False # true일 때, 홈 화면에 출력
    """

    product_item = product.dict(by_alias=True)
    # img을 파일로 받아서 azure blob에 저장 -> 저장된 url 반환
    try:
        result = await db["bonre_products"].insert_one(product_item)
        return {"message": "Product created successfully",
            "product_id": str(result.inserted_id)
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload-image/{product_id}", dependencies=[Depends(allow_admin)])
async def upload_product_image(
    product_id: str,
    image: UploadFile = File(...),
    auto_set_name: bool = Form(True)
):
    """
    auto_set_name : True일 경우 로직에 의해 이름이 자동 처리되어 storage 저장됌. False일 경우 파일명 그대로 storage에 저장.
    
    ## 주의

    ### main_image_url : json과 다른 방식으로 upload를 해야해서, 임의로 이미지 업로드 API를 분리했음. /product/upload-image/{product_id}로 업로드, 업데이트 수행
    """
    try:
        product_item = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
        if not product_item:
            raise HTTPException(status_code=404, detail="Product not found")

        img_storage_name = os.getenv("img_blob_name")
        img_content = await image.read()
        original_filename = image.filename
        
        name, ext = os.path.splitext(original_filename)
        if auto_set_name:
            product_name = product_item["name"].replace(" ", "_")
            product_subname = product_item["subname"].replace(" ", "_") if product_item["subname"] else ""
            img_name = f"product/{product_item['brand']}/{product_name}_{product_subname}{ext}"
        else:
            img_name = f"product/{product_item['brand']}/{name}_{product_item['subname']}{ext}"

        # 기존 이미지 삭제
        if product_item.get("main_image_url"):
            delete_blob_by_url(img_storage_name, product_item["main_image_url"])
        
        img_url = upload_imgFile_to_blob(img_storage_name, img_content, img_name)
            
        # 데이터베이스 업데이트
        await db["bonre_products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"main_image_url": img_url}}
        )

        return {"message": "Image uploaded successfully", "image_url": img_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")
    

@router.patch("/update-product/{product_id}", dependencies=[Depends(allow_admin)])
async def update_product(product_id: str, productUpdate: ProductUpdate):
    """
    input : product_id{object_id}, 수정할 필드 정보 key : value 형식으로 request body에 입력

    ex)
    -d '{"name_kr": "string", "name": "string"}

    # 사진 x. 사진은 /product/upload-image/{product_id}에서 처리 
    """

    try:
        product_item = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    except Exception as e:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        update_data = {k: v for k, v in productUpdate.dict(exclude_unset=True).items() if v is not None}
        await db["bonre_products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )
        return {"message": f"Product updated successfully. {update_data}"}
    except Exception as e:
        return {"message": "No fields to update"}



# product 삭제 API
@router.delete("/delete-product/{product_id}", dependencies=[Depends(allow_admin)])
async def delete_product(product_id: str):
    product_item = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    # 기존 이미지 삭제
    if product_item and product_item.get("main_image_url"):
        try:
            img_storage_name = os.getenv("img_blob_name")
            delete_blob_by_url(img_storage_name, product_item["main_image_url"])
        except Exception as e:
            return {"message": f"Error deleting image: {str(e)}"}
    result = await db["bonre_products"].delete_one({"_id": ObjectId(product_id)})
    if result.deleted_count == 1:
        return {"message": "Product deleted successfully"}
    raise HTTPException(status_code=404, detail="Product not found")
