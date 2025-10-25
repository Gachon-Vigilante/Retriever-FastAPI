"""텔레그램 채널 핸들러 모듈

Telethon에서 수집된 텔레그램 채널 정보를 처리하여 MongoDB와 Neo4j에 저장합니다.
TelethonChannel 객체를 내부 Channel(Pydantic) 및 ChannelNode(Neo4j)로 변환하고
영속화하는 비즈니스 로직을 담당합니다.
"""

from telethon.tl.types import Channel as TelethonChannel

from core.mongo.channel import Channel
from core.neo4j.ogm import ChannelNode


class ChannelHandler:
    """텔레그램 채널 처리 및 저장 작업을 담당하는 핸들러 클래스

    Telethon 라이브러리로 수집된 채널 정보를 처리합니다. TelethonChannel 객체를
    내부 Channel 모델로 변환하고 MongoDB에 저장하며, 그래프 분석을 위해 Neo4j 노드로도
    투영합니다. callable 객체로 구현되어 Telethon 이벤트 핸들러로 바로 사용할 수 있습니다.

    Attributes:
        없음: 현재 특별한 인스턴스 속성을 가지지 않습니다.

    Examples:
        # 핸들러 인스턴스 생성
        handler = ChannelHandler()

        # 채널 처리 (비동기)
        await handler(telethon_channel)

        # Telethon 이벤트 핸들러로 등록
        client.add_event_handler(handler, events.ChatAction)

    Note:
        이 핸들러는 채널 정보만 처리합니다. 메시지 처리는 별도의 MessageHandler를 사용하세요.
    """

    def __init__(self):
        """ChannelHandler 인스턴스를 초기화합니다.

        현재는 특별한 초기화 작업이 없으며, 향후 확장을 위해 정의되었습니다.
        로거나 설정 객체 등을 초기화할 수 있는 확장 지점입니다.
        """
        pass

    async def __call__(self, telethon_channel: TelethonChannel):
        """Telethon 채널 객체를 처리하고 저장하는 비동기 callable 메서드

        제공된 TelethonChannel 객체를 내부 Channel 모델로 변환하고 MongoDB에 저장합니다.
        또한 ChannelNode로 변환하여 Neo4j에도 반영합니다. 날짜/시간 정보는 ISO 형식으로 직렬화됩니다.

        Args:
            telethon_channel (TelethonChannel): 처리할 Telethon 채널 객체

        Returns:
            None: 반환값이 없습니다.

        Raises:
            pymongo.errors.PyMongoError: MongoDB 연결 또는 저장 오류 시 발생
            ValidationError: 채널 데이터 검증 실패 시 발생 (Pydantic)

        Examples:
            handler = ChannelHandler()
            await handler(some_telethon_channel)
        """
        # datetime을 ISO 형식 문자열로 변환하여 직렬화
        channel: Channel = Channel.from_telethon(telethon_channel)
        channel_node: ChannelNode = ChannelNode.from_mongo(channel.model_dump())
        channel.store()
        channel_node.merge()
