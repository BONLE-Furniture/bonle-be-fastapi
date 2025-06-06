# from logging import Logger
import os
from datetime import  timedelta, datetime

from db.database import db
from db.models import *

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from jose import JWTError, jwt
from passlib.context import CryptContext
from urllib.parse import unquote
from dotenv import load_dotenv

from router.user.token import create_access_token, define_crypt, oauth2_scheme, verify_password, get_current_user
from router.user.email_verification import create_verification_token, send_verification_email, verify_email
from router.user.token import allow_admin

# 환경 변수 로드
load_dotenv()

# 비밀번호 해시 컨텍스트 설정
crypt = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/user",
    tags=["user CRUD"]
)

@router.get("/token", tags=["user CRUD"])
async def read_users_token(current_user: dict = Depends(get_current_user)):
    """
    token 존재한다면 사용자 정보를 출력함
    """
    return current_user

@router.get("/terms-status", tags=["user CRUD"])
async def get_terms_status(current_user: dict = Depends(get_current_user)):
    """
    현재 사용자의 약관 동의 상태 조회 API
    """
    try:
        user = await db["bonre_users"].find_one({"email": current_user["email"]})
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        return {
            "service_terms_agreed": user.get("service_terms_agreed", False),
            "privacy_terms_agreed": user.get("privacy_terms_agreed", False)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/{email}", tags=["user CRUD"])
async def get_users(email: str):
    try:
        user = await db["bonre_users"].find_one({"email": email})
        if user:
            return {"exists": True, "user": sanitize_data([user])[0]}
        else:
            return {"exists": False}
    except Exception as e:
        raise HTTPException(status_code=404, detail="User not found")
    
@router.get("/check-email", tags=["user CRUD"])
async def check_email(email: str):
    user = await db["bonre_users"].find_one({"email": email})
    if user:
        return {"exists": True}
    return {"exists": False}

# @router.get("/check-phone/{phone}", tags=["user CRUD"])
# async def check_phone(phone: str):
#     user = await db["bonre_users"].find_one({"phone": phone})
#     if user:
#         return {"exists": True}
#     return {"exists": False}
    
@router.post("/send-verification", tags=["user CRUD"])
async def send_verification_email_endpoint(request: EmailRequest):
    """이메일 인증 요청 엔드포인트"""
    # 이미 가입된 이메일인지 확인
    existing_user = await db["bonre_users"].find_one({"email": request.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

    # 인증 토큰 생성 및 이메일 발송
    verification_token = create_verification_token(request.email)
    await send_verification_email(request.email, verification_token)
    
    return {"message": "인증 이메일이 발송되었습니다."}

@router.post("/verify-email", tags=["user CRUD"])
async def verify_email_endpoint(verification: EmailVerification):
    """이메일 인증 엔드포인트"""
    return await verify_email(verification)

@router.post("/resend-verification", tags=["user CRUD"])
async def resend_verification_email(email: str):
    """인증 이메일 재발송 엔드포인트"""
    user = await db["bonre_users"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    
    verification_token = create_verification_token(email)
    await db["bonre_users"].update_one(
        {"email": email},
        {"$set": {"verification_token": verification_token}}
    )
    
    await send_verification_email(email, verification_token)
    return {"message": "Verification email has been resent"}


@router.post("/create-user", tags=["user CRUD"])
async def create_user(create_user_data: CreateUser, crypt: CryptContext = Depends(define_crypt)):
    # 1. CreateUser 포맷으로 받은 데이터를 딕셔너리로 변환
    user_dict = create_user_data.dict(by_alias=True)
    
    # 2. 비밀번호 일치 여부 확인
    if user_dict["password"] != user_dict["password_validation"]:
        raise HTTPException(status_code=422, detail="비밀번호가 일치하지 않습니다.")
    del user_dict["password_validation"]

    # 4. 이메일 중복 확인
    existing_email = await db["bonre_users"].find_one({"email": user_dict["email"]})
    if existing_email:
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

    # 5. 이메일 인증 상태 확인
    try:
        user_verify = await db["email_verifications"].find_one({
            "email": user_dict["email"],
            "expires_at": {"$gt": datetime.utcnow()}  # 만료되지 않은 토큰만 확인
        })
        
        if not user_verify:
            raise HTTPException(status_code=401, detail="이메일 인증 정보를 찾을 수 없습니다.")
            
        if not user_verify.get("verified", False):  # verified가 false면 인증이 안 된 것
            raise HTTPException(status_code=400, detail="이메일 인증을 완료해주세요.")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 6. 비밀번호 해시 처리
    user_dict["password"] = crypt.hash(user_dict["password"]+os.getenv("SALT"))
    
    # 7. User 모델로 변환 및 검증
    try:
        user = User(**user_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    # 8. DB 저장
    try:
        await db["bonre_users"].insert_one(user_dict)
        await db["email_verifications"].delete_one({"email": user_dict["email"]})
        return {"message": "회원가입이 완료되었습니다.", "email": user_dict["email"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/update-password", tags=["user CRUD"])
async def update_password(password: UserPasswordUpdate, current_user: dict = Depends(get_current_user), crypt: CryptContext = Depends(define_crypt)):
    """
    비밀번호 변경 API

    input : current_password{str}, new_password{str}
    """
    user = await db["bonre_users"].find_one({"email": current_user["email"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 현재 비밀번호 검증
    if not verify_password(password.current_password, user["password"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # 새 비밀번호 해시 처리 후 업데이트
    hashed_new_password = crypt.hash(password.new_password + os.getenv("SALT"))
    await db["bonre_users"].update_one({"email": current_user["email"]}, {"$set": {"password": hashed_new_password}})
    return {"message": "Password updated successfully"}

@router.post("/login", tags=["user CRUD"])
async def login_user(login_form: OAuth2PasswordRequestForm = Depends()):
    # 사용자 조회
    user = await db["bonre_users"].find_one({"email": login_form.username})
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 비밀번호 검증
    if not verify_password(login_form.password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 액세스 토큰 생성
    access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_TIMES",3)))
    access_token = create_access_token(
        data={"sub": user["email"], "role": user['role']},  # 토큰에 저장할 사용자 식별 정보
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": user["email"]
    }
    
@router.patch("/change-role", tags=["user CRUD"], dependencies=[Depends(allow_admin)])
async def change_user_role(
    email: str,
    new_role: str
):
    """
    사용자 권한 변경 API (관리자 전용)
    
    input: 
    - email: 변경할 사용자의 이메일
    - new_role: 변경할 권한 ("member" 또는 "admin")
    """
    if new_role not in ["member", "admin"]:
        raise HTTPException(status_code=400, detail="유효하지 않은 권한입니다. 'member' 또는 'admin'만 가능합니다.")
        
    try:
        # 사용자 존재 여부 확인
        user = await db["bonre_users"].find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        # 권한 변경
        result = await db["bonre_users"].update_one(
            {"email": email},
            {"$set": {"role": new_role}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="권한 변경에 실패했습니다.")
            
        return {"message": f"사용자 권한이 {new_role}로 변경되었습니다."}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/update-terms-agreement", tags=["user CRUD"])
async def update_terms_agreement(
    service_terms_agreed: bool,
    privacy_terms_agreed: bool,
    current_user: dict = Depends(get_current_user)
):
    """
    약관 동의 상태 변경 API
    
    input:
    - service_terms_agreed: 서비스 이용약관 동의 여부
    - privacy_terms_agreed: 개인정보 수집 및 이용 동의 여부
    """
    try:
        # 사용자 존재 여부 확인
        user = await db["bonre_users"].find_one({"email": current_user["email"]})
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        # 약관 동의 상태 변경
        result = await db["bonre_users"].update_one(
            {"email": current_user["email"]},
            {"$set": {
                "service_terms_agreed": service_terms_agreed,
                "privacy_terms_agreed": privacy_terms_agreed
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="약관 동의 상태 변경에 실패했습니다.")
            
        return {
            "message": "약관 동의 상태가 변경되었습니다.",
            "service_terms_agreed": service_terms_agreed,
            "privacy_terms_agreed": privacy_terms_agreed
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.delete("/delete-user", tags=["user CRUD"])
async def delete_user(current_user: dict = Depends(get_current_user)):
    """
    사용자 삭제 API

    input : 없음 (로그인된 사용자 정보로 삭제)
    """
    user = await db["bonre_users"].find_one({"email": current_user["email"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 사용자 삭제
    await db["bonre_users"].delete_one({"email": current_user["email"]})
    return {"message": "User deleted successfully"}


# @router.get("/check-verification/{email}", tags=["user CRUD"])
# async def check_email_verification(email: str):
#     """이메일 인증 상태 확인 엔드포인트"""
#     try:
#         user_verify = await db["email_verifications"].find_one({
#             "email": email,
#             "expires_at": {"$gt": datetime.utcnow()}
#         })
        
#         if not user_verify:
#             return {
#                 "exists": False,
#                 "message": "이메일 인증 정보를 찾을 수 없습니다."
#             }
            
#         return {
#             "exists": True,
#             "verification_data": {
#                 "email": user_verify.get("email"),
#                 "verified": user_verify.get("verified", False),
#                 "expires_at": user_verify.get("expires_at"),
#                 "created_at": user_verify.get("created_at")
#             }
#         }
            
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))