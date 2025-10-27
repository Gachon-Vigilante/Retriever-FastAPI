"""검색 파이프라인 태스크 모듈

이 모듈은 Celery 태스크로 정의된 검색 파이프라인의 엔트리포인트를 제공합니다.
- Google Custom Search로 링크 수집
- 텔레그램 링크는 별도 telegram 채널 처리 큐로 발행
- 일반 웹페이지는 MongoDB에 저장 후 크롤 태스크 발행

비즈니스 규칙:
- 동일 링크는 Post.store() 업서트 정책으로 중복 저장을 방지합니다.
- 텔레그램 링크 판별은 crawlers.base.is_telegram_link 유틸을 사용합니다.
"""
from typing import List

from celery import shared_task

from crawlers.base import is_telegram_link
from crawlers.serpapi import SerpApiSearchEngine
from utils import Logger
from .crawl import crawl_page_task
from .telegram import telegram_channel_task
from ..names import SEARCH_TASK_NAME

logger = Logger(__name__)


@shared_task(name=SEARCH_TASK_NAME)
def search_pages_task(keywords: List[str], limit: int = 10, max_retries: int = 3):
    """검색 키워드로 Google Custom Search를 수행하고 후속 작업을 큐에 발행합니다.

    검색 결과에서 텔레그램 링크와 일반 웹페이지를 분기 처리합니다.

    Args:
        keywords (List[str]): 검색에 사용할 키워드 목록.
        limit (int): 키워드 당 최대 검색 결과 수.
        max_retries (int): 검색 실패 시 재시도 횟수(엔진 내부에서 활용).

    Returns:
        None

    Notes:
        - 텔레그램 링크는 telegram_channel_task 큐로 발행합니다.
        - 일반 웹페이지는 MongoDB에 업서트 저장 후 crawl_page_task 큐로 발행합니다.
    """
    crawler = SerpApiSearchEngine(keywords=keywords, limit=limit, max_retries=max_retries)
    telegram_link_count = 0
    webpage_count = 0
    for post in crawler.search_all(keywords, limit):
        if post.link:
            # 텔레그램 링크 여부로 분기
            if not is_telegram_link(post.link):
                post_id = post.store()
                # 새 문서가 생성된 경우에만 크롤 태스크를 발행
                if post_id is not None:
                    crawl_page_task.delay(str(post_id))
                    logger.info(f"Saved post '{post.title}' ({post.link}), published crawl task.")
                    webpage_count += 1
            else:
                telegram_channel_task.delay(post.link)
                logger.info(f"Saved post '{post.title}' ({post.link}), published telegram channel task.")
                telegram_link_count += 1

    logger.info(f"검색 결과를 모두 저장했습니다. Webpage count: {webpage_count}, Telegram link count: {telegram_link_count}")

