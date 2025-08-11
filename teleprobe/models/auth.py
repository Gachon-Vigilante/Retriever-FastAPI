"""텔레그램 인증 정보 모델 - API 자격증명 데이터 검증 및 정규화

이 모듈은 텔레그램 API 인증에 필요한 자격증명 정보를 관리하는 Pydantic 모델을 정의합니다.
API ID, API Hash, 전화번호, 세션 문자열 등의 인증 데이터를 검증하고 정규화하며,
특히 전화번호의 국제 형식 자동 변환 기능을 제공합니다.

Telegram Authentication Information Model - API credential data validation and normalization

This module defines Pydantic models for managing credential information required for Telegram API authentication.
It validates and normalizes authentication data such as API ID, API Hash, phone number, and session string,
with special focus on automatic international format conversion for phone numbers.
"""

import re
from typing import Optional

from pydantic import Field, BaseModel, field_validator


class TelegramCredentials(BaseModel):
    """텔레그램 API 인증 자격증명을 나타내는 Pydantic 모델

    텔레그램 개발자 포털에서 발급받은 API 자격증명과 인증 과정에서 생성되는
    세션 정보를 저장하고 검증합니다. 전화번호 자동 정규화, API Hash 형식 검증,
    보안을 위한 필드 제외 등의 기능을 제공합니다.

    Pydantic model representing Telegram API authentication credentials

    Stores and validates API credentials issued from Telegram developer portal
    and session information generated during authentication process.
    Provides features like automatic phone number normalization, API Hash format validation,
    and field exclusion for security.

    Attributes:
        phone (Optional[str]): 국제 형식으로 정규화되는 전화번호
                              Phone number normalized to international format
                              - 한국 번호 자동 감지 및 +82 변환
                              - 하이픈, 공백 자동 제거

        api_id (int): 텔레그램 개발자 포털에서 발급받은 API ID
                     API ID issued from Telegram developer portal
                     - 양수 값만 허용
                     - 필수 필드

        api_hash (Optional[str]): 텔레그램 API Hash (32자 16진수)
                                 Telegram API Hash (32-character hexadecimal)
                                 - 직렬화 시 보안을 위해 제외
                                 - 32자 16진수 패턴 검증

        session_string (Optional[str]): 텔레그램 클라이언트 세션 문자열
                                       Telegram client session string
                                       - 직렬화 시 보안을 위해 제외
                                       - 인증 완료 후 저장

    Examples:
        # 기본 사용법
        credentials = TelegramCredentials(
            api_id=12345678,
            api_hash="0123456789abcdef0123456789abcdef",
            phone="010-1234-5678"
        )

        # 전화번호 자동 정규화
        print(credentials.phone)  # "+821012345678"

        # JSON 직렬화 (보안 필드 제외)
        json_data = credentials.model_dump_json()
        # api_hash와 session_string은 포함되지 않음

    Note:
        보안 고려사항:
        - api_hash와 session_string은 exclude=True로 설정되어 직렬화에서 제외
        - 로그나 API 응답에 민감한 정보가 노출되지 않음
        - 데이터베이스 저장 시에는 별도로 처리 필요

        Security considerations:
        - api_hash and session_string are excluded from serialization
        - Prevents exposure of sensitive information in logs or API responses
        - Requires separate handling when storing in database
    """
    phone: Optional[str] = Field(
        default=None,
        title="전화번호",  # JSON Schema title
        description="국제 형식으로 정규화되는 전화번호",
        examples=[
            "+821012345678",
            "+8201012345678",
            "+82-01012345678",
            "+82-010-1234-5678",
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
        """전화번호를 검증하고 국제 형식으로 정규화하는 클래스 메서드

        입력된 전화번호를 분석하여 형식을 검증하고 국제 표준 형식으로 변환합니다.
        한국 전화번호의 경우 자동으로 +82 국가 코드를 추가하고,
        이미 국제 형식인 경우 하이픈과 공백만 제거합니다.

        Class method to validate and normalize phone number to international format

        Analyzes input phone number to validate format and convert to international standard format.
        For Korean phone numbers, automatically adds +82 country code,
        and for already international format, only removes hyphens and spaces.

        Args:
            v: 검증할 전화번호 값 (str 또는 None)
              Phone number value to validate (str or None)

        Returns:
            Optional[str]: 정규화된 국제 형식 전화번호 또는 None
                          Normalized international format phone number or None

        Raises:
            TypeError: 전화번호가 문자열이 아닌 경우
                      When phone number is not a string
            ValueError: 전화번호 형식이 올바르지 않은 경우
                       When phone number format is incorrect

        Examples:
            # 한국 번호 (하이픈 포함)
            result = validate_and_normalize_phone("010-1234-5678")
            # Returns: "+821012345678"

            # 한국 번호 (하이픈 없음)  
            result = validate_and_normalize_phone("01012345678")
            # Returns: "+821012345678"

            # 이미 국제 형식
            result = validate_and_normalize_phone("+82-10-1234-5678")
            # Returns: "+821012345678"

            # None 값
            result = validate_and_normalize_phone(None)
            # Returns: None

        Note:
            지원되는 한국 전화번호 형식:
            - "010-xxxx-xxxx" (표준 형식)
            - "10-xxxx-xxxx" (010에서 0 생략)
            - "010 xxxx xxxx" (공백 구분)
            - "01xxxxxxxxx" (구분자 없음)

            국제 형식은 + 기호로 시작하는 모든 형식을 지원합니다.

            Supported Korean phone number formats:
            - "010-xxxx-xxxx" (standard format)
            - "10-xxxx-xxxx" (omitting 0 from 010)
            - "010 xxxx xxxx" (space separated)
            - "01xxxxxxxxx" (no separators)

            International format supports all formats starting with + symbol.
        """
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
