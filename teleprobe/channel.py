from typing import TYPE_CHECKING, Optional, Union, Callable, Coroutine, Any

from telethon.events import NewMessage
from telethon.tl.types import Channel as TelethonChannel

from handlers.event import EventHandler
from .constants import Logger
from .errors import ChannelKeyInvalidError, ChannelNotWatchedError, ChannelAlreadyWatchedError

if TYPE_CHECKING:
    from teleprobe.base import TeleprobeClient

import asyncio


__all__ = [
    'TeleprobeClient',
    'ChannelMethods',
]
logger = Logger(__name__)

class ChannelMethods:
    async def get_channel(
            self:'TeleprobeClient',
            channel_key: Union[int, str],
            handler: Optional[Callable[[TelethonChannel], Coroutine[Any, Any, None]]] = None
    ) -> Optional[TelethonChannel]:
        """
        Retrieves a channel based on the given channel key and executes an optional
        handler if provided. The method ensures that the client is connected and
        attempts to retrieve the channel entity. If the connection fails, `None`
        is returned. The retrieved channel can be processed via a handler if
        applicable.

        Parameters:
            channel_key (Union[int, str]): The unique identifier or channel key to
                retrieve the channel (e.g., channel ID or username).
            handler (Optional[Callable[[TelethonChannel], Coroutine[Any, Any, None]]]): A coroutine function
                to process the retrieved channel. Must accept a single argument of
                type `TelethonChannel` and return a coroutine.

        Returns:
            Optional[TelethonChannel]: The retrieved channel object if the operation is
            successful; otherwise, `None`.
        """
        await self.ensure_connected()

        channel = await self.connect_channel(channel_key)

        if handler and isinstance(handler, Callable) and isinstance(channel, TelethonChannel):
            await handler(channel)

        return channel

    async def watch(
            self: 'TeleprobeClient',
            channel_key: Union[int, str],
            handler: Optional[Callable[[Any], Coroutine[Any, Any, None]]] = None
    ):
        """
        Watches a specified channel for new messages and assigns an event handler to process the
        messages asynchronously.

        Parameters:
            channel_key (Union[int, str]): The unique identifier of the channel to monitor. It can
                either be an integer or a string.
            handler (Optional[Callable[[None], Coroutine[Any, Any, None]]]): An optional asynchronous
                callback that processes new messages from the specified channel.

        Raises:
            Any errors that occur during channel retrieval or event handler assignment will be logged.
        """

        channel = await self.get_channel(channel_key)
        if channel:
            with self._managing_event_handler:
                if self._event_handlers.get(channel.id):
                    err = ChannelAlreadyWatchedError(f"이미 모니터링 중인 채널입니다. "
                                                     f"Channel ID: {channel.id}, "
                                                     f"title: {channel.title}, "
                                                     f"username: @{channel.username}")
                    logger.error(err.message)
                    raise err

                self.client.add_event_handler(
                    callback=handler,
                    event=NewMessage(chats=channel.id)
                )
                self._event_handlers[channel.id] = handler
                logger.info(f"채널 모니터링을 시작했습니다. "
                            f"Channel ID: {channel.id}, title: {channel.title}, username: @{channel.username}")
        else:
            err = ChannelKeyInvalidError(f"모니터링할 채널에 연결할 수 없습니다. Channel key: {channel_key}")
            logger.error(err.message)
            raise err


    async def unwatch(
            self: 'TeleprobeClient',
            channel_key: Union[int, str]
    ):
        """특정 채널 모니터링을 중단하는 함수입니다.

        Args:
            channel_key (int|str): 모니터링을 중단할 채널의 ID 또는 키
        """
        channel = await self.get_channel(channel_key)
        if channel:
            channel_id = channel.id
        elif isinstance(channel_key, int):
            channel_id = channel_key # 채널이 발견되지 않았을 경우, 채널 ID로 대신 이벤트 핸들러 검색 시도
        else:
            err = ChannelKeyInvalidError(f"채널에 더이상 접근이 불가능하거나, 잘못된 채널 식별자를 입력했습니다. "
                                         f"Channel key: {channel_key}")
            logger.error(err.message)
            raise err

        with self._managing_event_handler:
            # 이벤트 핸들러 취소 및 제거
            if event_handler := self._event_handlers.get(channel_id):
                self.client.remove_event_handler(event_handler)
                del self._event_handlers[channel_id]
                logger.info(f"채널 모니터링을 중단했습니다. "
                            f"Channel ID: {channel_id}, title: {channel.title}, username: @{channel.username}")
            else:
                err = ChannelNotWatchedError(
                    f"모니터링을 중단하려는 채널은 현재 모니터링 중이 아닙니다. "
                    f"Channel ID: {channel_id}, title: {channel.title}, username: @{channel.username}"
                )
                logger.error(err)
                raise err


