'''
chat interface
'''
import streamlit as st
import requests

@st.fragment
def render_chat_window():
    history = st.session_state["messages"]
    chat_box = st.container(border=True, height=600)

    with chat_box:
        for message in history:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    prompt = st.chat_input("Ask something")
    if prompt:
        st.session_state["messages"].append({
                "role": "user",
                "content": prompt
            })
        with chat_box:
            with st.chat_message("user"):
                st.write(prompt)
            with st.chat_message("assistant"):
                with st.spinner("I'm thinking..."):
                    try:
                        response = requests.post(url="http://api:8000/api/chat", json={"query": prompt, "chat_history": history})
                        if response.status_code == 200:
                            content = response.json()
                            st.session_state["messages"].append({
                                "role": "assistant",
                                "content": content["answer"]
                            })
                            #st.error(f"Status: {response.status_code}")
                            #st.error(f"Text: {response.text}")
                        else:
                            st.error(f"Chat failed with error: {response.status_code}. Retry!")
                        
                        
                    except Exception as e:
                        st.error(f"Connection error: {e}")
            
        
        st.rerun()

