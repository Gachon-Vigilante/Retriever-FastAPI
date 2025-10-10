import asyncio

from celery import shared_task

from core.mongo.connections import MongoCollections
from core.mongo.schemas import Post
from genai.analyzers.post import PostAnalyzer
from utils import Logger
from .telegram import telegram_channel_task
from ..names import POLL_GEMINI_TASK_NAME  # ANALYSIS_TASK_NAME 사용

logger = Logger(__name__)

@shared_task(name=POLL_GEMINI_TASK_NAME)
def poll_gemini_batches_task():
    async def _run():
        async with PostAnalyzer() as analyzer:
            # 새로운 요청이 들어오지 않을 경우, accepting_request 상태의 작업을 pending 상태로 전환
            await analyzer.flip_idle_accepting_job_to_pending()
            # pending 상태의 모든 작업을 전부 제출
            await analyzer.submit_batch()
            # 제출된 작업들 중 Gemini가 완료한 작업을 확인하고 반영
            await analyzer.check_batch_status()
            # 제출된 작업들 중 Gemini가 완료한 분석 결과 작업을 확인하고 반영
            await analyzer.complete_jobs()
        await invoke_telegram_task()

    loop = None
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
    finally:
        if loop is not None:
            loop.close()

async def invoke_telegram_task():
    post_collection = MongoCollections().posts
    pipeline = [
        # 1. [최적화] 처리할 identifier가 있는 문서만 빠르게 추려냄 (인덱스가 있다면 매우 빠름)
        {
            "$match": {
                "analysis.promotions.identifiers.is_processed": {"$ne": True}
            }
        },
        # 2. promotions 배열을 개별 문서로 풀면서 인덱스를 'promotion_idx' 필드에 저장
        {
            "$unwind": {
                "path": "$analysis.promotions",
                "includeArrayIndex": "promotion_idx",
            },
        },
        # 3. identifiers 배열을 개별 문서로 풀면서 인덱스를 'identifier_idx' 필드에 저장
        {
            "$unwind": {
                "path": "$analysis.promotions.identifiers",
                "includeArrayIndex": "identifier_idx"
            },
        },
        # 4. [최종 필터링] is_processed가 True가 아닌 identifier만 선택
        {
            "$match": {
                "analysis.promotions.identifiers.is_processed": {"$ne": True}
            }
        },
        # 5. [결과 재구성] 최종적으로 필요한 정보만으로 새로운 문서를 생성
        {
            "$project": {
                "_id": 0, # 새로 형성된 _id는 제외
                "original_doc_id": "$_id", # 원래 문서의 _id를 따로 저장
                "identifier": "$analysis.promotions.identifiers.identifier", # identifiers 배열의 원소의 identifier 값
                "path": {
                    # "analysis.promotions.[promotion_idx].identifiers.[identifier_idx]" 형식의 문자열 생성
                    # ex) analysis.promotions.0.identifiers.1
                    "$concat": [
                        "analysis.promotions.",
                        {"$toString": "$promotion_idx"},
                        ".identifiers.",
                        {"$toString": "$identifier_idx"}
                    ]
                }
            }
        }
    ]
    results = post_collection.aggregate(pipeline)
    for result_doc in results:
        logger.info(f"텔레그램 추적을 시도할 identifier 발견. "
                    f"post ID: {result_doc["original_doc_id"]}, "
                    f"identifier: {result_doc["identifier"]}, "
                    f"path: {result_doc['path']}")
        telegram_channel_task.delay(
            result_doc["identifier"],
            str(result_doc["original_doc_id"]),
            result_doc["path"],
        )
                