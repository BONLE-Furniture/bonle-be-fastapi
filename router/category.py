from fastapi import APIRouter, HTTPException, Depends

from db.database import db
from db.models import Category, CategoryUpdate

from router.user.token import allow_admin


router = APIRouter(
    prefix="/category",
    tags=["category CRUD"]
)

@router.get("")
async def get_all_categories():
    """
    bonre_categories 컬렉션에 있는 모든 필터 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_categories" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_categories"].find().to_list(1000)
    return items

@router.get("/{category_id}")
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

@router.post("/create-category", dependencies=[Depends(allow_admin)])
async def create_category(category: Category):
    category_dict = category.dict(by_alias=True)
    try:
        await db["bonre_categories"].insert_one(category_dict)
        return {"message":"success bonre_category create", "category" : category_dict}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.patch("/update-category/{category_id}", dependencies=[Depends(allow_admin)])
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
            
            
@router.delete("/delete-category/{category_id}", dependencies=[Depends(allow_admin)])
async def delete_category(category_id: str):
    try:
        result = await db["bonre_categories"].delete_one({"_id": category_id})
        if result.deleted_count == 1:
            return {"message": "Category deleted successfully"}
        raise HTTPException(status_code=404, detail="Category not found")
    except Exception as e:
        # 예외 처리
        return {"message": "Error deleting category"}