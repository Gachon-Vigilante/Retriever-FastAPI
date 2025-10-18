"""클러스터링(채널) 라우트 모듈

채널 메시지를 기반으로 한 채널 간 유사도 계산 작업을 트리거하는 엔드포인트를 제공합니다.
운영 환경에서는 배치/관리자 전용으로 사용하며, 대량 연산이 수행될 수 있습니다.

주의: 문서화만 추가되었고 기능 변경은 없습니다.
"""
from fastapi import APIRouter
from clustering.channel import calculate_and_store_channel_similarity
from clustering.channel_come_in import calculate_similarity_for_new_channels

router = APIRouter()

@router.post("/similarity")
def calculate_channel_similarity_endpoint():
    """채널 간 유사도 일괄 계산 엔드포인트

    전체 채널의 메시지를 종합하고, 마약 키워드 가중치를 적용하여 채널 간 유사도를 계산/저장합니다.

    Returns:
        dict: 처리 결과 메시지.
    """
    return calculate_and_store_channel_similarity()

@router.post("/new-channel-similarity")
def new_channel_similarity_endpoint():
    """신규 채널 유사도 계산 엔드포인트

    새로 추가된 채널과 기존 채널들 간의 유사도를 계산하고 저장합니다.

    Returns:
        dict: 처리 결과 메시지.
    """
    return calculate_similarity_for_new_channels()
