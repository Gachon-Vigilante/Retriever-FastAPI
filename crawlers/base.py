"""크롤러 공통 베이스 모듈

이 모듈은 검색 엔진 인터페이스와 웹페이지 방문/텍스트 추출 유틸리티를 제공합니다.
- SearchEngine: 검색 엔진 구현을 위한 추상 인터페이스
- WebpageCrawler: 정적 GET으로 HTML을 가져오고 고성능 텍스트 추출(extract)을 수행
- is_telegram_link: 텔레그램 링크 여부 판별 정규식 유틸리티
- extract: lxml 기반의 고속 텍스트 추출 함수(BeautifulSoup 대비 3~5배 빠름)

Google 스타일의 한국어 docstring을 사용하며, 기능 변경 없이 문서화만 수행합니다.
"""
import re
from typing import Optional, Callable, Coroutine, Any
import aiohttp
from pydantic import BaseModel, Field
from lxml import html, etree

from core.constants import TELEGRAM_LINK_PATTERN, CRAWLER_HEADERS
from core.mongo.schemas import Post, PostFields
from utils import Logger

logger = Logger(__name__)

class CrawlerResult(BaseModel):
    """웹페이지 방문 결과 모델

    정적 방문으로 가져온 HTML과, 추출된 순수 텍스트를 함께 보관합니다.

    Attributes:
        html (str | None): 원본 HTML 문자열.
        text (str | None): HTML에서 태그·스크립트 등을 제거하고 남은 의미 텍스트.
    """
    html: str | None = Field(
        default=None,
        title="게시글 원본 HTML",
        description="웹 게시글의 원본 HTML",
        alias=PostFields.html
    )
    text: str | None = Field(
        default=None,
        title="게시글의 텍스트",
        description="웹 게시글의 원본 HTML에서 HTML 태그 등 무의히만 내용을 제거하고 남은 텍스트",
        alias=PostFields.text
    )

class TotalCrawledResult(BaseModel):
    """키워드별 크롤링 총괄 결과 컨테이너

    여러 키워드에 대한 개별 CrawlerResult 집합을 보관합니다.
    """
    results: list[CrawlerResult] = Field(
        default_factory=list
    )

    def show(self):
        """사람이 읽기 쉬운 총괄 문자열을 생성합니다."""
        return (f"크롤링 결과: 키워드 {len(self.results)}개, "
                f"총 검색 결과: {sum([len(r) for r in self.results])}건, "
                f"게시글: {sum([len(r.posts) for r in self.results])}건, "
                f"텔레그램 채널: {sum([len(r.telegram_links) for r in self.results])}건")

class SearchEngine:
    """검색 엔진 인터페이스 기본 클래스

    각 검색 엔진 구현체는 이 클래스를 상속받아 search 메서드를 구현합니다.

    Attributes:
        keywords (list[str]): 검색에 사용할 키워드 목록.
        limit (int): 키워드 당 최대 결과 수.
        max_retries (int): 검색 실패 시 재시도 횟수(엔진 내부 활용).
    """
    def __init__(
            self,
            keywords: list[str],
            limit: int = 10,
            max_retries: int = 3
    ):
        """SearchEngine 초기화

        Args:
            keywords (list[str]): 검색 키워드 목록.
            limit (int): 키워드 당 최대 결과 수.
            max_retries (int): 실패 시 재시도 횟수.
        """
        self.keywords = keywords
        self.limit = limit
        self.max_retries = max_retries

    def search(
            self,
            keyword: str,
            limit: int,
    ) -> list[Post]:
        """단일 키워드에 대한 검색을 수행하여 Post 리스트를 반환합니다.

        구현체에서 반드시 오버라이드해야 합니다.
        """
        raise NotImplementedError("search() method is not implemented.")

