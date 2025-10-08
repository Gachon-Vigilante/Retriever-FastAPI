import asyncio

from celery import shared_task, current_app

from core.mongo.post import TelegramChannelIdentifierInfo, TelegramPromotion, Post
from genai.analyzers.post import PostAnalyzer
from utils import Logger
from core.mongo.connections import MongoCollections

from ..names import POLL_GEMINI_TASK_NAME
from .telegram import telegram_channel_task

logger = Logger(__name__)

@shared_task(name=POLL_GEMINI_TASK_NAME)
def poll_gemini_batches_task():
    async def _run():
        async with PostAnalyzer() as analyzer:
            await analyzer.check_batch_status()
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


