# Dockerfile

# 1. 모든 스테이지에서 공유할 'base' 스테이지
# uv 설치 및 pyproject.toml, uv.lock 파일 복사
FROM python:3.13-slim AS base
WORKDIR /app
RUN python -m pip install uv
COPY pyproject.toml ./

# 2. 공통 의존성만 설치한 'deps' 스테이지
# 이 레이어는 자주 변경되지 않으므로 캐시 효율이 높음
FROM base AS deps
# Extras 없이 기본 의존성만 먼저 설치 (레이어 캐싱 활용)
# 이 단계는 pyproject.toml이 변경될 때만 재실행됩니다.
RUN uv venv
RUN uv pip install --no-cache .

# 3. 실제 소스 코드를 추가하는 'builder' 스테이지
FROM deps AS builder
COPY . .

# ---------------------------------------------------------
# 여기서부터는 각 서비스의 최종 이미지를 만드는 스테이지입니다.
# ---------------------------------------------------------

# 4. FastAPI 앱을 위한 최종 이미지
FROM builder AS fastapi-app
# FastAPI 전용 extra 설치
RUN uv pip install --no-cache '.[fastapi]'
# 기본 CMD를 FastAPI 실행으로 변경 (docker-compose에서 오버라이드 가능)
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


# 5. 일반 Celery 워커 (beat, 가벼운 worker 등)를 위한 최종 이미지
FROM builder AS celery-base-worker
# 추가 의존성 없음 (기본 의존성만 사용)
CMD ["uv", "run", "celery", "-A", "celery_app.app", "worker", "-l", "info"]


# 6. 무거운 AI 모듈이 필요한 Celery 워커를 위한 최종 이미지
FROM builder AS celery-ai-worker
# C extensions을 컴파일 하기 위한 build-essential 설치
RUN apt-get update
RUN apt-get install -y build-essential
# 'ai_worker' extra를 설치 (torch, transformers 등)
RUN uv pip install --no-cache '.[ai_worker]'
CMD ["uv", "run", "celery", "-A", "celery_app.app", "worker", "-l", "info"]


# 7. Flower 서비스를 위한 최종 이미지
FROM builder AS flower-service
# 'flower' extra를 설치
RUN uv pip install --no-cache '.[flower]'
CMD ["uv", "run", "celery", "-A", "celery_app.app", "flower"]
