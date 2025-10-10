import os

from celery import Celery
from kombu import Queue, Exchange

import tasks

# Broker and backend from environment
BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//"))
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", None)  # optional

app = Celery(
    "retriever",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        tasks.analyze_module_name,
        tasks.crawl_module_name,
        tasks.poll_gemini_module_name,
        tasks.search_module_name,
        tasks.telegram_module_name,
    ],
)

default_exchange = Exchange("celery", type="topic", durable=True, )

def setup_celery():
    # Basic config
    app.conf.update(
        task_default_exchange="celery",
        task_default_exchange_type="topic",
        task_queues=(
            Queue("search", default_exchange, routing_key="search.#", durable=True,),
            Queue("crawl",  default_exchange, routing_key="crawl.#", durable=True,),
            Queue("analyze",default_exchange, routing_key="analyze.#", durable=True,),
            Queue("poll",   default_exchange, routing_key="poll.#", durable=True,),
            Queue("telegram",   default_exchange, routing_key="telegram.#", durable=True,),
            Queue("default",default_exchange, routing_key="default", durable=True,),
        ),
        task_default_queue="default",
        task_time_limit=60 * 10,
        worker_prefetch_multiplier=1,
    )

    # 등록된 task를 .delay() 등으로 직접 호출할 때 발행할 routing key를 설정.
    # queue를 추가로 설정함으로써 큐를 자동 선언
    app.conf.task_routes = {
        # 검색
        tasks.names.SEARCH_TASK_NAME: {"queue": "search", "routing_key": "search.start"},
        # 크롤링
        tasks.names.CRAWL_TASK_NAME: {"queue": "crawl", "routing_key": "crawl.page"},
        # gemini로 분석
        tasks.names.ANALYSIS_TASK_NAME: {"queue": "analyze", "routing_key": "analyze.gemini.batch"},
        # 배치 폴링
        tasks.names.POLL_GEMINI_TASK_NAME: {"queue": "poll", "routing_key": "poll.gemini.batch"},
        # 텔레그램 채널 및 메시지 수집
        tasks.names.TELEGRAM_CHANNEL_TASK_NAME: {"queue": "telegram", "routing_key": "telegram"},
    }

    # Periodic tasks: poll Gemini batches every minute
    app.conf.beat_schedule = {
        "poll-gemini-batches": {
            "task": tasks.names.POLL_GEMINI_TASK_NAME,
            "schedule": 60.0,  # every 60 seconds
        }
    }

setup_celery()

@app.task(bind=True)
def ping():
    return "pong"
