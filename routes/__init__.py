"""API 라우터 패키지 - FastAPI 애플리케이션의 라우터 모듈들

이 패키지는 FastAPI 애플리케이션에서 사용되는 모든 API 라우터들을 관리합니다.
루트 라우터를 설정하고 하위 라우터들을 포함시켜 계층적인 API 구조를 제공합니다.
Teleprobe 서비스의 모든 엔드포인트가 이 패키지를 통해 정의됩니다.

API Router Package - Router modules for FastAPI application

This package manages all API routers used in the FastAPI application.
It sets up the root router and includes sub-routers to provide a hierarchical API structure.
All endpoints of the Teleprobe service are defined through this package.

Routers:
    root_router (APIRouter): 애플리케이션의 메인 라우터
                           Main router for the application
    teleprobe (module): Teleprobe 서비스 관련 라우터들이 포함된 모듈
                       Module containing routers related to Teleprobe service

Examples:
    # FastAPI 앱에 라우터 등록
    from routes import root_router
    app.include_router(root_router)

    # 특정 라우터만 사용
    from routes.teleprobe import router as teleprobe_router
    app.include_router(teleprobe_router)
"""

from fastapi import APIRouter

from . import teleprobe

root_router = APIRouter(prefix="")

root_router.include_router(teleprobe.router)