from fastapi import APIRouter
from clustering.channel import calculate_and_store_channel_similarity
from clustering.channel_come_in import calculate_similarity_for_new_channels

router = APIRouter()

@router.post("/similarity")
def calculate_channel_similarity_endpoint():
    """
    전체 채널의 메시지를 종합하고, 마약 키워드 가중치를 적용하여
    채널 간 유사도를 계산하고 저장합니다.
    """
    return calculate_and_store_channel_similarity()

@router.post("/new-channel-similarity")
def new_channel_similarity_endpoint():
    """
    새로 추가된 채널과 기존 채널들 간의 유사도를 계산하고 저장합니다.
    """
    return calculate_similarity_for_new_channels()
