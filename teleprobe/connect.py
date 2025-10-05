"""텔레그램 채널 연결 및 초대 수락 유틸리티 모듈 - 다양한 방식의 채널 접근

이 모듈은 텔레그램 채널에 다양한 방법으로 연결하고 초대를 수락하는 기능을 제공합니다.
채널 ID, 사용자명(@username), 초대 링크 등을 통한 채널 접근과 재시도 로직,
에러 처리 등의 종합적인 연결 관리 기능을 포함합니다.

Telegram Channel Connection and Invite Acceptance Utility Module - Various channel access methods

This module provides functionality to connect to Telegram channels in various ways and accept invitations.
It includes comprehensive connection management features such as channel access through channel ID,
username (@username), invite links, retry logic, and error handling.
"""
import typing
from dataclasses import dataclass
from enum import Enum
from typing import Union, Optional

from telethon.sync import types
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import PeerChannel, Channel as TelethonChannel
from .constants import Logger
from .errors import *

if typing.TYPE_CHECKING:
    from teleprobe.base import TeleprobeClient


__all__ = [
    'TeleprobeClient',
    'ConnectMethods',
]
logger = Logger(__name__)


class TelegramConnectionError(Enum):
    """텔레그램 연결 오류 타입을 분류하는 열거형

    텔레그램 채널 연결 과정에서 발생할 수 있는 다양한 오류 유형을 정의합니다.
    각 오류 타입은 특정한 처리 방법과 재시도 전략을 결정하는 데 사용됩니다.

    Enumeration for classifying Telegram connection error types

    Defines various error types that can occur during Telegram channel connection process.
    Each error type is used to determine specific handling methods and retry strategies.

    Attributes:
        EMPTY_HASH (str): 초대 해시가 비어있는 경우
                         When invite hash is empty
        EXPIRED_HASH (str): 초대 해시가 만료된 경우
                           When invite hash is expired
        INVALID_HASH (str): 초대 해시가 유효하지 않은 경우
                           When invite hash is invalid
        INVALID_CHANNEL (str): 채널이 유효하지 않은 경우
                              When channel is invalid
        PRIVATE_CHANNEL (str): 비공개 채널인 경우
                              When channel is private
        FLOOD_WAIT (str): 요청 제한에 걸린 경우
                         When hit by request rate limit
        UNKNOWN_ERROR (str): 알 수 없는 오류인 경우
                           When unknown error occurs

    Examples:
        if error_type == TelegramConnectionError.FLOOD_WAIT:
            await asyncio.sleep(wait_time)
        elif error_type == TelegramConnectionError.EXPIRED_HASH:
            raise InviteHashExpiredError("초대 링크가 만료되었습니다.")
    """
    EMPTY_HASH = "empty_hash"
    EXPIRED_HASH = "expired_hash"
    INVALID_HASH = "invalid_hash"
    INVALID_CHANNEL = "invalid_channel"
    PRIVATE_CHANNEL = "private_channel"
    FLOOD_WAIT = "flood_wait"
    UNKNOWN_ERROR = "unknown_error"

class ChannelKeyType(Enum):
    """채널 식별 키의 타입을 분류하는 열거형

    채널에 연결하기 위해 사용되는 다양한 식별자 형태를 분류합니다.
    각 타입에 따라 적절한 연결 방법과 처리 로직이 선택됩니다.

    Enumeration for classifying channel identification key types

    Classifies various identifier formats used to connect to channels.
    Appropriate connection methods and processing logic are selected based on each type.

    Attributes:
        INVITE_LINK (str): 초대 링크 형태 (https://t.me/+hash 또는 +hash)
                          Invite link format (https://t.me/+hash or +hash)
        CHANNEL_ID (str): 채널 ID 형태 (정수, 예: -1001234567890)
                         Channel ID format (integer, e.g., -1001234567890)
        USERNAME (str): 사용자명 형태 (@username)
                       Username format (@username)

    Examples:
        key_type = ChannelKeyType.INVITE_LINK
        if key_type == ChannelKeyType.INVITE_LINK:
            return await accept_invitation(channel_key)
        elif key_type == ChannelKeyType.USERNAME:
            return await get_entity_by_username(channel_key)
    """
    INVITE_LINK = "invite_link"
    CHANNEL_ID = "channel_id" 
    USERNAME = "username"


