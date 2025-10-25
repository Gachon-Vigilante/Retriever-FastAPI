import threading
from typing import Optional

from langgraph.graph.state import CompiledStateGraph

from core.mongo.channel import Channel
from core.mongo.chatbots import ChatbotFields, Chatbot
from core.mongo.connections import MongoCollections
from genai.models import llm_model_name
from utils import generate_integer_id64, Logger
from .cache import SemanticCache
from .edges import LanggraphEdges
from .graph import LangGraphMethods
from .memory import MemoryMethods
from .nodes import LangGraphNodes
from .tools import Tools
from .vectorstore import VectorStoreMethods
from ..vectorstore.weaviate import get_vectorstore

logger = Logger(__name__)

class WatsonRegistry:
    """Watson 챗봇 인스턴스의 등록 및 관리 기능을 제공하는 레지스트리 클래스입니다."""
    instances: dict[int, 'Watson'] = {}
    _lock = threading.Lock()

    @classmethod
    def get(cls, bot_id: int) -> Optional['Watson']:
        """bot_id로 Watson 인스턴스를 조회합니다.

        Args:
            bot_id (int): Watson 인스턴스의 ID
        Returns:
            Optional[Watson]: Watson 인스턴스 또는 None
        """
        with cls._lock:
            return cls.instances.get(bot_id)

    @classmethod
    def register(cls, bot: 'Watson') -> None:
        """Watson 인스턴스를 레지스트리에 등록합니다.

        Args:
            bot (Watson): 등록할 Watson 인스턴스
        """
        with cls._lock:
            cls.instances[bot.id] = bot

    @classmethod
    def find_bot_id(cls, channel_ids: list[int]) -> Optional[int]:
        """채널 ID와 스코프로 Watson 인스턴스의 ID를 조회합니다.

        Args:
            channel_ids (list[int]): Watson이 참조하는 채널 ID 목록
        Returns:
            Optional[int]: Watson 인스턴스의 ID 또는 None
        """
        with cls._lock:
            for bot in cls.instances.values():
                if sorted(bot.channels) == sorted(channel_ids):
                    return bot.id
            return None

    @classmethod
    def load_existing_bots(cls) -> None:
        """DB에서 기존 Watson 인스턴스들을 모두 로드하여 레지스트리에 등록합니다."""
        for doc in MongoCollections().channels.find():
            bot = Watson(bot_id=doc['_id'], _from_db=True)
            cls.register(bot)


class Watson(
    VectorStoreMethods,
    LangGraphMethods,
    LangGraphNodes,
    LanggraphEdges,
    MemoryMethods,
    Tools,
):
    """RAG 기반 텔레그램 챗봇의 핵심 Watson 클래스입니다."""
    GLOBAL = "global"
    MULTI = "multi"
    LOCAL = "local"

    def __new__(cls, *, bot_id: Optional[int] = None, channels: Optional[list[Channel]] = None, _from_db: bool = False):
        """Watson 인스턴스를 생성하거나, 이미 존재하면 반환합니다.

        Args:
            bot_id (Optional[int]): Watson 인스턴스의 ID
            channels (Optional[list[Channel]]): Watson이 참조할 채널 ID 목록
            _from_db (bool): DB에서 직접 로드 여부
        Returns:
            Watson: Watson 인스턴스
        """
        if bot_id:
            if not _from_db:
                existing = WatsonRegistry.get(bot_id)
                if existing:
                    return existing
                else:
                    raise ValueError(f"ID {bot_id}로 생성된 Watson이 없습니다. DB에서 직접 로드할 수 없습니다.")
            else:
                # _from_db=True이면 무조건 새 인스턴스 생성
                return super().__new__(cls)

        if channels:
            found_bot_id = WatsonRegistry.find_bot_id([channel.channel_id for channel in channels])
            if found_bot_id is not None:
                return WatsonRegistry.get(found_bot_id)

            # 새로운 봇 생성
            new_bot = super().__new__(cls)
            return new_bot
        raise ValueError("bot_id 또는 (channel_ids와 scope) 둘 중 하나는 입력되어야 합니다.")

    def __init__(self, *, bot_id: Optional[int] = None, channels: Optional[list[Channel]] = None, _from_db: bool = False):
        """Watson 인스턴스를 초기화합니다.

        Args:
            bot_id (Optional[int]): Watson 인스턴스의 ID
            channels (Optional[list[Channel]]): Watson이 참조할 채널 ID 목록
            _from_db (bool): DB에서 직접 로드 여부
        """
        if not getattr(self, "initialized", False):
            if bot_id and _from_db:
                bot_info = MongoCollections().chatbots.find_one({ChatbotFields.chatbot_id: bot_id})
                if not bot_info:
                    raise KeyError(f"DB에 존재하지 않는 bot_id {bot_id}")
                chatbot = Chatbot.from_mongo(bot_info)
                self.id = chatbot.chatbot_id
                self.channels = [
                    Channel.from_mongo(doc)
                    for doc in MongoCollections().chatbots.find({ChatbotFields.channel_ids: chatbot.channel_ids})
                ]
                self.info: Chatbot = chatbot
                logger.info(f"챗봇 정보를 데이터베이스에서 로드했습니다. ID: {self.id}, channel IDs: {[channel.channel_id for channel in self.channels]}")
            elif channels:
                self.id = generate_integer_id64(existing_ids=WatsonRegistry.instances.keys())
                self.channels = channels
                self.info: Chatbot = Chatbot(
                    chatbot_id=self.id,
                    channel_ids=[channel.channel_id for channel in self.channels]
                )
                logger.info(f"새로운 챗봇을 생성했습니다. ID: {self.id}, channel IDs: {[channel.channel_id for channel in self.channels]}")
                self.vectorstore = get_vectorstore()
                self.cache: SemanticCache = SemanticCache(self.id)
                self.llm_name = llm_model_name
                self.graph: CompiledStateGraph = self._build_graph()
            else:
                raise ValueError("bot_id 또는 channel_ids와 둘 중 하나는 필요합니다.")

        if not getattr(self, "initialized", False):
            WatsonRegistry.register(self)
            logger.info(f"메모리에 챗봇을 등록했습니다. ID: {self.id}, channel IDs: {[channel.channel_id for channel in self.channels]}")

            self.initialized = True

    def update_mongo(self):
        self.info.update()