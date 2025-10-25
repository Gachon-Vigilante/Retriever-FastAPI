"""텔레프로브 텔레그램 메시지 라우트 모듈

이 모듈은 특정 텔레그램 채널로부터 메시지를 수집하여 저장하는 FastAPI 엔드포인트를 제공합니다.
- POST /channel/{channel_key}/messages: 채널 메시지를 순회하며 처리/저장합니다.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from handlers import MessageHandler, ChannelHandler
from routes.responses import SuccessfulResponse, TeleprobeHTTPException
from routes.teleprobe.models import channelKeyPath, TeleprobeClientManager
from teleprobe.base import TeleprobeClient
from utils import Logger

logger = Logger(__name__)

router = APIRouter(prefix="/channel")

@router.post("/{channel_key}/messages")
async def post_messages_from_channel(
        client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
        channel_key: channelKeyPath,
):
    """지정된 텔레그램 채널의 메시지를 수집·저장하는 엔드포인트

    비동기 텔레그램 클라이언트를 통해 채널 정보를 조회한 뒤, 해당 채널의 메시지를 순회하면서
    MessageHandler로 처리/저장합니다.

    Args:
        client (TeleprobeClient): 의존성으로 주입된 텔레그램 클라이언트 인스턴스.
        channel_key (int | str): 메시지를 수집할 대상 채널 식별자.

    Returns:
        SuccessfulResponse: 수집/저장이 완료되었음을 나타내는 성공 응답.
    """
    try:
        async with client:
            # 채널 정보 조회 (비동기 방식)
            logger.info(f"채널 정보 조회 요청: {channel_key}")
            channel_entity = await client.get_channel(channel_key, ChannelHandler())

            if not channel_entity:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"채널 정보를 찾을 수 없습니다: {channel_key}"
                )

            async for _ in client.iter_messages(channel_entity, MessageHandler()):
                pass
            logger.info("채널 내의 모든 메세지를 수집하고 DB에 저장했습니다.")
            return SuccessfulResponse(message=f"채널 내의 모든 메세지를 수집하고 DB에 저장했습니다. "
                                  f"Channel ID: {channel_entity.id}, Channel Type: {type(channel_entity)}")

    except Exception as e:
        TeleprobeHTTPException.from_error(e)