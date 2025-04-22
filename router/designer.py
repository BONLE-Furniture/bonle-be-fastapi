from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from db.database import db
from db.models import Designer, DesignerUpdate

from router.user.token import allow_admin

router = APIRouter(
    prefix="/designer",
    tags=["designer CRUD"]
)

@router.get("")
async def get_all_designers():
    """
    bonre_designers 컬렉션에 있는 모든 디자이너 정보를 반환하는 API
    """
    collections = await db.list_collection_names()
    if "bonre_designers" not in collections:
        raise HTTPException(status_code=404, detail="Collection not found")
    items = await db["bonre_designers"].find().to_list(1000)
    return items


@router.get("/{designer_id}")
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
@router.post("/create-designer", dependencies=[Depends(allow_admin)])
async def create_desginer(designer: Designer):
    designer_dict = designer.dict(by_alias=True)
    try:
        await db["bonre_designers"].insert_one(designer_dict)
        return designer_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# designer 수정 API
@router.patch("/update-designer/{designer_id}", dependencies=[Depends(allow_admin)])
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
@router.delete("/delete-designer/{designer_id}", dependencies=[Depends(allow_admin)])
async def delete_designer(designer_id: str):
    result = await db["bonre_designers"].delete_one({"_id": designer_id})
    if result.deleted_count == 1:
        return {"message": "Designer deleted successfully"}
    raise HTTPException(status_code=404, detail="Designer not found")
