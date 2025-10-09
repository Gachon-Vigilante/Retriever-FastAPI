"""이벤트 핸들러 모듈 - Telethon 이벤트 처리를 위한 핸들러

이 모듈은 Telethon에서 발생하는 채팅 이벤트를 처리하고,
메시지를 파싱하여 데이터베이스에 저장하는 기능을 제공합니다.

Event Handler Module - Handler for processing Telethon events

This module processes chat events from Telethon and provides functionality
to parse messages and store them in the database.
"""

from core.mongo.message import Message

from utils import Logger


logger = Logger(__name__)

class EventHandler:
    """Telethon 채팅 이벤트를 비동기적으로 처리하는 핸들러 클래스

    Telethon에서 발생하는 새로운 메시지 이벤트를 감지하고,
    해당 메시지를 파싱하여 MongoDB에 저장하는 기능을 제공합니다.
    callable 객체로 구현되어 이벤트 핸들러로 직접 사용할 수 있습니다.

    Handler class for processing Telethon chat events asynchronously

    Detects new message events from Telethon, parses the messages,
    and stores them in MongoDB. Implemented as a callable object
    to be used directly as an event handler.

    Attributes:
        logger (Logger): 로깅을 위한 Logger 인스턴스
                        Logger instance for logging purposes
    """

    def __init__(self):
        """EventHandler 인스턴스를 초기화합니다.

        현재는 특별한 초기화 작업이 없으며, 향후 확장을 위해 정의되었습니다.

        Initialize the EventHandler instance.

        Currently performs no special initialization tasks,
        defined for future extensibility.
        """
        pass

    async def __call__(self, telethon_event):
        """Telethon 이벤트를 비동기적으로 처리하는 callable 메서드

        제공된 이벤트가 채팅과 연관되어 있고 메시지를 포함하는 경우에만 처리합니다.
        조건이 충족되면 메시지 데이터를 추출하고 데이터베이스에 저장합니다.

        Callable method for handling Telethon events asynchronously

        Processes the provided event only if it is associated with a chat
        and contains a message. If these conditions are met, the message data
        is extracted and stored in the database.

        Args:
            telethon_event: 처리할 Telethon 이벤트 객체
                           The Telethon event object to be processed

        Returns:
            None: 반환값이 없습니다.
                  No return value

        Raises:
            Exception: MongoDB 연결 또는 저장 과정에서 발생할 수 있는 예외
                      Exceptions that may occur during MongoDB connection or storage
        """
        # 이벤트가 채팅방 이벤트이고, 메세지가 있을 때에만
        if (chat := await telethon_event.get_chat()) and (message := telethon_event.message):
            message: Message = Message.from_telethon(message)
            logger.debug(f"새로운 메세지가 발생했습니다. Chat|Channel ID: {chat.id}, Message ID: {message.message_id}")
            message.store()