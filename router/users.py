# from logging import Logger
# import json
import os
from datetime import  timedelta

from db.database import db
from db.models import *

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext
from urllib.parse import unquote

from router.user.token import create_access_token, define_crypt, oauth2_scheme, verify_password, get_current_user

router = APIRouter(
    prefix="/user",
    tags=["user CRUD"]
)

@router.get("/{user_id}", tags=["user CRUD"])
async def get_users(user_id):
    try:
        user = await db["bonre_users"].find_one({"_id": user_id})
        if user:
            return user
    except Exception as e:
        raise HTTPException(status_code=404, detail="User not found")

@router.get("/check-user-id/{user_id}", tags=["user CRUD"])
async def check_id(user_id: str):
    user = await db["bonre_users"].find_one({"_id": user_id})
    if user:
        return {"exists": True}
    return {"exists": False}
    

@router.get("/check-email/{email}", tags=["user CRUD"])
async def check_email(email: str):
    user = await db["bonre_users"].find_one({"email": email})
    if user:
        return {"exists": True}
    return {"exists": False}

@router.get("/check-phone/{phone}", tags=["user CRUD"])
async def check_phone(phone: str):
    user = await db["bonre_users"].find_one({"phone": phone})
    if user:
        return {"exists": True}
    return {"exists": False}
    
@router.post("/create-user", tags=["user CRUD"])
async def create_user(user: User, password_validation:str, crypt: CryptContext = Depends(define_crypt)):
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
    

@router.post("/login", tags=["user CRUD"])
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
        data={"sub": user["_id"],"role": user['role']},  # 토큰에 저장할 사용자 식별 정보
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["_id"]
    }


@router.post("/update-password", tags=["user CRUD"])
async def update_password(password: UserPasswordUpdate, current_user: dict = Depends(get_current_user), crypt: CryptContext = Depends(define_crypt)):
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

@router.delete("/delete-user", tags=["user CRUD"])
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


#front API 수정해야됌
@router.get("/token", tags=["user CRUD"])
async def read_users_token(current_user: dict = Depends(get_current_user)):
    """
    token 존재한다면 사용자 정보를 출력함
    """
    return current_user

