"""Teleprobe API 모델 및 유틸리티 모듈 - FastAPI 종속성과 데이터 모델

이 모듈은 Teleprobe API 엔드포인트에서 사용되는 FastAPI 종속성 함수들과
데이터 검증, 변환 유틸리티를 제공합니다. 채널 키 변환, 토큰 기반 클라이언트 인증,
Path 파라미터 정의 등의 공통 기능을 포함합니다.

Teleprobe API Models and Utilities Module - FastAPI dependencies and data models

This module provides FastAPI dependency functions and data validation/conversion utilities
used in Teleprobe API endpoints. It includes common functionality such as channel key conversion,
token-based client authentication, and Path parameter definitions.
"""

# TelegramCredentials 모델의 필드를 상속받아 새로운 모델 생성
from datetime import datetime
from typing import Annotated, Union, Optional

from fastapi import Path, HTTPException, status, Body
from pydantic import BeforeValidator

from core.sqlite import get_db, TelegramToken
from teleprobe.base import TeleprobeClient


# 채널 키 변환 및 검증 의존성 함수
def auto_convert_numeric_string(v: str) -> Union[int, str]:
    """숫자 형태의 문자열을 자동으로 정수로 변환하는 검증 함수

    채널 ID와 같은 숫자 문자열을 자동으로 정수 타입으로 변환합니다.
    음수 기호(-)가 포함된 채널 ID도 올바르게 처리합니다.
    숫자가 아닌 문자열은 그대로 반환합니다.

    Validation function to automatically convert numeric strings to integers

    Automatically converts numeric strings like channel IDs to integer type.
    Properly handles channel IDs that include negative sign (-).
    Non-numeric strings are returned as-is.

    Args:
        v (str): 변환할 문자열 값
                String value to convert

    Returns:
        Union[int, str]: 숫자 문자열인 경우 int, 아니면 원본 str
                        int if numeric string, otherwise original str

    Examples:
        auto_convert_numeric_string("-1001234567890")  # Returns: -1001234567890 (int)
        auto_convert_numeric_string("@channelname")    # Returns: "@channelname" (str)
        auto_convert_numeric_string("1234567890")      # Returns: 1234567890 (int)
    """
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
"""채널을 식별하기 위한 FastAPI Path 파라미터 타입 정의

채널 ID(정수), 사용자명(@username), 또는 초대 링크를 받아들이는 Path 파라미터입니다.
숫자 형태의 문자열은 자동으로 정수로 변환되며, 그 외는 문자열로 유지됩니다.

FastAPI Path parameter type definition for identifying channels

Path parameter that accepts channel ID (integer), username (@username), or invite link.
Numeric strings are automatically converted to integers, others remain as strings.

Type: Annotated[Union[int, str], BeforeValidator, Path]

Examples:
    @router.get("/channel/{channel_key}")
    async def get_channel(channel_key: channelKeyPath):
        # channel_key can be: -1001234567890 (int), "@channel" (str), or "https://t.me/+abc" (str)
        pass
"""


class TeleprobeClientManager:
    """TeleprobeClient 인스턴스 생성 및 관리를 위한 유틸리티 클래스

    액세스 토큰을 사용하여 데이터베이스에서 인증 정보를 조회하고
    인증된 TeleprobeClient 인스턴스를 생성하는 기능을 제공합니다.
    FastAPI 종속성 함수로 사용되어 API 엔드포인트에서 클라이언트 인증을 처리합니다.

    Utility class for creating and managing TeleprobeClient instances

    Provides functionality to retrieve authentication information from database using access tokens
    and create authenticated TeleprobeClient instances. Used as FastAPI dependency function
    to handle client authentication in API endpoints.

    Methods:
        get_client_by_token: 토큰으로 클라이언트 인스턴스 생성
                           Create client instance by token

    Examples:
        # FastAPI 종속성으로 사용
        @router.get("/some-endpoint")
        async def some_endpoint(
            client: TeleprobeClient = Depends(TeleprobeClientManager.get_client_by_token)
        ):
            # 인증된 클라이언트 사용
            pass
    """

    @staticmethod
    def get_client_by_token(
            token: Annotated[str, Body(description="인증 토큰")],
    ) -> TeleprobeClient:
        """토큰을 사용하여 인증된 TeleprobeClient를 생성하는 정적 메서드

        제공된 액세스 토큰을 데이터베이스에서 조회하여 유효성을 검증하고,
        해당 토큰에 연결된 텔레그램 자격증명으로 TeleprobeClient를 생성합니다.
        FastAPI 종속성 함수로 사용되어 API 엔드포인트의 인증을 처리합니다.

        Static method to create authenticated TeleprobeClient using token

        Validates provided access token by querying database and creates TeleprobeClient
        with Telegram credentials linked to that token. Used as FastAPI dependency function
        to handle authentication for API endpoints.

        Args:
            token (str): HTTP 요청에서 전달받은 Teleprobe 액세스 토큰
                        Teleprobe access token received from HTTP request

        Returns:
            TeleprobeClient: 인증된 클라이언트 인스턴스
                           Authenticated client instance

        Raises:
            HTTPException: 토큰이 유효하지 않거나 만료된 경우 401 Unauthorized
                          401 Unauthorized when token is invalid or expired

        Examples:
            # FastAPI 엔드포인트에서 사용
            @router.post("/watch-channel")
            async def watch_channel(
                channel_key: str,
                client: TeleprobeClient = Depends(TeleprobeClientManager.get_client_by_token)
            ):
                # client는 이미 인증된 상태
                await client.start_watching_channel(channel_key)

        Note:
            토큰 검증 조건:
            - 토큰이 데이터베이스에 존재
            - is_active = 1 (활성 상태)
            - expires_at > 현재 시간 (만료되지 않음)

            Token validation conditions:
            - Token exists in database
            - is_active = 1 (active status)
            - expires_at > current time (not expired)
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
