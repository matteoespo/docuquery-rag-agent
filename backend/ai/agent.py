from langgraph.graph import StateGraph, MessagesState, START, END
from ai.state import AgentState
from ai.rag_engine import retrieve, generate

def load_agent():
    workflow = StateGraph(AgentState)

    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)

    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    agent = workflow.compile()
    return agent