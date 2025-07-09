from fastapi import APIRouter, HTTPException, Depends
from db.database import db
from db.models import Bookmark, sanitize_data, Product
from typing import List
from datetime import datetime
from router.user.token import allow_admin, get_current_user
from bson import ObjectId

router = APIRouter(
    prefix="/bookmarks",
    tags=["bookmark CRUD"]
)

# 북마크 생성 (body 없이 product_id만 path param으로 받음)
@router.post("/create-bookmark/{product_id}", response_model=Bookmark)
async def create_bookmark(product_id: str, current_user: dict = Depends(get_current_user)):
    email = current_user["email"]
    # 이미 북마크했는지 확인
    exist = await db["bonre_bookmarks"].find_one({"email": email, "product_id": product_id})
    if exist:
        raise HTTPException(status_code=400, detail="이미 북마크한 상품입니다.")
    
    # bonre_products의 bookmark_counts +1
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    current_count = product.get("bookmark_counts", 0)
    await db["bonre_products"].update_one({"_id": ObjectId(product_id)}, {"$set": {"bookmark_counts": current_count + 1}})
    
    # 북마크 생성
    data = {
        "_id": ObjectId(),
        "email": email,
        "product_id": product_id,
        "created_at": datetime.utcnow()
    }
    await db["bonre_bookmarks"].insert_one(data)
    return Bookmark.from_mongo(data)

# 북마크 전체 조회 (admin만)
@router.get("/", response_model=List[Bookmark], dependencies=[Depends(allow_admin)])
async def get_all_bookmarks():
    bookmarks = await db["bonre_bookmarks"].find().to_list(1000)
    return [Bookmark.from_mongo(b) for b in bookmarks]

# 내 북마크 조회
@router.get("/me", response_model=List[Bookmark])
async def get_my_bookmarks(current_user: dict = Depends(get_current_user)):
    email = current_user["email"]
    bookmarks = await db["bonre_bookmarks"].find({"email": email}).to_list(1000)
    return [Bookmark.from_mongo(b) for b in bookmarks]

# 내 북마크의 상품 정보 조회
@router.get("/me/products")
async def get_my_bookmarks_products(current_user: dict = Depends(get_current_user)):
    """
    현재 로그인한 사용자의 북마크한 상품들의 정보를 반환하는 API

    output: 북마크한 상품들의 정보 리스트
    """
    email = current_user["email"]
    
    # 사용자의 북마크 목록 조회
    bookmarks = await db["bonre_bookmarks"].find({"email": email}).to_list(1000)
    if not bookmarks:
        return []
    
    # 북마크된 상품들의 id 목록
    product_ids = [ObjectId(bookmark["product_id"]) for bookmark in bookmarks]
    
    # 상품 정보 조회
    items = await db["bonre_products"].find({"_id": {"$in": product_ids}}).to_list(1000)
    if not items:
        return []
        
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

# 북마크 삭제
@router.delete("/delete-bookmark/{product_id}")
async def delete_bookmark(product_id: str, current_user: dict = Depends(get_current_user)):
    email = current_user["email"]
    bookmark = await db["bonre_bookmarks"].find_one({"email": email, "product_id": product_id})
    if not bookmark:
        raise HTTPException(status_code=404, detail="북마크를 찾을 수 없습니다.")
    
    # bonre_products의 bookmark_counts -1
    product = await db["bonre_products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    current_count = product.get("bookmark_counts", 0)
    new_count = max(current_count - 1, 0)
    await db["bonre_products"].update_one({"_id": ObjectId(product_id)}, {"$set": {"bookmark_counts": new_count}})
    
    await db["bonre_bookmarks"].delete_one({"_id": bookmark["_id"]})
    return {"message": "북마크가 삭제되었습니다."}

