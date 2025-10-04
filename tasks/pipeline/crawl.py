import asyncio

from bson import ObjectId
from celery import shared_task

from core.mongo.connections import MongoCollections
from core.mongo.post import Post, PostFields
from pydantic.fields import FieldInfo
from crawlers.base import WebpageCrawler, CrawlerResult
from utils import Logger
from .analyze import analyze_batch_task

logger = Logger(__name__)


@shared_task(name=__name__)
def crawl_page_task(post_id: str):
    post_collection = MongoCollections().posts
    doc = post_collection.find_one({"_id": ObjectId(post_id)})
    if not doc:
        logger.error(f"_id에 해당하는 게시글이 MongoDB에 없습니다. posts `_id`: {post_id}")
        return
    post = Post.from_mongo(doc)

    crawler = WebpageCrawler()

    if post.link:
        crawler_result: CrawlerResult | None = None
        try:
            crawler_result = asyncio.get_event_loop().run_until_complete(crawler.crawl(post.link))
        except RuntimeError:
            # No running loop
            crawler_result = asyncio.new_event_loop().run_until_complete(crawler.crawl(post.link))
        except Exception as e:
            logger.error(f"크롤링이 실패했습니다. posts `link`: {post.link}, error: {e}")
        if crawler_result is not None:
            post_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {
                    PostFields.html: crawler_result.html,
                    PostFields.text: crawler_result.text,
                }}
            )
            logger.info(f"크롤링 결과를 저장했습니다. posts `_id`: {post_id}, posts `link`: {post.link}")
    else:
        logger.warning(f"_id에 해당하는 게시글이 있지만, 링크가 없습니다. posts `_id`: {post_id}")

    analyze_batch_task.delay(post_id)
