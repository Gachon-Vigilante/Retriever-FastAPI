from typing import TYPE_CHECKING, Union, AsyncGenerator

from telethon.tl.types import (
    Channel as TelethonChannel,
    Chat as TelethonChat,
)

if TYPE_CHECKING:
    from .base import TeleprobeClient

__all__ = [
    'TeleprobeClient',
    'MessageMethods',
] # TeleprobeClient 클래스가 사용되었음을 표시


class MessageMethods:
    """텔레그램 채널 초대 수락 및 연결 기능을 제공하는 클래스입니다."""
    async def iter_messages(
            self: 'TeleprobeClient',
            entity: Union[TelethonChannel, TelethonChat],
    ):
        """채널 내의 채팅들을 비동기적으로 가져옵니다.

        Args:
            entity: telethon entity(Channel, Chat) 객체

        Returns:
            Channel 객체 또는 연결 실패시 None
        """
        async for message in self.client.iter_messages(entity):
            yield message

