"""메인 애플리케이션 모듈 - Teleprobe 서비스의 FastAPI 애플리케이션 진입점

이 모듈은 Teleprobe 서비스의 메인 FastAPI 애플리케이션을 정의하고 구성합니다.
애플리케이션의 생명주기 관리, 라우터 등록, 헬스체크 엔드포인트를 제공합니다.

Main Application Module - FastAPI application entry point for Teleprobe service

This module defines and configures the main FastAPI application for the Teleprobe service.
It provides application lifecycle management, router registration, and health check endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.setup import database_setup
from utils import Logger
from routes import root_router
from celery_app import setup_celery
from watson.vectorstore.weaviate import register_schema

setup_celery()
logger = Logger(__name__)

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """애플리케이션 생명주기를 관리하는 컨텍스트 매니저

    FastAPI 애플리케이션의 시작과 종료 시 실행할 작업을 정의합니다.
    등록된 모든 라우트를 디버그 로그로 출력합니다.

    Application lifecycle management context manager

    Defines tasks to be executed during FastAPI application startup and shutdown.
    Outputs all registered routes as debug logs.

    Args:
        fastapi_app (FastAPI): FastAPI 애플리케이션 인스턴스
                              FastAPI application instance

    Yields:
        None: 애플리케이션 실행 중 상태를 유지
              Maintains application running state
    """
    database_setup()
    logger.debug("Registered Routes:")
    for route in fastapi_app.routes:
        logger.debug(f"  {route}")
    await register_schema()
    yield

app = FastAPI(lifespan=lifespan)

# 허용할 오리진(origin) 목록
# "*"는 모든 오리진을 허용함을 의미합니다.
# 보안을 위해 실제 프로덕션 환경에서는 구체적인 도메인을 명시하는 것이 좋습니다.
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # origins 목록에 있는 도메인에서의 요청을 허용
    allow_credentials=True,    # 쿠키를 포함한 요청을 허용 (True 설정 시 allow_origins="*" 사용 불가)
    allow_methods=["*"],       # 모든 HTTP 메소드 허용 (GET, POST, PUT, DELETE 등)
    allow_headers=["*"],       # 모든 HTTP 헤더 허용
)

app.include_router(root_router)

@app.get("/healthcheck")
def healthcheck():
    """서비스 상태를 확인하는 헬스체크 엔드포인트

    애플리케이션의 정상 동작 여부를 확인할 수 있는 간단한 엔드포인트입니다.

    Health check endpoint to verify service status

    A simple endpoint to verify that the application is running normally.

    Returns:
        dict: 서비스 상태 정보를 포함하는 딕셔너리
              Dictionary containing service status information
            - status (str): "active" 문자열로 서비스 활성 상태를 나타냄
                          "active" string indicating service is active
    """
    logger.info("Health Checked.")
    return {"status": "active"}



