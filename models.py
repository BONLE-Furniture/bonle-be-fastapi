# models.py
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime

# Size 모델 (size 정보)
class Size(BaseModel):
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None
    length: Optional[float] = None

# Cheapest 모델 (가격 이력)
class Cheapest(BaseModel):
    date: datetime
    price: int
    shop_id: str

# ShopUrl 모델 (상점 URL)
class ShopUrl(BaseModel):
    url: HttpUrl
    shop_id: str

# Product 모델 (main 모델)
class Product(BaseModel):
    id: str = None # MongoDB의 ObjectId는 자동으로 처리
    name_kr: str
    name: str
    type: Optional[str] = None
    brand: str
    designer: List[str]
    color: str
    size: Size
    description: str
    material: str
    filter: dict  # 색상과 재질 필터
    category: str
    sales_links: List[HttpUrl]  # 판매 링크
    bookmark_counts: int
    shop_urls: List[ShopUrl]  # 각 상점 URL 정보
    main_image_url: str  # 이미지 URL
    cheapest: List[Cheapest]  # 가격 이력 리스트
    brand_kr: str
