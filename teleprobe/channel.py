"""텔레그램 채널 관리 메서드 모듈 - 채널 모니터링 및 이벤트 처리

이 모듈은 텔레그램 채널의 조회, 모니터링 시작/중단, 이벤트 핸들러 관리 등의
채널 관련 작업을 수행하는 메서드들을 제공합니다. TeleprobeClient의 mixin으로 사용되어
채널 관리 기능을 확장합니다.

Telegram Channel Management Methods Module - Channel monitoring and event handling

This module provides methods for performing channel-related tasks such as channel retrieval,
starting/stopping monitoring, and event handler management. Used as a mixin for TeleprobeClient
to extend channel management functionality.
"""

from typing import TYPE_CHECKING, Optional, Union, Callable, Coroutine, Any

from telethon.events import NewMessage
from telethon.tl.types import Channel as TelethonChannel

from .constants import Logger
from .errors import ChannelKeyInvalidError, ChannelNotWatchedError, ChannelAlreadyWatchedError

if TYPE_CHECKING:
    from teleprobe.base import TeleprobeClient

__all__ = [
    'TeleprobeClient',
    'ChannelMethods',
]
logger = Logger(__name__)

class ChannelMethods:
    """텔레그램 채널 관리 및 모니터링을 위한 메서드 모음 클래스

    채널 조회, 모니터링 시작/중단, 이벤트 핸들러 관리 등 채널과 관련된
    모든 작업을 수행하는 메서드들을 제공합니다. TeleprobeClient의 mixin으로 사용되어
    채널 관리 기능을 확장하며, 이벤트 기반 메시지 모니터링을 지원합니다.

    Collection class of methods for Telegram channel management and monitoring

    Provides methods for performing all channel-related tasks such as channel retrieval,
    starting/stopping monitoring, and event handler management. Used as a mixin for TeleprobeClient
    to extend channel management functionality and supports event-based message monitoring.

    Methods:
        get_channel: 채널 조회 및 핸들러 실행
                    Channel retrieval and handler execution
        watch: 채널 모니터링 시작
              Start channel monitoring
        unwatch: 채널 모니터링 중단
                Stop channel monitoring

    Examples:
        # TeleprobeClient에서 mixin으로 사용됨
        class TeleprobeClient(ChannelMethods, ConnectMethods, ...):
            pass

        client = TeleprobeClient(...)

        # 채널 조회
        channel = await client.get_channel("@channelname")

        # 모니터링 시작
        await client.watch("@channelname", message_handler)

        # 모니터링 중단
        await client.unwatch("@channelname")

    Note:
        이 클래스는 TeleprobeClient의 mixin으로 사용되며,
        단독으로 인스턴스화하지 않습니다. 이벤트 핸들러는
        클라이언트의 _event_handlers 딕셔너리로 관리됩니다.

        This class is used as a mixin for TeleprobeClient
        and is not instantiated independently. Event handlers are
        managed through the client's _event_handlers dictionary.
    """
    async def get_channel(
            self:'TeleprobeClient',
            channel_key: Union[int, str],
            handler: Optional[Callable[[TelethonChannel], Coroutine[Any, Any, None]]] = None
    ) -> Optional[TelethonChannel]:
        """채널을 조회하고 선택적으로 핸들러를 실행하는 비동기 메서드

        제공된 채널 키를 사용하여 채널을 조회하고, 핸들러가 제공된 경우 실행합니다.
        클라이언트 연결을 확인하고 채널 엔티티 조회를 시도하며, 연결 실패 시 None을 반환합니다.
        조회된 채널은 핸들러를 통해 추가 처리할 수 있습니다.

        Asynchronous method to retrieve channel and optionally execute handler

        Retrieves channel using provided channel key and executes handler if provided.
        Ensures client connection and attempts to retrieve channel entity, returning None on connection failure.
        Retrieved channel can be processed through handler for additional operations.

        Args:
            channel_key (Union[int, str]): 채널을 조회하기 위한 고유 식별자
                                         Unique identifier to retrieve channel
                                         - int: 채널 ID (예: -1001234567890)
                                         - str: 사용자명(@username) 또는 초대 링크
            handler (Optional[Callable]): 조회된 채널을 처리할 코루틴 함수 (선택적)
                                        Coroutine function to process retrieved channel (optional)
                                        - TelethonChannel을 매개변수로 받아야 함
                                        - Must accept TelethonChannel as parameter

        Returns:
            Optional[TelethonChannel]: 성공 시 조회된 채널 객체, 실패 시 None
                                     Retrieved channel object on success, None on failure

        Examples:
            # 기본 채널 조회
            channel = await client.get_channel("@channelname")
            if channel:
                print(f"채널명: {channel.title}")

            # 핸들러와 함께 조회
            async def channel_handler(channel):
                print(f"조회된 채널: {channel.title}")

            channel = await client.get_channel(-1001234567890, channel_handler)

        Note:
            이 메서드는 내부적으로 connect_channel을 사용하여 채널에 연결하므로,
            초대 링크나 새로운 채널의 경우 자동으로 참여가 이루어집니다.

            This method internally uses connect_channel to connect to the channel,
            so automatic joining occurs for invite links or new channels.
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


