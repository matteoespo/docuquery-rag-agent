from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
from api.models import RouteRequest, GradeAnswerResponse, RetrievalEvalRequest
import core.config as config
from ai.llm import get_llm, get_embeddings

# load llms and vector db
llm = get_llm()
embeddings = get_embeddings()
vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)
duckduckgo_search = DuckDuckGoSearchRun()


def router(state: AgentState):
    """Node to route the question to either the vector store or block generation if it's out of scope"""
    question = state["query"]

    llm_router = llm.with_structured_output(RouteRequest)

    system_prompt = """You are an expert at routing user questions to a vectorstore or out_of_scope.
                        The vectorstore contains documents about technical manuals.
                        Use the vectorstore for questions on these topics. For math, greetings, or general knowledge, use out_of_scope."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ])

    router_chain = prompt | llm_router

    route = router_chain.invoke({"query": question})

    return route.datasource

def check_if_more_info_needed(state: AgentState):
    """Node to check if the retrieved documents are sufficient, or if we need a web search for more info"""
    question = state["query"]
    docs = state.get("documents", [])
    
    if not docs:
        return "more_info_needed"
        
    context = "\n\n".join([doc.page_content for doc in docs])

    llm_evaluator = llm.with_structured_output(RetrievalEvalRequest)

    system_prompt = """You are a grader assessing relevance of retrieved documents to a user question.
    If the documents contain information relevant to answering the question, route to 'vector_store'. 
    If the documents do not contain the answer or lack sufficient detail, route to 'more_info_needed'."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {query}\n\nRetrieved Documents: {context}")
    ])

    evaluator_chain = prompt | llm_evaluator
    route = evaluator_chain.invoke({"query": question, "context": context})

    return route.datasource

def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "I am a technical assistant specialized in manuals. I cannot answer general or out-of-scope questions."
    
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

def generate(state: AgentState):
    """Node to generate an answer using the retrieved documents and the agent's query"""
    question = state["query"]
    context = "\n\n".join([doc.page_content for doc in state["documents"]])

    system_prompt = (
        "You are a technical assistant."
        "Use the following pieces of retrieved context to answer the question."
        "If you don't know the answer based on the context, say that you don't know."
        "Keep the answer concise and professional."
        "\n\n"
        "{context}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{question}"),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"context": context, "question": question})

    return {"answer": response}
