import re
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChannelStatus(str, Enum):
    """채널 상태 열거형"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESTRICTED = "restricted"
    BANNED = "banned"


class ChannelInfo(BaseModel):
    """텔레그램 채널 정보 모델

    텔레그램 채널의 기본 정보와 상태를 담는 데이터 모델입니다.
    """

    id: int = Field(
        title="채널 ID",
        description="텔레그램 채널의 고유 식별자",
        examples=[-1001234567890],
        serialization_alias="_id"
    )

    title: str = Field(
        title="채널 제목",
        description="채널의 공개 제목",
        examples=["테스트 채널", "뉴스 채널"],
        min_length=1,
    )

    username: Optional[str] = Field(
        default=None,
        title="채널 사용자명",
        description="채널의 공개 사용자명 (@username)",
        examples=["testchannel", "newschannel"],
        min_length=5,
        max_length=32,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$"
    )

    restricted: bool = Field(
        default=False,
        title="제한 여부",
        description="채널에 제한이 있는지 여부",
        examples=[False, True]
    )

    started_at: datetime = Field(
        title="생성 일시",
        description="채널이 생성된 일시",
        serialization_alias="startedAt",
        examples=["2024-01-01T00:00:00Z"]
    )

    discovered_at: datetime = Field(
        title="발견 일시",
        description="채널이 처음으로 발견된 일시",
        serialization_alias="discoveredAt",
        examples=["2024-01-01T12:00:00Z"],
        default_factory=datetime.now
    )

    status: ChannelStatus = Field(
        default=ChannelStatus.ACTIVE,
        title="채널 상태",
        description="채널의 현재 상태",
        examples=["active", "inactive"]
    )

    # 추가적인 메타데이터 필드들
    subscriber_count: Optional[int] = Field(
        default=None,
        title="구독자 수",
        description="채널의 구독자 수 (공개되는 경우)",
        serialization_alias="subscriberCount",
        ge=0
    )

    is_verified: Optional[bool] = Field(
        default=None,
        title="인증 여부",
        description="텔레그램에서 인증한 채널인지 여부",
        serialization_alias="isVerified"
    )

    description: Optional[str] = Field(
        default=None,
        title="채널 설명",
        description="채널의 상세 설명",
        max_length=1000
    )

    photo_url: Optional[str] = Field(
        default=None,
        title="프로필 사진 URL",
        description="채널 프로필 사진의 URL",
        serialization_alias="photoUrl"
    )

    last_message_date: Optional[datetime] = Field(
        default=None,
        title="마지막 메시지 일시",
        description="채널에서 마지막으로 게시된 메시지의 일시",
        serialization_alias="lastMessageDate"
    )

    @classmethod
    @field_validator('username')
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """사용자명 검증

        텔레그램 사용자명 규칙에 따라 검증합니다:
        - 5-32자 길이
        - 영문자로 시작
        - 영문자, 숫자, 밑줄(_)만 허용
        - 마지막은 밑줄이 아니어야 함
        """
        if v is None:
            return v

        # @로 시작하는 경우 제거
        if v.startswith('@'):
            v = v[1:]

        # 빈 문자열 체크
        if not v.strip():
            return None

        # 길이 체크
        if len(v) < 5 or len(v) > 32:
            raise ValueError('사용자명은 5-32자 사이여야 합니다')

        # 패턴 체크
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*[a-zA-Z0-9]$', v):
            raise ValueError('사용자명은 영문자로 시작하고, 영문자/숫자/밑줄만 포함할 수 있으며, 밑줄로 끝날 수 없습니다')

        return v

    @classmethod
    @field_validator('title')
    def validate_title(cls, v: str) -> str:
        """채널 제목 검증 및 정규화"""
        if not v or not v.strip():
            raise ValueError('채널 제목은 필수 필드입니다.')

        # 앞뒤 공백 제거
        title = v.strip()

        # 연속된 공백을 단일 공백으로 변환
        title = re.sub(r'\s+', ' ', title)

        return title

    @classmethod
    @field_validator('status')
    def validate_status(cls, v: str) -> ChannelStatus:
        """상태 검증"""
        if isinstance(v, str):
            try:
                return ChannelStatus(v.lower())
            except ValueError:
                raise ValueError(f'유효하지 않은 채널 상태: {v}. 허용된 값: {", ".join([s.value for s in ChannelStatus])}')
        return v

    def is_public(self) -> bool:
        """공개 채널인지 확인"""
        return self.username is not None

    def is_active(self) -> bool:
        """활성 상태인지 확인"""
        return self.status == ChannelStatus.ACTIVE

    def days_since_created(self) -> int:
        """생성 후 경과 일수"""
        return (datetime.now() - self.started_at).days

    def days_since_discovered(self) -> int:
        """발견 후 경과 일수"""
        return (datetime.now() - self.discovered_at).days



    # 이전 버전 호환성을 위한 Config 클래스
    class Config:
        """Pydantic 설정"""
        # Pydantic v2용 설정
        model_config = {
            # JSON 스키마에서 enum 값들을 표시
            "use_enum_values": True,
            # 별칭 허용
            "validate_by_name": True,
            # JSON 직렬화 시 모델 인스턴스 제외
            "arbitrary_types_allowed": True,
            # datetime 직렬화 방식
            "json_schema_extra": {
                "example": {
                    "id": -1001234567890,
                    "title": "테스트 채널",
                    "username": "testchannel",
                    "restricted": False,
                    "started_at": "2024-01-01T00:00:00Z",
                    "discovered_at": "2024-01-01T12:00:00Z",
                    "status": "active"
                }
            }
        }
        # JSON 스키마에서 enum 값들을 표시
        use_enum_values = True
        # datetime을 ISO 형식으로 직렬화
        json_encoders = {
            datetime: lambda dt: dt.isoformat() if dt else None
        }
        # 별칭 허용
        validate_by_name = True
        # JSON 직렬화 시 모델 인스턴스 제외
        arbitrary_types_allowed = True
