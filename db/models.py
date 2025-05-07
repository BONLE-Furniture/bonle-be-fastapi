# models.py
from pydantic import BaseModel, HttpUrl, Field, EmailStr, field_validator
from typing import List, Optional, Literal
from typing_extensions import Self
from datetime import datetime
from bson import ObjectId
from enum import Enum

from fastapi import HTTPException

"""
user
"""

class User(BaseModel):
    id: str = Field(alias="_id") 
    password: str = "password12"# 비밀번호 해시처리
    name: str
    email: EmailStr # 이메일 양식 확인
    phone:str = "010-0000-0000"# 전화번호 양식 확인
    role: Literal["member", "admin"] = "member" # member , admin
    birthday: str = "2000-01-01"# 년-월-일

    @field_validator("name", "password", "phone", "birthday")
    @classmethod
    def validate_required_fields(cls, v:str) -> str:
        if not v or v.isspace():
            raise HTTPException(status_code=422, detail="필수 항목을 입력해주세요.") 
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v:str) -> str:
        if len(v) < 8:
            raise HTTPException(status_code=422, detail="비밀번호는 8자 이상 영문과 숫자를 포함하여 작성해주세요.")
        if not any(char.isdigit() for char in v):
            raise HTTPException(status_code=422, detail="비밀번호는 8자 이상 영문과 숫자를 포함하여 작성해주세요.")
        if not any(char.isalpha() for char in v):
            raise HTTPException(status_code=422, detail="비밀번호는 8자 이상 영문과 숫자를 포함하여 작성해주세요.")
        return v
        
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v:str)-> str:
        if '-' not in v or len(v) != 13:
            raise HTTPException(status_code=422, detail="전화번호는 '-'를 포함하여 작성해주세요.")
        return v
    
    @field_validator('birthday')
    @classmethod
    def validate_birthday(cls, v: str) -> str:
        """생년월일 형식 검증 (YYYY-MM-DD)"""
        try:
            datetime.strptime(v, "%Y-%m-%d")  # 날짜 형식 확인
        except ValueError:
            raise HTTPException(status_code=422, detail="생년월일은 YYYY-MM-DD 형식이어야 합니다.")
        return v

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str

"""
Product
"""


# Cheapest 모델 (가격 이력)
class Product_Cheapest(BaseModel):
    date: datetime
    price: int
    shop_id: str


# Size 모델 (size 정보)
class Product_Size(BaseModel):
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None


# ShopUrl 모델 (상점 URL)
class Product_ShopUrl(BaseModel):
    shop_id: str
    url: HttpUrl
    priceCC: bool = True


# Product upload용 모델
class Product(BaseModel):
    name_kr: str
    name: str
    subname: Optional[str] = ""
    subname_kr: Optional[str] = ""
    brand: str
    brand_kr: str
    designer: Optional[List[str]] = []
    color: str
    size: Product_Size
    description: Optional[str] = ""
    material: Optional[str] = ""
    filter: Optional[object]  # 색상과 재질 필터
    category: Optional[str] = ""
    bookmark_counts: Optional[int] = 0
    shop_urls: Optional[List[Product_ShopUrl]] = List[Product_ShopUrl]  # 각 상점 URL 정보
    main_image_url: Optional[str] = ""  # 이미지 URL
    cheapest: Optional[List[Product_Cheapest]] = []  # 가격 이력 리스트
    upload: bool = False


# Product update용 모델
class ProductUpdate(BaseModel):
    name_kr: Optional[str] = None
    name: Optional[str] = None
    subname: Optional[str] = None
    subname_kr: Optional[str] = None
    brand: Optional[str] = None
    designer: Optional[List[str]] = None
    color: Optional[str] = None
    size: Optional[Product_Size] = None
    description: Optional[str] = None
    material: Optional[str] = None
    filter: Optional[object] = None  # 색상과 재질 필터
    category: Optional[str] = None
    bookmark_counts: Optional[int] = None
    shop_urls: List[Product_ShopUrl] = None  # 각 상점 URL 정보
    main_image_url: Optional[str] = None  # 이미지 URL
    cheapest: Optional[List[Product_Cheapest]] = None  # 가격 이력 리스트
    brand_kr: Optional[str] = None
    upload: Optional[bool] = None


