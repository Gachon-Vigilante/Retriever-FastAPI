import typing
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import ToolNode

from core.constants import tz
from genai.models import llm
from watson.constants import prompts_path, max_token_limit
from .datamodel import OverallState
from .utils import fill_prompt, load_prompts, trim_messages_by_token_limit_with_system_start

if typing.TYPE_CHECKING:
    from .bot import Watson

class LangGraphNodes:
    """
    LangGraph 기반 RAG 워크플로우의 각 노드(예: 설정, 에이전트 실행 등)를 정의하는 클래스입니다.

    이 클래스는 LangGraph 워크플로우 내에서 사용되는 노드 단위 작업들을 함수로 정의하며,
    질문 처리, 도구 사용, 응답 생성을 담당합니다.
    """
    def get_tool_node(self: 'Watson') -> ToolNode:
        return ToolNode(self.get_toolbox())


    def get_setup(self: 'Watson'):
        def setup(state: OverallState) -> OverallState:
            """
            시스템 및 사용자 프롬프트 메시지를 초기화하는 LangGraph 노드입니다.

            `prompts["system"]`과 `prompts["user"]`를 기반으로 메시지를 구성하며,
            현재 시각 및 질문 내용을 삽입합니다. 이 메시지들은 LLM 처리 체인에서 사용됩니다.

            Args:
                state (OverallState): 현재 워크플로우 상태. 질문(`question`) 필드를 포함해야 합니다.

            Returns:
                OverallState: 생성된 system/user 메시지가 포함된 새로운 상태 객체.

            Raises:
                ValueError: 필수 프롬프트가 비어 있거나, 질문이 없을 경우.
            """
            if cached := self.cache.lookup(state.question, self.llm_name):
                messages = [
                    SystemMessage(fill_prompt(load_prompts(prompts_path)["system"])),
                    HumanMessage(state.question),
                    AIMessage(
                        content=cached,
                        additional_kwargs={"cached": True}
                    ),
                ]
            else:
                # 시스템 프롬프트와 유저 프롬프트를 생성해서 message 객체로 변환
                messages = ChatPromptTemplate.from_messages([
                    ("system", fill_prompt(load_prompts(prompts_path)["system"])),
                    ("user", fill_prompt(load_prompts(prompts_path)["user"])),
                ]).invoke({
                    "question": state.question,
                    "now": datetime.now(tz=tz).isoformat()
                }).messages

            return OverallState(
                messages=messages,
            )
        return setup


    def get_agent(self: 'Watson'):
        def agent(state: OverallState) -> OverallState:
            """
            에이전트가 도구 사용 여부를 판단하고 응답을 생성하는 LangGraph 노드입니다.

            이전 단계에서 전달된 메시지를 기반으로 LLM과 도구를 결합한 체인을 실행합니다.
            필요 시 도구를 호출하고, 최종 응답 메시지를 상태에 추가하여 반환합니다.

            Args:
                state (OverallState): 현재 워크플로우 상태. 이전까지 누적된 메시지를 포함해야 합니다.

            Returns:
                OverallState: 응답 메시지가 포함된 새로운 상태 객체.

            Raises:
                ValueError: 메시지가 비어 있거나 프롬프트 구성에 실패한 경우.
                RuntimeError: LLM 호출이나 도구 처리 중 오류가 발생한 경우.
            """
            # LLM이 사용 가능한 도구를 인식하도록 bind
            llm_with_tools = llm.bind_tools(self.get_toolbox())

            prompt = ChatPromptTemplate.from_messages(
                trim_messages_by_token_limit_with_system_start(state.messages, max_tokens=max_token_limit)
            )

            # 프롬프트 -> llm 체인 생성
            chain = prompt | llm_with_tools

            # LLM에게 질문과 필요한 필드를 입력하고 응답 수신
            response = chain.invoke({})

            return OverallState(
                messages=[response]
            )

        return agent

