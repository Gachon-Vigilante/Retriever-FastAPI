from core.mongo.message import Message


class EventHandler:
    """
    Handles chat events asynchronously.

    Provides functionality to handle events, process incoming messages,
    and store them for further use.
    """
    def __init__(self):
        pass

    async def __call__(self, telethon_event):
        """
        Handles an incoming Telethon event asynchronously.

        This handler processes the provided event if it is associated with a chat
        and contains a message. If these conditions are met, the message data is
        extracted and stored for further use.

        Parameters:
            telethon_event: The Telethon event object to be processed.

        Returns:
            None

        Raises:
            No exceptions are raised explicitly in this method.
        """
        # 이벤트가 채팅방 이벤트이고, 메세지가 있을 때에만
        if (await telethon_event.get_chat()) and (message := telethon_event.message):
            message: Message = Message.from_telethon(message)
            message.store()