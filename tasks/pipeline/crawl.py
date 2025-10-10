import asyncio

from bson import ObjectId
from celery import shared_task

from core.mongo.connections import MongoCollections
from core.mongo.post import Post, PostFields
from crawlers.base import WebpageCrawler, CrawlerResult
from genai.analyzers.post import PostAnalyzer
from utils import Logger
from .analyze import analyze_batch_task
from ..names import CRAWL_TASK_NAME

logger = Logger(__name__)


@shared_task(name=CRAWL_TASK_NAME)
def crawl_page_task(post_id: str):
    async def _run():
        post_collection = MongoCollections().posts
        doc = post_collection.find_one(
            {"_id": ObjectId(post_id)},
            {PostFields.title: 1, PostFields.link: 1}
        )
        if not doc:
            logger.error(f"_id에 해당하는 게시글이 MongoDB에 없습니다. posts `_id`: {post_id}")
            return
        post = Post.from_dict(doc)

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

