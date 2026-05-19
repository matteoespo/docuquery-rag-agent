from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser, RetryOutputParser
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
from api.models import RouteRequest, RetrievalEvalRequest
import core.config as config
from ai.llm import get_llm, get_embeddings

# load llms and vector db
llm = get_llm()
embeddings = get_embeddings()
vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)
duckduckgo_search = DuckDuckGoSearchRun()

def _format_chat_messages(messages: list[dict]) -> str:
    """Format chat messages into a readable plain-text transcript."""
    lines = []
    for message in messages:
        role = str(message.get("role", "unknown")).strip().lower()
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def _build_memory_context(chat_history: list[dict]) -> str:
    """Keep recent messages verbatim and summarize older conversation."""
    if not chat_history:
        return ""

    recent_messages = chat_history[-3:]
    older_messages = chat_history[:-3]

    recent_block = _format_chat_messages(recent_messages)
    older_summary = ""

    if older_messages:
        summarize_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Summarize the prior conversation for assistant memory. "
                    "Capture user goals, constraints, preferences, and unresolved topics in 4 concise bullet points max."
                ),
                ("human", "Conversation:\n{conversation}"),
            ]
        )
        summarize_chain = summarize_prompt | llm | StrOutputParser()
        older_summary = summarize_chain.invoke(
            {"conversation": _format_chat_messages(older_messages)}
        ).strip()

    memory_sections = []
    if older_summary:
        memory_sections.append(f"Older conversation summary:\n{older_summary}")
    if recent_block:
        memory_sections.append(f"Most recent 3 messages:\n{recent_block}")

    return "\n\n".join(memory_sections)

def router(state: AgentState):
    """Node to route the question to either the vector store or block generation if it's out of scope"""
    question = state["query"]

    parser = PydanticOutputParser(pydantic_object=RouteRequest)
    retry_parser = RetryOutputParser.from_llm(parser=parser, llm=llm)

    system_prompt = """You are an expert at routing user questions.
                    The vectorstore contains documents about technical manuals.

                    Analyze the user question and route it:
                    - Use 'vector_store' (with underscore) for questions about technical manuals or documentation.
                    - Use 'out_of_scope' for general chat, math, greetings, coding advice, or general knowledge questions.

                    {format_instructions}"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ]).partial(format_instructions=parser.get_format_instructions())

    base_chain = prompt | llm | StrOutputParser()

    try:
        raw_response = base_chain.invoke({"query": question})
        route = parser.invoke(raw_response)
    except Exception:
        try:
            prompt_value = prompt.format_prompt(query=question)
            route = retry_parser.invoke_with_prompt(raw_response, prompt_value)
        except Exception:
            # fallback
            return "vector_store"

    return route.datasource


def check_if_more_info_needed(state: AgentState):
    """Node to check if the retrieved documents are sufficient, or if we need a web search for more info"""
    question = state["query"]
    docs = state.get("documents", [])
    
    if not docs:
        return "more_info_needed"
        
    context = "\n\n".join([doc.page_content for doc in docs])

    parser = PydanticOutputParser(pydantic_object=RetrievalEvalRequest)
    retry_parser = RetryOutputParser.from_llm(parser=parser, llm=llm)

    system_prompt = """You are a grader assessing relevance of retrieved documents to a user question.

                    Analyze the documents and route accordingly:
                    - Use 'vector_store' (with underscore) if the documents contain sufficient information to answer the question.
                    - Use 'more_info_needed' if the documents lack relevant information or detail to answer the question.

                    {format_instructions}"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {query}\n\nRetrieved Documents: {context}")
    ]).partial(format_instructions=parser.get_format_instructions())

    base_chain = prompt | llm | StrOutputParser()

    try:
        raw_response = base_chain.invoke({"query": question, "context": context})
        route = parser.invoke(raw_response)
    except Exception:
        try:
            prompt_value = prompt.format_prompt(query=question, context=context)
            route = retry_parser.invoke_with_prompt(raw_response, prompt_value)
        except Exception:
            # fallback
            return "vector_store"

    return route.datasource

def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "HI! I am a technical assistant specialized in manuals. I will answer all your technical questions based on the uploaded documents."
    
    return {"answer": response}

def retrieve(state: AgentState):
    """Node to retrieve relevant documents from the vector database based on the agent's query"""
    question = state["query"]
    docs = vector_db.similarity_search(question, k=3)
    return {"documents": docs}


def websearch(state: AgentState):
    question = state["query"]

    response = duckduckgo_search.run(question)

    web_doc = Document(page_content=response, metadata={"source": "web"})
    
    docs = state.get("documents", [])
    docs.append(web_doc)
    
    return {"documents": docs, "retries": 1}

def grade_answer(state: AgentState):
    """Determines if the generated answer is useful or if we need to search the web for more information"""
    question = state["query"]
    answer = state["answer"]
    retries = state.get("retries", 0)

    if retries >= 2:
        return "useful"
    
    system_prompt = """You are a strict grader assessing whether an answer addresses a user question.
    If the answer is helpful and resolves the question, respond with exactly the word 'yes'. 
    If the answer is evasive, states it doesn't know, or is incorrect, respond with exactly the word 'no'.
    Do NOT output any other text, explanations, or formatting. Only 'yes' or 'no'."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {query}\n\nAnswer: {answer}")
    ])

    grader_chain = prompt | llm | StrOutputParser()
    
    result = grader_chain.invoke({"query": question, "answer": answer}).strip().lower()

    if "yes" in result:
        return "useful"
    else:
        return "not_useful"

from langchain_core.runnables import RunnableConfig

async def generate(state: AgentState, config: RunnableConfig):
    """Node to generate an answer using retrieved documents and query.

    KV Cache Optimization: Static content (system + context) placed FIRST,
    dynamic query placed LAST for byte-for-byte prefix matching across requests.
    """
    question = state["query"]
    context = "\n\n".join([doc.page_content for doc in state["documents"]])
    chat_history = state.get("chat_history", [])
    memory_context = _build_memory_context(chat_history)

    system_base = (
        "You are a technical assistant. "
        "Use the following pieces of retrieved context to answer the question. "
        "Use conversation memory to keep continuity when relevant. "
        "If you don't know the answer based on the context, say that you don't know. "
        "Keep the answer concise and professional."
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

    chain = prompt | llm.with_config({"tags": ["generate_node"]}) | StrOutputParser()
    response = await chain.ainvoke({"question": question}, config=config)

    return {"answer": response}
