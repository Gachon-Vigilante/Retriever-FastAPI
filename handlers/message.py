"""텔레그램 메시지 핸들러 모듈 - Telethon 메시지 객체 처리 및 저장

이 모듈은 Telethon에서 수집된 텔레그램 메시지를 처리하고 MongoDB에 저장하는
다양한 핸들러들을 제공합니다. 발신자 정보 분석, 메시지 데이터 변환, 저장 등의
기능을 포함하며, 테스트용 가짜 핸들러도 함께 제공됩니다.

Telegram Message Handler Module - Processing and storage of Telethon message objects

This module provides various handlers for processing Telegram messages collected
from Telethon and storing them in MongoDB. It includes functionality for sender
information analysis, message data conversion, storage, and also provides
fake handlers for testing purposes.
"""

from typing import Union, Any

from telethon.tl.types import Message as TelethonMessage, User as TelethonUser, Channel as TelethonChannel

from core.mongo.message import Message
from core.mongo.types import SenderType
from utils import Logger


logger = Logger(__name__)

class MessageHandler:
    """텔레그램 메시지를 처리하는 기본 핸들러 클래스

    Telethon에서 수집된 메시지를 파싱하고 MongoDB에 저장하는 기능을 제공합니다.
    발신자 정보를 자동으로 분석하여 사용자/채널을 구분하고, 메시지 데이터를
    적절한 형태로 변환하여 저장합니다. callable 객체로 구현되어 있습니다.

    Base handler class for processing Telegram messages

    Provides functionality to parse messages collected from Telethon and store them in MongoDB.
    Automatically analyzes sender information to distinguish between users/channels,
    and converts message data to appropriate format for storage. Implemented as a callable object.

    Examples:
        # 핸들러 인스턴스 생성
        handler = MessageHandler()

        # 메시지 처리 (비동기)
        await handler(telethon_message)

        # Telethon 이벤트 핸들러로 등록
        client.add_event_handler(handler, events.NewMessage)

    Note:
        발신자 타입 감지 로직:
        - TelethonUser -> SenderType.USER
        - TelethonChannel -> SenderType.CHANNEL
        - 기타 -> None (경고 로그 출력)

        Sender type detection logic:
        - TelethonUser -> SenderType.USER
        - TelethonChannel -> SenderType.CHANNEL
        - Others -> None (warning log output)
    """

    async def __call__(self, message: Union[TelethonMessage, Any], chat_id: int):
        """텔레그램 메시지를 처리하고 저장하는 비동기 callable 메서드

        제공된 메시지의 발신자 정보를 분석하고, 메시지를 내부 Message 모델로
        변환하여 MongoDB에 저장합니다. 발신자를 가져올 수 없는 경우 에러 로그를 남기고
        발신자 정보 없이 처리를 계속합니다.

        Asynchronous callable method for processing and storing Telegram messages

        Analyzes sender information of the provided message, converts the message
        to internal Message model, and stores it in MongoDB. If sender cannot be retrieved,
        logs error and continues processing without sender information.

        Args:
            message (Union[TelethonMessage, Any]): 처리할 텔레그램 메시지 객체
                                                  Telegram message object to process

        Returns:
            None: 반환값이 없습니다.
                  No return value

        Raises:
            pymongo.errors.PyMongoError: MongoDB 연결 또는 저장 오류 시 발생
                                        Raised on MongoDB connection or storage errors

        Examples:
            handler = MessageHandler()

            # 단일 메시지 처리
            await handler(some_telethon_message)

            # 여러 메시지 처리
            for msg in telethon_messages:
                await handler(msg)

        Note:
            처리 과정:
            1. 메시지에서 발신자 정보 추출
            2. 발신자 타입 결정 (USER/CHANNEL)
            3. Message 모델로 변환
            4. MongoDB에 저장

            Processing steps:
            1. Extract sender information from message
            2. Determine sender type (USER/CHANNEL)
            3. Convert to Message model
            4. Store in MongoDB
        """
        sender = await message.get_sender()
        if not sender:
            logger.error("메세지 송신자를 받아올 수 없습니다.")
            sender_id = sender_type = None
        else:
            sender_id = sender.id
            if isinstance(sender, TelethonUser):
                sender_type = SenderType.USER
            elif isinstance(sender, TelethonChannel):
                sender_type = SenderType.CHANNEL
            else:
                logger.warning(
                    f"메세지 송신자가 알려지지 않은 타입입니다. Expected `User` or `Channel`, got `{type(sender)}`",
                )
                sender_type = None
        Message.from_telethon(
            message,
            sender_id=sender_id,
            chat_id=chat_id,
            sender_type=sender_type
        ).store()


class FakeMessageHandler(MessageHandler):
    """테스트 및 디버깅용 가짜 메시지 핸들러 클래스

    실제 데이터베이스 저장 없이 메시지 내용만을 로그로 출력하는 핸들러입니다.
    개발 환경에서 메시지 처리 로직을 테스트하거나 디버깅할 때 사용됩니다.
    MessageHandler를 상속받지만 저장 로직 대신 로깅만 수행합니다.

    Fake message handler class for testing and debugging purposes

    Handler that only logs message content without actual database storage.
    Used for testing message processing logic or debugging in development environment.
    Inherits from MessageHandler but performs only logging instead of storage logic.

    Examples:
        # 가짜 핸들러 인스턴스 생성
        fake_handler = FakeMessageHandler()

        # 메시지 처리 (로그만 출력)
        await fake_handler(telethon_message)

        # 테스트 환경에서 사용
        if testing_mode:
            handler = FakeMessageHandler()
        else:
            handler = MessageHandler()

    Note:
        이 핸들러는 실제 데이터를 저장하지 않으므로 프로덕션 환경에서는
        사용하지 않아야 합니다. 오직 개발/테스트 목적으로만 사용하세요.

        This handler does not store actual data, so it should not be used
        in production environment. Use only for development/testing purposes.
    """

    def __init__(self):
        """FakeMessageHandler 인스턴스를 초기화합니다.

        부모 클래스(MessageHandler)의 초기화를 호출합니다.
        별도의 추가 초기화 작업은 수행하지 않습니다.

        Initialize the FakeMessageHandler instance.

        Calls initialization of parent class (MessageHandler).
        Performs no additional initialization tasks.
        """
        super().__init__()

    async def __call__(self, message, chat_id):
        """메시지 내용을 디버그 로그로 출력하는 비동기 callable 메서드

        실제 저장 작업 없이 메시지의 텍스트 내용만을 디버그 레벨로 로그에 출력합니다.
        부모 클래스의 복잡한 처리 로직을 우회하여 간단한 로깅만 수행합니다.

        Asynchronous callable method that outputs message content as debug log

        Only outputs message text content to debug-level logs without actual storage.
        Bypasses complex processing logic of parent class to perform simple logging only.

        Args:
            message: 로그로 출력할 메시지 객체 (message.message 속성 필요)
                    Message object to output as log (requires message.message attribute)

        Returns:
            None: 반환값이 없습니다.
                  No return value

        Examples:
            fake_handler = FakeMessageHandler()

            # 메시지 로깅 (비동기)
            await fake_handler(some_message)
            # 출력: DEBUG - [메시지 내용]

        Note:
            이 메서드는 message.message 속성에 접근하므로, 전달되는 객체는
            해당 속성을 가져야 합니다. 일반적으로 TelethonMessage 객체를 사용합니다.

            This method accesses message.message attribute, so the passed object
            must have that attribute. Typically uses TelethonMessage objects.
        """
        logger.debug(message.message)