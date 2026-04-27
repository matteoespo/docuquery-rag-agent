from ai.rag_engine import router as router_node

def run_manual_test():
    # Case 1: Technical Question
    technical_state = {"query": "How do I reset my router to factory settings?"}
    result_1 = router_node(technical_state)
    print(f"Question: {technical_state['query']}")
    print(f"LLM Decision: {result_1}  <-- Expected: vector_store\n")

    # Case 2: General Knowledge Question
    general_state = {"query": "Hello! Can you tell me what 100 divided by 4 is?"}
    result_2 = router_node(general_state)
    print(f"Question: {general_state['query']}")
    print(f"LLM Decision: {result_2}  <-- Expected: out_of_scope\n")

if __name__ == "__main__":
    run_manual_test()