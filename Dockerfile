# 1. 베이스 이미지 선택 (FastAPI 실행을 위한 Python 기반 이미지)
FROM python:3.11

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 의존성 파일 복사 및 설치
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 4. 애플리케이션 소스 코드 복사
COPY . .

# 5. FastAPI 서버 실행 (Uvicorn 사용)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
