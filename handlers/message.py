from typing import Union, Any

from telethon.tl.types import Message as TelethonMessage, User as TelethonUser, Channel as TelethonChannel

from core.mongo.message import Message
from core.mongo.types import SenderType
from utils import Logger


class MessageHandler:
    """Base class for handling Telegram messages.

    This class defines the interface for message handlers and provides
    a default implementation that raises a warning when the handler is not implemented.
    """
    _logger = Logger("TelegramMessageHandler")

    async def __call__(self, message: Union[TelethonMessage, Any]):
        """Handle incoming Telegram message.

        Args:
            message: Telegram message to be handled

        Raises:
            MessageHandlerNotImplementedWarning: When handler is not implemented
        """
        sender = await message.get_sender()
        if not sender:
            self._logger.error("메세지 송신자를 받아올 수 없습니다.")
            sender_id = sender_type = None
        else:
            sender_id = sender.id
            if isinstance(sender, TelethonUser):
                sender_type = SenderType.USER
            elif isinstance(sender, TelethonChannel):
                sender_type = SenderType.CHANNEL
            else:
                self._logger.warning(
                    f"메세지 송신자가 알려지지 않은 타입입니다. Expected `User` or `Channel`, got `{type(sender)}`",
                )
                sender_type = None
        Message.from_telethon(
            message,
            sender_id=sender_id,
            chat_id=message.id,
            sender_type=sender_type
        ).store()


class FakeMessageHandler(MessageHandler):
    """Fake message handler that simply logs received messages.

    This handler is used for testing and debugging purposes.
    """
    _logger = Logger("FakeMessageHandler")

    def __init__(self):
        super().__init__()

    async def __call__(self, message):
        self._logger.debug(message.message)