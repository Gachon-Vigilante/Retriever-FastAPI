"""텔레그램 채널 핸들러 모듈 - Telethon 채널 객체 처리 및 저장

이 모듈은 Telethon에서 수집된 텔레그램 채널 정보를 처리하고 MongoDB에 저장하는
핸들러를 제공합니다. TelethonChannel 객체를 내부 Channel 모델로 변환하고
데이터베이스에 영구 저장하는 기능을 담당합니다.

Telegram Channel Handler Module - Processing and storage of Telethon channel objects

This module provides handlers for processing Telegram channel information collected
from Telethon and storing it in MongoDB. It is responsible for converting TelethonChannel
objects to internal Channel models and permanently storing them in the database.
"""

from telethon.tl.types import Channel as TelethonChannel

from core.mongo.channel import Channel


class ChannelHandler:
    """텔레그램 채널 처리 및 저장 작업을 담당하는 핸들러 클래스

    Telethon 라이브러리를 통해 수집된 채널 정보를 처리합니다.
    TelethonChannel 객체를 내부 Channel 모델로 변환하고, MongoDB에 저장하는
    기능을 제공합니다. callable 객체로 구현되어 이벤트 핸들러로 직접 사용할 수 있습니다.

    Handler class responsible for processing and storing Telegram channels

    Processes channel information collected through the Telethon library.
    Provides functionality to convert TelethonChannel objects to internal Channel models
    and store them in MongoDB. Implemented as a callable object for direct use as an event handler.

    Attributes:
        None: 현재 특별한 인스턴스 속성을 가지지 않습니다.
             Currently has no special instance attributes.

    Examples:
        # 핸들러 인스턴스 생성
        handler = ChannelHandler()

        # 채널 처리 (비동기)
        await handler(telethon_channel)

        # Telethon 이벤트 핸들러로 등록
        client.add_event_handler(handler, events.ChatAction)

    Note:
        이 핸들러는 채널 정보만을 처리합니다. 메시지 처리는 별도의
        MessageHandler를 사용해야 합니다.

        This handler only processes channel information. Message processing
        requires a separate MessageHandler.
    """

    def __init__(self):
        """ChannelHandler 인스턴스를 초기화합니다.

        현재는 특별한 초기화 작업이 없으며, 향후 확장을 위해 정의되었습니다.
        로거나 설정 객체 등을 초기화할 수 있는 확장 지점입니다.

        Initialize the ChannelHandler instance.

        Currently performs no special initialization tasks, defined for future extensibility.
        This is an extension point where loggers or configuration objects can be initialized.
        """
        pass

    async def __call__(self, telethon_channel: TelethonChannel):
        """Telethon 채널 객체를 처리하고 저장하는 비동기 callable 메서드

        제공된 TelethonChannel 객체를 내부 Channel 모델로 변환하고
        MongoDB에 영구 저장합니다. 데이터 변환 과정에서 날짜/시간 정보는
        ISO 형식으로 직렬화되어 저장됩니다.

        Asynchronous callable method for processing and storing Telethon channel objects

        Converts the provided TelethonChannel object to an internal Channel model
        and permanently stores it in MongoDB. Date/time information is serialized
        in ISO format during the data conversion process.

        Args:
            telethon_channel (TelethonChannel): 처리할 Telethon 채널 객체
                                              Telethon channel object to process

        Returns:
            None: 반환값이 없습니다.
                  No return value

        Raises:
            pymongo.errors.PyMongoError: MongoDB 연결 또는 저장 오류 시 발생
                                        Raised on MongoDB connection or storage errors
            ValidationError: 채널 데이터 검증 실패 시 발생 (Pydantic)
                           Raised on channel data validation failure (Pydantic)

        Examples:
            handler = ChannelHandler()

            # 단일 채널 처리
            await handler(some_telethon_channel)

            # 여러 채널 처리
            for channel in telethon_channels:
                await handler(channel)

        Note:
            저장 과정:
            1. TelethonChannel -> Channel 모델 변환
            2. 날짜/시간 데이터 ISO 형식 직렬화
            3. MongoDB channels 컬렉션에 저장

            Storage process:
            1. Convert TelethonChannel -> Channel model
            2. Serialize date/time data to ISO format
            3. Store in MongoDB channels collection
        """
        # datetime을 ISO 형식 문자열로 변환하여 직렬화
        channel: Channel = Channel.from_telethon(telethon_channel)
        channel.store()