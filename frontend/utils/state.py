'''
Manages chat history key and other session keys
'''
import streamlit as st

def init_session_state():
    
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        st.session_state["messages"].append({
            "role": "assistant",
            "content": "Hi! I'm your technical assistant. Ask me what you need to find in the pdf."
        })

    if "pdf_uploaded" not in st.session_state:
        st.session_state["pdf_uploaded"] = False

    if "doc_count" not in st.session_state:
        st.session_state["doc_count"] = 0

