from datetime import datetime
from typing import Dict, List, Optional, Sequence

from langchain_community.document_loaders import MongodbLoader
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from core.constants import mongo_connection_string, mongo_db_name
from core.mongo.connections import MongoCollections
from core.mongo.message import MessageFields
from utils import Logger
from ..constants import WeaviateProperties

logger = Logger(__name__)

class MappedMongodbLoader(MongodbLoader):
    """MongoDB에서 데이터를 로드할 때 메타데이터 필드명을 매핑하여 반환하는 커스텀 로더 클래스입니다."""
    def __init__(
            self,
            connection_string: str,
            db_name: str,
            collection_name: str,
            *,
            filter_criteria: Optional[Dict] = None,
            field_names: Optional[Sequence[str]] = None,
            metadata_names: Optional[Sequence[str]] = None,
            metadata_mapping: Optional[Dict[str, str]] = None,
            include_db_collection_in_metadata: bool = True,
    ) -> None:
        """커스텀 MongoDB 로더를 초기화합니다.

        Args:
            connection_string (str): MongoDB 연결 문자열
            db_name (str): 데이터베이스 이름
            collection_name (str): 컬렉션 이름
            filter_criteria (Optional[Dict]): 필터 조건
            field_names (Optional[Sequence[str]]): 로드할 필드명
            metadata_names (Optional[Sequence[str]]): 메타데이터 필드명
            metadata_mapping (Optional[Dict[str, str]]): 메타데이터 키 매핑
            include_db_collection_in_metadata (bool): DB/컬렉션 메타데이터 포함 여부
        """
        self.metadata_mapping = metadata_mapping or {}

        super().__init__(
            connection_string=connection_string,
            db_name=db_name,
            collection_name=collection_name,
            filter_criteria=filter_criteria,
            field_names=field_names,
            metadata_names=metadata_names,
            include_db_collection_in_metadata=include_db_collection_in_metadata,
        )

    async def aload(self) -> List[Document]:
        """비동기적으로 데이터를 Document 객체로 로드합니다. (메타데이터 필드명 매핑 적용)

        Returns:
            List[Document]: 로드된 Document 객체 리스트
        """
        result = []
        total_docs = await self.collection.count_documents(self.filter_criteria)
        projection = self._construct_projection()

        async for doc in self.collection.find(self.filter_criteria, projection):
            raw_metadata = self._extract_fields(doc, self.metadata_names, default="")

            # 필드명을 매핑된 키로 변환
            metadata = {}
            for k, v in raw_metadata.items():
                new_key = self.metadata_mapping.get(k, k)
                if k == "_id":
                    metadata[new_key] = str(v)
                elif isinstance(v, datetime):
                    # RFC3339 타입. weaviate에서는 date 속성에 대해 이 타입의 문자열을 기대하기 때문에, 이렇게 하지 않으면 에러 발생
                    metadata[new_key] = v.isoformat(timespec="seconds") + "Z"
                else:
                    metadata[new_key] = v

            if self.include_db_collection_in_metadata:
                metadata.update(
                    {
                        "database": self.db_name,
                        "collection": self.collection_name,
                    }
                )

            if self.field_names is not None:
                fields = self._extract_fields(doc, self.field_names, default="")
                texts = [str(value) for value in fields.values()]
                text = " ".join(texts)
            else:
                text = str(doc)

            result.append(Document(page_content=text, metadata=metadata))

        if len(result) != total_docs:
            logger.warning(
                f"Only partial collection of documents returned. "
                f"Loaded {len(result)} docs, expected {total_docs}."
            )

        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.client.close()

class MessageIdentifier(BaseModel):
    channel_id: int = Field(alias=MessageFields.channel_id)
    message_id: int = Field(alias=MessageFields.message_id)

async def build_loader(
        channel_ids: list[int],
        message_identifiers: Sequence[MessageIdentifier] = None,
) -> MongodbLoader:
    """MongoDB에서 특정 channel의 채팅 데이터를
    지정된 (channel_id, message_id) 조합 목록을 제외하고 로드하는 커스텀 로더를 반환합니다.

    Returns:
        MappedMongodbLoader: 커스텀 MongoDB 로더
    """
    # 데이터베이스에서 조회할 기준 (쿼리). 빈 텍스트가 아닌 채팅만 읽는 이유는, 빈 텍스트도 불러올 경우 벡터화 과정에서 오류 발생
    filter_criteria = {
        MessageFields.channel_id: {"$in": channel_ids},
        "$nor": [identifier.model_dump() for identifier in message_identifiers],
        MessageFields.message: {"$ne": ""}
    }
    if not message_identifiers: filter_criteria.pop("$nor")
    return MappedMongodbLoader(
        connection_string=mongo_connection_string,
        db_name=mongo_db_name,
        collection_name=MongoCollections().messages.name,
        filter_criteria=filter_criteria,
        field_names=(MessageFields.message,),
        # MongoDB의 필드 목록
        metadata_names=(
            "_id",
            MessageFields.message,
            MessageFields.channel_id,
            MessageFields.message_id,
            MessageFields.date,
            MessageFields.views,
        ),
        # MongoDB의 필드 이름을 문서의 메타데이터 필드 이름으로 변환하는 매핑 관계 정의
        metadata_mapping={
            "_id": WeaviateProperties.object_id,
        },
        # weaviate의 properties에는 database, collection 필드를 지정하지 않았음. 즉 여기서도 제외해야 함.
        include_db_collection_in_metadata=False,
    )