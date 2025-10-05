import asyncio

from celery import shared_task

from genai.analyzers.post import PostAnalyzer
from utils import Logger

logger = Logger(__name__)

@shared_task(name=__name__)
def poll_gemini_batches_task():
    async def _run():
        async with PostAnalyzer() as analyzer:
            try:
                await analyzer.check_batch_status()
                await analyzer.complete_jobs()
            except Exception as e:
                logger.warning(f"Polling error: {e}")

    try:
        asyncio.get_event_loop().run_until_complete(_run())
    except RuntimeError:
        asyncio.new_event_loop().run_until_complete(_run())
