"""Teleprobe API 라우터 패키지 - Teleprobe 서비스의 모든 API 엔드포인트

이 패키지는 Teleprobe 서비스의 핵심 기능들에 대한 API 엔드포인트들을 제공합니다.
인증, 채널 관리, 메시지 처리 등의 기능별로 모듈화되어 있으며,
각 모듈의 라우터들을 통합하여 단일 진입점을 제공합니다.

Teleprobe API Router Package - All API endpoints for Teleprobe service

This package provides API endpoints for core functionalities of the Teleprobe service.
It is modularized by functionality such as authentication, channel management, and message processing,
and provides a single entry point by integrating routers from each module.

Modules:
    auth: 텔레그램 클라이언트 인증 및 토큰 관리 API
         Telegram client authentication and token management API
    channel: 채널 모니터링 및 관리 API
            Channel monitoring and management API  
    message: 메시지 조회 및 처리 API
            Message retrieval and processing API

Router Configuration:
    router (APIRouter): "/teleprobe" 접두사를 가진 메인 라우터
                       Main router with "/teleprobe" prefix

    Included Routers:
        - auth.router: /teleprobe/auth/* 경로의 인증 관련 엔드포인트
                      Authentication-related endpoints at /teleprobe/auth/*
        - channel.router: /teleprobe/channel/* 경로의 채널 관련 엔드포인트
                         Channel-related endpoints at /teleprobe/channel/*
        - message.router: /teleprobe/message/* 경로의 메시지 관련 엔드포인트
                         Message-related endpoints at /teleprobe/message/*

Examples:
    # FastAPI 앱에 Teleprobe 라우터 등록
    from routes.teleprobe import router as teleprobe_router
    app.include_router(teleprobe_router)

    # 개별 라우터 사용
    from routes.teleprobe.auth import router as auth_router
    app.include_router(auth_router)

Dependencies:
    core.sqlite: SQLite 데이터베이스 연결 및 모델 초기화
                SQLite database connection and model initialization
"""

from fastapi import APIRouter

import core.sqlite
from . import (
    auth,
    channel,
    message
)

router = APIRouter(prefix="/teleprobe")

router.include_router(auth.router)
router.include_router(channel.router)
router.include_router(message.router)