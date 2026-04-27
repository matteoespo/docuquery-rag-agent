from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
from api.models import RouteRequest
import core.config as config
from ai.llm import get_llm, get_embeddings

# load llms and vector db
llm = get_llm()
embeddings = get_embeddings()
vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)


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

def out_of_scope_node(state: AgentState):
    """Node to handle out-of-scope questions by returning a default response indicating the assistant's limitations."""
    response = "I am a technical assistant specialized in manuals. I cannot answer general or out-of-scope questions."
    
    return {"answer": response}

def retrieve(state: AgentState):
    """Node to retrieve relevant documents from the vector database based on the agent's query"""
    question = state["query"]
    docs = vector_db.similarity_search(question, k=3)
    return {"documents": docs}


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
