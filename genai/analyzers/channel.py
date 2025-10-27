from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from pydantic import BaseModel, Field

from core.mongo.connections import MongoCollections
from core.mongo.channel import Catalog, ChannelFields
from core.mongo.message import MessageFields
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


SORT_FIELD = MessageFields.message_id  # 정렬 기준 필드
N_SAMPLES = 100  # 원하는 총 샘플 개수

async def get_channel_samples(channel_id: int) -> list[dict]:
    # --- 1. 설정 ---
    message_collection = MongoCollections().messages
    mongo_filter = {MessageFields.channel_id: channel_id}

    # --- 2. 총 문서 수 확인 및 간격 계산 ---
    total_docs = message_collection.count_documents(mongo_filter)

    if total_docs == 0 or N_SAMPLES <= 0:
        logger.warning(f"채널에서 샘플링할 문서가 없거나 샘플 개수가 0입니다. "
                       f"ID: {channel_id}")
        samples = []
    elif total_docs <= N_SAMPLES:
        logger.info(f"문서 개수({total_docs})가 샘플 개수({N_SAMPLES})보다 적어 모든 문서를 반환합니다. "
                    f"ID: {channel_id}")
        # 문서가 N개 이하면 그냥 모두 가져옴
        samples = list(message_collection.find(mongo_filter).sort(SORT_FIELD, 1))
    else:
        # N개의 샘플을 고르기 위한 간격(interval) 계산
        # 예: 1000개 문서, 100개 샘플 -> 간격 = 10
        # 1, 11, 21, ... 번째 문서를 선택
        interval = total_docs // N_SAMPLES

        # --- 3. Aggregation Pipeline 실행 ---
        pipeline = [
            {
                # 1. 지정한 필드로 정렬 (1: 오름차순, -1: 내림차순)
                "$sort": {SORT_FIELD: 1}
            },
            {
                # 2. (MongoDB 5.0+) 정렬된 순서대로 1부터 시작하는 "index" 필드 추가
                "$setWindowFields": {
                    "partitionBy": None,  # 전체 문서를 하나의 파티션으로
                    "sortBy": {SORT_FIELD: 1},  # $sort와 반드시 일치해야 함
                    "output": {
                        "index": {"$documentNumber": {}}
                    }
                }
            },
            {
                # 3. 계산된 간격(interval)에 맞는 문서만 필터링
                # (index - 1) % interval == 0 인 문서를 선택
                "$match": {
                    "$expr": {
                        "$eq": [
                            {"$mod": [{"$subtract": ["$index", 1]}, interval]},
                            0
                        ]
                    }
                }
            },
            {
                # 4. (선택 사항) 샘플링에 사용된 "index" 필드 제거
                "$project": {
                    "index": 0
                }
            }
        ]

        print(f"총 {total_docs}개 문서에서 {interval} 간격으로 샘플링합니다...")
        samples = list(message_collection.aggregate(pipeline))

    return samples


class BinaryClassification(BaseModel):
    """A binary score for whether telegram channel sells drugs or not."""
    binary_classification: bool = Field(
        description="""
            If the given chat history from a Telegram channel indicates that drugs are being sold or promoted, return True. 
            If drugs are not being sold or promoted, or if there is no chat history, return False."
        """
    )

async def is_channel_active(channel_id: int):
    message_samples = get_channel_samples(channel_id)

    # LLM 모델 초기화 -> 구조화된 출력을 위한 LLM 설정
    llm_with_structured_output = llm.with_structured_output(BinaryClassification)

    # HTML을 분석해서 마약 홍보글 여부와 텔레그램 링크를 요구하는 프롬프트 템플릿 정의
    system_prompt = SystemMessagePromptTemplate.from_template(
        """You are an assistant to an investigator tracking illegal drug sales on telegrams.
    
        You are given text extracted from telegram channel. Your job is to detect if the channel explicitly promotes the sale of illegal drugs.
    
        The following argot terms are commonly used to refer to illegal drugs:
    
        ### **Drug-related argot examples:**
        - 떨, 위드, 허브, 해쉬, 브액, 대마초, 대마, 고기 (refers to marijuana)
        - 아이스, 크리스탈, 술, 히로뽕, 필로폰, 작대기, 빙두 (refers to methamphetamine)
        - 몰리, 엑시, 엑스터시, 도리도리, 캔디, XTC (refers to MDMA or ecstasy)
        - 엘, 엘에스디, LSD (LSD)
        - 케이 (Ketamine)
    
        If the given chat history from a Telegram channel indicates that drugs are being sold or promoted, return True. 
        If drugs are not being sold or promoted, or if there is no chat history, return False.
    
        ### **Rules:**
        - Only rely on what is explicitly written in the text.
        - Do not hallucinate or imagine any content not present.
        - If the meaning is unclear or ambiguous, return `False` and leave other fields empty.
        """,
    )
    human_prompt = HumanMessagePromptTemplate.from_template("""Analyze the following text:\n\n{text}\n\n""")

    # prompt + llm 바인딩 체인 생성
    chain = ChatPromptTemplate.from_messages([system_prompt, human_prompt]) | llm_with_structured_output

    # 결과 수신
    analysis = chain.invoke({"text": " ".join([dict_to_xml(s) for s in await message_samples])})
    return analysis.binary_classification
