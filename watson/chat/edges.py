from typing import Any, Union, Literal, List

from langchain_core.messages import AnyMessage, AIMessage
from pydantic import BaseModel

from .utils import get_last_ai_message


class LanggraphEdges:
    @staticmethod
    def check_cached(
            state: Union[List[AnyMessage], dict[str, Any], BaseModel],
            messages_key: str = "messages",
    ) -> Literal["agent", "__end__"]:
        last_ai_msg = get_last_ai_message(state, messages_key)
        if isinstance(last_ai_msg, AIMessage) and last_ai_msg.additional_kwargs.get("cached", None):
            return "__end__"
        return "agent"

    @staticmethod
    def tools_condition(
            state: Union[List[AnyMessage], dict[str, Any], BaseModel],
            messages_key: str = "messages",
    ) -> Literal["tools", "__end__"]:
        """Use in the conditional_edge to route to the ToolNode if the last message

        has tool calls. Otherwise, route to the end.

        Args:
            state: The state to check for
                tool calls. Must have a list of messages (MessageGraph) or have the
                "messages" key (StateGraph).
            messages_key (str): key of messages in state.

        Returns:
            The next node to route to.


        """
        last_ai_msg = get_last_ai_message(state, messages_key)
        if hasattr(last_ai_msg, "tool_calls") and len(last_ai_msg.tool_calls) > 0:
            return "tools"
        return "__end__"
