"""Teleprobe 데이터 모델 패키지 - Pydantic 기반 데이터 모델 정의

이 패키지는 Teleprobe 시스템에서 사용되는 모든 데이터 모델들을 정의합니다.
Pydantic BaseModel을 기반으로 하여 데이터 검증, 직렬화/역직렬화, 타입 안전성을 보장하며,
API 요청/응답, 인증 정보, 설정 등의 구조화된 데이터를 관리합니다.

Teleprobe Data Model Package - Pydantic-based data model definitions

This package defines all data models used in the Teleprobe system.
Based on Pydantic BaseModel to ensure data validation, serialization/deserialization, and type safety,
it manages structured data such as API requests/responses, authentication information, and configurations.

Modules:
    auth: 텔레그램 인증 관련 데이터 모델
         Telegram authentication related data models

Models:
    TelegramCredentials: 텔레그램 API 자격증명 정보 모델
                        Telegram API credential information model

Examples:
    from teleprobe.models import TelegramCredentials

    # 인증 정보 생성
    credentials = TelegramCredentials(
        api_id=12345,
        api_hash="abcdef123456789",
        phone="+821012345678"
    )

    # 검증 및 정규화 자동 수행
    print(credentials.phone)  # "+821012345678"

Note:
    모든 모델은 Pydantic을 기반으로 하여 다음 기능을 제공합니다:
    - 자동 데이터 검증
    - 타입 안전성
    - JSON 직렬화/역직렬화
    - 필드 별칭 및 검증 규칙

    All models are based on Pydantic and provide the following features:
    - Automatic data validation
    - Type safety
    - JSON serialization/deserialization  
    - Field aliases and validation rules
"""

from .auth import TelegramCredentials