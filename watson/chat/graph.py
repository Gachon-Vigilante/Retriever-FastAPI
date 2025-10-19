import os
import typing

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod
from langgraph.errors import GraphRecursionError
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from utils import Logger
from watson.constants import graph_mermaid_path
from .datamodel import OverallState
from .memory import checkpointer
from .utils import is_cachable

if typing.TYPE_CHECKING:
    from .bot import Watson

load_dotenv()

logger = Logger(__name__)

use_checkpointer = True if os.getenv("BOT_MEMORY", False) == "true" else False

class LangGraphMethods:
    """
    LangGraph 기반 챗봇의 워크플로우 구성 및 실행 기능을 정의하는 클래스입니다.

    이 클래스는 에이전트 그래프를 구성하고 실행하며, 질문에 응답하거나
    메시지 기록을 관리하는 기능을 제공합니다. 그래프는 Postgres 기반 저장소와 연동됩니다.

    Note:
        이 클래스는 실제 Bot 클래스에 혼합(mixin)되어 사용됩니다.
    """
    def _build_graph(self: 'Watson') -> CompiledStateGraph:
        """
        LangGraph 기반의 워크플로우를 구성하고 Postgres 저장소 기반으로 컴파일합니다.

        노드 구성:
            - self.setup: 초기 설정 노드
            - self.agent: 주 에이전트 실행 노드
            - self.tool_node: 외부 도구 실행을 위한 노드

        그래프 연결 구조:
            - setup → agent → (tool_node or finish)
            - tool_node → agent (루프 연결)

        Returns:
            CompiledStateGraph: PostgresStore와 연결된 LangGraph 실행 그래프.

        Raises:
            ValueError: 그래프 구성 중 노드나 엣지 정의 오류 발생 시.
            RuntimeError: 저장소 연결 실패 시.
        """

        workflow: StateGraph = StateGraph(OverallState)
        # 에이전트와 도구 노드 정의 및 워크플로우 그래프에 추가
        tool_node = self.get_tool_node()
        setup_node = self.get_setup()
        agent_node = self.get_agent()
        workflow.add_node(setup_node.__name__, setup_node),
        workflow.add_node(agent_node.__name__, agent_node),
        workflow.add_node(tool_node.name, tool_node)

        # 워크플로우 시작점에서 설정 노드로 연결
        workflow.set_entry_point(setup_node.__name__)

        # 설정 노드에서 조건부 분기 설정, 에이전트 노드 또는 종료 지점으로 연결
        workflow.add_conditional_edges(setup_node.__name__, self.check_cached)

        # 에이전트 노드에서 조건부 분기 설정, 도구 노드 또는 종료 지점으로 연결
        workflow.add_conditional_edges(agent_node.__name__, self.tools_condition)

        # 도구 노드에서 에이전트 노드로 순환 연결
        workflow.add_edge(tool_node.name, agent_node.__name__)

        # 에이전트 노드에서 종료 지점으로 연결
        workflow.set_finish_point(agent_node.__name__)

        # 워크플로우 그래프 컴파일. Postgres SQL saver를 사용하여 checkpointer 구현
        compiled_workflow: CompiledStateGraph = (
            workflow.compile(checkpointer=checkpointer)
            if use_checkpointer else
            workflow.compile()
        )
        return compiled_workflow

    async def ask(self: 'Watson', question: str) -> str:
        """
        사용자의 질문을 LangGraph 기반 챗봇에 전달하고, 최종 응답 메시지를 반환합니다.

        Args:
            question (str): 사용자가 입력한 질문 문자열.

        Returns:
            str: 에이전트가 생성한 최종 응답 메시지. 그래프가 없거나 실패 시 오류 메시지를 반환합니다.

        Raises:
            GraphRecursionError: LangGraph 실행 중 재귀 한도를 초과했을 경우.
        """
        answer: str
        await self.update_vectorstore()

        inputs = OverallState(
            question=question,
        )

        # config 설정(재귀 최대 횟수, thread_id)
        config = RunnableConfig(
            recursion_limit=10,
            configurable={
                "thread_id": self.id
            }
        )

        # RecursionError에 대비해서 미리 상태 백업
        saved_state = None
        if use_checkpointer:
            try:
                saved_state = self.graph.get_state(config)
            except Exception as e:
                # PoolClosed/AdminShutdown 등 일시 오류는 로깅만 하고 진행
                logger.warning(
                    f"get_state 일시 실패(폴백 진행): {type(e).__name__}: {e}"
                )
                # 아주 짧게 대기 후 한 번만 재시도
                try:
                    import time
                    time.sleep(0.15)
                    saved_state = self.graph.get_state(config)
                except Exception as e2:
                    logger.warning(
                        f"get_state 재시도도 실패 → None 폴백: {type(e2).__name__}: {e2}"
                    )
        try:
            state = self.graph.invoke(
                input=inputs,
                config=config,
            )
            answer = state["messages"][-1].content
            if is_cachable(state["messages"]):
                self.cache.update(question, self.llm_name, answer)

        except GraphRecursionError:
            # RecursionError 발생 시, answer에 대응 메세지를 대입하고 graph를 안전한 상태로 롤백
            logger.warning(f"챗봇이 그래프를 순회하던 중 답변을 생성하지 못하고 중단했습니다. Q: '{question}'")
            answer = "죄송합니다. 답변을 생성하지 못했습니다. 질문이 이해하기 어렵거나, 정보가 없는 질문인 것 같습니다. 질문을 바꿔서 다시 입력해 보세요."
            # 체크포인터를 사용할 경우 백업해놓은 상태가 있으므로 복원
            if saved_state:
                self.graph.update_state(config, saved_state.values)

        logger.info(f"챗봇(ID: {self.id})이 질문에 응답했습니다. Q: `{question}`, A: `{answer}`")

        return answer


    def visualize(self: 'Watson') -> str:
        """
        현재 LangGraph 워크플로우 그래프를 시각화합니다.

        이 함수는 그래프를 DOT 형식으로 렌더링하거나,
        텍스트 기반의 구조를 출력할 수 있습니다. 내부적으로 `visualize_graph()` 함수를 사용합니다.

        Returns:
            None
        """
        self.graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API, # API를 사용하는 대신 추가 패키지 불필요
            curve_style=CurveStyle.NATURAL,
            output_file_path=graph_mermaid_path,
        )

        return graph_mermaid_path
