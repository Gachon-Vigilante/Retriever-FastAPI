"""크롤러 시작 라우트 모듈

이 모듈은 크롤링 파이프라인을 시작하기 위한 FastAPI 라우트를 제공합니다.
- POST /start: 키워드 기반 검색 작업을 Celery 큐에 등록하여 비동기 파이프라인을 시작합니다.
- POST /start/serp: SerpApi 기반 크롤러를 직접 실행하여 즉시 크롤링을 수행합니다.

주요 비즈니스 규칙:
- 대량 검색은 Celery 큐로 비동기 처리하여 API 응답을 빠르게 반환합니다.
- 요청 파라미터(keywords, limit, max_retries)는 유효성 검사를 거칩니다.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List

from crawlers.serpapi import SerpApiSearchEngine
from routes.responses import SuccessfulResponse
from tasks.pipeline.search import search_pages_task
from utils import Logger

logger = Logger(__name__)

router = APIRouter(prefix="/start")


class CrawlerRequestBody(BaseModel):
    """크롤러 시작 요청 바디 모델

    Attributes:
        keywords (list[str]): 검색에 사용할 키워드 목록.
        limit (int): 키워드 당 검색 결과 최대 개수.
        max_retries (int): 검색 실패 시 재시도 횟수.
    """
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
    """키워드 기반 크롤링 파이프라인 시작

    요청된 키워드 목록을 기반으로 검색 작업을 Celery 큐에 등록합니다. 이 엔드포인트는
    즉시 성공 응답을 반환하며, 이후 검색→방문→저장 파이프라인은 백그라운드에서 진행됩니다.

    Args:
        request (CrawlerRequestBody): 키워드, 제한, 재시도 횟수를 담은 요청 바디.

    Returns:
        SuccessfulResponse: 큐 등록 성공 메시지.
    """
    # Celery 기반 파이프라인 시작: 검색 작업을 큐에 등록
    search_pages_task.delay(request.keywords, request.limit, request.max_retries)
    return SuccessfulResponse(message="검색 작업을 큐에 등록했습니다. 이후 단계는 Celery에서 진행됩니다.")


@router.post("/serp", response_model=SuccessfulResponse)
async def start_serpapi_crawler(request: CrawlerRequestBody):
    """SerpApi 기반 크롤러 즉시 실행

    SerpApi Google 엔진을 사용해 동기적으로 크롤링을 수행합니다. 테스트나 소량 작업에 적합합니다.

    Args:
        request (CrawlerRequestBody): 키워드, 제한, 재시도 횟수를 담은 요청 바디.

    Returns:
        SuccessfulResponse: 처리 성공 메시지.
    """
    crawler = SerpApiSearchEngine(
        keywords=request.keywords,
        limit=request.limit,
        max_retries=request.max_retries
    )
    for post in crawler.search_all(queries=crawler.keywords, limit=crawler.limit):
        logger.debug(post)

    return SuccessfulResponse()
