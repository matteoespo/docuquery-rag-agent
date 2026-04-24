'''
chat interface
'''

import streamlit as st

def render_chat_window():
    prompt = st.chat_input("Ask something")

    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            st.write("Here the LLM answer")
