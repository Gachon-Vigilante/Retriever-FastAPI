from telethon.tl.types import Channel as TelethonChannel

from core.mongo.channel import Channel


class ChannelHandler:
    """
    Handles processing and logging operations for a Telegram channel using the Telethon library.

    This class provides functionality to process a TelethonChannel object, convert it into a custom
    Channel object, and perform storage operations. It also allows for logging of messages
    related to these operations.
    """

    def __init__(self):
        pass

    async def __call__(self, telethon_channel: TelethonChannel):
        """
        An asynchronous callable class method that processes a Telethon channel, converts it into a
        custom Channel object, and persists it by storing the data.

        Parameters:
            telethon_channel (TelethonChannel): The TelethonChannel object to be processed.

        Returns:
            None
        """
        # datetime을 ISO 형식 문자열로 변환하여 직렬화
        channel: Channel = Channel.from_telethon(telethon_channel)
        channel.store()