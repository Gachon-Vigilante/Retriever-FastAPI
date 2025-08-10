# TelegramCredentials 모델의 필드를 상속받아 새로운 모델 생성
from datetime import datetime
from typing import Annotated, Union, Optional

from fastapi import Path, Depends, HTTPException, status, Body
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from core.sqlite import get_db, TelegramToken
from teleprobe.base import TeleprobeClient
from teleprobe.models import TelegramCredentials


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
            db: Annotated[Session, Depends(get_db)]
    ) -> TeleprobeClient:
        """
        토큰을 사용하여 데이터베이스에서 인증 정보를 조회하고 TeleprobeClient를 생성합니다.

        Args:
            token: HTTP 헤더에서 전달받은 토큰
            db: 데이터베이스 세션

        Returns:
            TeleprobeClient 인스턴스

        Raises:
            HTTPException: 토큰이 유효하지 않거나 만료된 경우
        """
        try:
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
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"클라이언트 생성 중 오류 발생: {str(e)}"
            )

    @staticmethod
    def register(params: Annotated[TelegramCredentials, Depends()]) -> TeleprobeClient:
        """
            TelegramCredentials에서 제공된 자격 증명으로 TeleprobeClient 인스턴스를 생성하고 등록합니다.

            이 의존성 함수는 요청 파라미터에서 api_id, api_hash, session_string을
            추출하여 TeleprobeClient를 생성합니다.
            """
        try:
            # FastAPI의 각 요청은 별도의 이벤트 루프에서 실행되므로,
            # 기존 인스턴스가 있더라도 각 API 요청마다 새 인스턴스 생성
            client = TeleprobeClient.register(
                api_id=params.api_id,
                api_hash=params.api_hash,
                session_string=params.session_string,
                phone=params.phone
            )
            return client
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"텔레그램 클라이언트 생성 중 오류 발생: {str(e)}"
            )
