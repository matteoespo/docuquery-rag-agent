import streamlit as st
import requests
import json

def fetch_stream(prompt, history):
    '''Fetch streaming response from the backend API and yield tokens one by one.'''
    try:
        response = requests.post(
            url="http://api:8000/api/chat/stream",
            json={"query": prompt, "chat_history": history},
            stream=True,
            timeout=300
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        token = data.get("token", "")
                        if token and token != "[stream completed]":
                            # Yield tokens one by one instead of appending to a string
                            yield token 
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        yield f"Connection error: {e}"


@st.fragment
def render_chat_window():
    '''Renders the chat interface and handles user input and streaming responses.'''
    # Initialize history if it doesn't exist
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    chat_box = st.container(border=True, height=600)

    with chat_box:
        for message in st.session_state["messages"]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    if prompt := st.chat_input("Ask something"):
        
        # Append user message to history
        st.session_state["messages"].append({"role": "user", "content": prompt})
        
        with chat_box:
            # Show user message
            with st.chat_message("user"):
                st.write(prompt)
            
            # Stream assistant response
            with st.chat_message("assistant"):
                # Create the generator
                stream_generator = fetch_stream(prompt, st.session_state["messages"][:-1])
                
                # Use the spinner ONLY while waiting for the first token
                with st.spinner("Thinking..."):
                    try:
                        first_token = next(stream_generator)
                    except StopIteration:
                        first_token = None
                
                # If we successfully got a first token, stream the rest
                if first_token:
                    def combined_stream():
                        yield first_token
                        yield from stream_generator
                    
                    # Streamlit consumes the combined generator without a spinner
                    full_response = st.write_stream(combined_stream())
                    
                    # Save the final response to history
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": full_response
                    })
                    st.rerun()
                else:
                    st.error("The model didn't return any tokens.")