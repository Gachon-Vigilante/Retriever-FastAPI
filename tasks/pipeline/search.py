from typing import List

from celery import shared_task

from crawlers.google import GoogleSearchEngine
from crawlers.base import is_telegram_link
from utils import Logger

from .crawl import crawl_page_task
from .telegram import telegram_channel_task
from ..names import SEARCH_TASK_NAME

logger = Logger(__name__)


@shared_task(name=SEARCH_TASK_NAME)
def search_pages_task(keywords: List[str], limit: int = 10, max_retries: int = 3):
    """검색 키워드로 Google Custom Search를 수행해 MongoDB에 저장하고 크롤링 task를 발행한다."""
    crawler = GoogleSearchEngine(keywords=keywords, limit=limit, max_retries=max_retries)
    telegram_link_count = 0
    webpage_count = 0
    for post in crawler.search_all(keywords, limit):
        if post.link:
            if not is_telegram_link(post.link):
                post_id = post.store()
                if post_id is not None:
                    crawl_page_task.delay(str(post_id))
                    logger.info(f"Saved post '{post.title}' ({post.link}), published crawl task.")
                    webpage_count += 1
            else:
                telegram_channel_task.delay(post.link)
                logger.info(f"Saved post '{post.title}' ({post.link}), published telegram channel task.")
                telegram_link_count += 1

    logger.info(f"검색 결과를 모두 저장했습니다. Webpage count: {webpage_count}, Telegram link count: {telegram_link_count}")

