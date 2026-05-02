from langgraph.graph import StateGraph, MessagesState, START, END
from ai.state import AgentState
from ai.rag_engine import retrieve, generate, websearch, router, out_of_scope_node, grade_answer, check_if_more_info_needed

def load_agent():
    workflow = StateGraph(AgentState)

    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)
    workflow.add_node("block", out_of_scope_node)
    workflow.add_node("websearch", websearch)
    
    workflow.add_conditional_edges(
        START,
        router,
        {
            "vector_store": "retrieve",
            "out_of_scope": "block"
        }
    )

    workflow.add_conditional_edges(
        "retrieve",
        check_if_more_info_needed,
        {
            "vector_store": "generate",
            "more_info_needed": "websearch",
        }
    )

    workflow.add_conditional_edges(
        "generate",
        grade_answer,
        {
            "useful": END,
            "not_useful": "websearch" # loops back to search
        }
    )

    workflow.add_edge("block", END)
    workflow.add_edge("websearch", "generate")

    agent = workflow.compile()

    """
    png_data = agent.get_graph().draw_mermaid_png()
    with open("../docs/agent_graph.png", "wb") as f:
        f.write(png_data)
    """

    return agent