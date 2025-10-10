"""Teleprobe 패키지 - 텔레그램 채널 모니터링 및 데이터 수집 시스템

이 패키지는 Telethon 기반으로 텔레그램 채널을 모니터링하고 메시지를 수집하는
종합적인 시스템을 제공합니다. 클라이언트 관리, 채널 연결, 메시지 처리,
데이터베이스 저장 등의 핵심 기능을 포함합니다.

Teleprobe Package - Telegram channel monitoring and data collection system

This package provides a comprehensive system for monitoring Telegram channels and collecting messages
based on Telethon. It includes core functionality such as client management, channel connection,
message processing, and database storage.

Modules:
    base: TeleprobeClient 클래스와 핵심 기능
         TeleprobeClient class and core functionality
    connect: 채널 연결 및 초대 수락 유틸리티
            Channel connection and invitation acceptance utilities
    channel: 채널 모니터링 및 관리 기능
            Channel monitoring and management functionality
    message: 메시지 처리 및 반복 기능
            Message processing and iteration functionality
    errors: 커스텀 예외 클래스들
           Custom exception classes
    constants: 설정 상수 및 로거 구성
              Configuration constants and logger setup
    models: 데이터 모델 정의
           Data model definitions

Key Classes:
    TeleprobeClient: 텔레그램 클라이언트 관리 및 작업 수행
                    Telegram client management and task execution
    TelegramCredentials: 텔레그램 인증 정보 모델
                        Telegram authentication information model

Examples:
    # 기본 사용법
    from teleprobe import TeleprobeClient

    client = TeleprobeClient(api_id=12345, api_hash="abc123", session_string="...")
    await client.ensure_connected()

    # 채널 모니터링
    await client.watch("@channelname", message_handler)

    # 메시지 수집
    async for message in client.iter_messages(channel):
        process_message(message)
"""

from .base import TeleprobeClient