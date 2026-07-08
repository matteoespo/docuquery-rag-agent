"""Generation nodes — answer synthesis and hallucination grading.

``generate`` builds a KV-cache-optimized prompt with static context first
and the dynamic user query last, then streams the answer via the LLM.

``grade_answer`` is a conditional edge that evaluates whether the generated
answer is factual and useful, or whether the agent should retry with a
web search for additional context.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableConfig
from ai.state import AgentState
from ai.llm import get_llm
from ai.memory import build_memory_context
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


async def generate(state: AgentState, config: RunnableConfig):
    """Node to generate an answer using retrieved documents and query.

    KV Cache Optimization: Static content (system + context) placed FIRST,
    dynamic query placed LAST for byte-for-byte prefix matching across requests.
    """
    question = state["query"]
    
    import os
    context_chunks = []
    for doc in state["documents"]:
        source = doc.metadata.get("source", "Unknown Source")
        if source != "web":
            source = os.path.basename(str(source))
        page = doc.metadata.get("page", "Unknown Page")
        context_chunks.append(f"[Source: {source}, Page: {page}]\n{doc.page_content}")
    
    context = "\n\n".join(context_chunks)
    chat_history = state.get("chat_history", [])
    memory_context = build_memory_context(chat_history)

    system_base = (
        "You are a technical assistant. "
        "Use the following pieces of retrieved context to answer the question. "
        "Use conversation memory to keep continuity when relevant. "
        "If you don't know the answer based on the context, say that you don't know. "
        "Keep the answer concise and professional. "
        "CRITICAL: You must explicitly cite the source document name, web link, or page number you used to generate the answer. "
        "Format citations like [Source: document.pdf, Page: 5] or [Source: https://example.com]."
    )

    retrieved_context_block = f"RETRIEVED CONTEXT:\n{context}\n" if context else "RETRIEVED CONTEXT:\n(No documents retrieved)\n"
    memory_block = f"CONVERSATION MEMORY:\n{memory_context}\n" if memory_context else "CONVERSATION MEMORY:\n(No prior conversation)\n"

    static_prefix = f"{system_base}\n\n{retrieved_context_block}\n{memory_block}"

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", static_prefix),
            ("human", "{question}"),
        ]
    )

    chain = prompt | get_llm().with_config({"tags": ["generate_node"]}) | StrOutputParser()
    response = await chain.ainvoke({"question": question}, config=config)

    return {"answer": response}


def grade_answer(state: AgentState):
    """Determines if the generated answer is useful or if we need to search the web for more information"""
    question = state["query"]
    answer = state["answer"]
    retries = state.get("retries", 0)

    if retries >= settings.max_retries:
        return "useful"
    
    system_prompt = """You are a grader assessing whether an answer addresses a user question.
    
    If the answer accurately reflects the retrieved documents and addresses the user's question, respond with exactly the word 'yes'.
    
    IMPORTANT: If the answer honestly states that the provided documents do not contain enough information to fully answer the question, this is considered a GOOD and FACTUAL answer. In this case, also respond with 'yes'.
    
    If the answer is a hallucination, makes up facts not in the context, or completely ignores the user's question, respond with exactly 'no'.
    
    Do NOT output any other text, explanations, or formatting. Only 'yes' or 'no'."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {query}\n\nAnswer: {answer}")
    ])

    grader_chain = prompt | get_llm() | StrOutputParser()
    
    result = grader_chain.invoke({"query": question, "answer": answer}).strip().lower()

    if "yes" in result:
        return "useful"
    else:
        return "not_useful"
