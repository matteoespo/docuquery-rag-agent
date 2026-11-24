import operator
from typing import Annotated, List, NotRequired, TypedDict

from langchain_core.documents import Document


# here we use TypedDict instead of Pydantic because it's internal and we dont want validation overhead. We assume we always have the correct data structure :)
class AgentState(TypedDict):
    """Represents the state of an agent in the system."""
    query: str
    # Standalone version of ``query`` (follow-ups rewritten using chat history).
    # Used for routing, retrieval and web search; ``query`` is what gets answered.
    search_query: NotRequired[str]
    documents: List[Document]
    answer: str
    chat_history: List[dict]  # [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there!"}]
    retries: Annotated[int, operator.add] # keeps track of loops


def get_search_query(state: AgentState) -> str:
    """The query to search with: the standalone rewrite if present, else the raw query."""
    return state.get("search_query") or state["query"]
