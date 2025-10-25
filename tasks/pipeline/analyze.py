"""분석 배치 등록 태스크 모듈

이 모듈은 크롤링으로 수집된 게시글 텍스트를 Gemini Batch 분석 작업에 등록하기 위한
Celery 태스크를 제공합니다. 대용량 처리를 위해 실제 배치 제출/폴링은 다른 태스크에서
수행되며, 본 태스크는 특정 Post를 현재 ACCEPTING_REQUESTS Job에 안전하게 적재하는 역할을
담당합니다.

주의: 문서화만 추가되었으며, 기능 변경은 없습니다.
"""
import asyncio

from celery import shared_task

from genai.analyzers.post import PostAnalyzer
from utils import Logger
from ..names import ANALYSIS_TASK_NAME

logger = Logger(__name__)

# 반드시 동시에 1개만 실행되어야 하는 celery 프로세스. 
# 만약 2개 이상 실행될 경우 mongoDB에 여러 프로세스가 접근해서 동시에 분석 작업 컬렉션을 편집하려고 하기 때문에,
# 오류 또는 불필요한 데이터베이스 I/O가 발생할 수 있음.
@shared_task(name=ANALYSIS_TASK_NAME)
def analyze_batch_task(post_id: str, estimated_request_size: int) -> None:
    """게시글을 Gemini 분석 Job에 등록하는 Celery 태스크

    주어진 posts 문서(ObjectId)와 예상 요청 크기를 기반으로 현재 ACCEPTING_REQUESTS 상태의
    작업에 안전하게 등록합니다. 작업의 파일 크기 한도를 초과하는 경우, 내부 로직에서 자동으로
    새로운 Job을 생성하고 기존 Job을 PENDING으로 전환합니다.

    Args:
        post_id (str): MongoDB posts 컬렉션 문서의 ObjectId 문자열.
        estimated_request_size (int): 본 게시글의 요청 라인이 JSONL로 직렬화될 때의 예상 바이트 크기.

    Returns:
        None
    """
    async def _run():
        """비동기 실행 본문(이벤트 루프에서 실행)."""
        async with PostAnalyzer() as analyzer:
            # analyzer에 post를 등록하면 analyzer 안에서 post를 등록하고,
            # 작업의 크기가 일정 크기 이상으로 커지면 자동으로 작업을 등록
            await analyzer.register(post_id, estimated_request_size)

    loop = None
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
    finally:
        if loop is not None:
            loop.close()
