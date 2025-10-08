# Python 3.13 기반 이미지 사용
FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 관리를 위해 uv 설치
RUN pip install uv

# 프로젝트 파일 복사
COPY pyproject.toml ./
COPY uv.lock ./


# 의존성 설치 (uv 사용)
RUN uv sync --frozen --no-dev

# 애플리케이션 코드 복사
COPY . .

# 기본 명령어 (docker-compose.yml에서 오버라이드됨)
CMD ["uv", "run", "python", "main.py"]