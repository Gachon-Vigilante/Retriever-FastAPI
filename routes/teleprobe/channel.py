from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from handlers import ChannelHandler
from routes.teleprobe.models import channelKeyPath, TeleprobeClientManager
from teleprobe.base import TeleprobeClient
from core.mongo.schemas import Channel
from utils import Logger

logger = Logger("RoutesTelegramChannels")

router = APIRouter(prefix="/channel")

@router.post("/{channel_key}", response_model=Channel)
async def post_channel_info(
    client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
    channel_key: channelKeyPath,
):
    """
    Handles a POST request to fetch channel information based on the provided channel key.

    This endpoint retrieves channel information from a Telegram client asynchronously. If the
    channel information is successfully retrieved, it serializes the channel entity into a response
    model and stores the information. If the channel key is not found, it returns a 404 error. In
    case of invalid channel key formats, connection issues, or unexpected server errors, the
    appropriate HTTP exception is raised.

    Parameters:
        client: An injected instance of TeleprobeClient required for communication with Telegram.
        channel_key: The key identifying the channel whose information is to be retrieved.

    Returns:
        Channel: The channel information deserialized from the retrieved entity.

    Raises:
        HTTPException: Raised when the channel key is invalid, the channel is not found,
                       there is a connection issue, or any unexpected internal server error occurs.
    """
    try:
        # 채널 정보 조회 (비동기 방식)
        logger.debug(f"채널 정보 조회 요청: {channel_key}")
        if channel_entity := await client.get_channel(channel_key, ChannelHandler()):
            channel: Channel = Channel.from_telethon(channel_entity)
            return channel
        # 결과가 없는 경우 404 오류
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"채널 정보를 찾을 수 없습니다: {channel_key}"
            )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"잘못된 채널 키 형식 또는 채널 키가 없음: `{str(channel_key)}`"
        )
    except ConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="텔레그램 서비스에 연결할 수 없습니다"
        )