class WebpageCrawler:
    """정적 웹페이지 크롤러

    aiohttp를 사용하여 지정된 링크를 GET으로 방문하고, 원본 HTML과 추출 텍스트를 반환합니다.
    서버 사이드 렌더링 없이 정적 HTML만을 대상으로 합니다.

    Attributes:
        max_retries (int): 방문 실패 시 재시도 횟수.
    """
    def __init__(
            self,
            max_retries: int = 3
    ):
        """WebpageCrawler 초기화.

        Args:
            max_retries (int): 방문 재시도 횟수 (기본 3).
        """
        self.max_retries = max_retries

    async def crawl(self, link: str) -> CrawlerResult | None:
        """링크를 방문하여 HTML과 텍스트를 반환합니다.

        방문이 성공하면 CrawlerResult(html, text)를 반환하고, 모든 재시도 실패 시 None을 반환합니다.

        Args:
            link (str): 방문할 절대 URL.

        Returns:
            CrawlerResult | None: 방문 및 추출 결과 또는 실패 시 None.
        """
        visit_error = None
        timeout_seconds = 1
        for retry in range(self.max_retries):
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=CRAWLER_HEADERS) as session:
                    async with session.get(link, headers=CRAWLER_HEADERS) as response:
                        if response.status == 200:
                            html_content = await response.text()
                            # HTML에서 유의미한 텍스트만 추출
                            extracted_text = extract(html_content)
                            # HTML과 추출한 텍스트를 CrawlerResult로 묶어서 반환
                            return CrawlerResult(
                                html=html_content,
                                text=extracted_text.strip()
                            )
                        else:
                            logger.warning(f"방문한 웹 페이지에서 다음과 같은 오류를 반환했습니다. "
                                           f"Status code: {response.status}, Reason: {response.reason}")
                            continue
            except TimeoutError as e:
                visit_error = e
                logger.warning(f"웹 페이지 접속 시간을 초과했습니다. timeout: {timeout}s, retry: {retry + 1}")
                timeout_seconds += 1
            except Exception as e:
                visit_error = e
                logger.warning(f"웹 페이지 방문 결과 다음과 같은 오류가 발생했습니다: {e}")

        logger.warning(f"모든 웹 페이지 방문 시도가 실패했습니다. Tried {self.max_retries} times, Error: {visit_error}")
        return None

def is_telegram_link(link: str) -> bool:
    """주어진 링크가 텔레그램 링크인지 판별합니다.

    Args:
        link (str): 검사할 URL 문자열.

    Returns:
        bool: 텔레그램 링크(t.me 등)로 식별되면 True, 아니면 False.
    """
    return True if re.findall(TELEGRAM_LINK_PATTERN, link) else False


def extract(html_content: str) -> str:
    """HTML에서 유의미한 텍스트를 추출하는 함수 (lxml 최적화 버전)

    순수 lxml과 XPath를 사용하여 최고 성능으로 텍스트를 추출합니다.
    BeautifulSoup 대비 3-5배 빠른 처리 속도를 제공합니다.

    Args:
        html_content (str): 파싱할 HTML 문자열

    Returns:
        str: 추출된 텍스트 (공백과 줄바꿈으로 정리됨)
    """
    if not html_content or not html_content.strip():
        return ""

    try:
        # lxml로 직접 파싱 (가장 빠름)
        doc = html.fromstring(html_content)

        # 불필요한 태그들을 한 번에 제거 (XPath 사용으로 빠름)
        unwanted_xpath = "//script | //style | //nav | //header | //footer | //aside | //noscript | //iframe"
        unwanted_elements = doc.xpath(unwanted_xpath)
        for element in unwanted_elements:
            element.getparent().remove(element)

        extracted_texts = []

        # 1. 특별한 태그들에서 텍스트 추출 (XPath 사용)
        special_selectors = [
            '//title/text()',
            '//h1//text()',
            '//h2//text()', 
            '//h3//text()',
            '//h4//text() | //h5//text() | //h6//text()',
        ]

        for xpath_expr in special_selectors:
            for text in doc.xpath(xpath_expr):
                text = text.strip()
                if text and len(text) > 2:
                    extracted_texts.append(text)

        # 2. 메타 태그에서 텍스트 추출 (XPath로 한 번에)
        meta_xpath = """
            //meta[@name='description' or @name='keywords' or @name='author']/@content |
            //meta[@property='og:title' or @property='og:description']/@content
        """
        for content in doc.xpath(meta_xpath):
            content = content.strip()
            if content and len(content) > 10:
                extracted_texts.append(content)

        # 3. 유의미한 속성들에서 텍스트 추출 (XPath로 한 번에)
        attr_xpath = """
            //*/@alt | //*/@title | //*/@data-title | //*/@data-content |
            //input/@value | //button/@value | //*/@label | //details/@summary
        """
        for attr_text in doc.xpath(attr_xpath):
            attr_text = attr_text.strip()
            if attr_text and len(attr_text) > 2:
                # URL 필터링
                if not (attr_text.startswith('http') and len(attr_text) > 100):
                    extracted_texts.append(attr_text)

        # 4. 본문 콘텐츠 추출 (XPath로 한 번에, 텍스트 노드만 직접 추출)
        content_xpath = """
            //p//text() | //div//text() | //span//text() | //article//text() |
            //section//text() | //main//text() | //li//text() | //td//text() |
            //th//text() | //blockquote//text() | //a//text()
        """
        for text in doc.xpath(content_xpath):
            text = text.strip()
            if text and len(text) > 5:  # 너무 짧은 텍스트 제외
                extracted_texts.append(text)

        # 텍스트 정리 및 중복 제거
        if not extracted_texts:
            return ""
        
        # 정규화: 공백 여러 개를 하나로 압축하고, 3자 이하의 텍스트는 무시, set을 사용한 빠른 중복 제거
        extracted_texts = map(lambda s: ' '.join(s.split()), extracted_texts)
        extracted_texts = filter(lambda s: len(s) > 3, extracted_texts)

        # set을 사용한 빠른 중복 제거 및 최종 텍스트 조합 (join이 + 연산보다 빠름)
        result = ' '.join(set(extracted_texts))

        # 길이 제한 (슬라이싱이 더 빠름)
        return result[:4000] if len(result) > 4000 else result

    except (etree.XMLSyntaxError, etree.ParserError, UnicodeDecodeError) as e:
        logger.debug(f"lxml HTML 파싱 실패 (일반적인 오류): {type(e).__name__}: {e}")
        # 간단한 정규식 fallback
        return _extract_text_simple_regex(html_content)
    except MemoryError:
        logger.warning("HTML이 너무 커서 메모리 부족으로 파싱 실패")
        return ""
    except Exception as e:
        logger.warning(f"예상치 못한 lxml 파싱 오류: {e}")
        return _extract_text_simple_regex(html_content)


