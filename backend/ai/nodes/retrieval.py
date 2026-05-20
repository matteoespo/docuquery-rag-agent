"""Retrieval nodes — vector store search and document sufficiency grading.

``retrieve`` performs a similarity search against ChromaDB.

``check_if_more_info_needed`` is a conditional edge that evaluates whether
the retrieved documents contain enough information to answer the query,
or if the agent should fall back to a web search.
"""

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser, RetryOutputParser
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
from api.models import RetrievalEvalRequest
import core.config as config
from ai.llm import get_llm, get_embeddings

llm = get_llm()
embeddings = get_embeddings()
vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)


def retrieve(state: AgentState):
    """Node to retrieve relevant documents from the vector database based on the agent's query"""
    question = state["query"]
    docs = vector_db.similarity_search(question, k=3)
    return {"documents": docs}


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
    - Use 'vector_store' if the documents contain sufficient information to answer the question.
    - Use 'more_info_needed' if the documents lack relevant information or detail to answer the question.

    CRITICAL RULE: DO NOT output a JSON schema definition. DO NOT output "properties" or "type".
    You must ONLY output a valid JSON object matching exactly one of these two formats:
    {{"datasource": "vector_store"}}
    OR
    {{"datasource": "more_info_needed"}}

    {format_instructions}"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {query}\n\nRetrieved Documents: {context}")
    ]).partial(format_instructions=parser.get_format_instructions())

    base_chain = prompt | llm | StrOutputParser()

    try:
        raw_response = base_chain.invoke({"query": question, "context": context})
        route = parser.invoke(raw_response)
    except Exception as e:
        print(f"\n[EVAL DEBUG] Initial parse failed.\nOutput: {raw_response}\nError: {e}\n")
        try:
            prompt_value = prompt.format_prompt(query=question, context=context)
            route = retry_parser.parse_with_prompt(raw_response, prompt_value)
        except Exception as retry_e:
            print(f"\n[EVAL DEBUG] Retry parse failed! Error: {retry_e}\n")
            return "vector_store"

    return route.datasource
