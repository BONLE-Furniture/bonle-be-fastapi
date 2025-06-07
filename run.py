import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from pytz import timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

# Import routers
from router.price import router as price_router
from router.product import router as product_router
from router.product import router_total as total_router
from router.shop import router as shop_router
from router.users import router as user_router
from router.filter import router as filter_router
from router.designer import router as designer_router
from router.category import router as category_router
from router.brand import router as brand_router

app = FastAPI()
utc = timezone('UTC')
scheduler = AsyncIOScheduler(timezone=utc)

# HTTPS 리다이렉션 미들웨어
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.scheme == "https" and os.getenv("ENVIRONMENT") == "production":
            url = str(request.url).replace("http://", "https://", 1)
            return RedirectResponse(url=url, status_code=301)
        return await call_next(request)

# 보안 헤더 미들웨어
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # HSTS 헤더 (1년 = 31536000초)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # CSP 헤더
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'"
        
        # XSS 보호
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # 클릭재킹 방지
        response.headers["X-Frame-Options"] = "DENY"
        
        # MIME 타입 스니핑 방지
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 리퍼러 정책
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

# 미들웨어 추가
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://bonle.co.kr",
        "http://localhost:3000",  # 개발 환경
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 신뢰할 수 있는 호스트 설정
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=[
            "bonle.co.kr",
        ]
    )
else:
    # 개발 환경에서는 호스트 검증 비활성화
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=["*"]
    )

"""
FAST API 연결, MongoDB 연결 테스트
"""

@app.get("/", tags=["root"])
async def read_root():
    return {"message": "welcome to bonle"}

# Include routers
app.include_router(user_router)
app.include_router(total_router)
app.include_router(product_router)
app.include_router(price_router)
app.include_router(brand_router)
app.include_router(shop_router)
app.include_router(designer_router)
app.include_router(category_router)
app.include_router(filter_router)

"""
Scheduler
"""
import logging

# 로깅 설정을 더 자세하게 수정
logging.basicConfig(
    level=logging.INFO,  # 기본 로깅 레벨을 INFO로 변경
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# pymongo의 로깅 레벨을 INFO로 설정
logging.getLogger('pymongo').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

async def run_update_prices_all():
    logger.info("Starting scheduled price update task")
    current_time_utc = datetime.now(utc)
    logger.info(f"Current time in UTC: {current_time_utc}")
    
    try:
        from router.price import update_prices_all
        result = await update_prices_all()
        logger.info(f"Scheduled task completed: {result}")
    except Exception as e:
        logger.error(f"Error in scheduled task: {e}", exc_info=True)

@app.on_event("startup")
def schedule_price_updates():
    try:
        logger.info("Initializing scheduler...")
        logger.info(f"Current time in UTC: {datetime.now(timezone('UTC'))}")
                
        try:
            scheduler.add_job(
                run_update_prices_all, 
                CronTrigger(hour=15, minute=10, timezone=utc),
                id='price_update_job',
                name='Update all prices',
                replace_existing=True
            )
            logger.info("Added new job successfully")
        except Exception as e:
            logger.error(f"Failed to add new job: {e}", exc_info=True)
        
        scheduler.start()
        logger.info("Scheduler started successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}", exc_info=True)
        
@app.get("/scheduler/status", tags=["scheduler"])
async def get_scheduler_status():
    jobs = scheduler.get_jobs()
    return {
        "scheduler_running": scheduler.running,
        "total_jobs": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in jobs
        ]
    }
        

@app.on_event("shutdown")
def shutdown_scheduler():
    try:
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {e}", exc_info=True)
