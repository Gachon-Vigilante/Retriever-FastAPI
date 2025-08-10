"""텔레그램 채널 초대/연결 관련 유틸리티 메서드 모듈."""
import typing
from dataclasses import dataclass
from enum import Enum
from typing import Union, Optional

from telethon.errors import (
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
)
from telethon.sync import types
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import PeerChannel, Channel as TelethonChannel

from utils import get_logger
logger = get_logger()

if typing.TYPE_CHECKING:
    from teleprobe.base import TeleprobeClient


class TelegramConnectionError(Enum):
    """연결 오류 타입"""
    EMPTY_HASH = "empty_hash"
    EXPIRED_HASH = "expired_hash"
    INVALID_HASH = "invalid_hash"
    INVALID_CHANNEL = "invalid_channel"
    PRIVATE_CHANNEL = "private_channel"
    FLOOD_WAIT = "flood_wait"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class TelegramConnectionResult:
    """채널 연결 결과"""
    success: bool
    entity: Optional[TelethonChannel] = None
    error_type: Optional[TelegramConnectionError] = None
    error_message: Optional[str] = None
    wait_time: Optional[int] = None  # FloodWaitError의 경우


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
        else:
            raise ValueError(f"지원되지 않는 채널 키 타입: {type(channel_key)}")

    @staticmethod
    def _extract_invite_hash(invite_link: str) -> str:
        """초대 링크에서 해시를 추출합니다."""
        if invite_link.startswith("https://t.me/+"):
            return invite_link.split("+")[1]
        elif invite_link.startswith("+"):
            return invite_link[1:]
        else:
            raise ValueError(f"잘못된 초대 링크 형식: {invite_link}")

    @staticmethod
    def _handle_telethon_exception(e: Exception) -> TelegramConnectionResult:
        """Telethon 예외를 처리하고 ConnectionResult를 반환합니다."""
        error_mappings = {
            InviteHashEmptyError: (TelegramConnectionError.EMPTY_HASH, "초대 해시가 비어있습니다."),
            InviteHashExpiredError: (TelegramConnectionError.EXPIRED_HASH, "초대 링크가 만료되었습니다."),
            InviteHashInvalidError: (TelegramConnectionError.INVALID_HASH, "초대 해시가 유효하지 않습니다."),
            ChannelInvalidError: (TelegramConnectionError.INVALID_CHANNEL, "유효하지 않은 채널입니다."),
            ChannelPrivateError: (TelegramConnectionError.PRIVATE_CHANNEL, "비공개 채널이며 초대되지 않았습니다."),
        }
        
        for exception_type, (error_type, message) in error_mappings.items():
            if isinstance(e, exception_type):
                logger.warning(f"{message} 오류: {e}")
                return TelegramConnectionResult(
                    success=False,
                    error_type=error_type,
                    error_message=message
                )
        
        if isinstance(e, FloodWaitError):
            logger.warning(f"[Connect] 요청이 너무 많아 제한되었습니다. {e.seconds}초 후에 다시 시도하세요.")
            return TelegramConnectionResult(
                success=False,
                error_type=TelegramConnectionError.FLOOD_WAIT,
                error_message="요청 제한이 걸렸습니다.",
                wait_time=e.seconds
            )
        
        # 예상하지 못한 오류
        logger.error(f"[Connect] 예상하지 못한 오류: {e}")
        return TelegramConnectionResult(
            success=False,
            error_type=TelegramConnectionError.UNKNOWN_ERROR,
            error_message=str(e)
        )

    async def accept_invitation(self: 'TeleprobeClient', invite_link: str) -> TelegramConnectionResult:
        """텔레그램 초대 링크를 수락하고 채널 엔티티를 반환합니다."""
        try:
            # 연결 상태 확인
            if not await self.ensure_connected():
                return TelegramConnectionResult(
                    success=False, 
                    error_type=TelegramConnectionError.UNKNOWN_ERROR,
                    error_message="텔레그램 서버에 연결할 수 없습니다."
                )
                
            invite_hash = self._extract_invite_hash(invite_link)
            logger.debug(f"초대 링크 처리 중... 해시: {invite_hash}")

            # 초대 링크 유효성 검사
            invite_info = await self.client(CheckChatInviteRequest(invite_hash))

            if isinstance(invite_info, types.ChatInvite):
                logger.debug("채널에 참여 중...")
                entity = await self.client(ImportChatInviteRequest(invite_hash))
                logger.info("[Connect] 초대 링크를 통해 채널에 성공적으로 참여했습니다.")
                return TelegramConnectionResult(success=True, entity=entity)
                
            elif isinstance(invite_info, types.ChatInviteAlready):
                logger.info("[Connect] 이미 채널에 참여 중입니다. 엔티티를 가져옵니다.")
                entity = await self.client.get_entity(invite_info.chat)
                return TelegramConnectionResult(success=True, entity=entity)
            
            else:
                logger.warning(f"[Connect] 알 수 없는 초대 정보 타입: {type(invite_info)}")
                return TelegramConnectionResult(
                    success=False,
                    error_type=TelegramConnectionError.UNKNOWN_ERROR,
                    error_message="알 수 없는 초대 정보 타입"
                )

        except Exception as e:
            return self._handle_telethon_exception(e)

    async def connect_channel(self: 'TeleprobeClient', channel_key: Union[int, str]) -> TelegramConnectionResult:
        """채널 ID, @username, 초대 링크 등 다양한 키로 텔레그램 채널에 연결합니다."""
        try:
            # 연결 상태 확인
            if not await self.ensure_connected():
                return TelegramConnectionResult(
                    success=False, 
                    error_type=TelegramConnectionError.UNKNOWN_ERROR,
                    error_message="텔레그램 서버에 연결할 수 없습니다."
                )
                
            key_type = self._identify_channel_key_type(channel_key)
            logger.debug(f"[Connect] 채널 연결 중... 키: {channel_key}, 타입: {key_type.value}")

            if key_type == ChannelKeyType.INVITE_LINK:
                return await self.accept_invitation(channel_key)
            else:
                # 채널 ID 또는 사용자명으로 직접 연결
                if key_type == ChannelKeyType.CHANNEL_ID:
                    channel_key = PeerChannel(channel_key)
                entity = await self.client.get_entity(channel_key)
                if not isinstance(entity, TelethonChannel):
                    logger.error(f"[Connect] 연결된 객체가 채널이 아닙니다. 타입: `{type(entity)}`")
                    raise TypeError(f"Connected object is not a channel. type: `{type(entity)}`")
                logger.info(f"[Connect] 채널에 성공적으로 연결되었습니다. 타입: {key_type.value}")
                return TelegramConnectionResult(success=True, entity=entity)

        except Exception as e:
            return self._handle_telethon_exception(e)

    async def connect_channel_with_retry(
        self: 'TeleprobeClient',
        channel_key: Union[int, str],
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> TelegramConnectionResult:
        """재시도 로직이 포함된 채널 연결"""
        import asyncio
        
        for attempt in range(max_retries):
            result = await self.connect_channel(channel_key)
            
            if result.success:
                return result
            
            if result.error_type == TelegramConnectionError.FLOOD_WAIT and result.wait_time:
                # FloodWaitError의 경우 지정된 시간만큼 대기
                logger.info(f"[Connect] FloodWait으로 인해 {result.wait_time}초 대기 중...")
                await asyncio.sleep(result.wait_time)
                continue
            
            if attempt < max_retries - 1:
                logger.info(f"[Connect] 연결 실패, {retry_delay}초 후 재시도... (시도 {attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # 지수 백오프

        return TelegramConnectionResult(success=False)