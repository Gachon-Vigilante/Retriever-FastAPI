"""SQLite 데이터베이스 설정 모듈 - SQLAlchemy를 사용한 데이터베이스 연결 및 모델 정의

이 모듈은 Teleprobe 애플리케이션의 SQLite 데이터베이스 연결을 설정하고,
텔레그램 토큰 정보를 저장하기 위한 데이터베이스 모델을 정의합니다.
SQLAlchemy ORM을 사용하여 데이터베이스 작업을 수행합니다.

SQLite Database Configuration Module - Database connection and model definitions using SQLAlchemy

This module configures SQLite database connections for the Teleprobe application
and defines database models for storing Telegram token information.
It uses SQLAlchemy ORM for database operations.

Classes:
    TelegramToken: 텔레그램 API 토큰과 세션 정보를 저장하는 모델
                  Model for storing Telegram API tokens and session information

Functions:
    get_db: 데이터베이스 세션을 제공하는 컨텍스트 매니저
           Context manager for providing database sessions
"""

from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column

from core.constants import SQLALCHEMY_DATABASE_URL


# 의존성 함수들
@contextmanager
def get_db():
    """데이터베이스 세션을 제공하는 컨텍스트 매니저

    SQLAlchemy 세션을 생성하고 관리하는 컨텍스트 매니저입니다.
    자동으로 세션을 생성하고 작업 완료 후 정리합니다.

    Database session context manager

    A context manager that creates and manages SQLAlchemy sessions.
    Automatically creates sessions and cleans up after work completion.

    Yields:
        Session: SQLAlchemy 데이터베이스 세션 객체
                SQLAlchemy database session object

    Examples:
        with get_db() as db:
            # 데이터베이스 작업 수행
            # Perform database operations
            token = db.query(TelegramToken).first()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TelegramToken(Base):
    """텔레그램 API 토큰과 세션 정보를 저장하는 데이터베이스 모델

    텔레그램 봇 API 토큰, API 자격증명, 세션 문자열 등의 정보를 저장합니다.
    각 토큰은 고유한 식별자를 가지며 만료 날짜와 활성 상태를 관리합니다.

    Database model for storing Telegram API tokens and session information

    Stores Telegram bot API tokens, API credentials, session strings, and other
    related information. Each token has a unique identifier and manages
    expiration date and active status.

    Attributes:
        id (int): 기본 키로 사용되는 고유 식별자
                 Unique identifier used as primary key
        token (str): 텔레그램 API 토큰 (최대 128자)
                    Telegram API token (max 128 characters)
        api_id (int): 텔레그램 API ID
                     Telegram API ID
        api_hash (str): 텔레그램 API 해시 (32자)
                       Telegram API hash (32 characters)
        session_string (Optional[str]): 텔레그램 세션 문자열
                                      Telegram session string
        phone (Optional[str]): 연결된 전화번호 (최대 20자)
                              Associated phone number (max 20 characters)
        created_at (datetime): 토큰 생성 시간
                              Token creation timestamp
        expires_at (datetime): 토큰 만료 시간
                              Token expiration timestamp
        is_active (int): 토큰 활성 상태 (1: 활성, 0: 비활성)
                        Token active status (1: active, 0: inactive)
    """
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