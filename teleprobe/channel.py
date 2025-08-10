from typing import TYPE_CHECKING, Optional, Union, Callable, Coroutine, Any

from telethon.tl.types import Channel as TelethonChannel
from .constants import Logger
if TYPE_CHECKING:
    from teleprobe.base import TeleprobeClient


__all__ = [
    'TeleprobeClient',
    'ChannelMethods',
]
logger = Logger("TeleprobeChannels")

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
        if not await self.ensure_connected():
            return None

        connection_result = await self.connect_channel(channel_key)
        if not connection_result.success:
            logger.warning("채널 정보를 받아올 수 없습니다. 채널 연결에 실패했습니다.")
            return None

        channel = connection_result.entity
        if handler and isinstance(handler, Callable) and isinstance(channel, TelethonChannel):
            await handler(channel)

        return connection_result.entity