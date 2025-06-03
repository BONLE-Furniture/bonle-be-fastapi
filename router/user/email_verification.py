import os
import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException
from pydantic import EmailStr
from db.database import db
from db.models import EmailVerification, EmailVerificationResponse
import emails
from emails.template import JinjaTemplate
from dotenv import load_dotenv

load_dotenv()  # 환경 변수 로드

# 이메일 설정
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAILS_FROM_EMAIL = SMTP_USER  # SMTP_USER와 동일한 이메일 주소 사용
EMAILS_FROM_NAME = "bonle"    # 발신자 표시 이름

def create_verification_token(email: str) -> str:
    """5자리 숫자 인증 코드 생성"""
    return str(random.randint(10000, 99999))

async def send_verification_email(email: str, token: str):
    """이메일 발송 함수"""
    # 이미 가입된 이메일인지 확인
    user = await db["bonle_users"].find_one({"email": email})
    if user:
        raise HTTPException(status_code=400, detail="가입된 계정이 존재합니다.")
    
    # 기존 인증 메일이 있다면 삭제
    await db["email_verifications"].delete_many({"email": email})
    
    # 이메일 인증 정보 저장
    expires_at = datetime.utcnow() + timedelta(hours=1)
    await db["email_verifications"].insert_one({
        "email": email,
        "token": token,
        "expires_at": expires_at,
        "verified": False,
        "created_at": datetime.utcnow()
    })

    # 이메일 템플릿
    html_content = f"""
    <html>
        <body>
            <h1>이메일 인증</h1>
            <p>안녕하세요! 이메일 인증을 완료하기 위해 아래 인증번호를 입력해주세요:</p>
            <p style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 24px; text-align: center;">{token}</p>
            <p>이 인증번호는 1시간 동안 유효합니다.</p>
            <p>감사합니다.</p>
        </body>
    </html>
    """
    
    message = emails.Message(
        subject="이메일 인증",
        html=html_content,
        mail_from=(EMAILS_FROM_NAME, EMAILS_FROM_EMAIL),
    )
    
    # SMTP 설정
    smtp_options = {
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "tls": True,
        "user": SMTP_USER,
        "password": SMTP_PASSWORD,
    }
    
    try:
        response = message.send(
            to=email,
            render={"token": token},
            smtp=smtp_options
        )
        if response.status_code not in [250, 200, 201, 202]:
            # 이메일 발송 실패 시 저장된 토큰 삭제
            await db["email_verifications"].delete_one({"email": email, "token": token})
            raise HTTPException(status_code=500, detail="이메일 발송에 실패했습니다.")
    except Exception as e:
        # 이메일 발송 실패 시 저장된 토큰 삭제
        await db["email_verifications"].delete_one({"email": email, "token": token})
        raise HTTPException(status_code=500, detail=f"이메일 발송 중 오류가 발생했습니다: {str(e)}")

async def verify_email(verification: EmailVerification) -> EmailVerificationResponse:
    """이메일 인증 처리"""
    # 이메일 인증 토큰 확인
    verification_record = await db["email_verifications"].find_one({
        "email": verification.email,
        "token": verification.token,
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if not verification_record:
        raise HTTPException(status_code=400, detail="유효하지 않거나 만료된 인증번호입니다.")

    # 인증 완료 처리
    await db["email_verifications"].update_one(
        {"email": verification.email, "token": verification.token},
        {"$set": {"verified": True, "verified_at": datetime.utcnow()}}
    )

    return EmailVerificationResponse(
        message="이메일 인증이 완료되었습니다.",
        verified=True
    ) 