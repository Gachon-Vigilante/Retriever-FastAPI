from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column

from core.constants import SQLALCHEMY_DATABASE_URL


# 의존성 함수들
def get_db():
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TelegramToken(Base):
    """텔레그램 토큰 정보를 저장하는 테이블"""
    __tablename__ = "telegram_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    api_id: Mapped[int] = mapped_column(Integer, nullable=False)
    api_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    session_string: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # SQLite에서는 Boolean 대신 Integer 사용


# 테이블 생성
Base.metadata.create_all(bind=engine)