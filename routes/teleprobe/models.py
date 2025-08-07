# TelegramCredentials 모델의 필드를 상속받아 새로운 모델 생성
from typing import Annotated, Union
from pydantic import BeforeValidator

from fastapi import Path


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
