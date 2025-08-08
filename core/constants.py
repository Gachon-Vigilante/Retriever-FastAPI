import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING")

LOG_PATH = os.getenv("LOG_PATH", "logs/server.log")
SQLALCHEMY_DATABASE_URL = "sqlite:///./teleprobe.db"


TELEPROBE_TOKEN_TTL_DAYS = os.getenv("TELEPROBE_TOKEN_TTL_DAYS", 30)
if not TELEPROBE_TOKEN_TTL_DAYS.isdigit():
    raise ValueError("environment variable `TELEPROBE_TOKEN_TTL_DAYS` must be a number")
TELEPROBE_TOKEN_EXPIRATION = timedelta(days=int(TELEPROBE_TOKEN_TTL_DAYS)) # 토큰 생성 후 30일 후 만료
