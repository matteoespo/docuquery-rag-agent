"""Shared test double: a chat model that answers by which node is calling it."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    """Replies are chosen by a substring of the system prompt; every call is recorded.

    ``with_structured_output`` (used by the router) returns ``schema(datasource=route)``,
    or raises ``route_error`` if set.
    """

    replies: dict[str, str] = Field(default_factory=dict)
    default: str = "answer"
    route: str = "vector_store"
    route_error: Exception | None = None
    calls: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(messages)
        system = messages[0].content if messages and messages[0].type == "system" else ""
        reply = next((r for key, r in self.replies.items() if key in system), self.default)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])

    def with_structured_output(self, schema, **kwargs):
        def decide(messages):
            self.calls.append(messages)
            if self.route_error:
                raise self.route_error
            return schema(datasource=self.route)

        return RunnableLambda(decide)

    def calls_with_system(self, text: str) -> list:
        return [m for m in self.calls if m and m[0].type == "system" and text in m[0].content]
