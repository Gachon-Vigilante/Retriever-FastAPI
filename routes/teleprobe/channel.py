from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from routes.teleprobe.models import channelKeyPath, TeleprobeClientManager
from teleprobe.base import TeleprobeClient
from teleprobe.models import ChannelInfo
from utils import get_logger

logger = get_logger()

router = APIRouter(prefix="/channel")

@router.get("/{channel_key}", response_model=ChannelInfo)
async def get_channel_info(
    client: Annotated[TeleprobeClient, Depends(TeleprobeClientManager.get_client_by_token)],
    channel_key: channelKeyPath,
):
    """
    채널 정보를 조회합니다.
    
    - 경로 파라미터:
      - channel_key: 채널 ID(정수), 사용자명(@username) 또는 초대 링크
      
    - 쿼리 파라미터 (TelegramCredentials에서 정의):
      - api_id: Telegram API ID
      - api_hash: Telegram API Hash
      - session_string: 세션 문자열 (선택적)
      - phone: 전화번호 (선택적)
    
    - 응답:
      - ChannelInfo 객체를 JSON으로 직렬화하여 반환
    """
    try:
        # 채널 정보 조회 (비동기 방식)
        logger.info(f"[ChannelInfo] 채널 정보 조회 요청: {channel_key}")
        channel_info = await client.get_channel_info(channel_key)
        
        # 결과가 없는 경우 404 오류
        if channel_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"채널 정보를 찾을 수 없습니다: {channel_key}"
            )
        
        # datetime을 ISO 형식 문자열로 변환하여 직렬화
        logger.info(f"[ChannelInfo]채널 정보 조회 요청: {channel_key}")
        return channel_info
        
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
    except Exception as e:
        logger.error(f"[ChannelInfo] 예상하지 못한 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="서버 내부 오류가 발생했습니다"
        )