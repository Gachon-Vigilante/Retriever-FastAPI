import asyncio
import threading
from asyncio import AbstractEventLoop
from typing import Optional, Union, Any, List, Dict, ClassVar, Callable, Coroutine

from telethon.sessions import Session, StringSession
from telethon import TelegramClient
from telethon.tl.types import User, Message

from .channel import ChannelMethods
from .connect import ConnectMethods
from .constants import Logger
from .errors import *
from .message import MessageMethods
from .models import TelegramCredentials

logger = Logger(__name__)

class TeleprobeClient(
    ConnectMethods,
    ChannelMethods,
    MessageMethods,
):
    """텔레그램 클라이언트 기능을 확장한 TeleprobeClient 클래스
    """
    _global_client: Optional['TeleprobeClient'] = None
    _event_handlers: Dict[int, Callable[[Any], Coroutine[Any, Any, None]]] = {}
    _managing_event_handler: threading.Lock = threading.Lock()

    def __init__(
            self,
            api_id: int,
            api_hash: Optional[str],
            session: Optional[Union[str, Session]] = None,
            phone: Optional[str] = None,
            session_string: Optional[str] = None
    ):
        """TeleprobeClient 초기화
        """

        super().__init__()
        self.session = session or f"teleprobe_{api_id}"
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_string = session_string
        self._client: Optional[TelegramClient] = None

        logger.info(f"TeleprobeClient 초기화 완료 (api_id: {api_id})")

    @classmethod
    def set_global_client(
            cls,
            api_id: int,
            api_hash: Optional[str],
            session: Optional[Union[str, Session]] = None,
            phone: Optional[str] = None,
            session_string: Optional[str] = None
    ):
        with cls._managing_event_handler:
            if cls._global_client is None:
                cls._global_client = cls(api_id, api_hash, session, phone, session_string)

    @classmethod
    def from_credentials(cls, credentials: TelegramCredentials, session_name: Optional[str] = None):
        """TelegramCredentials 객체로부터 클라이언트 생성

        Args:
            credentials: TelegramCredentials 객체
            session_name: 세션 이름 (선택적)

        Returns:
            TeleprobeClient 객체
        """
        return cls(
            api_id=credentials.api_id,
            api_hash=credentials.api_hash,
            session=session_name or f"teleprobe_{credentials.api_id}",
            phone=credentials.phone,
            session_string=getattr(credentials, 'session_string', None)
        )


    @property
    def client(self) -> TelegramClient:
        """TelegramClient 객체 반환 (지연 초기화)

        필요할 때만 TelegramClient 객체를 생성하고 반환합니다.
        이미 생성된 경우 기존 객체를 반환합니다.

        Returns:
            TelegramClient 객체
        """
        if self._client is None:
            if self.session_string:
                # 세션 문자열이 있는 경우 StringSession 사용
                session = StringSession(self.session_string)
            else:
                # 아니면 전달받은 세션 사용
                session = self.session
            self._client = TelegramClient(session, self.api_id, self.api_hash)
        return self._client


    async def is_authorized(self) -> bool:
        """인증 여부 확인

        Returns:
            bool: 인증되었는지 여부
        """
        if not self._client:
            return False

        return await self.client.is_user_authorized()

    async def send_code(self) -> str:
        """인증 코드 요청

        Returns:
            인증 코드 해시
        """
        if not self.phone:
            raise ValueError("전화번호가 설정되지 않았습니다.")

        sent = await self.client.send_code_request(self.phone)
        return sent.phone_code_hash

    async def sign_in(self, code: str, phone_code_hash: str) -> User:
        """인증 코드로 로그인

        Args:
            code: 받은 인증 코드
            phone_code_hash: send_code에서 반환된 해시

        Returns:
            User 객체
        """
        if not self.phone:
            raise ValueError("전화번호가 설정되지 않았습니다.")

        return await self.client.sign_in(self.phone, code, phone_code_hash=phone_code_hash)

    async def get_me(self) -> User:
        """현재 사용자 정보 반환

        Returns:
            User 객체
        """
        return await self.client.get_me()

    async def get_session_string(self) -> str:
        """현재 세션의 문자열 반환

        현재 세션을 문자열로 직렬화하여 반환합니다.
        이 문자열은 나중에 다시 로그인할 때 사용할 수 있습니다.

        Returns:
            세션 문자열
        """
        if isinstance(self.client.session, StringSession):
            return self.client.session.save()
        else:
            # 현재 세션이 StringSession이 아닌 경우 새로운 StringSession 생성
            string_session = StringSession.save(self.client.session)
            return string_session

    async def send_message(self, entity: Union[str, int], message: str, **kwargs) -> Message:
        """메시지 전송

        Args:
            entity: 대화 상대 (사용자명, 전화번호, ID 등)
            message: 전송할 메시지
            **kwargs: 추가 매개변수

        Returns:
            전송된 Message 객체
        """
        return await self.client.send_message(entity, message, **kwargs)

    async def get_dialogs(self, limit: int = 100) -> List[Any]:
        """대화 목록 가져오기

        Args:
            limit: 가져올 대화 수

        Returns:
            대화 목록
        """
        return await self.client.get_dialogs(limit=limit)

    async def get_messages(self, entity: Union[str, int], limit: int = 100, **kwargs) -> List[Message]:
        """메시지 가져오기

        Args:
            entity: 대화 상대 (사용자명, 전화번호, ID 등)
            limit: 가져올 메시지 수
            **kwargs: 추가 매개변수

        Returns:
            메시지 목록
        """
        return await self.client.get_messages(entity, limit=limit, **kwargs)

    async def download_profile_photo(self, entity: Union[str, int], file: str = None) -> str:
        """프로필 사진 다운로드

        Args:
            entity: 사용자 또는 채팅 (사용자명, 전화번호, ID 등)
            file: 저장할 파일 경로 (None이면 자동 생성)

        Returns:
            저장된 파일 경로
        """
        return await self.client.download_profile_photo(entity, file=file)

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.client.connect()
        logger.info(f"텔레그램 연결 성공 (api_id: {self.api_id})")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        # 채널 모니터링 핸들러를 관리하는 전역 인스턴스가 아닐 경우에만 연결 종료
        if self._global_client is not self:
            await self._client.disconnect()

    def __repr__(self):
        return f"TeleprobeClient(api_id={self.api_id}, phone={self.phone})"
