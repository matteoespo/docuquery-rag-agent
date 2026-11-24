"""Routing nodes — query classification and out-of-scope blocking.

``router`` is a conditional edge after ``contextualize``: it decides whether
the question goes to retrieval or gets the out-of-scope reply. It uses
structured output (Ollama constrains the reply to the JSON schema) and is
told to prefer answering: wrongly blocking a real question is worse than
retrieving for a greeting.

``out_of_scope_node`` returns the friendly default message.
"""

from pathlib import Path
from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError

from ai.llm import get_llm
from ai.state import AgentState, get_search_query
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

MAX_LISTED_DOCUMENTS = 20


class RouteDecision(BaseModel):
    """Whether the question should be answered from the documents."""
    datasource: Literal["vector_store", "out_of_scope"] = Field(
        description="vector_store for anything that could be answered from the documents; "
                    "out_of_scope only for greetings, small talk or clearly unrelated requests.",
    )


ROUTER_PROMPT = """You decide whether a user message should be answered from the user's documents.

Documents available:
{documents}

Choose "vector_store" for any question that could be answered from documents like these: \
facts, specifications, procedures, error codes, comparisons, people, authors, tables, \
methods, definitions or anything about the topics, products or papers above.
Choose "out_of_scope" ONLY for greetings and small talk, or requests clearly unrelated to \
any document (jokes, poems, weather, general trivia).
When in doubt, choose "vector_store"."""


def _document_names() -> str:
    pdfs = sorted(p.stem for p in Path(settings.manual_path).glob("**/*.pdf"))
    if not pdfs:
        return "(none uploaded yet)"
    listed = "\n".join(f"- {name}" for name in pdfs[:MAX_LISTED_DOCUMENTS])
    more = len(pdfs) - MAX_LISTED_DOCUMENTS
    return listed + (f"\n- ... and {more} more" if more > 0 else "")


def router(state: AgentState):
    """Conditional edge: "vector_store" or "out_of_scope"."""
    messages = [
        SystemMessage(ROUTER_PROMPT.format(documents=_document_names())),
        HumanMessage(get_search_query(state)),
    ]
    structured = get_llm().with_structured_output(RouteDecision, method="json_schema")
    # LLM errors (e.g. Ollama unreachable) propagate: answering "I'm a technical
    # assistant..." would hide the outage. The chat stream reports them as errors.
    try:
        decision = structured.invoke(messages)
    except (OutputParserException, ValidationError) as e:
        logger.warning("Unparseable routing output, defaulting to vector_store: %s", e)
        return "vector_store"
    if decision is None:
        logger.warning("Empty routing output, defaulting to vector_store")
        return "vector_store"
    return decision.datasource


def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "I'm a technical assistant specialized in documentation and manuals. I can answer questions based on the uploaded documents. Please ask me something related to your technical documentation!"

    return {"answer": response}
