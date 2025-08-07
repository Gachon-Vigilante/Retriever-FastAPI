from typing import Annotated, Union
from fastapi import APIRouter, Path, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from core.constants import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING
from teleprobe.base import TeleprobeClient
from teleprobe.models import ChannelInfo, TelegramCredentials
from routes.teleprobe.models import channelKeyPath

router = APIRouter(prefix="/channel")

def get_teleprobe_client(params: Annotated[TelegramCredentials, Depends()]) -> TeleprobeClient:
    """
    TelegramCredentials에서 제공된 자격 증명으로 TeleprobeClient 인스턴스를 생성합니다.
    
    이 의존성 함수는 요청 파라미터에서 api_id, api_hash, session_string을 
    추출하여 TeleprobeClient를 생성합니다.
    """
    try:
        # FastAPI의 각 요청은 별도의 이벤트 루프에서 실행되므로,
        # 기존 인스턴스가 있더라도 각 API 요청마다 새 인스턴스 생성
        client = TeleprobeClient.create_new(
            api_id=params.api_id,
            api_hash=params.api_hash,
            session_string=params.session_string,
            phone=params.phone
        )
        return client
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"텔레그램 클라이언트 생성 중 오류 발생: {str(e)}"
        )

@router.get("/{channel_key}", response_model=ChannelInfo)
async def get_channel_info(
    client: Annotated[TeleprobeClient, Depends(get_teleprobe_client)],
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
        channel_info = await client.get_channel_info(channel_key)
        
        # 결과가 없는 경우 404 오류
        if channel_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"채널 정보를 찾을 수 없습니다: {channel_key}"
            )
        
        # datetime을 ISO 형식 문자열로 변환하여 직렬화
        return channel_info
        
    except Exception as e:
        # 오류 처리
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"채널 정보 조회 중 오류 발생: {str(e)}"
        )