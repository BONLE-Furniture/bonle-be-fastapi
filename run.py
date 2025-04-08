# from logging import Logger
# import json
import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from dotenv import load_dotenv
from math import ceil
from bson import ObjectId
from database import db
from datetime import datetime, timedelta

from models import *
from price_crwaling import *
from router.user.token import *
from search_result import run_search
from storage import upload_imgFile_to_blob, delete_blob_by_url
from passlib.context import CryptContext
# from redis_connection import redis_client

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt

from pytz import timezone

app = FastAPI()
kst = timezone('Asia/Seoul')
utc = timezone('UTC')
scheduler = AsyncIOScheduler(timezone=utc)

crypt = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")

def verify_password(plain_password, hashed_password):
    return crypt.verify(plain_password, hashed_password)



"""
FAST API 연결, MongoDB 연결 테스트
"""


@app.get("/", tags=["root"])
async def read_root():
    return {"message": "welcome to bonle"}


"""
MVP
"""

#############
### login ###
#############

@app.get("/user/{user_id}", tags=["user CRUD"])
async def get_users(user_id):
    try:
        user = await db["bonre_users"].find_one({"_id": user_id})
        if user:
            return user
    except Exception as e:
        raise HTTPException(status_code=404, detail="User not found")

@app.get("/user/check-user-id/{user_id}", tags=["user CRUD"])
async def check_id(user_id: str):
    user = await db["bonre_users"].find_one({"_id": user_id})
    if user:
        return {"exists": True}
    return {"exists": False}
    
@app.get("/user/check-email/{email}", tags=["user CRUD"])
async def check_email(email: str):
    user = await db["bonre_users"].find_one({"email": email})
    if user:
        return {"exists": True}
    return {"exists": False}

@app.get("/user/check-phone/{phone}", tags=["user CRUD"])
async def check_phone(phone: str):
    user = await db["bonre_users"].find_one({"phone": phone})
    if user:
        return {"exists": True}
    return {"exists": False}
    
@app.post("/user/create-user", tags=["user CRUD"])
async def create_user(user: User, password_validation:str):
    user_dict = user.dict(by_alias=True)

    # 필수 항목 체크        
    required_fields = ["_id", "email", "phone", "password"]
    for field in required_fields:
        if not user_dict.get(field):
            raise HTTPException(status_code=422, detail=f"{field} is required.")

    user_dict["password"] = crypt.hash(user_dict["password"])
    if not verify_password(password_validation, user_dict["password"]):
        raise HTTPException(status_code=404, detail="비밀번호가 일치하지 않습니다.")
    
    try:
        await db["bonre_users"].insert_one(user_dict)
        return {"message": "user created successfully", "user_id": str(user_dict["_id"])}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@app.post("/user/login", tags=["user CRUD"])
