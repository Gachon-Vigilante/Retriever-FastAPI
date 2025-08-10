import hashlib
import secrets
from datetime import datetime
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status, APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.constants import TELEPROBE_TOKEN_EXPIRATION
from core.sqlite import TelegramToken, get_db
from teleprobe.base import TeleprobeClient
from teleprobe.errors import ApiIdInvalidError, ApiHashInvalidError, TelegramSessionStringInvalidError
from teleprobe.models import TelegramCredentials
from utils import logger


# 응답 모델
class RegisterResponse(BaseModel):
    """등록 응답 모델"""
    token: str
    expires_at: datetime
    message: str

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat() if dt else None
        }



def generate_token(api_id: int, api_hash: str) -> str:
    """고유한 토큰 생성"""
    # 현재 시간과 랜덤 값을 조합하여 고유성 보장
    timestamp = str(int(datetime.now().timestamp() * 1000000))
    random_part = secrets.token_hex(16)
    unique_data = f"{api_id}:{api_hash}:{timestamp}:{random_part}"

    # SHA256 해시로 토큰 생성
    token_hash = hashlib.sha256(unique_data.encode()).hexdigest()
    return f"tpb_{token_hash[:40]}"  # teleprobe 접두어 + 40자 해시

router = APIRouter(prefix="/register")

@router.post("", response_model=RegisterResponse)
async def register(
    credentials: TelegramCredentials,
    db: Annotated[Session, Depends(get_db)]
):
    """
    TeleprobeClient를 등록하고 인증 토큰을 생성합니다.

    - 쿼리 파라미터:
      - api_id: Telegram API ID (필수)
      - api_hash: Telegram API Hash (필수)
      - session_string: 세션 문자열 (필수)
      - phone: 전화번호 (선택적)

    - 응답:
      - token: 생성된 인증 토큰
      - expires_at: 토큰 만료 시간
      - message: 처리 결과 메시지
    """
    try:
        # TeleprobeClient 생성
        client = TeleprobeClient.register(
            api_id=credentials.api_id,
            api_hash=credentials.api_hash,
            session_string=credentials.session_string,
            phone=credentials.phone
        )

        # 클라이언트 등록 (연결 테스트)
        logger.info(f"[Register] TeleprobeClient 등록 시작: api_id={client.api_id}")

        # 클라이언트 연결 확인
        if not await client.ensure_connected():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="텔레그램 클라이언트 연결에 실패했습니다. API 자격 증명을 확인해주세요."
            )

        # 기존 토큰 확인 (같은 api_id로 이미 등록된 경우)
        existing_token: Optional[TelegramToken] = db.query(TelegramToken).filter(
            TelegramToken.api_id == client.api_id,
            TelegramToken.is_active == 1,
            TelegramToken.expires_at > datetime.now()
        ).first()

        if existing_token:
            logger.info(f"[Register] 기존 활성 토큰 발견: {existing_token.token[:10]}...")
            return RegisterResponse(
                token=existing_token.token,
                expires_at=existing_token.expires_at,
                message="기존 활성 토큰을 반환했습니다."
            )

        # 새 토큰 생성
        token = generate_token(client.api_id, client.api_hash)
        expires_at = datetime.now() + TELEPROBE_TOKEN_EXPIRATION  # 만료일 설정

        # 데이터베이스에 저장
        db_token = TelegramToken(
            token=token,
            api_id=client.api_id,
            api_hash=client.api_hash,
            session_string=client.session_string,
            phone=client.phone,
            expires_at=expires_at,
            is_active=1
        )
        db.add(db_token)
        db.commit()
        db.refresh(db_token)

        logger.info(f"[Register] 새 토큰 생성 완료: {token[:10]}... (api_id: {client.api_id})")

        return RegisterResponse(
            token=token,
            expires_at=expires_at,
            message="클라이언트가 성공적으로 등록되었습니다."
        )
    except HTTPException:
        raise
    except (ApiIdInvalidError, ApiHashInvalidError, TelegramSessionStringInvalidError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"[Register] 등록 중 오류 발생: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="클라이언트 등록 중 서버 오류가 발생했습니다."
        )
