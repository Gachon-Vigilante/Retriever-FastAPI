"""웹페이지 크롤 태스크 모듈

이 모듈은 MongoDB에 저장된 게시글 링크를 실제로 방문하여 HTML과 텍스트를 추출하고,
추출 결과를 다시 MongoDB에 반영한 뒤, 분석 배치에 등록하도록 Celery 태스크를 제공합니다.

비즈니스 규칙:
- 게시글의 link가 존재하는 경우에만 방문합니다.
- 방문 성공 시 html, text 필드를 업데이트합니다(초기 저장 정책과 충돌 없음).
- 추출된 텍스트의 예상 요청 크기를 계산하여 분석 작업 큐(analyze_batch_task)에 함께 전달합니다.

Google 스타일의 한국어 docstring을 사용하며, 기능 변경은 없습니다.
"""
import asyncio

from bson import ObjectId
from celery import shared_task

from core.mongo.connections import MongoCollections
from core.mongo.post import Post, PostFields
from core.neo4j.ogm import PostNode
from crawlers.base import WebpageCrawler
from genai.analyzers.post import PostAnalyzer
from utils import Logger
from .analyze import analyze_batch_task
from ..names import CRAWL_TASK_NAME

logger = Logger(__name__)


@shared_task(name=CRAWL_TASK_NAME)
def crawl_page_task(post_id: str):
    """MongoDB 게시글을 크롤링하고 분석 큐에 등록하는 Celery 태스크

    주어진 posts 컬렉션의 ObjectId를 사용하여 문서를 조회하고, 링크가 있으면 정적 방문을 수행합니다.
    방문 성공 시 html/text 필드를 업데이트하고, 분석 배치(analyze_batch_task)에 등록합니다.

    Args:
        post_id (str): posts 컬렉션 문서의 ObjectId 문자열.

    Returns:
        None
    """
    async def _run():
        """비동기 실행 본문(이벤트 루프에서 실행).

        Note:
        - Celery 태스크는 동기 함수여야 하므로, 내부에서 별도의 이벤트 루프를 생성하여
          비동기 크롤러(WebpageCrawler)를 실행합니다.
        """
        post_collection = MongoCollections().posts
        doc = post_collection.find_one(
            {"_id": ObjectId(post_id)}
        )
        if not doc:
            logger.error(f"_id에 해당하는 게시글이 MongoDB에 없습니다. posts `_id`: {post_id}")
            return
        post = Post.from_mongo(doc, autofill=True)

        crawler = WebpageCrawler()

        if post.link:
            try:
                crawler_result = await crawler.crawl(post.link)
                if crawler_result is not None:
                    post.html = crawler_result.html
                    post.text = crawler_result.text
                    post_collection.update_one(
                        {"_id": ObjectId(post_id)},
                        {"$set": {
                            PostFields.html: post.html,
                            PostFields.text: post.text,
                        }}
                    )
                    logger.info(f"크롤링 결과를 저장했습니다. posts `_id`: {post_id}, posts `link`: {post.link}")
                    analyze_batch_task.delay(
                        post_id,
                        PostAnalyzer.estimate_request_size(post)
                    )
            except Exception as e:
                logger.error(f"크롤링이 실패했습니다. posts `link`: {post.link}, error: {e}")

        else:
            logger.warning(f"_id에 해당하는 게시글이 있지만, 링크가 없습니다. posts `_id`: {post_id}")

    loop = None
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
    finally:
        if loop is not None:
            loop.close()

