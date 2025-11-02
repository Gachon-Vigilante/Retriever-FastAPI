from typing import Optional
import os

import weaviate
from langchain_weaviate import WeaviateVectorStore
from weaviate import WeaviateClient
from weaviate.collections.classes.config import Configure, Property, DataType
from weaviate.exceptions import WeaviateGRPCUnavailableError

from utils import Logger
from ..constants import weaviate_http_host, weaviate_http_port, weaviate_grpc_host, weaviate_grpc_port, \
    weaviate_headers, weaviate_index_name, WeaviateProperties

logger = Logger(__name__)

def connect_weaviate() -> WeaviateClient:
    """로컬 Weaviate 인스턴스에 연결합니다.

    연결 시 gRPC 헬스 체크가 실패하면 예외를 잡아서 gRPC를 비활성화(및 초기화 체크 건너뜀)한 상태로
    HTTP 전용 연결로 재시도합니다. 또한 예기치 않은 연결 예외에 대해서도 동일한 방식으로 재시도합니다.

    환경변수:
        WEAVIATE_SKIP_INIT_CHECKS=1  -> 항상 skip_init_checks=True로 시작해서 gRPC 헬스체크를 건너뜁니다.

    Returns:
        WeaviateClient: 연결된 Weaviate 클라이언트
    """
    # 환경변수로 강제 스킵 설정이 되어 있으면 처음부터 초기화 체크를 건너뜁니다.
    if os.getenv("WEAVIATE_SKIP_INIT_CHECKS", "").lower() in ("1", "true", "yes"):
        logger.info("WEAVIATE_SKIP_INIT_CHECKS set; connecting with skip_init_checks=True (HTTP-only)")
        return weaviate.connect_to_custom(
            http_host=weaviate_http_host,
            http_port=weaviate_http_port,
            http_secure=False,
            headers=weaviate_headers,
            grpc_host=weaviate_grpc_host,
            grpc_port=weaviate_grpc_port,
            grpc_secure=False,
            skip_init_checks=True,
        )

    try:
        # 기본 시도: gRPC 포함 (기본 동작)
        return weaviate.connect_to_custom(
            http_host=weaviate_http_host,
            http_port=weaviate_http_port,
            http_secure=False,
            grpc_host=weaviate_grpc_host,
            grpc_port=weaviate_grpc_port,
            headers=weaviate_headers,
            grpc_secure=False,
        )
    except (WeaviateGRPCUnavailableError, Exception) as e:
        # gRPC 또는 다른 연결 문제가 발생한 경우: 로그 후 gRPC 없이, 초기화 체크를 건너뛰고 HTTP 전용으로 재시도
        # (Exception까지 포괄적으로 잡는 이유는 환경에 따라 다른 예외가 발생할 수 있기 때문입니다.)
        logger.warning("Weaviate connection failed (%s). Falling back to HTTP-only connection with skip_init_checks=True.", e)
        return weaviate.connect_to_custom(
            http_host=weaviate_http_host,
            http_port=weaviate_http_port,
            http_secure=False,
            headers=weaviate_headers,
            grpc_host=weaviate_grpc_host,
            grpc_port=weaviate_grpc_port,
            grpc_secure=False,
            skip_init_checks=True,
        )


class WeaviateClientContext:
    """with 문에서 Weaviate 클라이언트 연결을 관리하는 컨텍스트 매니저 클래스입니다."""
    def __enter__(self):
        """컨텍스트 진입 시 Weaviate 클라이언트 연결을 반환합니다.

        주의: connect_to_custom 내부에서 이미 초기화(또는 초기화 체크 건너뛰기)를 수행하므로
        여기서 추가로 client.connect()를 호출하지 않습니다. 추가 호출은 gRPC 헬스 체크를 재발생시켜
        초기화 실패를 유발할 수 있습니다.
        """
        self.client = connect_weaviate()
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
