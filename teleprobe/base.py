import asyncio
import threading
from typing import Optional, Union, Any, List, Dict, ClassVar, Callable, Coroutine

from telethon.sessions import Session, StringSession
from telethon.sync import TelegramClient
from telethon.tl.types import User, Message

from .channel import ChannelMethods
from .connect import ConnectMethods
from .constants import Logger
from .errors import ApiIdInvalidError, ApiHashInvalidError, TelegramSessionStringInvalidError
from .message import MessageMethods
from .models import TelegramCredentials

logger = Logger(__name__)

class TeleprobeClient(
    ConnectMethods,
    ChannelMethods,
    MessageMethods,
):
    """텔레그램 클라이언트 기능을 확장한 TeleprobeClient 클래스

    싱글톤 패턴을 사용하여 api_id별로 인스턴스를 관리합니다.
    지연 초기화(lazy initialization) 패턴을 사용하여 TelegramClient를 필요할 때만 생성합니다.
    """

    # 클래스 변수: api_id별로 인스턴스를 저장
    _instances: ClassVar[Dict[int, 'TeleprobeClient']] = {}
    _event_handlers: Dict[int, Callable[[None], Coroutine[Any, Any, None]]] = {}
    _managing_event_handler: threading.Lock = threading.Lock()

    def __new__(
            cls,
            api_id: int,
            api_hash: Optional[str] = None,
            session: Optional[Union[str, Session]] = None,
            phone: Optional[str] = None,
            session_string: Optional[str] = None
    ):
        """새로운 인스턴스 생성 또는 기존 인스턴스 반환
        
        Args:
            api_id: Telegram API ID (필수)
            api_hash: Telegram API Hash (새 인스턴스 생성시 필수)
            session: 세션 이름 또는 세션 객체 (선택적)
            phone: 전화번호 (선택적)
            session_string: 저장된 세션 문자열 (선택적)
            
        Returns:
            TeleprobeClient 인스턴스
        """
        # 이미 존재하는 인스턴스가 있으면 반환
        if api_id in cls._instances:
            existing_instance = cls._instances[api_id]
            logger.debug(f"기존 TeleprobeClient 인스턴스 반환 (api_id: {api_id})")
            existing_instance.update_credentials(
                api_hash=api_hash,
                phone=phone,
                session_string=session_string
            )
            return existing_instance

        # 새 인스턴스 생성시 api_hash는 필수
        if api_hash is None:
            raise ValueError(f"새로운 TeleprobeClient 생성시 api_hash는 필수입니다. (api_id: {api_id})")

        # 새 인스턴스 생성
        logger.debug(f"새로운 TeleprobeClient 인스턴스 생성 (api_id: {api_id})")
        instance = super().__new__(cls)
        cls._instances[api_id] = instance
        return instance

    def __init__(
            self,
            api_id: int,
            api_hash: Optional[str] = None,
            session: Optional[Union[str, Session]] = None,
            phone: Optional[str] = None,
            session_string: Optional[str] = None
    ):
        """TeleprobeClient 초기화
        
        주의: 이미 초기화된 인스턴스의 경우 다시 초기화하지 않습니다.
        """
        # 이미 초기화된 인스턴스인지 확인
        if hasattr(self, '_initialized'):
            logger.debug(f"이미 초기화된 인스턴스 (api_id: {api_id})")
            return

        super().__init__()
        self.session = session or f"teleprobe_{api_id}"
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_string = session_string
        self._client: Optional[TelegramClient] = None
        self._initialized = True  # 초기화 완료 플래그

        # 각 인스턴스별 전용 이벤트 루프 생성
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            logger.debug(f"인스턴스 전용 이벤트 루프 생성 완료 (api_id: {api_id})")
        except Exception as e:
            logger.warning(f"이벤트 루프 생성 중 오류: {e}")
            self.loop = None

        logger.info(f"TeleprobeClient 초기화 완료 (api_id: {api_id})")

    @classmethod
    def create_new(
            cls,
            api_id: int,
            api_hash: str,
            session: Optional[Union[str, Session]] = None,
            phone: Optional[str] = None,
            session_string: Optional[str] = None
    ) -> 'TeleprobeClient':
        """새로운 인스턴스를 강제로 생성
        
        기존 인스턴스가 있더라도 새로운 인스턴스를 생성합니다.
        주의: 기존 인스턴스는 덮어씌워집니다.
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session: 세션 이름 또는 세션 객체 (선택적)
            phone: 전화번호 (선택적)
            session_string: 저장된 세션 문자열 (선택적)
            
        Returns:
            새로운 TeleprobeClient 인스턴스
        """
        # 기존 인스턴스가 있다면 제거
        if api_id in cls._instances:
            old_instance = cls._instances[api_id]
            # 기존 연결이 있다면 정리
            if hasattr(old_instance, '_client') and old_instance._client:
                try:
                    old_instance.run_until_complete(old_instance.disconnect())
                except Exception as e:
                    logger.warning(f"기존 인스턴스 정리 중 오류: {e}")

            del cls._instances[api_id]
            logger.info(f"기존 인스턴스 제거 후 새 인스턴스 생성 (api_id: {api_id})")

        # 새 인스턴스 생성
        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session=session,
            phone=phone,
            session_string=session_string
        )
    @classmethod
    def register(
        cls,
        api_id: int,
        api_hash: str,
        session_string: str,
        session: Optional[Union[str, Session]] = None,
        phone: Optional[str] = None,
    ) -> 'TeleprobeClient':
        if not api_id:
            logger.error("세션 정보에 API ID가 제공되지 않았습니다.")
            raise ApiIdInvalidError("API ID is not provided.")
        if not api_hash:
            logger.error("세션 정보에 API Hash가 제공되지 않았습니다.")
            raise ApiHashInvalidError("API Hash is not provided.")
        if not session_string:
            logger.error("세션 정보에 Session String이 제공되지 않았습니다.")
            raise TelegramSessionStringInvalidError("Session string is not provided.")

        return cls.create_new(
            api_id=api_id,
            api_hash=api_hash,
            session=session,
            phone=phone,
            session_string=session_string
        )

    @classmethod
    def get_instance(cls, api_id: int) -> Optional['TeleprobeClient']:
        """기존 인스턴스 가져오기
        
        Args:
            api_id: Telegram API ID
            
        Returns:
            기존 TeleprobeClient 인스턴스 또는 None
        """
        return cls._instances.get(api_id)

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

    @classmethod
    def list_instances(cls) -> List[int]:
        """생성된 모든 인스턴스의 api_id 목록 반환
        
        Returns:
            api_id 목록
        """
        return list(cls._instances.keys())

    @classmethod
    def clear_all_instances(cls):
        """모든 인스턴스 제거
        
        모든 연결을 정리하고 인스턴스를 제거합니다.
        """
        for api_id, instance in list(cls._instances.items()):
            try:
                if hasattr(instance, '_client') and instance._client:
                    instance.run_until_complete(instance.disconnect())
            except Exception as e:
                logger.warning(f"인스턴스 정리 중 오류 (api_id: {api_id}): {e}")

        cls._instances.clear()
        logger.info("모든 TeleprobeClient 인스턴스 제거 완료")

    def update_credentials(
            self,
            api_hash: Optional[str] = None,
            phone: Optional[str] = None,
            session_string: Optional[str] = None
    ):
        """기존 인스턴스의 자격 증명 업데이트
        
        Args:
            api_hash: 새로운 API Hash (선택적)
            phone: 새로운 전화번호 (선택적)
            session_string: 새로운 세션 문자열 (선택적)
        """
        if api_hash is not None:
            self.api_hash = api_hash
        if phone is not None:
            self.phone = phone
        if session_string is not None:
            self.session_string = session_string
            # 기존 클라이언트가 있다면 재생성 필요
            if self._client is not None:
                try:
                    self.run_until_complete(self.disconnect())
                    self._client = None
                except Exception as e:
                    logger.warning(f"클라이언트 연결 해제 중 오류: {e}")
                    self._client = None

        logger.info(f"자격 증명 업데이트 완료 (api_id: {self.api_id})")

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

    async def connect(self) -> bool:
        """텔레그램 서버에 연결

        Returns:
            bool: 연결 성공 여부
        """
        try:
            await self.client.connect()
            logger.info(f"텔레그램 연결 성공 (api_id: {self.api_id})")
            return True
        except Exception as e:
            logger.error(f"Connection error (api_id: {self.api_id}): {e}")
            return False

    async def disconnect(self):
        """텔레그램 서버에서 연결 해제"""
        if self._client is not None:
            await self._client.disconnect()
            logger.info(f"텔레그램 연결 해제 (api_id: {self.api_id})")

    async def ensure_connected(self) -> bool:
        """클라이언트가 연결되어 있는지 확인하고, 연결되어 있지 않으면 연결을 시도합니다.

        Returns:
            bool: 연결 성공 여부
        """
        try:
            # 이미 연결되어 있는지 확인
            if self.client and self.client.is_connected():
                return True

            # 연결 시도
            logger.debug("텔레그램 서버에 연결 시도 중...")
            await self.client.connect()
            logger.debug("텔레그램 서버에 성공적으로 연결됨")
            return True
        except Exception as e:
            logger.error(f"텔레그램 서버 연결 중 오류 발생: {e}")
            return False

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

    def run_until_complete(self, coro):
        """코루틴 실행 헬퍼 함수

        동기 코드에서 비동기 메서드를 쉽게 호출할 수 있게 해주는 헬퍼 함수입니다.
        인스턴스 전용 이벤트 루프를 사용하거나, 필요시 새로 생성합니다.

        Args:
            coro: 실행할 코루틴

        Returns:
            코루틴 실행 결과
        """
        # 인스턴스 루프가 없거나 닫혀있는 경우 새로 생성
        if not hasattr(self, 'loop') or self.loop is None or self.loop.is_closed():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                logger.debug(f"새 이벤트 루프 생성 (api_id: {self.api_id})")
            except Exception as e:
                logger.error(f"이벤트 루프 생성 오류: {e}")
                # 마지막 수단으로 글로벌 이벤트 루프 시도
                self.loop = asyncio.get_event_loop_policy().get_event_loop()

        return self.loop.run_until_complete(coro)

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.disconnect()

        # 이벤트 루프 정리 
        if hasattr(self, 'loop') and self.loop is not None and not self.loop.is_closed():
            try:
                # 보류 중인 작업 취소
                tasks = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task(self.loop)]
                for task in tasks:
                    task.cancel()

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                self.loop.stop()
                self.loop.close()
                logger.debug(f"이벤트 루프를 닫았습니다.")

            except Exception as e:
                logger.warning(f"이벤트 루프 정리 중 오류: {e}")

    def __repr__(self):
        return f"TeleprobeClient(api_id={self.api_id}, phone={self.phone})"
