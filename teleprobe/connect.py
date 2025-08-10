"""텔레그램 채널 초대/연결 관련 유틸리티 메서드 모듈."""
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
    """연결 오류 타입"""
    EMPTY_HASH = "empty_hash"
    EXPIRED_HASH = "expired_hash"
    INVALID_HASH = "invalid_hash"
    INVALID_CHANNEL = "invalid_channel"
    PRIVATE_CHANNEL = "private_channel"
    FLOOD_WAIT = "flood_wait"
    UNKNOWN_ERROR = "unknown_error"

class ChannelKeyType(Enum):
    """채널 키 타입"""
    INVITE_LINK = "invite_link"
    CHANNEL_ID = "channel_id" 
    USERNAME = "username"


class ConnectMethods:
    """텔레그램 채널 초대 수락 및 연결 기능을 제공하는 클래스입니다."""
    
    def __init__(self):
        super().__init__()

    @staticmethod
    def _identify_channel_key_type(channel_key: Union[int, str]) -> ChannelKeyType:
        """채널 키의 타입을 식별합니다."""
        if isinstance(channel_key, int):
            return ChannelKeyType.CHANNEL_ID
        elif isinstance(channel_key, str):
            if channel_key.startswith("https://t.me/+") or channel_key.startswith("+"):
                return ChannelKeyType.INVITE_LINK
            else:
                return ChannelKeyType.USERNAME
        err = ChannelKeyInvalidError(f"지원되지 않는 채널 키 타입: {type(channel_key)}")
        logger.error(err.message)
        raise err

    @staticmethod
    def _extract_invite_hash(invite_link: str) -> str:
        """초대 링크에서 해시를 추출합니다."""
        if invite_link.startswith("https://t.me/+"):
            return invite_link.split("+")[1]
        elif invite_link.startswith("+"):
            return invite_link[1:]
        else:
            raise ValueError(f"잘못된 초대 링크 형식: {invite_link}")


    async def accept_invitation(self: 'TeleprobeClient', invite_link: str) -> TelethonChannel:
        """텔레그램 초대 링크를 수락하고 채널 엔티티를 반환합니다."""
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
            logger.warning(err.message)
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
                    logger.error(err.message)
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
            raise ValueError("Max retries must be greater than or equal to 1.")

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