"""Routing nodes — semantic query classification and out-of-scope blocking.

``router`` is used as a conditional edge from START to decide whether a
query should be sent to the vector store or blocked as out-of-scope.

``out_of_scope_node`` returns a friendly default message when the query
is classified as non-technical.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser, RetryOutputParser
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
from api.models import RouteDecision
from ai.llm import get_llm
from core.logger import get_logger

logger = get_logger(__name__)


def router(state: AgentState):
    """Node to route the question to either the vector store or block generation if it's out of scope"""
    question = state["query"]

    parser = PydanticOutputParser(pydantic_object=RouteDecision)
    retry_parser = RetryOutputParser.from_llm(parser=parser, llm=get_llm())

    system_prompt = """You are a strict routing system. Your ONLY job is to classify the user's input and output a JSON object.

    The vectorstore contains technical manuals, documentation, and product specifications (including simulators, software, and hardware).

    Route to 'vector_store' if the question is:
    - Asking for technical information, product details, or comparisons (e.g., "What is the best simulator?").
    - Asking about features, sensors, specifications, or how to operate a system.
    - Related to technical concepts that might be found in a manual.

    Route to 'out_of_scope' if the question is:
    - General chat, greetings ("hi", "hello"), or completely unrelated topics (weather, math, cooking).
    - Asking you to write code, scripts, or programming algorithms.

    CRITICAL RULE: DO NOT output a JSON schema definition. DO NOT output "properties" or "type".
    You must ONLY output a valid JSON object matching exactly one of these two formats:
    {{"datasource": "vector_store"}}
    OR
    {{"datasource": "out_of_scope"}}

    {format_instructions}"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ]).partial(format_instructions=parser.get_format_instructions())

    base_chain = prompt | get_llm() | StrOutputParser()

    raw_response = None
    try:
        raw_response = base_chain.invoke({"query": question})
        route = parser.invoke(raw_response)
    except Exception as e:
        logger.warning("Initial parse failed. Output: %s, Error: %s", raw_response, e)
        if raw_response is None:
            return "out_of_scope"
        try:
            prompt_value = prompt.format_prompt(query=question)
            route = retry_parser.parse_with_prompt(raw_response, prompt_value)
        except Exception as retry_e:
            logger.warning("Retry parse failed! Error: %s", retry_e)
            return "out_of_scope"

    return route.datasource


def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "I'm a technical assistant specialized in documentation and manuals. I can answer questions based on the uploaded documents. Please ask me something related to your technical documentation!"
    
    return {"answer": response}
