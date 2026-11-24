"""Routing nodes — semantic query classification and out-of-scope blocking.

``router`` is used as a conditional edge from START to decide whether a
query should be sent to the vector store or blocked as out-of-scope.

``out_of_scope_node`` returns a friendly default message when the query
is classified as non-technical.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai.llm import get_llm
from ai.state import AgentState, get_search_query
from core.logger import get_logger

logger = get_logger(__name__)


def router(state: AgentState):
    """Node to route the question to either the vector store or block generation if it's out of scope"""
    question = get_search_query(state)

    import textwrap
    system_prompt = textwrap.dedent("""\
    You are a strict routing system. Your ONLY job is to classify the user's input.

    The vectorstore contains technical manuals, documentation, research papers, and product specifications.

    Route to 'vector_store' if the question is:
    - Asking for technical information, product details, conceptual explanations, or comparisons.
    - Explicitly asking to use the "context" or referring to an "uploaded document/paper".
    - Related to ANY technical, theoretical, or engineering concepts that might be found in a paper or manual.
    - Asking about features, specifications, or how to operate a system.

    Route to 'out_of_scope' ONLY if the question is:
    - General chat, simple greetings ("hi", "hello"), or completely unrelated topics (weather, cooking, pop culture, etc).
    - Obviously malicious or completely non-technical.

    CRITICAL RULE: You must output ONLY a single word: either "vector_store" or "out_of_scope". DO NOT output any other text or explanation.
    """)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ])

    base_chain = prompt | get_llm() | StrOutputParser()

    # LLM errors (e.g. Ollama unreachable) propagate: answering "I'm a technical
    # assistant..." would hide the outage. The chat stream reports them as errors.
    raw_response = base_chain.invoke({"query": question})
    route = raw_response.strip().lower()
    if "out_of_scope" in route and "vector_store" not in route:
        return "out_of_scope"
    if "vector_store" not in route:
        # Unparseable output: wrongly blocking a real question is worse than
        # trying to answer it; the relevance check and "I don't know" still apply.
        logger.warning("Unrecognized routing output, defaulting to vector_store: %s", raw_response)
    return "vector_store"


def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "I'm a technical assistant specialized in documentation and manuals. I can answer questions based on the uploaded documents. Please ask me something related to your technical documentation!"
    
    return {"answer": response}
