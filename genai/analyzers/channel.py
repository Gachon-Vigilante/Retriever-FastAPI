from langchain_core.prompts import ChatPromptTemplate

from core.mongo.connections import MongoCollections
from core.mongo.channel import Catalog, ChannelFields
from core.mongo.types import ChannelStatus
from ..models import llm, prompts
from utils import Logger, dict_to_xml

logger = Logger(__name__)


async def get_catalog(channel_id: int) -> Catalog:
    """특정 텔레그램 채널에서 가격 정보를 추출합니다.

    Args:
        channel_id (int): 가격 정보를 추출할 텔레그램 채널 ID

    Returns:
        dict: 추출된 가격 정보와 관련 채팅 ID 목록
            - chatIds: 가격 정보가 포함된 채팅 ID 리스트
            - description: 가격 정보 요약 문자열
    """
    logger.info(f"텔레그램 채널에서 가격 정보 검색 시작. Channel ID: {channel_id}")
    messages_collection = MongoCollections().messages

    # g, ml, 정, 팟, 지, 통, 만원, 만과 같은 단위가 포함되어 있고 숫자도 있거나,
    # 숫자가 2개 이상 있는 채팅을 불러오는 aggregation pipeline.
    pipeline = [
        {
            "$match": {
                "$and": [  # 기존 필터와 channel_id 조건을 모두 만족해야 하므로 AND로 묶음
                    {
                        ChannelFields.channel_id: channel_id
                    },
                    {
                        "$or": [
                            {
                                "$and": [
                                    {
                                        "text": {
                                            "$regex": "(g|ml|정|팟|지|통|만원|만)",
                                            "$options": "i"
                                        }
                                    },
                                    {
                                        "text": {
                                            "$regex": "\\d"
                                        }
                                    }
                                ]
                            },
                            {
                                "$expr": {
                                    "$gte": [
                                        {
                                            "$size": {
                                                "$regexFindAll": {
                                                    "input": "$text",
                                                    "regex": "\\d"
                                                }
                                            }
                                        },
                                        2
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        }
    ]

    context = ["<chat>"+dict_to_xml({
        "id": doc["id"],
        "text": doc["text"],
    })+"</chat>" for doc in messages_collection.aggregate(pipeline)]

    if context:
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompts["channel"]["catalog"]),
            ("human", "Analyze this chats:\n{context}"),
        ])

        rag_chain = prompt | llm.with_structured_output(Catalog)

        catalog:Catalog = rag_chain.invoke({"context": context})
    else:
        catalog = Catalog()

    logger.info(f"가격 정보 검색 결과(Channel Id: {channel_id}: {catalog.summary}")

    return catalog

async def update_catalog(channel_id: int) -> None:
    """특정 채널의 가격 정보를 DB에 갱신합니다.

    Args:
        channel_id (int): 가격 정보를 갱신할 텔레그램 채널 ID
    """
    MongoCollections().channels.update_one(
        {"_id": channel_id},
        {"$set": {"catalog": get_catalog(channel_id)}}
    )

async def update_all_catalogs():
    for doc in MongoCollections().channels.find(
        {ChannelFields.status: ChannelStatus.ACTIVE},
        {ChannelFields.channel_id: 1}
    ):
        await update_catalog(doc[ChannelFields.channel_id])
