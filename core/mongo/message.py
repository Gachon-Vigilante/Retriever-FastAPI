from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel, Field
from telethon.tl.types import Message as TelethonMessage

from .types import SenderType
from .connections import MongoCollections
from utils import get_logger

logger = get_logger()


class Message(BaseModel):
    """텔레그램 메시지 모델 (Telethon Message 기반)"""
    oid: Optional[str] = Field(
        default=None,
        title="Object ID",
        description="MongoDB object ID (string representation)",
        exclude=True # MongoDB에 json 직렬화 후 삽입 시 충돌을 방지하기 위해 직렬화 시에는 제외
    )

    # === 채팅 정보 ===
    chat_id: Optional[int] = Field(
        default=None,
        title="채팅 ID",
        description="메시지가 속한 채팅(채널/그룹)의 ID",
        examples=[1234567890]
    )

    # === 기본 정보 ===
    id: int = Field(
        title="메시지 ID",
        description="텔레그램 채팅 내에서의 메시지 고유 번호",
        examples=[12345],
        ge=1,
    )

    message: Optional[str] = Field(
        default=None,
        title="메시지 내용",
        description="메시지의 텍스트 내용",
        examples=["안녕하세요!", "https://example.com"],
        max_length=4096  # 텔레그램 메시지 최대 길이
    )

    date: datetime = Field(
        title="전송 시간",
        description="메시지가 전송된 시간",
        examples=["2024-01-01T12:00:00Z"]
    )

    # === 커스텀 정보 ===
    collected_at: datetime = Field(
        default_factory=datetime.now,
        title="수집 시각",
        description="채팅을 발견하고 수집한 시각"
    )

    # === 발신자 정보 ===
    from_id: Optional[int] = Field(
        default=None,
        title="발신자 ID",
        description="메시지를 보낸 사용자 또는 채널의 ID",
        examples=[123456789]
    )
    sender_type: Optional[SenderType] = Field(
        default=None,
        title="발신자 유형",
        description="메세지를 보낸 객체의 유형(user 혹은 channel)",
        examples=["channel", "user"],
    )

    # === 메시지 타입 및 상태 ===
    out: bool = Field(
        default=False,
        title="발신 메시지 여부",
        description="내가 보낸 메시지인지 여부"
    )

    mentioned: bool = Field(
        default=False,
        title="멘션 여부",
        description="이 메시지에서 나를 멘션했는지 여부"
    )

    media_unread: bool = Field(
        default=False,
        title="미디어 미읽음 여부",
        description="미디어가 아직 읽히지 않았는지 여부"
    )

    silent: bool = Field(
        default=False,
        title="조용한 메시지 여부",
        description="알림 없이 전송된 메시지인지 여부"
    )

    # === 답글 및 전달 정보 ===
    reply_to_msg_id: Optional[int] = Field(
        default=None,
        title="답글 대상 메시지 ID",
        description="이 메시지가 답글인 경우, 원본 메시지의 ID",
        examples=[12340]
    )

    fwd_from_id: Optional[int] = Field(
        default=None,
        title="전달 원본 발신자 ID",
        description="전달된 메시지인 경우, 원본 발신자의 ID"
    )

    fwd_from_name: Optional[str] = Field(
        default=None,
        title="전달 원본 발신자 이름",
        description="전달된 메시지인 경우, 원본 발신자의 이름"
    )

    fwd_date: Optional[datetime] = Field(
        default=None,
        title="전달 원본 날짜",
        description="전달된 메시지인 경우, 원본 메시지의 전송 시간"
    )

    # === 미디어 정보 ===
    media: Any = Field(
        default=None,
        title="미디어 정보",
        description="첨부된 미디어 파일 정보"
    )

    # === 메시지 포맷팅 ===
    entities: Any = Field(
        default_factory=list,
        title="메시지 엔티티",
        description="메시지 내 특수 요소들 (링크, 멘션, 포맷팅 등)"
    )

    # === 편집 정보 ===
    edit_date: Optional[datetime] = Field(
        default=None,
        title="편집 시간",
        description="메시지가 마지막으로 편집된 시간"
    )

    edit_hide: bool = Field(
        default=False,
        title="편집 숨김 여부",
        description="편집 표시를 숨길지 여부"
    )

    # === 조회수 및 반응 ===
    views: Optional[int] = Field(
        default=None,
        title="조회수",
        description="메시지 조회수 (채널 메시지인 경우)",
        ge=0
    )

    forwards: Optional[int] = Field(
        default=None,
        title="전달 수",
        description="메시지가 전달된 횟수",
        ge=0
    )

    reactions: Any = Field(
        default_factory=list,
        title="반응 목록",
        description="메시지에 달린 반응들"
    )

    # === 봇 관련 ===
    via_bot_id: Optional[int] = Field(
        default=None,
        title="경유 봇 ID",
        description="인라인 봇을 통해 전송된 경우 해당 봇의 ID"
    )

    # === 기타 메타데이터 ===
    post: bool = Field(
        default=False,
        title="포스트 여부",
        description="채널 포스트인지 여부"
    )

    legacy: bool = Field(
        default=False,
        title="레거시 메시지 여부",
        description="구 버전 텔레그램에서 온 메시지인지 여부"
    )

    grouped_id: Optional[int] = Field(
        default=None,
        title="그룹 ID",
        description="미디어 그룹인 경우의 그룹 ID"
    )

    model_config = {
        "json_encoders": {
            datetime: lambda dt: dt.isoformat() if dt else None
        },
        "json_schema_extra": {
            "example": {
                "id": 12345,
                "message": "안녕하세요! 이것은 예시 메시지입니다.",
                "date": "2024-01-01T12:00:00Z",
                "from_id": 123456789,
                "chat_id": -1001234567890,
                "out": False,
                "mentioned": False,
                "media": None,
                "entities": [],
                "views": 150,
                "reactions": [
                    {"emoticon": "👍", "count": 5, "chosen": False}
                ]
            }
        }
    }

    def __init__(self, **data):
        super().__init__(**data)
        if _id := data.get("_id"):
            self.oid = str(data["_id"])

    @classmethod
    def from_telethon(
            cls,
            telethon_message: TelethonMessage,
            sender_id: Optional[int] = None,
            chat_id: Optional[int] = None,
            sender_type: Optional[SenderType] = None,
    ) -> 'Message':
        """Telethon Message 객체에서 변환"""
        return cls(
            id=telethon_message.id,
            message=telethon_message.message,
            date=telethon_message.date,
            from_id=sender_id,
            sender_type=sender_type,
            chat_id=chat_id,
            out=telethon_message.out,
            mentioned=telethon_message.mentioned,
            media_unread=telethon_message.media_unread,
            silent=telethon_message.silent,
            edit_date=telethon_message.edit_date,
            views=telethon_message.views,
            forwards=telethon_message.forwards,
            post=telethon_message.post,
            legacy=telethon_message.legacy,
            grouped_id=telethon_message.grouped_id,
            # 미디어와 엔티티는 별도 처리 필요
            media=None,
            entities=[],
        )

    def __eq__(self, other):
        return self.id == other.id and self.chat_id == other.chat_id and self.message == other.message

    def store(self):
        chat_collection = MongoCollections().chats
        existing_message = chat_collection.find_one({"id": self.id, "chat_id": self.chat_id})
        if existing_message:
            if self == Message(**existing_message):
                return
            else:
                logger.debug(f"[MongoMessage] 기존에 저장된 메세지 중 수정된 메세지가 발견되었습니다. "
                             f"Message ID: {self.id}, Chat|Channel ID: {self.chat_id}")
        chat_collection.insert_one(self.model_dump())