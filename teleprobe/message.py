"""텔레그램 메시지 처리 메서드 모듈 - 메시지 반복 및 처리 기능

이 모듈은 텔레그램 채널이나 채팅에서 메시지를 반복하고 처리하는 기능을 제공합니다.
대량의 메시지 데이터를 효율적으로 순회하고, 각 메시지에 대해 커스텀 핸들러를
적용할 수 있는 유틸리티 메서드들을 포함합니다.

Telegram Message Processing Methods Module - Message iteration and processing functionality

This module provides functionality to iterate and process messages from Telegram channels or messages.
It includes utility methods for efficiently traversing large amounts of message data
and applying custom handlers to each message.
"""

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
    """텔레그램 메시지 반복 및 처리를 위한 메서드 모음 클래스

    텔레그램 채널이나 채팅에서 메시지를 효율적으로 순회하고 처리하는 기능을 제공합니다.
    TeleprobeClient의 mixin으로 사용되어 메시지 관련 기능을 확장하며,
    대량의 메시지 데이터를 스트리밍 방식으로 처리할 수 있습니다.

    Collection class of methods for Telegram message iteration and processing

    Provides functionality to efficiently iterate and process messages from Telegram channels or messages.
    Used as a mixin for TeleprobeClient to extend message-related functionality,
    and can process large amounts of message data in streaming fashion.

    Methods:
        iter_messages: 엔티티의 메시지를 비동기 반복
                      Asynchronously iterate messages from entity

    Examples:
        # TeleprobeClient에서 mixin으로 사용됨
        class TeleprobeClient(MessageMethods, ChannelMethods, ...):
            pass

        client = TeleprobeClient(...)
        channel = await client.get_channel("@channelname")

        # 메시지 반복 처리
        async for message in client.iter_messages(channel, message_handler):
            print(f"메시지: {message.message}")

    Note:
        이 클래스는 TeleprobeClient의 mixin으로 사용되며,
        단독으로 인스턴스화하지 않습니다. 메시지 반복은 제너레이터를
        사용하여 메모리 효율적으로 처리됩니다.

        This class is used as a mixin for TeleprobeClient
        and is not instantiated independently. Message iteration
        is processed memory-efficiently using generators.
    """
    async def iter_messages(
            self: 'TeleprobeClient',
            entity: Union[TelethonChannel, TelethonChat],
            handler: Callable[[Message, int], Coroutine] = None,
    ):
        """지정된 엔티티의 메시지들을 비동기적으로 반복하는 제너레이터 메서드

        채널이나 채팅에서 사용 가능한 모든 메시지를 조회하고 순회합니다.
        선택적으로 각 메시지를 처리할 비동기 핸들러 함수를 제공할 수 있으며,
        메모리 효율적인 스트리밍 방식으로 대량의 메시지를 처리할 수 있습니다.

        Generator method to asynchronously iterate messages from specified entity

        Retrieves and traverses all available messages from channel or chat.
        Optionally provides async handler function to process each message,
        and can process large amounts of messages in memory-efficient streaming fashion.

        Args:
            entity (Union[TelethonChannel, TelethonChat]): 메시지를 조회할 대상 엔티티
                                                         Target entity to retrieve messages from
                                                         - TelethonChannel: 텔레그램 채널
                                                         - TelethonChat: 텔레그램 채팅
            handler (Optional[Callable]): 각 메시지를 처리할 비동기 호출 가능 객체 (선택적)
                                        Async callable to process each message (optional)
                                        - Message 객체를 매개변수로 받아야 함
                                        - Must accept Message object as parameter

        Yields:
            Message: 지정된 엔티티에서 조회된 메시지 객체
                    Message object retrieved from specified entity

        Examples:
            # 기본 메시지 반복
            channel = await client.get_channel("@channelname")
            async for message in client.iter_messages(channel):
                print(f"메시지: {message.message}")
                print(f"날짜: {message.date}")

            # 핸들러와 함께 반복
            async def message_handler(message):
                if message.message:
                    print(f"텍스트 메시지: {message.message}")

            async for message in client.iter_messages(channel, message_handler):
                # 핸들러가 자동으로 실행됨
                pass

        Note:
            - 이 메서드는 제너레이터로 구현되어 메모리 효율적입니다.
            - 핸들러는 각 메시지마다 자동으로 호출됩니다.
            - 메시지는 최신부터 과거 순으로 조회됩니다.

            - This method is implemented as generator for memory efficiency.
            - Handler is automatically called for each message.
            - Messages are retrieved from newest to oldest.
        """
        async for message in self.client.iter_messages(entity):
            if handler and isinstance(handler, Callable) and isinstance(message, Message):
                await handler(message, entity.id)
            yield message
