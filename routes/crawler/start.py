from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

from crawlers.google import GoogleCrawler
from crawlers.serpapi import SerpApiCrawler
from handlers.webpage import PostHandler
from routes.responses import SuccessfulResponse
from utils import Logger

logger = Logger(__name__)

router = APIRouter(prefix="/start")


class CrawlerRequestBody(BaseModel):
    keywords: List[str] = Field(
        default_factory=list,
        title="검색 키워드",
        description="텔레그램 채널 검색에 사용할 키워드 목록",
        examples=[["텔레 아이스 팝니다", "텔레 떨 팝니다"], ["t.me 아이스"]]
    )
    limit: int = Field(
        default=10,
        title="검색 제한",
        description="검색어 한 개당 검색 결과를 제한할 최대 개수 (10의 배수를 권장)",
        ge=10,
        examples=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    )
    max_retries: int = Field(
        default=3,
        title="재시도 횟수",
        description="검색 실패 시 재시도할 최대 횟수",
        ge=1,
        examples=[3]
    )


@router.post("", response_model=SuccessfulResponse)
async def start_crawler(request: CrawlerRequestBody):
    crawler = GoogleCrawler(
        keywords=request.keywords,
        limit=request.limit,
        max_retries=request.max_retries,
        handler=PostHandler(),
    )
    results = await crawler.crawl()
    logger.info(results.show())

    return SuccessfulResponse()


@router.post("/serp", response_model=SuccessfulResponse)
async def start_serpapi_crawler(request: CrawlerRequestBody):
    crawler = SerpApiCrawler(
        keywords=request.keywords,
        limit=request.limit,
        max_retries=request.max_retries
    )
    await crawler.crawl()

    return SuccessfulResponse()