class Product_Period(str, Enum):
    one_week = "1week"
    one_month = "1month"
    one_year = "1year"
    all_time = "all"

"""
filter & category
"""

class Filter(BaseModel):
    id: str = Field(alias="_id")
    type: str
    filters :List[str]
    name: str
    
    class Config:
        allow_population_by_field_name = True
        
class FilterUpdate(BaseModel):
    type: Optional[str] = None
    filters: Optional[List[str]] = None
    name: Optional[str] = None
    
    class Config:
        allow_population_by_field_name = True
        
class Category(BaseModel):
    id: str = Field(alias="_id")
    name: str
    required_filters: List[str]
    optional_filters: Optional[List[str]] = []
    
    class Config:
        allow_population_by_field_name = True
        
class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    required_filters: Optional[List[str]] = None
    optional_filters: Optional[List[str]] = None
    
    class Config:
        allow_population_by_field_name = True
"""
Brand
"""


class Brand(BaseModel):
    id: str = Field(alias="_id")
    brand_kr: str
    brand: str
    comment: Optional[str] = None
    bookmark_count: Optional[int] = 0
    main_image_url: str

    class Config:
        allow_population_by_field_name = True

# Brand 생성 모델
class BrandUpdate(BaseModel):
    brand_kr: Optional[str] = None
    brand: Optional[str] = None
    comment: Optional[str] = None
    bookmark_count: Optional[int] = None
    main_image_url: Optional[str] = None


class Shop(BaseModel):
    id: str = Field(alias="_id")
    shop_kr: str
    shop: str
    comment: Optional[str] = ""
    bookmark_count: Optional[int] = 0
    link: str
    sld: str
    brand_list: Optional[List[str]] = []

    class Config:
        allow_population_by_field_name = True


class ShopUpdate(BaseModel):
    shop_kr: Optional[str] = None
    shop: Optional[str] = None
    comment: Optional[str] = None
    bookmark_count: Optional[int] = None
    link: Optional[str] = None
    sld: Optional[str] = None
    brand_list: Optional[List[str]] = []

    class Config:
        allow_population_by_field_name = True


class Designer(BaseModel):
    id: str = Field(alias="_id")
    designer_kr: str = ""
    designer: str = ""
    comment: Optional[str] = ""
    bookmark_count: Optional[int] = 0

    class Config:
        allow_population_by_field_name = True


class DesignerUpdate(BaseModel):
    designer_kr: Optional[str] = None
    designer: Optional[str] = None
    comment: Optional[str] = None
    bookmark_count: Optional[int] = None

    class Config:
        allow_population_by_field_name = True


class Price(BaseModel):
    date: datetime
    price: int


class Product_Price(BaseModel):
    product_id: str
    shop_sld: str
    shop_id: str
    prices: List[Price]


class bookmark(BaseModel):
    id: str = None
    userId: str
    product_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    __v: Optional[int] = 0


# Object Type to STR변환
def sanitize_data(data):
    sanitized_data = []
    for item in data:
        sanitized_item = {}
        for key, value in item.items():
            if isinstance(value, ObjectId):
                sanitized_item[key] = str(value)
            elif isinstance(value, float):
                if value == float('inf') or value == float('-inf') or value != value:
                    sanitized_item[key] = None
                else:
                    sanitized_item[key] = value
            elif isinstance(value, dict):
                sanitized_item[key] = sanitize_data([value])[0]
            elif isinstance(value, list):
                sanitized_item[key] = [
                    str(v) if isinstance(v, ObjectId)
                    else sanitize_data([v])[0] if isinstance(v, dict)
                    else v
                    for v in value
                ]
            else:
                sanitized_item[key] = value
        sanitized_data.append(sanitized_item)
    return sanitized_data

class URLRequest(BaseModel):
    url: str