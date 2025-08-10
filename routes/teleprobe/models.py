# TelegramCredentials 모델의 필드를 상속받아 새로운 모델 생성
from datetime import datetime
from typing import Annotated, Union, Optional

from fastapi import Path, HTTPException, status, Body
from pydantic import BeforeValidator

from core.sqlite import get_db, TelegramToken
from teleprobe.base import TeleprobeClient


# 채널 키 변환 및 검증 의존성 함수
def auto_convert_numeric_string(v: str) -> Union[int, str]:
    """숫자 형태의 문자열을 자동으로 정수로 변환"""
    if isinstance(v, str) and v.lstrip('-').isdigit():
        return int(v)
    return v


# FastAPI의 Path 타입 매개변수 정의
channelKeyPath = Annotated[
    Union[int, str],
    BeforeValidator(auto_convert_numeric_string),
    Path(
        title="채널 키",
        description="채널을 식별할 수 있는 채널 ID(int), 또는 username(str) 또는 초대 링크(str)",
        serialization_alias="channelKey",
        examples=["-1001234567890", "@channelname", "https://t.me/+abcdefgh"]
    )
]


class TeleprobeClientManager:
    @staticmethod
    def get_client_by_token(
            token: Annotated[str, Body(description="인증 토큰")],
    ) -> TeleprobeClient:
        """
        토큰을 사용하여 데이터베이스에서 인증 정보를 조회하고 TeleprobeClient를 생성합니다.

        Args:
            token: HTTP 헤더에서 전달받은 토큰

        Returns:
            TeleprobeClient 인스턴스

        Raises:
            HTTPException: 토큰이 유효하지 않거나 만료된 경우
        """
        try:
            with get_db() as db:
                # 데이터베이스에서 토큰 조회
                db_token: Optional[TelegramToken] = db.query(TelegramToken).filter(
                    TelegramToken.token == token,
                    TelegramToken.is_active == 1,
                    TelegramToken.expires_at > datetime.now()
                ).first()

                if not db_token:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="유효하지 않거나 만료된 토큰입니다."
                    )

                # 토큰에서 인증 정보 추출하여 TeleprobeClient 생성
                client = TeleprobeClient(
                    api_id=db_token.api_id,
                    api_hash=db_token.api_hash,
                    session_string=db_token.session_string,
                    phone=db_token.phone
                )

                return client

        except HTTPException:
            raise
