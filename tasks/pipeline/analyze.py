import asyncio

from celery import shared_task

from genai.analyzers.post import PostAnalyzer
from utils import Logger
from ..names import ANALYSIS_TASK_NAME

logger = Logger(__name__)

# 반드시 동시에 1개만 실행되어야 하는 celery 프로세스. 
# 만약 2개 이상 실행될 경우 mongoDB에 여러 프로세스가 접근해서 동시에 batch 작업을 트리거하면서 오류 또는 불필요한 AI 호출이 발생할 수 있음.
@shared_task(name=ANALYSIS_TASK_NAME)
def analyze_batch_task(post_id: str):
    async def _run():
        async with PostAnalyzer() as analyzer:
            # analyzer에 post를 등록하면 analyzer 안에서 post를 등록하고,
            # 작업의 크기가 일정 크기 이상으로 커지면 자동으로 작업을 등록
            await analyzer.register(post_id)

    loop = None
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
    finally:
        if loop is not None:
            loop.close()
