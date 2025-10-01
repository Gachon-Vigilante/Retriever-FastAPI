from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List
import asyncio

from crawlers.google import GoogleCrawler
from crawlers.serpapi import SerpApiCrawler
from handlers.webpage import PostHandler
from routes.responses import SuccessfulResponse
from utils import Logger
from genai.analyzers.post import PostAnalyzer

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


@router.post("/analyze", response_model=SuccessfulResponse)
async def start_crawler_with_analysis(request: CrawlerRequestBody, background_tasks: BackgroundTasks):
    handler = PostHandler()
    crawler = GoogleCrawler(
        keywords=[],  # We'll drive search manually to get Post objects here
        limit=request.limit,
        max_retries=request.max_retries,
        handler=None,
    )

    async def poll_and_process():
        try:
            async with PostAnalyzer() as analyzer:
                # 주기적으로 상태 확인 및 결과 처리
                while True:
                    try:
                        await analyzer.check_batch_status()
                        stats = await analyzer.process_completed_jobs()
                        # 완료된 잡이 더 이상 없고 진행 중인 잡도 없으면 종료 시도
                        active = await analyzer.check_batch_status()
                        if not active:
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(15)
        except Exception:
            # Background task errors are logged implicitly by FastAPI; keep silent here
            pass

    async with PostAnalyzer() as analyzer:
        # 키워드별로 검색 후 방문, 저장, 등록
        for keyword in request.keywords:
            posts = crawler.search(keyword, limit=request.limit)
            for post in posts:
                # Visit to fetch text content
                try:
                    content = await crawler.visit(post.link)
                except Exception:
                    content = None
                if content:
                    post.text = content
                # Store to Mongo
                await handler(post)
                # Register for batch analysis
                await analyzer.register(post)
        # Submit all batches
        await analyzer.submit_batch()

    # Start background polling to process results
    background_tasks.add_task(poll_and_process)

    return SuccessfulResponse(message="크롤링 및 배치 분석을 시작했습니다. 결과는 준비되는 대로 MongoDB에 저장됩니다.")