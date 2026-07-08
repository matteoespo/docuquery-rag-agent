"""Web search fallback node.

``websearch`` queries DuckDuckGo when the local vector store does not
contain sufficient information. Results are appended to the existing
document list so the generation node can incorporate web context.
"""

from ddgs import DDGS
from langchain_core.documents import Document

from ai.state import AgentState
from core.logger import get_logger

logger = get_logger(__name__)


def websearch(state: AgentState):
    """Search DuckDuckGo and append results to the document list."""
    question = state["query"]

    docs = state.get("documents", [])
    try:
        raw_results = DDGS().text(question, max_results=5)
        for res in raw_results:
            docs.append(Document(page_content=res['body'], metadata={"source": res['href'], "page": "web"}))
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        docs.append(Document(page_content="Web search unavailable.", metadata={"source": "web", "page": "N/A"}))

    return {"documents": docs, "retries": 1}
