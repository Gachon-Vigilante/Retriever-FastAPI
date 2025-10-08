import asyncio
import os
from urllib.parse import urljoin

import requests

from celery import shared_task

from core.constants import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING
from core.mongo.connections import MongoCollections
from teleprobe import TeleprobeClient
from teleprobe.errors import ACCEPTABLE_EXCEPTIONS
from handlers import ChannelHandler, MessageHandler

from utils import Logger

from ..names import TELEGRAM_CHANNEL_TASK_NAME, TELEGRAM_MESSAGE_TASK_NAME

logger = Logger(__name__)


@shared_task(name=TELEGRAM_CHANNEL_TASK_NAME)
def telegram_channel_task(channel_identifier: str, post_id: str | None = None, mongo_key: str | None = None):
    logger.info(f"Collecting telegram channel key: {channel_identifier}")

    async def _run():
        post_collection = MongoCollections().posts
        try:
            async with TeleprobeClient(
                    api_id=TELEGRAM_API_ID,
                    api_hash=TELEGRAM_API_HASH,
                    session_string=TELEGRAM_SESSION_STRING
            ) as client:
                # 채널 정보 조회 (비동기 방식)
                logger.info(f"채널 정보 수집 및 모니터링을 시도합니다. channel key: {channel_identifier}")
                channel = await client.get_channel(channel_identifier, ChannelHandler()) # 채널 정보 수집 후 저장
                logger.info(f"채널 정보를 수집(또는 업데이트)했습니다. channel key: {channel_identifier}")
                if post_id and mongo_key:
                    post_collection.update_one(
                        {"_id": post_id},
                        {"$set": {mongo_key: {"channel_id": channel.id}}}
                    )

                response = requests.post(
                    url=urljoin(os.getenv("FASTAPI_HOST"), f"/api/v1/channel/{channel_identifier}/monitor"),
                    timeout=10,
                )
                logger.info(f"FastAPI 서버에 채널 모니터링을 요청했습니다. "
                            f"status code: {response.status_code}, response: {response.text}")

                # 채널 정보 조회 (비동기 방식)
                logger.info(f"채널 메시지 수집을 시도합니다: {channel_identifier}")
                channel_entity = await client.get_channel(channel_identifier, ChannelHandler())
                async for _ in client.iter_messages(channel_entity, MessageHandler()):
                    pass
                logger.info(f"채널 내의 모든 메세지를 수집하고 DB에 저장했습니다: {channel_identifier}")

                if post_id and mongo_key:
                    post_collection.update_one(
                        {"_id": post_id},
                        {"$set": {mongo_key: {"is_processed": True}}}
                    )

        except Exception as e:
            if type(e) in ACCEPTABLE_EXCEPTIONS: # 예상되는 에러
                logger.error(f"예상된 오류 발생: {type(e).__name__}: {str(e)}")

                if post_id and mongo_key:
                    post_collection.update_one(
                        {"_id": post_id},
                        {"$set": {
                            mongo_key: {
                                "is_processed": True,
                                "error": f"{type(e).__name__}: {str(e)}"
                            }
                        }}
                    )
            else:
                logger.error(f"예상하지 못한 오류 발생: {type(e).__name__}: {str(e)}")
                raise e # 예상하지 못한 에러

    loop = None
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
    finally:
        if loop is not None:
            loop.close()
