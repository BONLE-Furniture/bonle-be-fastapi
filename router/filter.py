from fastapi import APIRouter, HTTPException, Depends

from db.database import db
from db.models import Filter, FilterUpdate

from router.user.token import allow_admin

router = APIRouter(
    prefix="/filter",
    tags=["filter CRUD"]
)

@router.get("")
async def get_all_filters():
    """
    bonre_filters 컬렉션에 있는 모든 필터 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_filters" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_filters"].find().to_list(1000)
    return items

@router.get("/{filter_id}")
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

@router.post("/create-filter", dependencies=[Depends(allow_admin)])
async def create_filter(filter: Filter):
    filter_dict = filter.dict(by_alias=True)
    try:
        await db["bonre_filters"].insert_one(filter_dict)
        return {"message":"success bonre_filter create", "filter" : filter_dict}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.patch("/update-filter/{filter_id}", dependencies=[Depends(allow_admin)])
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
    
@router.delete("/delete-filter/{filter_id}", dependencies=[Depends(allow_admin)])
async def delete_filter(filter_id: str):
    try:
        result = await db["bonre_filters"].delete_one({"_id": filter_id})
        if result.deleted_count == 1:
            return {"message": "filter deleted successfully"}
        raise HTTPException(status_code=404, detail="filter not found")    
    except Exception as e:
        return {"message": "Error deleting filter"}