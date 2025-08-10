"""애플리케이션 상수 정의 모듈 - Teleprobe 서비스의 설정 상수들

이 모듈은 Teleprobe 애플리케이션에서 사용되는 모든 상수 값들을 정의합니다.
환경 변수로부터 설정값을 로드하고, 데이터베이스 연결 설정, 토큰 만료 시간 등을 관리합니다.

Application Constants Module - Configuration constants for Teleprobe service

This module defines all constant values used in the Teleprobe application.
It loads configuration values from environment variables and manages
database connection settings, token expiration times, etc.

Constants:
    LOG_PATH (str): 로그 파일 경로
                   Log file path
    SQLALCHEMY_DATABASE_URL (str): SQLAlchemy 데이터베이스 연결 URL
                                  SQLAlchemy database connection URL  
    TELEPROBE_TOKEN_TTL_DAYS (str): 토큰 유효 기간 (일 단위)
                                   Token time-to-live in days
    TELEPROBE_TOKEN_EXPIRATION (timedelta): 토큰 만료 시간 객체
                                          Token expiration time object

Raises:
    ValueError: TELEPROBE_TOKEN_TTL_DAYS 환경 변수가 숫자가 아닌 경우
               When TELEPROBE_TOKEN_TTL_DAYS environment variable is not a number
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

LOG_PATH = os.getenv("LOG_PATH", "logs/server.log")
SQLALCHEMY_DATABASE_URL = "sqlite:///./teleprobe.db"

TELEPROBE_TOKEN_TTL_DAYS = os.getenv("TELEPROBE_TOKEN_TTL_DAYS", 30)
if not TELEPROBE_TOKEN_TTL_DAYS.isdigit():
    raise ValueError("environment variable `TELEPROBE_TOKEN_TTL_DAYS` must be a number")
TELEPROBE_TOKEN_EXPIRATION = timedelta(days=int(TELEPROBE_TOKEN_TTL_DAYS)) # 토큰 생성 후 30일 후 만료
