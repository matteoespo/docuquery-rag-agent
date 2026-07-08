"""Routing nodes — semantic query classification and out-of-scope blocking.

``router`` is used as a conditional edge from START to decide whether a
query should be sent to the vector store or blocked as out-of-scope.

``out_of_scope_node`` returns a friendly default message when the query
is classified as non-technical.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
from ai.llm import get_llm
from core.logger import get_logger

logger = get_logger(__name__)


def router(state: AgentState):
    """Node to route the question to either the vector store or block generation if it's out of scope"""
    question = state["query"]

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

    try:
        raw_response = base_chain.invoke({"query": question})
        print(f"RAW_RESPONSE: {repr(raw_response)}")
        route = raw_response.strip().lower()
        if "vector_store" in route:
            route = "vector_store"
        elif "out_of_scope" in route:
            route = "out_of_scope"
        else:
            print(f"WARNING UNRECOGNIZED: {raw_response}")
            logger.warning("Unrecognized routing output: %s", raw_response)
            route = "out_of_scope"
    except Exception as e:
        print(f"EXCEPTION: {repr(e)}")
        logger.warning("Initial parse failed. Error: %s", e)
        route = "out_of_scope"

    return route


def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "I'm a technical assistant specialized in documentation and manuals. I can answer questions based on the uploaded documents. Please ask me something related to your technical documentation!"
    
    return {"answer": response}
