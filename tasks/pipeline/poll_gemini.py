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
    for post in post_collection.find(
        {"analysis.promotions.links_processed": False},
        {"_id": 1, "analysis.promotions.identifiers": 1},
    ):
        post_id = str(post["_id"])
        post = Post.model_validate_dict(post)
        for promotion_idx, promotion in enumerate(post.analysis.promotions):
            for identifier_idx, identifier_info in enumerate(promotion.identifiers):
                telegram_channel_task.delay(
                    identifier_info.identifier,
                    post_id,
                    f"analysis.promotions.{promotion_idx}.identifiers.{identifier_idx}",
                )
                