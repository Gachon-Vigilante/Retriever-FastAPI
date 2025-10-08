"""텔레그램 메시지 모델 모듈 - Telethon 기반 메시지 데이터 처리

이 모듈은 Telethon에서 수집된 텔레그램 메시지를 MongoDB에 저장하기 위한
Pydantic 모델을 정의합니다. 메시지의 모든 속성을 포함하며, 데이터 검증,
직렬화, MongoDB 저장 기능을 제공합니다.

Telegram Message Model Module - Telethon-based message data processing

This module defines Pydantic models for storing Telegram messages collected
from Telethon in MongoDB. It includes all message attributes and provides
data validation, serialization, and MongoDB storage functionality.
"""

from datetime import datetime
from typing import Optional, Any

import pymongo
from pydantic import Field, ConfigDict
from pymongo.errors import DuplicateKeyError
from telethon.tl.types import Message as TelethonMessage

from utils import Logger
from .base import BaseMongoObject
from .connections import MongoCollections
from .types import SenderType

logger = Logger(__name__)

protected_fields = [
    "updated_at"
]

class Message(BaseMongoObject):
    """텔레그램 메시지를 나타내는 MongoDB 문서 모델 (Telethon Message 기반)

    Telethon에서 수집된 텔레그램 메시지의 모든 정보를 저장하는 Pydantic 모델입니다.
    메시지 내용, 발신자 정보, 미디어, 전달/답글 관계, 반응 등의 데이터를 포함하며,
    MongoDB에 저장하고 조회할 수 있는 기능을 제공합니다.

    MongoDB document model representing Telegram messages (based on Telethon Message)

    A Pydantic model that stores all information from Telegram messages collected through Telethon.
    Includes message content, sender information, media, forward/reply relationships, reactions, etc.,
    and provides functionality to store and retrieve from MongoDB.

    Attributes:
        chat_id (Optional[int]): 메시지가 속한 채팅(채널/그룹)의 ID
                               ID of the chat (channel/group) the message belongs to
        id (int): 텔레그램 채팅 내에서의 메시지 고유 번호
                 Unique message number within the Telegram chat
        message (Optional[str]): 메시지의 텍스트 내용 (최대 4096자)
                               Text content of the message (max 4096 characters)
        date (datetime): 메시지가 전송된 시간
                        Time when the message was sent
        updated_at (datetime): 메시지를 수집한 시각
                               Time when the message was collected
        from_id (Optional[int]): 메시지를 보낸 사용자 또는 채널의 ID
                               ID of the user or channel that sent the message
        sender_type (Optional[SenderType]): 발신자 유형 (user 또는 channel)
                                          Sender type (user or channel)
        out (bool): 내가 보낸 메시지인지 여부
                   Whether this is an outgoing message
        mentioned (bool): 이 메시지에서 나를 멘션했는지 여부
                         Whether I was mentioned in this message
        media_unread (bool): 미디어가 아직 읽히지 않았는지 여부
                           Whether media is still unread
        silent (bool): 알림 없이 전송된 메시지인지 여부
                      Whether message was sent silently
        reply_to_msg_id (Optional[int]): 답글 대상 메시지의 ID
                                       ID of the message being replied to
        fwd_from_id (Optional[int]): 전달된 메시지의 원본 발신자 ID
                                    Original sender ID of forwarded message
        fwd_from_name (Optional[str]): 전달된 메시지의 원본 발신자 이름
                                     Original sender name of forwarded message
        fwd_date (Optional[datetime]): 전달된 메시지의 원본 전송 시간
                                     Original send time of forwarded message
        media (Any): 첨부된 미디어 파일 정보
                    Attached media file information
        entities (Any): 메시지 내 특수 요소들 (링크, 멘션, 포맷팅 등)
                       Special elements in message (identifiers, mentions, formatting, etc.)
        edit_date (Optional[datetime]): 메시지가 마지막으로 편집된 시간
                                      Time when message was last edited
        edit_hide (bool): 편집 표시를 숨길지 여부
                         Whether to hide edit indication
        views (Optional[int]): 메시지 조회수 (채널 메시지인 경우)
                             Message view count (for channel messages)
        forwards (Optional[int]): 메시지가 전달된 횟수
                                Number of times message was forwarded
        reactions (Any): 메시지에 달린 반응들
                        Reactions attached to the message
        via_bot_id (Optional[int]): 인라인 봇을 통해 전송된 경우 해당 봇의 ID
                                  ID of inline bot if sent through one
        post (bool): 채널 포스트인지 여부
                    Whether this is a channel post
        legacy (bool): 구 버전 텔레그램에서 온 메시지인지 여부
                      Whether message is from legacy Telegram version
        grouped_id (Optional[int]): 미디어 그룹인 경우의 그룹 ID
                                  Group ID if part of media group

    Examples:
        # Telethon 메시지로부터 생성
        message = Message.from_telethon(telethon_msg, sender_id=123, chat_id=456)

        # MongoDB에 저장
        message.store()

        # 메시지 비교
        if message1 == message2:
            print("동일한 메시지입니다")
    """

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
    updated_at: datetime = Field(
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

    model_config = ConfigDict(
        **BaseMongoObject.model_config,
        json_encoders = {
            datetime: lambda dt: dt.isoformat() if dt else None
        },
        json_schema_extra = {
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
    )

    @classmethod
    def from_telethon(
            cls,
            telethon_message: TelethonMessage,
            sender_id: Optional[int] = None,
            chat_id: Optional[int] = None,
            sender_type: Optional[SenderType] = None,
    ) -> 'Message':
        """Telethon Message 객체를 Message 인스턴스로 변환하는 클래스 메서드

        Telethon에서 제공하는 Message 객체의 속성들을 추출하여
        내부 Message 모델로 변환합니다. 일부 복잡한 속성들(미디어, 엔티티)은
        별도 처리가 필요하여 기본값으로 설정됩니다.

        Class method to convert Telethon Message object to Message instance

        Extracts attributes from Telethon's Message object and converts them
        to internal Message model. Some complex attributes (media, entities)
        require separate processing and are set to default values.

        Args:
            telethon_message (TelethonMessage): 변환할 Telethon Message 객체
                                              Telethon Message object to convert
            sender_id (Optional[int]): 발신자 ID (수동 지정 시)
                                     Sender ID (when manually specified)
            chat_id (Optional[int]): 채팅 ID (수동 지정 시)
                                   Chat ID (when manually specified)
            sender_type (Optional[SenderType]): 발신자 타입 (수동 지정 시)
                                              Sender type (when manually specified)

        Returns:
            Message: 변환된 Message 인스턴스
                    Converted Message instance

        Examples:
            # 기본 변환
            message = Message.from_telethon(telethon_msg)

            # 추가 정보와 함께 변환
            message = Message.from_telethon(
                telethon_msg, 
                sender_id=12345, 
                chat_id=67890,
                sender_type=SenderType.USER
            )

        Note:
            미디어와 엔티티 속성은 현재 기본값(None, [])으로 설정되며,
            향후 별도 처리 로직이 필요합니다.

            Media and entities attributes are currently set to default values (None, [])
            and require separate processing logic in the future.
        """
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

    def model_dump_only_insert(self):
        return {k: v for k, v in self.model_dump().items() if k in self.protected_fields}

    def model_dump_only_update(self):
        return {k: v for k, v in self.model_dump().items() if k not in self.protected_fields}

    def store(self):
        """메시지를 MongoDB chats 컬렉션에 저장하는 메서드

        현재 메시지 인스턴스를 MongoDB에 저장합니다. 중복 저장을 방지하기 위해
        동일한 ID와 채팅 ID를 가진 기존 메시지를 확인하고, 내용이 다른 경우에만 저장합니다.
        메시지가 수정된 경우 디버그 로그를 남깁니다.

        Method to store the message in MongoDB chats collection

        Stores the current message instance in MongoDB. To prevent duplicate storage,
        it checks for existing messages with the same ID and chat ID, and only stores
        if the content is different. Logs debug information when message is edited.

        Raises:
            pymongo.errors.PyMongoError: MongoDB 연결 또는 쓰기 오류 시 발생
                                        Raised on MongoDB connection or write errors

        Examples:
            message = Message(id=123, chat_id=456, message="Hello World")
            message.store()  # MongoDB에 저장됨

            # 동일한 메시지 다시 저장 시도
            message.store()  # 저장되지 않음 (중복)

            # 수정된 메시지 저장
            message.message = "Hello Updated"
            message.store()  # 저장됨, 디버그 로그 출력

        Note:
            저장 로직:
            1. MongoDB에서 동일한 id와 chat_id를 가진 문서 검색
            2. 기존 문서가 있으면 내용 비교
            3. 내용이 동일하면 저장 중단
            4. 내용이 다르면 수정 로그 출력 후 새 문서 삽입
            5. 기존 문서가 없으면 바로 새 문서 삽입

            Storage logic:
            1. Search for document with same id and chat_id in MongoDB
            2. Compare content if existing document found
            3. Skip storage if content is identical
            4. Log modification and insert new document if content differs
            5. Insert new document directly if no existing document
        """
        chat_collection = MongoCollections().chats
        try:
            result = chat_collection.find_one_and_update(
                filter={"id": self.id, "chat_id": self.chat_id, "message": self.message},
                update={"$set": self.model_dump_only_update(),
                        "$setOnInsert": self.model_dump_only_insert()},
                sort=[("updated_at", pymongo.DESCENDING)],
                upsert=True,
                return_document=pymongo.ReturnDocument.BEFORE,
            )

            if result:
                logger.info(f"기존에 저장된 메세지 중 수정된 메세지가 발견되었습니다. "
                            f"Message ID: {self.id}, Chat|Channel ID: {self.chat_id}")
        except DuplicateKeyError:
            logger.info(f"메시지 정보의 동시 입력이 감지되었습니다. Channel ID: {self.id}, Chat|Channel ID: {self.chat_id}")
