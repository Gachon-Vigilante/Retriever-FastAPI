"""Watson RAG 시스템의 메모리 관리 및 체크포인트 관련 기능 모듈.

Attributes:
    checkpointer: LangGraph MongoDBSaver 인스턴스
"""
import typing

from langgraph.checkpoint.mongodb import MongoDBSaver

from core.constants import mongo_db_name
from core.mongo.connections import MongoCollections, mongo_client

if typing.TYPE_CHECKING:
    from .bot import Watson


checkpointer = MongoDBSaver(mongo_client(),
                            db_name=mongo_db_name,
                            checkpoint_collection_name=MongoCollections().chatbot_checkpoints.name,
                            writes_collection_name=MongoCollections().chatbot_checkpoint_writes.name,)


class MemoryMethods:
    """챗봇의 메모리(체크포인트) 관리 메서드를 제공하는 클래스입니다."""
    def clear_memory(self: 'Watson') -> None:
        """MongoDB에 저장된 챗봇의 기억을 제거하는 메서드.

        Returns:
            None
        """
        MongoCollections().chatbot_checkpoints.delete_many({"thread_id": self.id})
        MongoCollections().chatbot_checkpoint_writes.delete_many({"thread_id": self.id})

        if self.cache:
            self.cache.clear_all()
