from typing import TYPE_CHECKING, Union, Callable, Coroutine

from telethon.tl.types import (
    Channel as TelethonChannel,
    Chat as TelethonChat,
    Message,
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
            handler: Callable[[Message], Coroutine] = None,
    ):
        """
        Asynchronously iterates over messages for a specified entity.

        This function retrieves all available messages for a given entity
        such as a channel or chat. An optional async handler function can be
        provided to process each message during iteration.

        Args:
            self: The current instance of the TeleprobeClient.
            entity: The target entity for which messages will be retrieved
                (e.g., TelethonChannel or TelethonChat).
            handler: An optional async callable that takes a single Message object
                as a parameter and performs processing.

        Yields:
            Message: A message object retrieved from the specified entity.
        """
        async for message in self.client.iter_messages(entity):
            if handler and isinstance(handler, Callable) and isinstance(message, Message):
                await handler(message)
            yield message

