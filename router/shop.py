import os
import re

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, FastAPI, Query

from db.database import db
from db.models import Shop, ShopUpdate

from db.storage import delete_blob_by_url, upload_imgFile_to_blob
from router.crawling.shop_search.search_result import run_search
from router.user.token import allow_admin

app=FastAPI()
router = APIRouter(
    prefix="/shop",
    tags=["shop CRUD"]
)

@router.get("/shop")
async def get_all_shops():
    """
    bonre_shops 컬렉션에 있는 모든 샵 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_shops" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_shops"].find().to_list(1000)
    return items

##############
## Crawling ##
##############

@router.get("/admin-search", dependencies=[Depends(allow_admin)])
async def search(keyword: str = Query("놀", description="검색어"), number: int = Query(2, description="사이트당 결과 수")):
    # 1. 여러 사이트에서 검색 결과 가져오기
    search_results = run_search(keyword, number)
    
    # 2. DB에서 모든 제품의 shop_urls 가져오기
    products = await db["bonre_products"].find({
        "$or": [
            {"name_kr": {"$regex": keyword, "$options": "i"}},
            {"name_kr": {"$regex": ".*" + keyword + ".*", "$options": "i"}}
        ],
        "upload": True
    }).to_list(1000)
    
    # 3. DB에 있는 URL 목록 생성
    existing_urls = set()
    for product in products:
        if "shop_urls" in product:
            for shop_url in product["shop_urls"]:
                if shop_url.get("url"):
                    existing_urls.add(shop_url["url"])
    # 4. 검색 결과 처리
    processed_results = []
    for result in search_results:
        product_url = result.get("product_url", "")
        # URL 직접 비교
        already_exist = product_url in existing_urls if product_url else False
        
        # 결과 데이터 구성
        processed_result = {
            "image_url": result.get("image_url"),
            "product_url": result.get("product_url"),
            "name": result.get("name"),
            "price": result.get("price"),
            "brand": result.get("brand"),
            "site": process_site_name(result.get("site", "")),
            "already_exist": already_exist
        }
        processed_results.append(processed_result)
    
    return {"results": processed_results}

def process_site_name(site: str) -> str:
    """
    site 이름을 처리하는 함수
    1. 숫자를 영어로 변환
    2. 특수문자 제거
    3. 대문자를 소문자로 변환
    """
    # 숫자를 영어로 변환
    number_map = {
        '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
        '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
    }
    
    # 숫자를 영어로 변환
    for num, word in number_map.items():
        site = site.replace(num, word)
    
    # 특수문자 제거
    site = re.sub(r'[^a-zA-Z0-9]', '', site)
    
    # 대문자를 소문자로 변환
    site = site.lower()
    
    return f"shop_{site}"

# brand_id를 받아서 해당 브랜드 정보를 반환하는 API
# test : /brands/get_bonre_brand_by_id/brand_andtrandition
@router.get("/shop/{shop_id}")
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
@router.post("/shop/create-shop", dependencies=[Depends(allow_admin)])
async def create_shop(shop: Shop):
    shop_dict = shop.dict(by_alias=True)
    try:
        await db["bonre_shops"].insert_one(shop_dict)
        return {"message": "create successfully", "shop_id": shop_dict.get("_id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/shop/upload-image/{shop_id}", dependencies=[Depends(allow_admin)])
async def upload_shop_image(
    shop_id: str,
    image: UploadFile = File(...),
    auto_set_name: bool = Form(False)
):
    """
    auto_set_name : True일 경우 로직에 의해 이름이 자동 처리되어 storage 저장됌. False일 경우 파일명 그대로 storage에 저장.
    
    ## 주의

    ### shop_image_url : json과 다른 방식으로 upload를 해야해서, 임의로 이미지 업로드 API를 분리했음. /shop_logos/{shop_id}.ext로 업로드, 업데이트 수행
    """
    try:
        shop_item = await db["bonre_shops"].find_one({"_id": shop_id})
        if not shop_item:
            raise HTTPException(status_code=404, detail="shop not found")

        img_storage_name = os.getenv("img_blob_name")
        img_content = await image.read()
        original_filename = image.filename
        
        if auto_set_name:
            _, ext = os.path.splitext(original_filename)
            img_name = f"shop_logos/{shop_item['shop']}{ext}"
        else:
            img_name = f"shop_logos/{original_filename}"

        # 기존 이미지 삭제
        if shop_item.get("shop_image_url"):
            delete_blob_by_url(img_storage_name, shop_item["shop_image_url"])

        img_url = upload_imgFile_to_blob(img_storage_name, img_content, img_name)
                    
        # 데이터베이스 업데이트
        await db["bonre_shops"].update_one(
            {"_id": shop_id},
            {"$set": {"shop_image_url": img_url}}
        )

        return {"message": "Image uploaded successfully", "image_url": img_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

# shop 수정 API
@router.patch("/shop/update-shop/{shop_id}", dependencies=[Depends(allow_admin)])
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
@router.delete("/shop/delete-shop/{shop_id}", dependencies=[Depends(allow_admin)])
async def delete_shop(shop_id: str):
    shop_item = await db["bonre_shops"].find_one({"_id": shop_id})
    if shop_item and shop_item.get("shop_image_url"):
        try:
            img_storage_name = os.getenv("img_blob_name")
            delete_blob_by_url(img_storage_name, shop_item["shop_image_url"])
        except Exception as e:
            return {"message": f"Error deleting image: {str(e)}"}
        
    result = await db["bonre_shops"].delete_one({"_id": shop_id})
    if result.deleted_count == 1:
        return {"message": "Shop deleted successfully"}
    raise HTTPException(status_code=404, detail="Shop not found")
