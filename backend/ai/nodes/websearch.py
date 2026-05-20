"""Web search fallback node.

``websearch`` queries DuckDuckGo when the local vector store does not
contain sufficient information. Results are appended to the existing
document list so the generation node can incorporate web context.
"""

from ddgs import DDGS
from langchain_core.documents import Document
from ai.state import AgentState

duckduckgo_search = DDGS()


def websearch(state: AgentState):
    question = state["query"]

    raw_results = duckduckgo_search.text(question, max_results=5)
    formatted_response = "\n\n".join([f"Source: {res['href']}\n{res['body']}" for res in raw_results])

    web_doc = Document(page_content=formatted_response, metadata={"source": "web"})
    docs = state.get("documents", []) + [web_doc]
    
    return {"documents": docs, "retries": 1}
