import re
from typing import Optional

from pydantic import Field, BaseModel, field_validator


class TelegramCredentials(BaseModel):
    phone: Optional[str] = Field(
        default=None,
        title="전화번호",  # JSON Schema title
        description="국제 형식으로 정규화되는 전화번호",
        examples=[
            "+82-010-1234-5678",
            "+82-01012345678",
            "+8201012345678",
            "+821012345678",
            "01012345678",
        ],
        min_length=10,  # 최소 길이
        max_length=20,  # 최대 길이
    )
    api_id: int = Field(
        title="Telegram API ID",
        description="Telegram 개발자 포털에서 발급받은 API ID",
        examples=[12345678],
        serialization_alias="apiId",
        gt=0,
        json_schema_extra = {
            "format": "number",
            "placeholder": "12345678"
        },
    )

    api_hash: Optional[str] = Field(
        default=None,
        title="Telegram API Hash",
        description="Telegram 개발자 포털에서 발급받은 API Hash",
        examples=["0123456789abcdef0123456789abcdef"],
        serialization_alias="apiHash",
        min_length=32,
        max_length=32,
        pattern=r"^[a-fA-F0-9]{32}$",
        json_schema_extra={
            "format": "password",  # 입력 시 비밀번호처럼 표시됨
            "placeholder": "Enter your API Hash"
        },
        exclude=True,  # 직렬화 시 제외되어 반환되지 않음 (보안)
    )
    session_string: Optional[str] = Field(
        default=None,
        title="Telegram Session String",
        description="Telegram client로 발급받은 Session String",
        serialization_alias="apiHash",
        min_length=1,
        json_schema_extra={
            "format": "password",  # 입력 시 비밀번호처럼 표시됨
            "placeholder": "Enter your Session String"
        },
        exclude=True,  # 직렬화 시 제외되어 반환되지 않음 (보안)
    )


    @classmethod
    @field_validator('phone')
    def validate_and_normalize_phone(cls, v):
        # 기본값(None)일 경우 무시
        if v is None:
            return None
        elif not isinstance(v, str):
            raise TypeError(f'전화번호는 문자열이어야 합니다. 현재 타입: {type(v)}')

        # 1. 먼저 국제번호인지 확인 (+로 시작하는지)
        if v.strip().startswith('+'):
            # 국제번호라면 하이픈과 공백을 모두 제거하고 반환
            cleaned = re.sub(r'[-\s]', '', v)
            return cleaned

        # 2. 국제번호가 아니라면 한국 번호 형식인지 확인

        # 하이픈이나 공백이 있는지 확인
        has_separators = '-' in v or ' ' in v

        if has_separators:
            # 하이픈/공백이 있을 경우: 한국 전화번호 형식에 맞는지 확인
            patterns = [
                r'^010-\d{4}-\d{4}$',  # 010-1234-5678
                r'^10-\d{4}-\d{4}$',  # 10-1234-5678
                r'^010\s\d{4}\s\d{4}$',  # 010 1234 5678
                r'^10\s\d{4}\s\d{4}$',  # 10 1234 5678
            ]

            is_valid_format = any(re.match(pattern, v) for pattern in patterns)
            if not is_valid_format:
                raise ValueError('국가번호 없이 입력되었지만, 한국 개인 전화번호 형식에 맞지 않습니다. (010-xxxx-xxxx 또는 10-xxxx-xxxx)')

        else:
            # 하이픈/공백이 없을 경우: 길이 확인
            if not (re.match(r'^010\d{8}$', v) or re.match(r'^10\d{8}$', v)):
                raise ValueError('국가번호 없이 입력되었지만, 한국 개인 전화번호 길이에 맞지 않습니다. (010xxxxxxxx 또는 10xxxxxxxx)')

        # 3. 한국 번호가 맞다면 +82 추가하고 하이픈/공백 제거
        cleaned = re.sub(r'[-\s]', '', v)

        # 010으로 시작하는 경우 0 제거, 10으로 시작하는 경우 그대로
        if cleaned.startswith('010'):
            normalized = '+82' + cleaned[1:]  # 맨 앞 0 제거
        else:  # 10으로 시작
            normalized = '+82' + cleaned

        return normalized
