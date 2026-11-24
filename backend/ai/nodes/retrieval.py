"""Retrieval nodes — vector store search and document sufficiency grading.

``retrieve`` performs a similarity search against ChromaDB.

``check_if_more_info_needed`` is a conditional edge that evaluates whether
the retrieved documents contain enough information to answer the query,
or if the agent should fall back to a web search.
"""

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai.llm import get_embeddings, get_llm
from ai.state import AgentState, get_search_query
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def retrieve(state: AgentState):
    """Node to retrieve relevant documents from the vector database based on the agent's query"""
    question = get_search_query(state)
    vector_db = Chroma(persist_directory=settings.db_dir, embedding_function=get_embeddings())
    docs = vector_db.similarity_search(question, k=settings.retrieval_k)
    return {"documents": docs}


def check_if_more_info_needed(state: AgentState):
    """Node to check if the retrieved documents are sufficient, or if we need a web search for more info"""
    question = get_search_query(state)
    docs = state.get("documents", [])
    
    if not docs:
        return "more_info_needed"
        
    context = "\n\n".join([doc.page_content for doc in docs])

    import textwrap
    system_prompt = textwrap.dedent("""\
    You are a grader assessing relevance of retrieved documents to a user question.

    Analyze the documents and route accordingly:
    - Use 'vector_store' if the documents contain sufficient information to answer the question.
    - Use 'more_info_needed' if the documents lack relevant information or detail to answer the question.

    CRITICAL RULE: You must output ONLY a single word: either "vector_store" or "more_info_needed". DO NOT output any other text or explanation.
    """)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {query}\n\nRetrieved Documents: {context}")
    ])

    base_chain = prompt | get_llm() | StrOutputParser()

    try:
        raw_response = base_chain.invoke({"query": question, "context": context})
        route = raw_response.strip().lower()
        if "vector_store" in route:
            route = "vector_store"
        elif "more_info_needed" in route:
            route = "more_info_needed"
        else:
            logger.warning("Unrecognized routing output: %s", raw_response)
            route = "vector_store"
    except Exception as e:
        logger.warning("Initial parse failed. Error: %s", e)
        route = "vector_store"

    return route
