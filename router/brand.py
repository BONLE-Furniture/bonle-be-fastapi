import os

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from db.database import db
from db.models import Brand, BrandUpdate, sanitize_data
from db.storage import upload_imgFile_to_blob, delete_blob_by_url

from router.user.token import allow_admin

router = APIRouter(
    prefix="/brand",
    tags=["brand CRUD"]
)


@router.get("")
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
@router.get("/{brand_id}")
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
@router.get('/{brand_id}/products')
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
@router.post("/create-brand", dependencies=[Depends(allow_admin)])
async def create_brand(brand: Brand):
    brand_dict = brand.dict(by_alias=True)
    try:
        await db["bonre_brands"].insert_one(brand_dict)
        return {"message": "create successfully", "brand_id": brand_dict.get("_id")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-image/{brand_id}", dependencies=[Depends(allow_admin)])
async def upload_brand_image(
    brand_id: str,
    image: UploadFile = File(...),
    auto_set_name: bool = Form(False)
):
    """
    auto_set_name : True일 경우 로직에 의해 이름이 자동 처리되어 storage 저장됌. False일 경우 파일명 그대로 storage에 저장.
    
    ## 주의

    ### brand_image_url : json과 다른 방식으로 upload를 해야해서, 임의로 이미지 업로드 API를 분리했음. /brand logos/{shop_id}.ext로 업로드, 업데이트 수행
    """
    try:
        brand_item = await db["bonre_brands"].find_one({"_id": brand_id})
        if not brand_item:
            raise HTTPException(status_code=404, detail="brand not found")

        img_storage_name = os.getenv("img_blob_name")
        img_content = await image.read()
        original_filename = image.filename
        
        if auto_set_name:
            _, ext = os.path.splitext(original_filename)
            img_name = f"brand_logos/{brand_item['brand']}{ext}"
        else:
            img_name = f"brand_logos/{original_filename}"

        # 기존 이미지 삭제
        if brand_item.get("brand_image_url"):
            delete_blob_by_url(img_storage_name, brand_item["brand_image_url"])

        img_url = upload_imgFile_to_blob(img_storage_name, img_content, img_name)
            
        # 데이터베이스 업데이트
        await db["bonre_brands"].update_one(
            {"_id": brand_id},
            {"$set": {"brand_image_url": img_url}}
        )
        return {"message": "Image uploaded successfully", "image_url": img_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")

# brand 수정 API
@router.patch("/update-brand/{brand_id}", dependencies=[Depends(allow_admin)])
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
@router.delete("/delete-brand/{brand_id}", dependencies=[Depends(allow_admin)])
async def delete_brand(brand_id: str):
    brand_item = await db["bonre_brands"].find_one({"_id": brand_id})
    if brand_item and brand_item.get("brand_image_url"):
        try:
            img_storage_name = os.getenv("img_blob_name")
            delete_blob_by_url(img_storage_name, brand_item["brand_image_url"])
        except Exception as e:
            return {"message": f"Error deleting image: {str(e)}"}
        
    result = await db["bonre_brands"].delete_one({"_id": brand_id})
    if result.deleted_count == 1:
        return {"message": "Brand deleted successfully"}
    raise HTTPException(status_code=404, detail="Brand not found")
