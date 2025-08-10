"""텔레그램 이벤트 핸들러 패키지 - Telethon 이벤트 처리를 위한 핸들러 모듈들

이 패키지는 Telethon에서 발생하는 다양한 텔레그램 이벤트를 처리하기 위한
핸들러 클래스들을 제공합니다. 채널 정보 처리, 메시지 처리, 전체 이벤트 처리 등
각각의 특화된 기능을 가진 핸들러들을 포함합니다.

Telegram Event Handler Package - Handler modules for processing Telethon events

This package provides handler classes for processing various Telegram events
that occur in Telethon. It includes handlers with specialized functions such as
channel information processing, message processing, and overall event processing.

Modules:
    channel: 텔레그램 채널 정보를 처리하는 핸들러
            Handler for processing Telegram channel information
    message: 텔레그램 메시지를 처리하는 핸들러들
            Handlers for processing Telegram messages
    event: 전체 텔레그램 이벤트를 처리하는 메인 핸들러
          Main handler for processing overall Telegram events

Classes:
    ChannelHandler: 채널 정보를 MongoDB에 저장하는 핸들러
                   Handler for storing channel information in MongoDB
    MessageHandler: 메시지를 파싱하고 저장하는 기본 핸들러
                   Base handler for parsing and storing messages
    FakeMessageHandler: 테스트 및 디버깅용 가짜 메시지 핸들러
                       Fake message handler for testing and debugging
    EventHandler: 모든 텔레그램 이벤트를 통합 처리하는 핸들러
                 Handler for integrated processing of all Telegram events

Examples:
    # 개별 핸들러 사용
    from handlers import ChannelHandler, MessageHandler

    channel_handler = ChannelHandler()
    message_handler = MessageHandler()

    # 통합 이벤트 핸들러 사용
    from handlers import EventHandler
    event_handler = EventHandler()

    # Telethon 클라이언트에 핸들러 등록
    client.add_event_handler(event_handler, events.NewMessage)
"""

from .channel import ChannelHandler
from .message import MessageHandler, FakeMessageHandler
from .event import EventHandler

__all__ = [
    'ChannelHandler',
    'MessageHandler',
    'FakeMessageHandler',
    'EventHandler',
]