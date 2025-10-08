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
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

default_log_path = "logs/server.log"
if not os.getenv("LOG_PATH"):
    Path(os.path.dirname(default_log_path)).mkdir(parents=True, exist_ok=True)
LOG_PATH = os.getenv("LOG_PATH", default_log_path)
SQLALCHEMY_DATABASE_URL = "sqlite:///./teleprobe.db"

TELEPROBE_TOKEN_TTL_DAYS: int | None
TELEPROBE_TOKEN_EXPIRATION: timedelta | None
try:
    if (ttl_days := os.getenv("TELEPROBE_TOKEN_TTL_DAYS", 30)) is not None:
        TELEPROBE_TOKEN_TTL_DAYS = int(ttl_days)
        TELEPROBE_TOKEN_EXPIRATION = timedelta(days=int(TELEPROBE_TOKEN_TTL_DAYS)) # 토큰 생성 후 30일 후 만료
except ValueError:
    raise ValueError("environment variable `TELEPROBE_TOKEN_TTL_DAYS` must be a number")

TELEGRAM_API_ID: int | None = None
try:
    if (api_id:= os.getenv("TELEGRAM_API_ID")) is not None:
        TELEGRAM_API_ID = int(api_id)
except ValueError:
    raise ValueError("environment variable `TELEGRAM_API_ID` must be a number")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING")

TELEGRAM_LINK_PATTERN = r"(?i)(?:https?://)?t\.me/(?:s/|joinchat/)?([~+]?[a-zA-Z0-9_-]+)(?:/\d+)?"

CRAWLER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/114.0.0.0 "
                  "Safari/537.36"
}