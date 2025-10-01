# Teleprobe

OSINT 플랫폼을 위한 백엔드 서버. 웹 검색(SerpApi/Google)을 통해 마약 관련 키워드를 수집하고, 정적 크롤링으로 페이지 본문을 추출한 뒤, Gemini Batch API로 "실제 판매글인지"를 판정하여 MongoDB에 저장합니다.

- 판매글로 판정된 경우: 게시글의 전체 텍스트와 분석 결과를 저장
- 판매글이 아닌 경우: 링크 등 메타데이터만 저장하여 재검색 시 빠르게 판별

또한 텔레그램은 "게시글에서 발견된 텔레그램 채널을 자동으로 추적"하는 것을 최종 목표로 합니다. 현재는 Telethon 기반의 채널/메시지 API와 간단한 토큰/세션 관리도 함께 제공합니다(점진적으로 자동 추적에 통합 예정).


## 목차
- 프로젝트 개요
- 아키텍처 개요
- 주요 모듈과 책임(API Reference 수준 설명)
- 데이터 모델 및 저장소
- 환경 변수 설정
- 설치 및 실행 방법
- 사용 방법(HTTP API 예시)
- 워크플로우: 크롤링 → 분석 → 저장
- 개발 가이드(기여자 안내)
- 트러블슈팅 / FAQ


## 프로젝트 개요
Teleprobe는 다음 기능을 목표로 합니다.
- 검색엔진(SerpApi / Google Custom Search)을 이용해 마약 판매 의심 키워드로 웹 문서를 찾습니다.
- 정적 HTML 방문으로 본문 텍스트를 빠르게 추출합니다(lxml 최적화 + 정규식 fallback).
- 추출된 텍스트는 Gemini Batch API로 대량 분석하여 판매글 여부를 판정합니다.
- 판매글이면 본문까지 MongoDB에 저장, 아니면 링크만 저장합니다.
- 텔레그램 채널/메시지 수집(별도 API)도 지원합니다.


