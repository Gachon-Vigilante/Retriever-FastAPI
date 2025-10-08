import re
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from telethon.tl.types import Channel as TelethonChannel

from utils import Logger

from .types import ChannelStatus
from .connections import MongoCollections
from .base import BaseMongoObject


logger = Logger(__name__)

protected_fields = [
    "updated_at", "last_message_date", "monitoring", "status"
]

class ChannelRestrictionReason(BaseModel):
    """채널 제한 사유"""
    platform: str = Field(description="플랫폼 (ios, android, web 등)")
    reason: str = Field(description="제한 사유")
    text: str = Field(description="제한 메시지")


class Channel(BaseMongoObject):
    """텔레그램 채널 정보 모델

    Telethon의 Channel 클래스의 모든 핵심 속성을 포함하는 완전한 채널 모델입니다.
    """

    # === 기본 식별 정보 ===
    id: int = Field(
        title="채널 ID",
        description="텔레그램 채널의 고유 식별자",
        examples=[1234567890],
        serialization_alias="id"
    )

    access_hash: Optional[int] = Field(
        default=None,
        title="액세스 해시",
        description="채널 접근을 위한 해시값",
        serialization_alias="accessHash"
    )

    title: str = Field(
        title="채널 제목",
        description="채널의 공개 제목",
        examples=["테스트 채널", "뉴스 채널"],
        min_length=1,
        max_length=255
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

    # === 채널 생성 및 시간 정보 ===
    date: datetime = Field(
        title="생성 일시",
        description="채널이 생성된 일시",
        examples=["2024-01-01T00:00:00Z"]
    )

    updated_at: datetime = Field(
        title="발견 일시",
        description="채널의 변경사항이 마지막으로 발견된 일시(최초 발견 포함)",
        examples=["2024-01-01T12:00:00Z"],
        default_factory=datetime.now
    )
    checked_at: datetime = Field(
        title="확인 일시",
        description="채널의 변경사항을 마지막으로 확인한 일시(최초 발견 포함)",
        examples=["2024-01-01T12:00:00Z"],
        default_factory=datetime.now
    )

    left: bool = Field(
        default=False,
        title="탈퇴 여부",
        description="현재 사용자가 이 채널을 떠났는지 여부"
    )

    broadcast: bool = Field(
        default=True,
        title="방송 채널 여부",
        description="일반 방송 채널인지 여부 (vs 메가그룹)"
    )

    verified: bool = Field(
        default=False,
        title="인증 여부",
        description="텔레그램에서 공식 인증한 채널인지 여부"
    )

    megagroup: bool = Field(
        default=False,
        title="메가그룹 여부",
        description="메가그룹(대규모 그룹)인지 일반 채널인지"
    )

    # === 제한 및 상태 ===
    restricted: bool = Field(
        default=False,
        title="제한 여부",
        description="채널에 제한이 있는지 여부"
    )

    signatures: bool = Field(
        default=False,
        title="서명 표시 여부",
        description="메시지에 작성자 서명을 표시하는지 여부"
    )

    min: bool = Field(
        default=False,
        title="최소 정보 여부",
        description="최소한의 정보만 포함된 객체인지 여부"
    )

    scam: bool = Field(
        default=False,
        title="스캠 여부",
        description="스캠으로 분류된 채널인지 여부"
    )

    has_link: bool = Field(
        default=False,
        title="링크 보유 여부",
        description="공개 링크를 가지고 있는지 여부",
    )

    has_geo: bool = Field(
        default=False,
        title="지역 정보 여부",
        description="지리적 위치 정보를 가지고 있는지 여부",
    )

    slowmode_enabled: bool = Field(
        default=False,
        title="슬로우 모드 여부",
        description="슬로우 모드가 활성화되어 있는지 여부",
    )

    call_active: bool = Field(
        default=False,
        title="음성채팅 활성 여부",
        description="음성채팅이 진행 중인지 여부",
    )

    call_not_empty: bool = Field(
        default=False,
        title="음성채팅 참여자 존재 여부",
        description="음성채팅에 참여자가 있는지 여부",
    )

    fake: bool = Field(
        default=False,
        title="가짜 계정 여부",
        description="가짜 계정으로 분류된 채널인지 여부"
    )

    gigagroup: bool = Field(
        default=False,
        title="기가그룹 여부",
        description="기가그룹(초대형 그룹)인지 여부"
    )

    noforwards: bool = Field(
        default=False,
        title="전달 금지 여부",
        description="메시지 전달이 금지되어 있는지 여부"
    )

    # === 참여자 및 통계 ===
    participants_count: Optional[int] = Field(
        default=None,
        title="참여자 수",
        description="채널의 총 참여자(구독자) 수",
        ge=0
    )

    # === 제한 정보 ===
    restriction_reason: List[ChannelRestrictionReason] = Field(
        default_factory=list,
        title="제한 사유",
        description="채널이 제한된 이유들",
    )

    # === 추가 메타데이터 ===
    photo: Optional[Any] = Field(
        default=None,
        title="프로필 사진",
        description="채널 프로필 사진 정보"
    )

    about: Optional[str] = Field(
        default=None,
        title="채널 소개",
        description="채널의 상세 소개글",
        max_length=500
    )

    # === 커스텀 상태 및 분석 ===
    status: ChannelStatus = Field(
        default=ChannelStatus.ACTIVE,
        title="채널 상태",
        description="채널의 현재 상태 (커스텀 필드)",
        examples=["active", "inactive"]
    )

    last_message_date: Optional[datetime] = Field(
        default=None,
        title="마지막 메시지 일시",
        description="채널에서 마지막으로 게시된 메시지의 일시",
    )

    monitoring: bool = Field(
        default=False,
        title="모니터링 여부",
        description="채널을 모니터링하고 있는지 여부"
    )

    # === 검증 메서드들 ===
    @classmethod
    @field_validator('username')
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """사용자명 검증 및 정규화"""
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

        title = v.strip()
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

    # === 유틸리티 메서드들 ===
    def is_public(self) -> bool:
        """공개 채널인지 확인"""
        return self.username is not None

    def is_active(self) -> bool:
        """활성 상태인지 확인"""
        return self.status == ChannelStatus.ACTIVE

    def is_channel(self) -> bool:
        """일반 채널인지 확인 (vs 그룹)"""
        return self.broadcast and not self.megagroup

    def is_group(self) -> bool:
        """그룹인지 확인"""
        return not self.broadcast or self.megagroup

    def is_supergroup(self) -> bool:
        """슈퍼그룹인지 확인"""
        return not self.broadcast and self.megagroup

    def has_admin_rights(self) -> bool:
        """관리자 권한이 있는지 확인"""
        return self.admin_rights is not None

    def days_since_created(self) -> int:
        """생성 후 경과 일수"""
        return (datetime.now() - self.date).days

    def days_since_discovered(self) -> int:
        """발견 후 경과 일수"""
        return (datetime.now() - self.updated_at).days

    # === Telethon 변환 메서드 ===
    @classmethod
    def from_telethon(cls, telethon_channel: TelethonChannel) -> 'Channel':
        """Telethon Channel 객체에서 변환"""

        # 제한 사유 변환
        restriction_reasons = []
        if getattr(telethon_channel, 'restriction_reason', None):
            for reason in telethon_channel.restriction_reason:
                restriction_reasons.append(ChannelRestrictionReason(
                    platform=reason.platform,
                    reason=reason.reason,
                    text=reason.text
                ))

        return cls(
            id=telethon_channel.id,
            access_hash=telethon_channel.access_hash,
            title=telethon_channel.title,
            username=telethon_channel.username,
            date=telethon_channel.date,
            left=telethon_channel.left,
            broadcast=telethon_channel.broadcast,
            verified=telethon_channel.verified,
            megagroup=telethon_channel.megagroup,
            restricted=telethon_channel.restricted,
            signatures=telethon_channel.signatures,
            min=telethon_channel.min,
            scam=telethon_channel.scam,
            has_link=telethon_channel.has_link,
            has_geo=telethon_channel.has_geo,
            slowmode_enabled=telethon_channel.slowmode_enabled,
            call_active=telethon_channel.call_active,
            call_not_empty=telethon_channel.call_not_empty,
            fake=telethon_channel.fake,
            gigagroup=telethon_channel.gigagroup,
            noforwards=telethon_channel.noforwards,
            participants_count=telethon_channel.participants_count,
            restriction_reason=restriction_reasons,
            # photo 오브젝트에도 대응할 수 있도록 구현해야 함
            # photo=telethon_channel.photo,
        )

    model_config = ConfigDict(
        **BaseMongoObject.model_config,
        use_enum_values=True,
        json_encoders={
            datetime: lambda dt: dt.isoformat() if dt else None
        },
        json_schema_extra={
            "example": {
                "id": 1234567890,
                "title": "테스트 채널",
                "username": "testchannel",
                "date": "2024-01-01T00:00:00Z",
                "broadcast": True,
                "verified": False,
                "megagroup": False,
                "restricted": False,
                "participants_count": 1500,
                "status": "active"
            }
        }
    )

    def model_dump_only_insert(self):
        return {k: v for k, v in self.model_dump().items() if k in self.protected_fields}

    def model_dump_only_update(self):
        return {k: v for k, v in self.model_dump().items() if k not in self.protected_fields}

    def store(self) -> None:
        channel_collection = MongoCollections().channels
        try:
            result = channel_collection.find_one_and_update(
                {"id": self.id, "username": self.username, "title": self.title},
                {"$set": self.model_dump_only_update(),
                 "$setOnInsert": self.model_dump_only_insert(),},
                sort=[("checked_at", -1)],
                upsert=True,
                return_document=ReturnDocument.BEFORE
            )
            if result:
                logger.info(f"이미 존재하는 채널이 발견되었습니다. 채널 정보를 업데이트합니다. Channel ID: {self.id}")
            else:
                logger.info(f"새로운 채널, 또는 핵심 정보가 변경된 채널을 수집하여 새 아카이브를 생성했습니다. "
                            f"Channel ID: {self.id}, username: {self.username}, title: {self.title}")

        except DuplicateKeyError:
            logger.info(f"채널 정보의 동시 생성이 감지되었습니다. Channel ID: {self.id}")