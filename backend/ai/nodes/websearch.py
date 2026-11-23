"""Web search fallback node.

``websearch`` queries DuckDuckGo when the local vector store does not
contain sufficient information. New results are appended to the existing
document list so the generation node can incorporate web context.
"""

from ddgs import DDGS
from langchain_core.documents import Document

from ai.state import AgentState, get_search_query
from core.logger import get_logger

logger = get_logger(__name__)


def websearch(state: AgentState):
    """Search DuckDuckGo and append results not already in the document list."""
    question = get_search_query(state)

    # Copy: never mutate the list held in graph state.
    docs = list(state.get("documents", []))
    seen = {doc.metadata.get("source") for doc in docs}
    try:
        for res in DDGS().text(question, max_results=5):
            if res["href"] in seen:
                continue
            seen.add(res["href"])
            docs.append(Document(page_content=res["body"], metadata={"source": res["href"], "page": "web"}))
    except Exception as e:
        # No placeholder document: the model could otherwise cite it as a source.
        logger.warning("Web search failed: %s", e)

    return {"documents": docs, "retries": 1}
