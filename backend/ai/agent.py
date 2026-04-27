from langgraph.graph import StateGraph, MessagesState, START, END
from ai.state import AgentState
from ai.rag_engine import retrieve, generate, router, out_of_scope_node

def load_agent():
    workflow = StateGraph(AgentState)

    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)
    workflow.add_node("block", out_of_scope_node)

    
    workflow.add_conditional_edges(
        START,
        router,
        {
            "vector_store": "retrieve",
            "out_of_scope": "block",
        }
    )

    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    workflow.add_edge("block", END)

    agent = workflow.compile()
    return agent