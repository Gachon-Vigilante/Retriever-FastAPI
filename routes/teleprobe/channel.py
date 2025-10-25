"""텔레프로브 텔레그램 채널 라우트 모듈

이 모듈은 텔레그램 채널 정보를 조회하고 모니터링을 시작/중지하는 FastAPI 엔드포인트를 제공합니다.
비즈니스 규칙:
- 채널 정보 조회 시 Telethon 클라이언트를 단일 요청 수명주기로 열고 닫습니다.
- 모니터링은 서버 측 이벤트 핸들러(EventHandler)를 통해 비동기로 수행됩니다.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from core.mongo.schemas import Channel
from handlers import ChannelHandler, EventHandler
from routes.responses import SuccessfulResponse, TeleprobeHTTPException
from routes.teleprobe.models import channelKeyPath, TeleprobeClientManager
from teleprobe.base import TeleprobeClient
from utils import Logger

logger = Logger(__name__)

router = APIRouter(prefix="/channel")

@router.post("/{channel_key}", response_model=Channel)
async def post_channel_info(
    client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
    channel_key: channelKeyPath,
):
    """채널 키로 텔레그램 채널 정보를 조회하는 엔드포인트

    비동기 텔레그램 클라이언트를 사용해 채널 정보를 조회합니다. 성공 시 Telethon 채널
    엔티티를 내부 Pydantic 모델(Channel)로 직렬화하여 반환합니다. 채널이 없거나 키 형식이
    잘못된 경우, 연결 문제 등이 발생하면 적절한 HTTP 예외를 반환합니다.

    Args:
        client (TeleprobeClient): 텔레그램과 통신하기 위한 주입된 클라이언트 인스턴스.
        channel_key (int | str): 조회할 채널을 식별하는 키(채널 ID/username/초대 링크).

    Returns:
        Channel: 직렬화된 채널 정보 모델.
    """
    try:
        async with client:
            # 채널 정보 조회 (비동기 방식)
            if channel_entity := await client.get_channel(channel_key, ChannelHandler()):
                channel: Channel = Channel.from_telethon(channel_entity)
                return channel
    except Exception as e:
        TeleprobeHTTPException.from_error(e)


@router.post("/{channel_key}/monitor", response_model=SuccessfulResponse)
async def post_channel_monitor(
    client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
    channel_key: channelKeyPath,
):
    """채널 모니터링을 시작하는 엔드포인트

    지정된 채널에 대한 새로운 메시지 이벤트를 서버에서 감지하고 처리하도록 모니터링을 시작합니다.

    Args:
        client (TeleprobeClient): 인증된 텔레그램 클라이언트.
        channel_key (int | str): 모니터링할 채널 식별자.

    Returns:
        SuccessfulResponse: 성공 메시지.
    """
    try:
        async with client:
            await client.watch(channel_key, EventHandler())
            return SuccessfulResponse()
    except Exception as e:
        TeleprobeHTTPException.from_error(e)

@router.delete("/{channel_key}/monitor", response_model=SuccessfulResponse)
async def delete_channel_monitor(
    client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
    channel_key: channelKeyPath,
):
    """채널 모니터링을 중지하는 엔드포인트

    서버에서 해당 채널에 대한 이벤트 핸들러를 제거하여 모니터링을 중단합니다.

    Args:
        client (TeleprobeClient): 인증된 텔레그램 클라이언트.
        channel_key (int | str): 모니터링 중단할 채널 식별자.

    Returns:
        SuccessfulResponse: 성공 메시지.
    """
    try:
        async with client:
            await client.unwatch(channel_key)
            return SuccessfulResponse()
    except Exception as e:
        TeleprobeHTTPException.from_error(e)