class ConnectMethods:
    """텔레그램 채널 연결 및 초대 수락을 위한 메서드 모음 클래스

    다양한 형태의 채널 식별자(ID, 사용자명, 초대 링크)를 통해 텔레그램 채널에
    연결하는 기능을 제공합니다. 초대 링크 처리, 채널 키 타입 식별, 재시도 로직 등
    채널 연결과 관련된 모든 유틸리티 메서드를 포함합니다.

    Collection class of methods for Telegram channel connection and invite acceptance

    Provides functionality to connect to Telegram channels through various channel identifiers
    (ID, username, invite link). Includes all utility methods related to channel connection
    such as invite link processing, channel key type identification, and retry logic.

    Methods:
        _identify_channel_key_type: 채널 키 타입 식별
                                   Identify channel key type
        _extract_invite_hash: 초대 링크에서 해시 추출
                             Extract hash from invite link
        accept_invitation: 초대 링크 수락 및 채널 참여
                          Accept invite link and join channel
        connect_channel: 다양한 키로 채널 연결
                        Connect to channel with various keys
        connect_channel_with_retry: 재시도 로직이 포함된 채널 연결
                                   Channel connection with retry logic

    Examples:
        # TeleprobeClient에서 mixin으로 사용됨
        class TeleprobeClient(ConnectMethods, ...):
            pass

        client = TeleprobeClient(...)
        channel = await client.connect_channel("@channelname")
        channel = await client.connect_channel("https://t.me/+abcdef123")

    Note:
        이 클래스는 TeleprobeClient의 mixin으로 사용되며,
        단독으로 인스턴스화하지 않습니다.

        This class is used as a mixin for TeleprobeClient
        and is not instantiated independently.
    """
    
    def __init__(self):
        super().__init__()

    @staticmethod
    def _identify_channel_key_type(channel_key: Union[int, str]) -> ChannelKeyType:
        """채널 키의 타입을 자동으로 식별하는 정적 메서드

        제공된 채널 키의 형태를 분석하여 적절한 ChannelKeyType을 반환합니다.
        정수형은 채널 ID로, 초대 링크 형태는 INVITE_LINK로, 그 외 문자열은 USERNAME으로 분류합니다.

        Static method to automatically identify channel key type

        Analyzes the format of provided channel key and returns appropriate ChannelKeyType.
        Integers are classified as channel ID, invite link formats as INVITE_LINK, other strings as USERNAME.

        Args:
            channel_key (Union[int, str]): 분석할 채널 키
                                         Channel key to analyze
                                         - int: 채널 ID (예: -1001234567890)
                                         - str: 초대 링크 또는 사용자명

        Returns:
            ChannelKeyType: 식별된 채널 키 타입
                           Identified channel key type

        Raises:
            ChannelKeyInvalidError: 지원되지 않는 채널 키 타입인 경우
                                   When unsupported channel key type is provided

        Examples:
            # 채널 ID
            key_type = ConnectMethods._identify_channel_key_type(-1001234567890)
            # Returns: ChannelKeyType.CHANNEL_ID

            # 초대 링크
            key_type = ConnectMethods._identify_channel_key_type("https://t.me/+abcdef123")
            # Returns: ChannelKeyType.INVITE_LINK

            # 사용자명
            key_type = ConnectMethods._identify_channel_key_type("@channelname")
            # Returns: ChannelKeyType.USERNAME

        Note:
            초대 링크 형태:
            - "https://t.me/+hash" 형식
            - "+hash" 형식 (축약형)

            Invite link formats:
            - "https://t.me/+hash" format
            - "+hash" format (abbreviated)
        """
        if isinstance(channel_key, int):
            return ChannelKeyType.CHANNEL_ID
        elif isinstance(channel_key, str):
            if channel_key.startswith("https://t.me/+") or channel_key.startswith("+") or ".me/joinchat" in channel_key:
                return ChannelKeyType.INVITE_LINK
            else:
                return ChannelKeyType.USERNAME
        err = ChannelKeyInvalidError(f"지원되지 않는 채널 키 타입: {type(channel_key)}")
        logger.error(err)
        raise err

    @staticmethod
    def _extract_invite_hash(invite_link: str) -> str:
        """텔레그램 초대 링크에서 해시 값을 추출하는 정적 메서드

        완전한 초대 링크나 축약형 해시에서 실제 해시 부분만을 추출합니다.
        Telethon API 호출에 필요한 순수 해시 값을 반환합니다.

        Static method to extract hash value from Telegram invite link

        Extracts only the actual hash part from complete invite link or abbreviated hash.
        Returns pure hash value required for Telethon API calls.

        Args:
            invite_link (str): 초대 링크 또는 해시
                              Invite link or hash
                              - "https://t.me/+hash" 형식
                              - "+hash" 형식

        Returns:
            str: 추출된 해시 값
                Extracted hash value

        Raises:
            ValueError: 잘못된 초대 링크 형식인 경우
                       When invalid invite link format is provided

        Examples:
            # 완전한 링크
            hash_val = ConnectMethods._extract_invite_hash("https://t.me/+abcdef123456")
            # Returns: "abcdef123456"

            # 축약형
            hash_val = ConnectMethods._extract_invite_hash("+abcdef123456")
            # Returns: "abcdef123456"

        Note:
            추출된 해시는 텔레그램의 CheckChatInviteRequest나
            ImportChatInviteRequest API 호출에 사용됩니다.

            Extracted hash is used for Telegram's CheckChatInviteRequest
            or ImportChatInviteRequest API calls.
        """
        if invite_link.startswith("https://t.me/+"):
            return invite_link.split("+")[1]
        elif invite_link.startswith("+"):
            return invite_link[1:]
        else:
            raise ValueError(f"잘못된 초대 링크 형식: {invite_link}")


    async def accept_invitation(self: 'TeleprobeClient', invite_link: str) -> TelethonChannel:
        """텔레그램 초대 링크를 수락하고 채널에 참여하는 비동기 메서드

        제공된 초대 링크를 검증하고 수락하여 채널에 참여합니다.
        이미 참여한 채널인 경우 기존 채널 엔티티를 반환하고,
        새로운 초대인 경우 채널에 참여한 후 엔티티를 반환합니다.

        Asynchronous method to accept Telegram invite link and join channel

        Validates and accepts provided invite link to join the channel.
        Returns existing channel entity if already joined,
        or joins channel and returns entity for new invitations.

        Args:
            invite_link (str): 수락할 텔레그램 초대 링크
                              Telegram invite link to accept
                              - "https://t.me/+hash" 형식
                              - "+hash" 형식

        Returns:
            TelethonChannel: 참여한 채널의 엔티티 객체
                           Entity object of the joined channel

        Raises:
            InviteHashEmptyError: 초대 해시가 비어있는 경우
                                 When invite hash is empty
            InviteHashExpiredError: 초대 링크가 만료된 경우
                                   When invite link is expired
            InviteHashInvalidError: 초대 해시가 유효하지 않은 경우
                                   When invite hash is invalid
            UnknownInvitationTypeError: 알 수 없는 초대 정보 타입인 경우
                                       When unknown invitation info type is received

        Examples:
            client = TeleprobeClient(...)
            await client.ensure_connected()

            # 초대 링크 수락
            channel = await client.accept_invitation("https://t.me/+abcdef123456")
            print(f"참여한 채널: {channel.title}")

            # 축약형 링크 수락
            channel = await client.accept_invitation("+abcdef123456")

        Note:
            처리 과정:
            1. 클라이언트 연결 상태 확인
            2. 초대 링크에서 해시 추출
            3. CheckChatInviteRequest로 초대 정보 확인
            4. ChatInvite인 경우 ImportChatInviteRequest로 참여
            5. ChatInviteAlready인 경우 기존 엔티티 반환

            Processing steps:
            1. Check client connection status
            2. Extract hash from invite link
            3. Check invitation info with CheckChatInviteRequest
            4. Join with ImportChatInviteRequest if ChatInvite
            5. Return existing entity if ChatInviteAlready
        """
        # 연결 상태 확인
        await self.ensure_connected()

        invite_hash = self._extract_invite_hash(invite_link)
        logger.debug(f"초대 링크 처리 중... 해시: {invite_hash}")

        # 초대 링크 유효성 검사
        invite_info = await self.client(CheckChatInviteRequest(invite_hash))

        if isinstance(invite_info, types.ChatInvite):
            logger.debug("채널에 참여 중...")
            entity = await self.client(ImportChatInviteRequest(invite_hash))
            logger.info("초대 링크를 통해 채널에 성공적으로 참여했습니다.")
            return entity

        elif isinstance(invite_info, types.ChatInviteAlready):
            logger.info("이미 채널에 참여 중입니다. 엔티티를 가져옵니다.")
            entity = await self.client.get_entity(invite_info.chat)
            return entity

        else:
            err = UnknownInvitationTypeError(f"알 수 없는 초대 정보 타입: {type(invite_info)}")
            logger.warning(err)
            raise err

    async def connect_channel(self: 'TeleprobeClient', channel_key: Union[int, str]) -> TelethonChannel:
        """채널 ID, @username, 초대 링크 등 다양한 키로 텔레그램 채널에 연결합니다."""
        # 연결 상태 확인
        await self.ensure_connected()
        key_type = self._identify_channel_key_type(channel_key)
        logger.debug(f"채널 연결 중... 키: {channel_key}, 타입: {key_type.value}")

        if key_type == ChannelKeyType.INVITE_LINK:
            return await self.accept_invitation(channel_key)
        else:
            # 채널 ID 또는 사용자명으로 직접 연결
            if key_type == ChannelKeyType.CHANNEL_ID:
                channel_key = PeerChannel(channel_key)
            try:
                entity = await self.client.get_entity(channel_key)
            except ValueError as e:
                if "No user has" in str(e):
                    err = UsernameNotFoundError(f"@username {channel_key}에 해당하는 채널이 없습니다.")
                    logger.error(err)
                    raise err from e
                else:
                    raise e
            if not isinstance(entity, TelethonChannel):
                err = NotChannelError(f"연결된 객체가 채널이 아닙니다. 타입: `{type(entity)}`")
                logger.error(err)
                raise err
            logger.info(f"채널에 성공적으로 연결되었습니다. 타입: {key_type.value}")
            return entity

    async def connect_channel_with_retry(
        self: 'TeleprobeClient',
        channel_key: Union[int, str],
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Union[TelethonChannel, None]:
        """재시도 로직이 포함된 채널 연결"""
        import asyncio

        if max_retries < 1:
            logger.warning(f"Invalid max retries(expected greater than or equal to 1, got {max_retries}). "
                           f"It is set to 1 by default. ")
            max_retries = 1

        channel = None
        for attempt in range(max_retries + 1):
            try:
                channel = await self.connect_channel(channel_key)
            except FloodWaitError as e:
                logger.warning(f"FloodWait으로 인해 {e.seconds}초 대기 중...")
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                if attempt < max_retries:
                    logger.info(f"연결 실패, {retry_delay}초 후 재시도... (시도 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 지수 백오프
                else:
                    raise e

        return channel