def _extract_text_simple_regex(html_content: str) -> str:
    """lxml 파싱 실패 시 사용할 간단한 정규식 기반 텍스트 추출

    lxml이 실패하는 극단적인 경우에만 사용되는 fallback 함수입니다.
    대부분의 경우 lxml이 성공적으로 처리하므로 이 함수는 거의 호출되지 않습니다.
    """
    if not html_content or len(html_content.strip()) < 10:
        return ""

    try:
        # 안전을 위해 입력 크기 제한 (ReDoS 공격 방지)
        if len(html_content) > 1000000:  # 1MB 제한
            logger.debug("HTML이 너무 커서(>1MB) 정규식 fallback에서도 처리 제한")
            html_content = html_content[:1000000]

        # 스크립트, 스타일 제거 (타임아웃 방지를 위해 간단한 패턴 사용)
        text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html_content, flags=re.IGNORECASE)
        text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)

        # 기본적인 속성 추출 (안전한 패턴만 사용)
        attr_texts = []

        # 각 패턴을 개별적으로 처리하여 하나가 실패해도 다른 것들은 처리 가능
        safe_patterns = [
            (r'alt="([^"]{1,200})"', 'alt'),
            (r"alt='([^']{1,200})'", 'alt'),
            (r'title="([^"]{1,200})"', 'title'),
            (r"title='([^']{1,200})'", 'title'),
        ]

        for pattern, attr_name in safe_patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE)[:5]  # 개수 제한
                attr_texts.extend(matches)
            except (re.error, MemoryError):
                logger.debug(f"정규식 패턴 {attr_name} 처리 중 오류 발생, 건너뜀")
                continue

        # HTML 태그 제거 (간단한 패턴만 사용)
        text = re.sub(r'<[^>]{1,200}>', ' ', text)  # 태그 길이 제한

        # 기본적인 HTML 엔티티만 변환 (안전한 방법)
        entities = {
            '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', 
            '&gt;': '>', '&quot;': '"', '&#39;': "'"
        }
        for entity, replacement in entities.items():
            text = text.replace(entity, replacement)

        # 속성 텍스트를 앞쪽에 추가 (메모리 안전성 고려)
        if attr_texts:
            safe_attr_text = ' '.join(attr_texts[:20])  # 개수 제한
            text = safe_attr_text + ' ' + text

        # 공백 정리 (메모리 효율적인 방법)
        text_parts = text.split()[:500]  # 단어 개수 제한
        result = ' '.join(text_parts)

        return result[:1200] if len(result) > 1200 else result

    except (re.error, MemoryError) as e:
        logger.debug(f"정규식 처리 중 알려진 오류 발생: {type(e).__name__}")
        return ""
    except (UnicodeError, UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.debug(f"인코딩 오류 발생: {type(e).__name__}")
        return ""
    except RecursionError:
        logger.debug("정규식 처리 중 재귀 한계 초과")
        return ""
    except Exception as e:
        logger.debug(f"예상치 못한 정규식 처리 오류: {type(e).__name__}")
        return ""