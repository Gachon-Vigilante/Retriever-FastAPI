from typing import List, TYPE_CHECKING, Optional
from pydantic import Field

from langchain_core.documents import Document
from langchain_core.tools import BaseTool, tool
from weaviate.classes.query import Rerank

from utils import Logger, dict_to_xml
from .vectorstore import parse_filter_node, parse_sort_list
from ..constants import WeaviateProperties, weaviate_index_name
from ..vectorstore.weaviate import WeaviateClientContext

if TYPE_CHECKING:
    from .bot import Watson

logger = Logger(__name__)

class Tools:
    # 문서 검색 도구
    def get_retriever_tool(self: 'Watson'):
        @tool
        def retriever_from_weaviate(
                original_question: str = Field(
                    title="Original Question",
                    description="The user's original question to be answered by the chatbot. This field is REQUIRED."
                ),
                query: Optional[list[str]] = None,
                filters: Optional[dict] = None,
                sort: Optional[list[dict]] = None,
                limit: Optional[int] = 10
        ) -> str:
            """
            Retrieves relevant Telegram chat messages from a Weaviate collection using semantic query and structured filters.

            This tool supports both vector-based similarity search (`near_text`) and traditional metadata-based filtering
            (`fetch_objects`) depending on whether a semantic query is provided.

            Parameters:
                - original_question(str): The user's original question to be answered. This field is required.
                - query (Optional[str]): A semantic search string. If provided, vector similarity (`near_text`) is used.
                - filters (Optional[dict]): A nested filter structure in JSON format specifying logical conditions for message retrieval.
                    Must use only allowed fields: "message", "views", "timestamp".
                    Logical operators supported: "and", "or". Not supported: "not".
                    Comparison operators: "eq", "neq", "gt", "gte", "lt", "lte", "like", "contains_any", "contains_all", "isnull".
                - sort (Optional[List[dict]]): A list of sorting preferences. Each element must include:
                    - "field": one of ["message", "views", "date"]
                    - "direction": "asc" (ascending) or "desc" (descending)
                - limit (int): Maximum number of results to return. If unspecified, defaults to 10.

            Behavior:
            - If `query` is provided, performs vector search using `near_text`.
            - If `query` is not provided, performs metadata-only filtering using `fetch_objects`.
            - Regardless of mode, results are always filtered by the allowed `channel_ids` via an internal AND condition.
            - Results are returned as XML-like formatted string for downstream processing.

            Returns:
            - A string of chat documents, each formatted as:
              <document>
                <context>{chat_text}</context>
                <metadata>
                    <timestamp>...</timestamp>
                    <url>...</url>
                    <views>...</views>
                </metadata>
              </document>


            # When using `retriever_from_weaviate` tool

            ## parameter "filters"
            parameter "filters" is an optional nested `LogicalFilter` structure.
            LogicalFilter is one of:
            - {{ "and": [LogicalFilter, ...] }}
            - {{ "or": [LogicalFilter, ...] }}
            - {{ "field": str, "op": str, "value": Any }}

            ## Constraints:
            - only return fields, filters, and sort conditions that are **explicitly stated** in the question.
            - Do **NOT guess** or infer missing information.
            - Logical operators allowed: "and", "or"
            - `not` is **not supported**
            - You may only use the following fields for filtering or sorting:
            - `message` (type: TEXT)
            - `views` (type: INT)
            - `date` (type: DATE)

            Return only the fields listed above. If anything is unclear or not explicitly requested, omit it or set to null.

            ## Field-specific operator rules:
            - `message` (TEXT):
            - allowed operators: `"eq"`, `"neq"`, `"like"`, `"isnull"`
            - `views` (INT):
            - allowed operators: `"eq"`, `"neq"`, `"gt"`, `"gte"`, `"lt"`, `"lte"`, `"isnull"`
            - DO NOT use `"like"`, `"contains_*"` on `views`
            - `date` (DATETIME):
            - Only `gte` (greater than or equal), `lte` (less than or equal), `gt` (greater than) and `le`(less than) operators are allowed.
            - Value must be in valid UTC ISO 8601 format ending with 'Z'. (e.g., "2025-01-01T00:00:00Z")

            If an invalid operator is used with a field (e.g., `like` on `date`), reject that condition or omit it entirely.

            ## Examples:
            1. question: question: "2025년 4월 1일부터 2025년 5월 1일까지 올라온 조회수 높은 메시지 3개 보여줘"
            ->
              "query": null,
              "filters": {{
                "and": [
                  {{ "field": "date", "op": "gte", "value": "2025-04-01T00:00:00Z" }},
                  {{ "field": "date", "op": "lt", "value": "2025-05-02T00:00:00Z" }}
                ]
              }},
              "sort": [{{ "field": "views", "direction": "desc" }}],
              "limit": 3

            2. question: "'좌표'나 '링크'가 들어간 텍스트를 시간순으로 정렬해서 보여줘"
            ->
              "query": null,
              "filters": {{
                "or": [
                  {{ "field": "message", "op": "like", "value": "*좌표*" }},
                  {{ "field": "message", "op": "like", "value": "*링크*" }}
                ]
              }},
              "sort": [{{ "field": "date", "direction": "asc" }}],
              "limit": null

            ### Additional Guidance on `message` Field Usage
            Do not use a "message" filter with the "like" operator unless the user explicitly requests that a specific word or phrase must appear in the message.

            If the user's question is phrased semantically (e.g., "어떤 채팅에서 직원 모집 공고가 있었나?") and does not specify an exact substring to be matched, then use the "query" field with a natural language string instead of a filter.

            Examples:
            "'링크'가 포함된 메세지를 보여줘" -> use filters with {{"field": "message", "op": "like", "value": "*link*"}}
            "어느 지역에서 판매돼?" -> use query=["지역", "좌표"], do not use a message filter
            "상품 안내를 하는 채팅이 있어?" -> use query=["상품"], do not use a message filter
            "거래 연락처가 어떻게 되지?" -> use query=["거래", "연락"], do not use a message filter
            "드라퍼 구인 정보가 포함된 글을 알려줘" -> use query=["드라퍼", "직원", "모집", "구인"], do not use a message filter
            "거래 방식이 포함된 글을 알려줘" -> use query=["거래 방식"], do not use a message filter
            "가격 이벤트를 언제 했지?" -> use query=["가격 이벤트", "할인"], do not use a message filter

            # When using `get_drug_pricing_information` tool for Price-related queries:
            If the user's question is about price, price range, or payment amount (e.g., contains terms like "가격", "가격대", "금액", "얼마", "비용", etc.),
            **do not attempt to generate additional arguments or parameters.**

            Instead, a dedicated tool for price intelligence should be called.

            This is because questions about drug pricing require deeper structured reasoning and catalog-style summarization, which is better handled by a specialized tool rather than raw retrieval.

            """
            limit = min(20, limit) if limit else 8
            channel_id_filter = {
                "or": [
                    {"field": WeaviateProperties.channel_id, "op": "eq", "value": channel_id}
                    for channel_id in [channel.channel_id for channel in self.channels]
                ]
            }

            filters = {
                "and": [
                    filters,
                    channel_id_filter
                ]
            } if filters else channel_id_filter

            with WeaviateClientContext() as client:
                filter_obj = parse_filter_node(filters) if filters else None
                sort_obj = parse_sort_list(sort) if sort else None
                collection = client.collections.get(weaviate_index_name)

                # near_text or fetch_objects
                if query:
                    # rerank된 결과로 20개를 고정적으로 받아오고, 그 후 limit으로 잘라낸다.
                    response = collection.query.near_text(
                        query=query,
                        filters=filter_obj,
                        rerank=Rerank(
                            prop=WeaviateProperties.message,
                            query=original_question
                        ),
                        # sort: 벡터 검색 수행 시에는 sort 인자는 사용 불가!
                        limit=20  # limit은 사용 가능하긴 한데 벡터 검색 시에는 불필요함. 대신 rerank한 결과에서 나중에 limit만큼 잘라낼것
                    )
                else:
                    response = collection.query.fetch_objects(
                        filters=filter_obj,
                        sort=sort_obj,
                        limit=limit
                    )

                # 결과를 LangChain Document로 변환
                documents = []
                for i, obj in enumerate(response.objects):
                    if i >= limit:
                        break
                    page_content = obj.properties.get(WeaviateProperties.message) or ""
                    metadata = {
                        "channel id": obj.properties.get(WeaviateProperties.message.channel_id),
                        "timestamp": obj.properties.get(WeaviateProperties.date),
                        "views": obj.properties.get(WeaviateProperties.views),
                    }
                    documents.append(Document(page_content=page_content, metadata=metadata))

            message = "\n\n".join(
                f"<document><context>{doc.page_content}</context><metadata>{dict_to_xml(doc.metadata)}</metadata></document>"
                for doc in documents
            )

            return message
        return retriever_from_weaviate

    def get_drug_pricing_tool(self: 'Watson'):
        @tool
        def get_drug_pricing_information() -> str:
            """
            Retrieves structured summaries of drug pricing information from monitored Telegram channels.

            For each channel where catalog data is available, this function returns a formatted document containing:
            - <channel_id>: The unique Telegram channel ID
            - <catalog>: A human-readable summary of drug product types and their prices, grouped by item
            - <source>: A comma-separated list of t.me URLs pointing to the original Telegram messages containing the pricing information

            Only channels that have both catalog description and message references (chatIds) will be included.

            Returns:
                A concatenated XML-style string with one <document> block per channel, each containing:
                <channel_id>...</channel_id>
                <catalog>...</catalog>
                <sources>...</sources>

            This output is designed to be read by an AI model or investigator for reviewing summarized pricing intelligence per channel.
            """
            doc = ""
            for channel in self.channels:
                if channel.catalog and channel.catalog.message_ids:
                    doc += "<document>"
                    doc += f"<channel_id>{channel.channel_id}</channel_id>"
                    doc += f"<catalog>{channel.catalog.summary}</catalog>"
                    sources = [f"<url>https://t.me/{channel.username}/{message_id}</url>" for message_id in
                               channel.catalog.message_ids]
                    doc += f"<sources>\n{"\n".join(sources)}\n</sources>"
                    doc += f"</document>"
            return doc
        return get_drug_pricing_information

    def get_toolbox(self: 'Watson'):
        return [
            self.get_retriever_tool(),
            self.get_drug_pricing_tool(),
        ] + static_tools


# 2. Tools 클래스의 모든 정적 멤버 중 Tool 인스턴스인 것만 가져오기
static_tools: List[BaseTool] = []

for attr_name in dir(Tools):
    attr = getattr(Tools, attr_name)
    if isinstance(attr, BaseTool):
        static_tools.append(attr)

logger.info(f"현재 챗봇 Agent가 사용 가능한 정적 도구 목록: {[t.name for t in static_tools]}")
