"""Query contextualization: rewrite follow-up questions into standalone ones.

Router, retriever and web search only see a single string. A follow-up like
"what about its voltage?" is meaningless without the conversation, so this
node rewrites it using chat history before anything else runs.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai.llm import get_llm
from ai.memory import format_chat_messages
from ai.state import AgentState
from core.logger import get_logger

logger = get_logger(__name__)

HISTORY_MESSAGES = 6
MAX_REWRITE_CHARS = 1000

SYSTEM_PROMPT = (
    "Given a conversation and a follow-up question, rewrite the follow-up into a "
    "standalone question that can be understood without the conversation. "
    "Replace pronouns and references (it, that, the second one...) with what they refer to. "
    "Keep the user's own words and technical terms (e.g. firmware, oil, filter, error code) and "
    "product names exactly; don't replace them with synonyms. "
    "If the question is already standalone, return it unchanged. "
    "Do NOT answer the question. Output ONLY the rewritten question."
)


async def contextualize(state: AgentState):
    """Set ``search_query``: the standalone form of ``query``."""
    query = state["query"]
    history = format_chat_messages(state.get("chat_history", [])[-HISTORY_MESSAGES:])
    if not history:
        return {"search_query": query}

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Conversation:\n{history}\n\nFollow-up question: {query}\n\nStandalone question:"),
    ])
    chain = prompt | get_llm() | StrOutputParser()

    try:
        rewritten = (await chain.ainvoke({"history": history, "query": query})).strip().strip('"')
    except Exception as e:
        logger.warning("Query rewrite failed, using original query: %s", e)
        return {"search_query": query}

    if not rewritten or len(rewritten) > MAX_REWRITE_CHARS:
        logger.warning("Unusable query rewrite (%d chars), using original query", len(rewritten))
        return {"search_query": query}

    logger.info("Rewrote follow-up %r -> %r", query, rewritten)
    return {"search_query": rewritten}
