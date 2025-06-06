import os

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status

from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt

from db.database import db
from db.models import sanitize_data

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")

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
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = await db["bonre_users"].find_one({"email": email})
    if user is None:
        raise credentials_exception
    return sanitize_data([user])[0]

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

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    secret_key = os.getenv("SECRET_KEY")
    algorithm = os.getenv("ALGORITHM")
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    
    return encoded_jwt

def define_crypt():
    crypt = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return crypt

def verify_password(plain_password, hashed_password, crypt: CryptContext = define_crypt()):
    salt = os.getenv("SALT")
    return crypt.verify(plain_password + salt, hashed_password)