from typing import Optional

from utils import Logger

logger = Logger(__name__)

class SemanticCache:
    def __init__(
            self,
            thread_id: int,
            similarity_threshold: float = 0.2
    ):
        self.id: int = thread_id
        self.similarity_threshold: float = similarity_threshold

    def lookup(self, prompt: str, llm_string: str) -> Optional[str]:
        """
        캐시에서 프롬프트에 대한 응답을 조회합니다.
        시맨틱 유사도 검색을 사용합니다.
        """
        pass

    def update(self, prompt: str, llm_string: str, response: str) -> None:
        """
        캐시에 프롬프트와 응답을 저장합니다.
        """
        pass


    def clear(self, prompt: str = None, llm_string: str = None) -> None:
        """
        캐시를 비웁니다.
        """
        pass

    def clear_all(self) -> None:
        pass

    @staticmethod
    def clean_old():
        pass

    @staticmethod
    def hit(cache_id: int):
        pass


    @staticmethod
    def count_all():
        pass

    @staticmethod
    def delete_lfu(num_to_delete: int = 1):
        """
            가장 적게 사용된 캐시(LFU)를 지정된 개수만큼 삭제합니다.
            사용 빈도가 같다면 가장 오래된 캐시(LRU)를 먼저 삭제합니다.
        """
        pass


