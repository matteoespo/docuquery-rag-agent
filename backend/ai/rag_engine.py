from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ai.state import AgentState
import core.config as config
from ai.llm import get_llm, get_embeddings

# load llms and vector db
llm = get_llm()
embeddings = get_embeddings()
vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)


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
