"""분석 배치 제어 라우트 모듈

이 모듈은 Gemini Batch 분석 파이프라인을 수동으로 제어하기 위한 FastAPI 엔드포인트를 제공합니다.
등록(register) → 제출(submit) → 상태 확인(check) → 완료 처리(complete) 흐름을 개별로 호출할 수 있습니다.

주의: 운영 환경에서는 Celery beat가 poll_gemini 태스크를 통해 주기적으로 상태를 갱신하므로,
이 라우트들은 운영 중 수동 개입이나 디버깅용으로 사용하십시오.
"""
from fastapi import APIRouter

from genai.analyzers.post import PostAnalyzer, JobCompletionResult
from tasks.pipeline.analyze import analyze_batch_task

router = APIRouter(prefix="/batch")

@router.post("/register")
async def register_batch():
    """현재 ACCEPTING_REQUESTS Job에 적재된 요청을 제출 대기(previous 단계)로 준비합니다.

    내부적으로 analyze_batch_task를 비동기 큐에 등록하여, 수집된 게시글 텍스트를
    분석 배치 요청으로 변환/적재합니다.

    Returns:
        dict: 처리 메시지.
    """
    analyze_batch_task.delay()
    return {"message": "batch registered."}


@router.post("/register/all")
async def register_batch_all():
    """분석 대상 조건에 부합하는 모든 게시글을 현재 Job에 등록합니다.

    Returns:
        dict: 처리 메시지.
    """
    await PostAnalyzer().register_all()
    return {"message": "all batch registered."}


@router.post("/submit")
async def submit_all_batches():
    """PENDING 상태의 모든 Job을 Gemini Batch API로 제출합니다.

    Returns:
        dict: 처리 메시지.
    """
    await PostAnalyzer().submit_batch()
    return {"message": "batch submitted."}

@router.post("/check")
async def check_batch_status():
    """SUBMITTED Job들의 현재 상태를 Gemini에서 조회하여 MongoDB에 반영합니다.

    Returns:
        dict: 처리 메시지.
    """
    await PostAnalyzer().check_batch_status()
    return {"message": "batch status checked."}

@router.post("/complete")
async def complete_jobs() -> JobCompletionResult:
    """PROCESSED Job들의 결과 파일을 다운로드/파싱하고 Post 문서를 갱신합니다.

    Returns:
        JobCompletionResult: 완료/처리 건수 통계 정보.
    """
    return await PostAnalyzer().complete_jobs()
