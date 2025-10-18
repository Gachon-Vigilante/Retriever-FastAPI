from typing import TYPE_CHECKING

from weaviate.classes.query import Filter, Sort

from utils import Logger
from ..constants import weaviate_index_name, WeaviateProperties
from ..vectorstore.loaders import MessageIdentifier, build_loader
from ..vectorstore.weaviate import WeaviateClientContext

if TYPE_CHECKING:
    from .bot import Watson

logger = Logger(__name__)

def parse_filter_node(node: dict):
    """Weaviate 필터 노드를 재귀적으로 파싱하여 Filter 객체로 변환합니다.

    Args:
        node (dict): 필터 조건 노드

    Returns:
        Filter: 변환된 Weaviate Filter 객체
    """
    if "and" in node:
        return Filter.all_of([parse_filter_node(sub) for sub in node["and"]])
    if "or" in node:
        return Filter.any_of([parse_filter_node(sub) for sub in node["or"]])
    if "field" in node and "op" in node:
        field = node["field"]
        op = node["op"]
        value = node["value"]
        base = Filter.by_property(field)

        match op:
            case "eq": return base.equal(value)
            case "neq": return base.not_equal(value)
            case "gt": return base.greater_than(value)
            case "gte": return base.greater_or_equal(value)
            case "lt": return base.less_than(value)
            case "lte": return base.less_or_equal(value)
            case "like": return base.like(value)
            case "contains_any": return base.contains_any(value)
            case "contains_all": return base.contains_all(value)
            case "isnull": return base.is_none(value)
            case _: raise ValueError(f"Unsupported operator: {op}")

    raise ValueError("Invalid filter node structure")

def parse_sort_list(sort_json: list[dict]):
    """
        Converts a list of sort conditions into a chained Sort object.

        Each element in sort_json must be a dict like:
            { "field": "views", "direction": "desc" }

        Returns:
            Sort object with multiple fields chained via .by_property()
    """
    sort_obj = None
    for i, item in enumerate(sort_json):
        if i == 0:
            sort_obj = Sort.by_property(
                name=item["field"],
                ascending=(item["direction"] == "asc")
            )
        else:
            sort_obj = sort_obj.by_property(
                name=item["field"],
                ascending=(item["direction"] == "asc")
            )
    return sort_obj

class VectorStoreMethods:
    async def update_vectorstore(self: 'Watson'):
        """MongoDB와 Weaviate 벡터스토어를 동기화합니다.

        Returns:
            None
        """
        with WeaviateClientContext() as weaviate_client:
            for channel_id in [channel.channel_id for channel in self.channels]:
                collection = weaviate_client.collections.get(weaviate_index_name)
                response = collection.query.fetch_objects(
                    filters=Filter.by_property(WeaviateProperties.channel_id).equal(channel_id),
                    limit=10000,  # 10000이 최대인듯. 100000으로 하면 query maximum result exceeded 오류 발생
                )

                message_identifier_in_vectorstore = []

                for o in response.objects:
                    props = o.properties or {}
                    message_id = props.get(WeaviateProperties.message_id)
                    channel_id = props.get(WeaviateProperties.channel_id)

                    if channel_id is None or message_id is None: continue

                    message_identifier_in_vectorstore.append(
                        MessageIdentifier(channel_id=channel_id, message_id=message_id)
                    )

            # MongoDB에서 문서 로딩 후 Weaviate에 추가
            with await build_loader(channel_ids=[channel.channel_id for channel in self.channels],
                                    message_identifiers=message_identifier_in_vectorstore) as loader:
                if docs := await loader.aload():  # 문서 목록이 비어 있지 않을 때만 추가(비어 있을 경우 add_documents() 에서 오류 발생)
                    # # 문서 분할(Split Documents) -> 채팅 데이터가 크지 않아서 필요 없음.
                    # logger.debug(
                    #     f"Splitting loaded chat documents from MongoDB. Channel IDs: {self.channels}, scope: {self.scope}")
                    # text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
                    # split_documents = text_splitter.split_documents(docs)

                    self.vectorstore.add_documents(docs)
                    logger.debug(
                        f"Added documents to the vectorstore. Channel IDs: {[channel.channel_id for channel in self.channels]}")

            if weaviate_client.batch.failed_objects:
                for failed in weaviate_client.batch.failed_objects:
                    logger.error(f"Failed to add documents into weaviate: {failed}")

            self.info.update()  # MongoDB에서 현재 챗봇의 정보 업데이트 (없을 경우 신규 생성)
