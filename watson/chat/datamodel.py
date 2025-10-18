from typing import Annotated, Sequence, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# Langgraph가 업데이트되면서 TypedDict는 경고 발생.
class OverallState(BaseModel):
    """
        LangGraph 기반 워크플로우에서 사용하는 에이전트 상태 모델입니다.

        이 클래스는 LangChain 메시지 시퀀스를 상태로 관리하며, 질문을 함께 저장합니다.
        `messages` 필드는 LangGraph의 `add_messages` 리듀서를 통해 자동으로 업데이트됩니다.

        Attributes:
            messages (Sequence[BaseMessage]): LangChain 메시지 객체들의 시퀀스입니다.
                LangGraph의 `add_messages` 리듀서를 통해 메시지가 누적됩니다.
            question (Optional[str]): 현재 상태와 관련된 질문입니다. 질문이 없을 수도 있습니다.
    """
    # add_messages reducer 함수를 사용하여 메시지 시퀀스를 관리
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list, description="add_messages")
    question: Optional[str] = Field(default=None, description="Question")  # 질문 필드. 기본값 없음 허용