async def login_user(login_form: OAuth2PasswordRequestForm = Depends()):
    # 사용자 조회
    user = await db["bonre_users"].find_one({"_id": login_form.username})
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 비밀번호 검증
    if not verify_password(login_form.password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 액세스 토큰 생성
    access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_TIMES",3)))
    access_token = create_access_token(
        data={"sub": user["_id"]},  # 토큰에 저장할 사용자 식별 정보
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["_id"]
    }

async def get_current_user(token: str = Depends(oauth2_scheme)):
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM")
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = await db["bonre_users"].find_one({"_id": username})
    if user is None:
        raise credentials_exception
    return user


@app.post("/user/update-password", tags=["user CRUD"])
async def update_password(password: UserPasswordUpdate, current_user: dict = Depends(get_current_user)):
    """
    비밀번호 변경 API

    input : current_password{str}, new_password{str}
    """
    user = await db["bonre_users"].find_one({"_id": current_user["_id"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 현재 비밀번호 검증
    if not verify_password(password.current_password, user["password"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # 새 비밀번호 해시 처리 후 업데이트
    hashed_new_password = crypt.hash(password.new_password)
    await db["bonre_users"].update_one({"_id": current_user["_id"]}, {"$set": {"password": hashed_new_password}})
    return {"message": "Password updated successfully"}

@app.delete("/user/delete-user", tags=["user CRUD"])
async def delete_user(current_user: dict = Depends(get_current_user)):
    """
    사용자 삭제 API

    input : 없음 (로그인된 사용자 정보로 삭제)
    """
    user = await db["bonre_users"].find_one({"_id": current_user["_id"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 사용자 삭제
    await db["bonre_users"].delete_one({"_id": current_user["_id"]})
    return {"message": "User deleted successfully"}

class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="접근 권한이 없습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

allow_admin = RoleChecker(["admin"])

@app.get("/users/token", tags=["user CRUD"])
async def read_users_token(current_user: dict = Depends(get_current_user)):
    """
    token 존재한다면 사용자 정보를 출력함
    """
    return current_user

#############
### Total ###
#############

@app.get("/product-all", tags=["Detail Page"])
# @app.get("/product-all", tags=["Detail Page"], dependencies=[Depends(allow_admin)])
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

# bonre_brands 컬렉션에 있는 모든 상품 정보를 반환하는 API
@app.get("/product", tags=["product CRUD"])
async def get_all_products():
    collections = await db.list_collection_names()
    if "bonre_products" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")

    items = await db["bonre_products"].find().to_list(1000)
    sanitized_items = sanitize_data(items)
    return sanitized_items


# product 조회 API
@app.get("/product/{product_id}", tags=["product CRUD"])
async def get_product(product_id: str):
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if product:
        sanitized_data = sanitize_data([product])[0]
        return sanitized_data
    raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")


# 판매처 링크 조회 API
@app.get("/product/{product_id}/shop-urls", tags=["product CRUD"])
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
@app.get("/product/{product_id}/cheapest", tags=["product CRUD"])
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
@app.get("/product/{product_id}/cheapest-graph", tags=["product CRUD"])
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


# home 화면에 페이징 처리된 상품 리스트를 반환하는 API
# test : /home/products/?page=3&limit=2
@app.get("/home/products/", tags=["product CRUD"])
async def get_products_list_in_page(page: int = 1, limit: int = 20):
    skip = (page - 1) * limit
    total_count = await db["bonre_products"].count_documents({})

    cursor = db["bonre_products"].find({"upload": True}).sort({"brand":1,"name":1,"subname":1}).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)

    sanitized_items = sanitize_data(items)
    if sanitized_items:
        filtered_items = [
            {
                "_id": str(item["_id"]),  # ObjectId -> str 변환
                "name_kr": item["name_kr"],
                "name": item["name"],
                "subname": item["subname"],
                "subname_kr": item["subname_kr"],
                "brand": item["brand_kr"],
                "main_image_url": item["main_image_url"],
                "bookmark_counts": item["bookmark_counts"],
                "cheapest": item["cheapest"][-1]["price"] if item.get("cheapest") and len(item["cheapest"]) > 0 else None
            }
            for item in sanitized_items
        ]

    return {
        "items": filtered_items,
        "item-total-number": total_count,
        "selected-item-number": len(filtered_items),
        "page": page,
        "limit": limit,
        "total_pages": ceil(total_count / limit)
    }

@app.post("/product/create-product", tags=["product CRUD"])
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

@app.post("/product/upload-image/{product_id}", tags=["product CRUD"])
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
        
        if auto_set_name:
            name, ext = os.path.splitext(original_filename)
            img_name = f"product/{product_item['brand']}/{name}_{product_item['subname']}{ext}"
        else:
            img_name = f"product/{product_item['brand']}/{original_filename}"

        img_url = upload_imgFile_to_blob(img_storage_name, img_content, img_name)

        # 기존 이미지 삭제
        if product_item.get("main_image_url"):
            delete_blob_by_url(img_storage_name, product_item["main_image_url"])
            
        # 데이터베이스 업데이트
        await db["bonre_products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"main_image_url": img_url}}
        )

        return {"message": "Image uploaded successfully", "image_url": img_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")
    
# 북마크 수 업데이트 API
@app.post("/product/{product_id}/bookmark", tags=["product CRUD"])
async def add_bookmark(product_id: str):
    """
    특정 상품의 bookmark_counts를 1 증가시키는 엔드포인트.

    param product_id: 제품 ID
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


@app.patch("/product/update-product/{product_id}", tags=["product CRUD"])
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
@app.delete("/product/delete-product/{product_id}", tags=["product CRUD"])
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


#############
## brand ####
#############

@app.get("/brand", tags=["brand CRUD"])
async def get_all_brands():
    """
    bonre_brands 컬렉션에 있는 모든 브랜드 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_brands" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_brands"].find().to_list(1000)
    sanitized_items = sanitize_data(items)
    return sanitized_items


# brand_id를 받아서 해당 브랜드 정보를 반환하는 API
# test : /brands/get_bonre_brand_by_id/brand_andtrandition
@app.get("/brand/{brand_id}", tags=["brand CRUD"])
async def get_brand_info_by_brand_id(brand_id: str):
    """
    brand_id를 받아서 해당 브랜드 정보를 반환하는 API

    input : brand_id {str} ex) brand_andtrandition

    output : brand info {all fields}
    """
    item = await db["bonre_brands"].find_one({"_id": brand_id})
    if item is not None:
        return item
    raise HTTPException(status_code=404, detail="Item not found")


# brand_id를 받아서 해당 브랜드의 상품 정보를 반환하는 API
# test : http://127.0.0.1:8000/brands/get_bonre_products_by_brandId/brand_andtrandition
@app.get('/brand/{brand_id}/products', tags=["brand CRUD"])
async def get_products_info_by_brand_id(brand_id: str):
    """
    brand_id를 받아서 해당 브랜드의 상품 정보를 반환하는 API

    input : brand_id {str} ex) brand_andtrandition

    output : product list of brand_id {_id, name_kr, name, brand, main_image_url, cheapest}
    """
    items = await db["bonre_products"].find({"brand": brand_id,"upload": True}).sort({"name":1,"subname":1}).to_list(10)
    if items:
        filtered_items = [
            {
                "_id": str(item["_id"]),
                "name_kr": item["name_kr"],
                "name": item["name"],
                "brand": item["brand"],
                "main_image_url": item["main_image_url"],
                "cheapest": str(
                    item["cheapest"][-1]["price"] if item.get("cheapest") and len(item["cheapest"]) > 0 else None)
            }
            for item in items
        ]
        return filtered_items
    raise HTTPException(status_code=404, detail="Items not found")

# brand 생성 API
@app.post("/brand/create-brand", tags=["brand CRUD"])
async def create_brand(brand: Brand):
    brand_dict = brand.dict(by_alias=True)
    try:
        await db["bonre_brands"].insert_one(brand_dict)
        return brand_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# brand 수정 API
@app.patch("/brand/update-brand/{brand_id}", tags=["brand CRUD"])
async def update_brand(brand_id: str, brand: BrandUpdate):
    brand_item = await db["bonre_brands"].find_one({"_id": brand_id})
    if brand_item:
        pass
    else:
        raise HTTPException(status_code=404, detail="Brand not found")

    try:
        update_data = {k: v for k, v in brand.dict(exclude_unset=True).items() if v is not None}
        await db["bonre_brands"].update_one(
            {"_id": brand_id},
            {"$set": update_data}
        )
        return {"message": "Brand updated successfully"}
    except Exception as e:
        return {"message": "No fields to update"}


# brand 삭제 API
@app.delete("/brand/delete-brand/{brand_id}", tags=["brand CRUD"])
async def delete_brand(brand_id: str):
    result = await db["bonre_brands"].delete_one({"_id": brand_id})
    if result.deleted_count == 1:
        return {"message": "Brand deleted successfully"}
    raise HTTPException(status_code=404, detail="Brand not found")


############
## price ###
############

# 특정 shop & product의 날짜별 price 조회 API
@app.get("/price/{product_id}/{shop_sld}/", tags=["price CRUD"])
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
@app.get("/price/{product_id}/", tags=["price CRUD"])
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


@app.post("/update_prices/one", tags=["price CRUD"])
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
            await db["bonre_prices"].update_one(
                {"product_id": product_id, "shop_sld": shop_sld},
                {"$push": {"prices": {"date": current_date, "price": price}}}
            )
        else:
            new_doc = {
                "product_id": product_id,
                "shop_sld": shop_sld,
                "prices": [{"date": current_date, "price": price}]
            }
            await db["bonre_prices"].insert_one(new_doc)

    # 최저가 업데이트
    if price_records:
        cheapest_shop = min(price_records, key=lambda x: x[1])
        cheapest_price = cheapest_shop[1]
        cheapest_shop_id = cheapest_shop[0]

        await db["bonre_products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$push": {"cheapest": {"date": current_date, "price": cheapest_price, "shop_id": cheapest_shop_id}}}
        )
    return {"message": "Prices updated successfully"}

# 수정
@app.post("/update_prices/all", tags=["price CRUD"])
async def update_prices_all():
    # 제품 정보 가져오기
    product_cursor = db["bonre_products"].find({"upload": True})
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
            else:
                new_doc = {
                    "product_id": product_id,
                    "shop_sld": shop_sld,
                    "shop_id": shop_id,
                    "prices": [{"date": current_date, "price": price}]
                }
                await db["bonre_prices"].insert_one(new_doc)
                updated_count += 1

        # 최저가 업데이트
        if price_records:
            cheapest_shop = min(price_records, key=lambda x: x[1])
            cheapest_price = cheapest_shop[1]
            cheapest_shop_id = cheapest_shop[0]

            await db["bonre_products"].update_one(
                {"_id": ObjectId(product_id)},
                {"$push": {"cheapest": {"date": current_date, "price": cheapest_price, "shop_id": cheapest_shop_id}}}
            )

    return {"message": f"Prices updated successfully for {updated_count} products"}


##########
## shop ##
##########
@app.get("/shop", tags=["shop CRUD"])
async def get_all_shops():
    """
    bonre_shops 컬렉션에 있는 모든 샵 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_shops" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_shops"].find().to_list(1000)
    return items


# brand_id를 받아서 해당 브랜드 정보를 반환하는 API
# test : /brands/get_bonre_brand_by_id/brand_andtrandition
@app.get("/shop/{shop_id}", tags=["shop CRUD"])
async def get_shop_info_by_shop_id(shop_id: str):
    """
    shop_id를 받아서 해당 샵 정보를 반환하는 API

    input : shop_id {str} ex) shop_andtrandition

    output : shop info {all fields}
    """
    item = await db["bonre_shops"].find_one({"_id": shop_id})
    if item is not None:
        return item
    raise HTTPException(status_code=404, detail="Item not found")


# shop 생성 API
@app.post("/shop/create-shop", tags=["shop CRUD"])
async def create_shop(shop: Shop):
    shop_dict = shop.dict(by_alias=True)
    try:
        await db["bonre_shops"].insert_one(shop_dict)
        return shop_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# shop 수정 API
@app.patch("/shop/update-shop/{shop_id}", tags=["shop CRUD"])
async def update_shop(shop_id: str, shop: ShopUpdate):
    shop_item = await db["bonre_shops"].find_one({"_id": shop_id})
    if shop_item:
        pass
    else:
        raise HTTPException(status_code=404, detail="Shop not found")

    try:
        update_data = {k: v for k, v in shop.dict(exclude_unset=True).items() if v is not None}
        await db["bonre_shops"].update_one(
            {"_id": shop_id},
            {"$set": update_data}
        )
        return {"message": "Shop updated successfully"}
    except Exception as e:
        return {"message": "No fields to update"}


# shop 삭제 API
@app.delete("/shop/delete-shop/{shop_id}", tags=["shop CRUD"])
async def delete_shop(shop_id: str):
    result = await db["bonre_shops"].delete_one({"_id": shop_id})
    if result.deleted_count == 1:
        return {"message": "Shop deleted successfully"}
    raise HTTPException(status_code=404, detail="Shop not found")


############
# designer #
############

@app.get("/designer", tags=["designer CRUD"])
async def get_all_designers():
    """
    bonre_designers 컬렉션에 있는 모든 디자이너 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_designers" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_designers"].find().to_list(1000)
    return items


@app.get("/designer/{designer_id}", tags=["designer CRUD"])
async def get_designer_info_by_designer_id(designer_id: str):
    """
    designer_id를 받아서 해당 디자이너 정보를 반환하는 API

    input : designer_id {str} ex) designer_hd

    output : designer info {all fields}
    """
    item = await db["bonre_designers"].find_one({"_id": designer_id})
    if item is not None:
        return item
    raise HTTPException(status_code=404, detail="Item not found")


# designer 생성 API
@app.post("/designer/create-designer", tags=["designer CRUD"])
async def create_desginer(designer: Designer):
    designer_dict = designer.dict(by_alias=True)
    try:
        await db["bonre_designers"].insert_one(designer_dict)
        return designer_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# designer 수정 API
@app.patch("/designer/update-designer/{designer_id}", tags=["designer CRUD"])
async def update_designer(designer_id: str, designer: DesignerUpdate):
    designer_item = await db["bonre_designers"].find_one({"_id": designer_id})
    if designer_item:
        pass
    else:
        raise HTTPException(status_code=404, detail="Designer not found")

    try:
        update_data = {k: v for k, v in designer.dict(exclude_unset=True).items() if v is not None}
        await db["bonre_designers"].update_one(
            {"_id": designer_id},
            {"$set": update_data}
        )
        return {"message": "Designer updated successfully"}
    except Exception as e:
        return {"message": "No fields to update"}


# designer 삭제 API
@app.delete("/designer/delete-designer/{designer_id}", tags=["designer CRUD"])
async def delete_designer(designer_id: str):
    result = await db["bonre_designers"].delete_one({"_id": designer_id})
    if result.deleted_count == 1:
        return {"message": "Designer deleted successfully"}
    raise HTTPException(status_code=404, detail="Designer not found")


############
## Filter ##
############

@app.get("/filter", tags=["filter CRUD"])
async def get_all_filters():
    """
    bonre_filters 컬렉션에 있는 모든 필터 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_filters" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_filters"].find().to_list(1000)
    return items

@app.get("/filter/{filter_id}", tags=["filter CRUD"])
async def get_filter_info_by_filter_id(filter_id: str):
    """
    filter_id를 받아서 해당 필터 정보를 반환하는 API

    input : filter_id {str} ex) filter_hd

    output : filter info {all fields}
    """
    item = await db["bonre_filters"].find_one({"_id": filter_id})
    if item is not None:
        return item
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/filter/create-filter", tags=["filter CRUD"])
async def create_filter(filter: Filter):
    filter_dict = filter.dict(by_alias=True)
    try:
        await db["bonre_filters"].insert_one(filter_dict)
        return {"message":"success bonre_filter create", "filter" : filter_dict}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.patch("/filter/update-filter/{filter_id}", tags=["filter CRUD"])
async def update_filter(filter_id: str, filterUpdate: FilterUpdate):
    """
    변경되는 필드만 업데이트
    
    * list 수정이라면, 기존 내용도 list에 포함하여 전송. not push but set
    """
    filter_item = await db["bonre_filters"].find_one({"_id": filter_id})
    if filter_item:
        pass
    else:
        raise HTTPException(status_code=404, detail="Filter not found")

    try:
        update_data = {k: v for k, v in filterUpdate.dict(exclude_unset=True).items() if v is not None}
        
        # id 필드는 업데이트하지 않음
        if "_id" in update_data:
            del update_data["_id"]
        
        if update_data:
            await db["bonre_filters"].update_one(
                {"_id": filter_id},
                {"$set": update_data}
            )
            return {"message": "Filter updated successfully"}
        else:
            return {"message": "No fields to update"}
    except Exception as e:
        return {"message": "Error updating filter"}
    
@app.delete("/filter/delete-filter/{filter_id}", tags=["filter CRUD"])
async def delete_filter(filter_id: str):
    try:
        result = await db["bonre_filters"].delete_one({"_id": filter_id})
        if result.deleted_count == 1:
            return {"message": "filter deleted successfully"}
        raise HTTPException(status_code=404, detail="filter not found")    
    except Exception as e:
        return {"message": "Error deleting filter"}
############
# Category #
############

@app.get("/category", tags=["category CRUD"])
async def get_all_categories():
    """
    bonre_categories 컬렉션에 있는 모든 필터 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_categories" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_categories"].find().to_list(1000)
    return items

@app.get("/category/{category_id}", tags=["category CRUD"])
async def get_category_info_by_category_id(category_id: str):
    """
    category_id를 받아서 해당 카테고리 정보를 반환하는 API

    input : category_id {str} ex) category_hd

    output : category info {all fields}
    """
    item = await db["bonre_categories"].find_one({"_id": category_id})
    if item is not None:
        return item
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/category/create-category", tags=["category CRUD"])
async def create_category(category: Category):
    category_dict = category.dict(by_alias=True)
    try:
        await db["bonre_categories"].insert_one(category_dict)
        return {"message":"success bonre_category create", "category" : category_dict}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.patch("/category/update-category/{category_id}", tags=["category CRUD"])
async def update_category(category_id: str, category: CategoryUpdate):
    """
    변경되는 필드만 업데이트
    
    * list 수정이라면, 기존 내용도 list에 포함하여 전송. not push but set
    """
    category_item = await db["bonre_categories"].find_one({"_id": category_id})
    if category_item:
        pass
    else:
        raise HTTPException(status_code=404, detail="Category not found")
    
    try:
        update_data = {k: v for k, v in category.dict(exclude_unset=True).items() if v is not None}
        
        # id 필드는 업데이트하지 않음
        if "_id" in update_data:
            del update_data["_id"]
        
        if update_data:
            await db["bonre_categories"].update_one(
                {"_id": category_id},
                {"$set": update_data}
            )
            return {"message": "Category updated successfully"}
        else:
            return {"message": "No categories to update"}
    except Exception as e:
        return {"message": "Error updating filter"}
            
            
@app.delete("/category/delete-category/{category_id}", tags=["category CRUD"])
async def delete_category(category_id: str):
    try:
        result = await db["bonre_categories"].delete_one({"_id": category_id})
        if result.deleted_count == 1:
            return {"message": "Category deleted successfully"}
        raise HTTPException(status_code=404, detail="Category not found")
    except Exception as e:
        # 예외 처리
        return {"message": "Error deleting category"}

"""
스케줄링
"""
import logging

# 로깅 설정을 더 자세하게 수정
logging.basicConfig(
    level=logging.INFO,  # 기본 로깅 레벨을 INFO로 변경
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# pymongo의 로깅 레벨을 INFO로 설정
logging.getLogger('pymongo').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

async def run_update_prices_all():
    logger.info("Starting scheduled price update task")
    current_time_utc = datetime.now(utc)
    logger.info(f"Current time in UTC: {current_time_utc}")
    
    try:
        result = await update_prices_all()
        logger.info(f"Scheduled task completed: {result}")
    except Exception as e:
        logger.error(f"Error in scheduled task: {e}", exc_info=True)

# 스케줄링된 작업 정의
@app.on_event("startup")
def schedule_price_updates():
    try:
        logger.info("Initializing scheduler...")
        logger.info(f"Current time in UTC: {datetime.now(timezone('UTC'))}")
                
        try:
            scheduler.add_job(
                run_update_prices_all, 
                CronTrigger(hour=15, minute=20, timezone=utc),
                id='price_update_job',
                name='Update all prices',
                replace_existing=True
            )
            logger.info("Added new job successfully")
        except Exception as e:
            logger.error(f"Failed to add new job: {e}", exc_info=True)
        
        scheduler.start()
        logger.info("Scheduler started successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}", exc_info=True)
        
# 스케줄러 상태 확인을 위한 엔드포인트 추가
@app.get("/scheduler/status", tags=["scheduler"])
async def get_scheduler_status():
    jobs = scheduler.get_jobs()
    return {
        "scheduler_running": scheduler.running,
        "total_jobs": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in jobs
        ]
    }
        

# 애플리케이션 종료 시 스케줄러 종료
@app.on_event("shutdown")
def shutdown_scheduler():
    try:
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}", exc_info=True)

@app.get("/admin-search")
def search(keyword: str = Query("놀", description="검색어"), number: int = Query(2, description="사이트당 결과 수")):
    result = run_search(keyword, number)
    return {"results": result}
