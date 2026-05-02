from typing import TypedDict, List, Annotated
import operator
from langchain_core.documents import Document

# here we use TypedDict instead of Pydantic because it's internal and we dont want validation overhead. We assume we always have the correct data structure :)
class AgentState(TypedDict):
    """Represents the state of an agent in the system."""
    query: str
    documents: List[Document]
    answer: str
    chat_history: List[dict]  # [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there!"}]
    retries: Annotated[int, operator.add] # keeps track of loops
