from typing import Optional

import weaviate
from langchain_weaviate import WeaviateVectorStore
from weaviate import WeaviateClient
from weaviate.collections.classes.config import Configure, Property, DataType

from utils import Logger
from ..constants import weaviate_http_host, weaviate_http_port, weaviate_grpc_host, weaviate_grpc_port, \
    weaviate_headers, weaviate_index_name, WeaviateProperties

logger = Logger(__name__)

def connect_weaviate() -> WeaviateClient:
    """로컬 Weaviate 인스턴스에 연결합니다.

    Returns:
        WeaviateClient: 연결된 Weaviate 클라이언트
    """
    return weaviate.connect_to_custom(
        http_host=weaviate_http_host,
        http_port=weaviate_http_port,
        http_secure=False,
        grpc_host=weaviate_grpc_host,
        grpc_port=weaviate_grpc_port,
        headers=weaviate_headers,
        grpc_secure=False,
    )


class WeaviateClientContext:
    """with 문에서 Weaviate 클라이언트 연결을 관리하는 컨텍스트 매니저 클래스입니다."""
    def __enter__(self):
        """컨텍스트 진입 시 Weaviate 클라이언트 연결을 반환합니다."""
        self.client = connect_weaviate()
        self.client.connect()
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료 시 클라이언트 연결을 닫습니다."""
        if hasattr(self.client, "close"):
            self.client.close()

def get_vectorstore(weaviate_client: Optional[WeaviateClient]=None):
    """Weaviate 벡터스토어 인스턴스를 반환합니다.

    Args:
        weaviate_client (Optional[WeaviateClient]): 외부에서 전달받은 클라이언트 (없으면 새로 연결)

    Returns:
        WeaviateVectorStore: 벡터스토어 인스턴스
    """
    return WeaviateVectorStore(
        client=weaviate_client if weaviate_client else connect_weaviate(),
        index_name=weaviate_index_name,
        text_key=WeaviateProperties.message,
    )


async def register_schema() -> None:
    """Weaviate에 TelegramMessages 스키마를 등록합니다.
    """
    with WeaviateClientContext() as client:
        # 먼저 클래스가 존재하는지 확인
        if weaviate_index_name in client.collections.list_all().keys():
            logger.info("TelegramMessages already exists in Weaviate.")
            return

        # weaviate index 생성
        client.collections.create(
            weaviate_index_name,
            description="Telegram channel messages with metadata",
            reranker_config=Configure.Reranker.cohere(),
            vectorizer_config=Configure.Vectorizer.text2vec_huggingface(model="upskyy/bge-m3-korean"),
            properties=[  # property configuration is optional
                Property(name=WeaviateProperties.object_id, data_type=DataType.TEXT),
                Property(name=WeaviateProperties.message, data_type=DataType.TEXT),
                Property(name=WeaviateProperties.channel_id, data_type=DataType.INT, skip_vectorization=True),
                Property(name=WeaviateProperties.message_id, data_type=DataType.INT, skip_vectorization=True),
                Property(name=WeaviateProperties.date, data_type=DataType.DATE, skip_vectorization=True),
                Property(name=WeaviateProperties.views, data_type=DataType.INT, skip_vectorization=True),
            ]
        )
        logger.info("TelegramMessages schema is created in Weaviate.")