## 아키텍처 개요
고수준 구성 요소
- API 서버: FastAPI (main.py) — REST/WebSocket 엔드포인트 제공
- 크롤러: crawlers/* — 검색 및 정적 방문/추출
- AI 분석: genai/analyzers/post.py — Gemini Batch API 큐/제출/결과 처리
- 저장소:
  - MongoDB: 수집 결과(Post/Message/Channel) 저장
  - SQLite: 텔레그램 토큰/세션(core/sqlite.py), 배치 큐(genai/analyzers/post.py 내부)
- 핸들러: handlers/* — 크롤링 결과/텔레그램 이벤트 처리 후 저장

간단한 데이터 흐름(웹 크롤링 경로)
1) /api/v1/crawling/start/analyze 호출
2) Google 검색(기본: GoogleCrawler) → 링크 목록 획득 (SerpApiCrawler도 옵션 지원)
3) 각 링크에 대해 정적 방문(본문 추출)
4) MongoDB에는 우선 링크/메타데이터만 저장(Text는 제외)
5) Gemini Batch에 분석 요청 등록 → 배치 제출
6) 백그라운드 폴링 → 결과 수신
7) 결과가 drugs_related=true이면 해당 문서의 text를 MongoDB에 채움 + analysis 저장


## 디렉터리 구조 및 핵심 모듈(API Reference)
- main.py
  - FastAPI 앱 엔트리포인트. root_router 등록 및 /healthcheck 제공

- routes/
  - __init__.py: 루트 라우터. 아래 라우터들을 /api/v1/* 로 연결
  - crawler/
    - start.py
      - POST /api/v1/crawling/start: GoogleCrawler로 키워드 검색 + 방문 + 저장
      - POST /api/v1/crawling/start/serp: SerpApiCrawler로 동일 동작(옵션)
      - POST /api/v1/crawling/start/analyze: GoogleCrawler(기본)로 검색+방문 후 Gemini 배치 분석 등록 및 제출, 백그라운드 폴링 시작
  - teleprobe/
    - auth.py: 텔레그램 인증(웹소켓 기반 Telethon 인증 플로우 콜백 포함)
    - channel.py: 채널 정보 조회/모니터링 시작·중지 API
    - message.py: 채널 메시지 수집 API

- crawlers/
  - base.py
    - Crawler: 공통 크롤링 로직
      - crawl(): 키워드 순회, search() 호출, 각 링크를 visit()으로 방문/추출, handler(post) 실행
      - visit(): aiohttp로 HTML GET 후 lxml로 고성능 텍스트 추출(BeautifulSoup 미사용, lxml 최적화)
      - extract(): 의미 텍스트 추출(XPath 기반) + fallback 정규식
  - google.py
    - GoogleCrawler.search(): Google Custom Search API 사용
  - serpapi.py
    - SerpApiCrawler.search(): SerpApi Google 엔진 사용

- genai/
  - models.py: 프롬프트 로더, LangChain ChatGoogleGenerativeAI 구성(일부 경로에서 사용)
  - prompts.yml: 분석 지시문 텍스트들
  - analyzers/post.py
    - PostAnalyzer: Gemini Batch 큐 관리 및 제출/상태조회/결과처리
      - register(post): 요청 JSONL 라인 준비 후 SQLite 큐에 적재
      - submit_batch(): 현재 수집된 요청들을 Google GenAI Batch로 제출
      - check_batch_status(): Batch 상태 모니터링
      - process_completed_jobs(): 결과 파일 다운로드/파싱 → MongoDB Post의 analysis와 text를 조건부 업데이트
    - 내부 SQLite 스키마: GeminiBatchJobs, GeminiRequests (sqlalchemy aiosqlite)

- core/
  - constants.py: 경로/토큰 TTL/크롤링 헤더 등 상수
  - mongo/
    - connections.py: MongoDB 연결/컬렉션 접근(MONGO_CONNECTION_STRING, MONGO_DB_NAME 사용)
    - base.py, channel.py, message.py, post.py, types.py: MongoDB 모델/베이스
      - post.Post.store(): 중복 검사 후 본문 text는 미저장(분석 완료 후에만 저장)
  - sqlite.py: 텔레그램 토큰용 SQLite 스키마 및 세션(get_db), TelegramToken 테이블

- handlers/
  - webpage.py: PostHandler — post.store() 호출로 Mongo 저장
  - channel.py, message.py, event.py: 텔레그램 채널/메시지 처리 로직

- teleprobe/
  - Telegram 클라이언트 관리, 모델, 에러/상수 등(Telethon 기반)

- utils/
  - logger 설정 등 보조 유틸리티


## 데이터 모델 및 저장 정책
- MongoDB 컬렉션 (core/mongo)
  - posts: 웹 게시글 저장
    - 필드: title, link, domain, text(옵션), analysis(옵션), description, publishedAt, discoveredAt
    - 저장 정책: 초기 저장 시 text 제외. Gemini 결과에서 drugs_related=true일 때 text를 추가 저장. 아니면 text는 None으로 유지.
  - channels, chats: 텔레그램 관련 데이터

- SQLite
  - core/sqlite.py: TelegramToken(토큰/세션/만료일 등)
  - genai/analyzers/post.py: GeminiBatchJobs, GeminiRequests (aiosqlite) — 배치 큐 및 결과 보관


## 환경 변수 설정(.env)
- MongoDB
  - MONGO_CONNECTION_STRING: mongodb 연결 문자열
  - MONGO_DB_NAME: 사용할 데이터베이스명

- 검색 엔진
  - SERPAPI_API_KEY: SerpApi 키(권장)
  - GOOGLE_API_KEY: 구글 LLM/검색 키(선택: google custom search, genai 클라이언트도 동일 키 사용 가능)
  - GOOGLE_CUSTOM_SEARCH_API_ID: Google Custom Search Engine ID(선택)

- Gemini / Google GenAI
  - GOOGLE_API_KEY: Google GenAI SDK가 사용하는 키(상동). 환경에 따라 Application Default Credentials도 사용 가능

- 기타
  - LOG_PATH: 로그 파일 경로 (기본: logs/server.log)
  - TELEPROBE_TOKEN_TTL_DAYS: 텔레그램 토큰 TTL 일수(기본 30)


## 설치 및 실행
사전 준비: Python 3.11+ 권장, MongoDB 인스턴스, SerpApi 또는 Google CSE/API 키, Astral uv 설치

1) uv 설치(없다면)
- Windows/macOS/Linux: https://docs.astral.sh/uv/getting-started/ 참고
  예) pipx install uv 또는 curl 설치 스크립트 사용

2) 의존성 동기화
- uv sync  # pyproject.toml 및 uv.lock 기반 환경 동기화

3) 환경 변수 구성
- 프로젝트 루트에 .env 생성 후 위 변수 설정 (.env는 uv로도 자동 로드됨)

4) 서버 실행
- uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

5) 헬스체크
- GET http://localhost:8000/healthcheck → {"status":"active"}


## 사용 방법(HTTP API 예시)
Base URL: http://localhost:8000

- 크롤링 시작 (Google)
  - POST /api/v1/crawling/start
  - Body
    {
      "keywords": ["텔레 아이스 팝니다", "텔레 떨 팝니다"],
      "limit": 20,
      "max_retries": 3
    }

- 크롤링 시작 (SerpApi)
  - POST /api/v1/crawling/start/serp
  - Body: 위와 동일(SERPAPI_API_KEY 필요)

- 크롤링 + 배치 분석(권장)
  - POST /api/v1/crawling/start/analyze
  - 동작: Google로 검색(기본: GoogleCrawler)→방문→Mongo 링크 저장→Gemini 배치 등록/제출→백그라운드 폴링→Mongo 결과 갱신

- 텔레그램 채널 정보 조회
  - POST /api/v1/teleprobe/channel/{channel_key}

- 텔레그램 채널 모니터링 시작/중지
  - POST /api/v1/teleprobe/channel/{channel_key}/monitor
  - DELETE /api/v1/teleprobe/channel/{channel_key}/monitor

- 텔레그램 채널 메시지 수집
  - POST /api/v1/teleprobe/channel/{channel_key}/messages

- 텔레그램 인증 플로우
  - routes/teleprobe/auth.py 에 웹소켓 기반 Telethon 인증 콜백 포함
  - core/sqlite.TelegramToken 로컬 저장

응답 스키마
- 공통 성공 응답: routes/responses.SuccessfulResponse 사용
- Channel/Message/Post 데이터 모델: core/mongo/* 의 Pydantic 모델 참고


## 워크플로우 상세: 크롤링 → 분석 → 저장
1) 검색
- SerpApiCrawler.search() 또는 GoogleCrawler.search()
- 키워드 당 limit 개수까지 링크 수집

2) 방문/본문 추출
- Crawler.visit(): aiohttp + CRAWLER_HEADERS로 GET
- lxml 기반 extract()로 의미 텍스트만 고속 추출(메타 태그, 헤딩, 본문 노드, 속성들)

3) 저장(초기)
- handlers.webpage.PostHandler → Post.store()
- Mongo posts 컬렉션에 link/domain/title 등 저장, text는 제외(요구사항 반영)

4) Gemini 배치 등록/제출
- genai.analyzers.post.PostAnalyzer.register(post)
- 큐 크기/파일 크기를 관리하며 JSONL 작성 → submit_batch()로 Google GenAI Batch 제출

5) 결과 폴링/처리
- start/analyze 라우트가 백그라운드로 check_batch_status()+process_completed_jobs()를 주기적으로 호출
- process_completed_jobs(): 결과 JSONL 다운로드→각 요청 매핑→Mongo Post 문서 업데이트
  - drugs_related == true → text 필드 채움 + analysis 저장
  - 그 외 → analysis만 저장하고 text는 None 유지


## 개발 가이드(신규 기여자)
- 코딩 규칙
  - Pydantic v2 모델 사용, 타입 힌트 적극 활용
  - 네트워크 호출은 타임아웃/재시도 고려
  - 크롤링은 순수 정적 접근만 수행(렌더링 없음)
- 테스트/실행 팁
  - .env에서 MONGO_DB_NAME, MONGO_CONNECTION_STRING, SERPAPI_API_KEY 설정 필수
  - 로컬 MongoDB를 사용할 경우 docker run -p 27017:27017 mongo
  - 분석 기능은 GOOGLE_API_KEY가 유효해야 정상 동작
- 확장 포인트
  - 새로운 검색 엔진: crawlers/base.Crawler 상속 후 search()만 구현
  - 후처리/필터링: handlers/webpage.PostHandler를 대체/확장
  - 분석 파이프라인: genai/analyzers/post.py 의 PostAnalyzer 훅 활용
- 데이터 정책 유의사항
  - 개인 정보/민감 정보 저장 최소화. 판매글 아님이 판정되면 본문 저장 금지 정책 유지


## 트러블슈팅 / FAQ
- Q: 분석 결과가 갱신되지 않습니다.
  - A: /start/analyze는 배치 제출 후 백그라운드 폴링을 시작합니다. Google GenAI Batch 처리 시간이 필요합니다. 환경 변수(GOOGLE_API_KEY)와 네트워크를 확인하세요.
- Q: 본문(text)이 왜 저장되지 않나요?
  - A: 요구사항에 따라 판매글로 확정되기 전에는 본문을 저장하지 않습니다. 분석 결과 drugs_related=true일 때만 저장됩니다.
- Q: Google과 SerpApi 중 무엇을 써야 하나요?
  - A: 비용 이슈로 기본값은 GoogleCrawler입니다. SerpApiCrawler는 옵션으로 지원하며 /api/v1/crawling/start/serp 엔드포인트로 사용할 수 있습니다.
- Q: SQLite는 어디에 쓰나요?
  - A: 텔레그램 토큰(core/sqlite.py)과 Gemini 배치 큐(genai/analyzers/post.py, aiosqlite)에 사용합니다. 운영환경에서는 별도 RDB나 작업 큐로의 대체를 고려할 수 있습니다.


## 라이선스
이 리포지토리 내 소스 코드의 라이선스 정책은 프로젝트 요구에 따라 별도로 명시하세요.
