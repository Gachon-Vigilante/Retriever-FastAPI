"""Celery 태스크 이름 상수 모듈

Celery 태스크 등록과 라우팅에서 사용하는 작업 이름 상수들을 모아둔 모듈입니다.
큐 라우팅 키(celery_app.py)와 각 태스크의 name 인자(@shared_task(name=...))가
일치해야 하므로, 상수로 중앙 관리하여 오타를 방지하고 일관성을 유지합니다.

주의: 이름을 변경하면 celery_app.py의 task_routes 및 관련 태스크 데코레이터도 함께 수정해야 합니다.
"""

# 분석 파이프라인: Gemini 배치 요청 적재/제출/폴링 등
ANALYSIS_TASK_NAME = "analysis"
# 웹페이지 방문 및 본문 추출
CRAWL_TASK_NAME = "crawl"
# Gemini 배치 상태 주기적 폴링
POLL_GEMINI_TASK_NAME = "poll_gemini"
# 검색 엔진(구글/CSE)으로 링크 수집
SEARCH_TASK_NAME = "search"
# 텔레그램 채널 수집/모니터링 트리거
TELEGRAM_CHANNEL_TASK_NAME = "telegram.channel"
# 텔레그램 메시지 수집(미사용 또는 확장용 자리)
TELEGRAM_MESSAGE_TASK_NAME = "telegram.message"
