import streamlit as st

st.title("Quick Reference: DocuQuery RAG")

st.markdown("""
Welcome to the DocuQuery system. This guide provides instructions on how to set up 
and utilize your Agentic RAG system for efficient analysis of technical manuals.
""")

tab1, tab2, tab3 = st.tabs(["Getting Started", "How it Works", "Troubleshooting"])

with tab1:
    st.header("Quick Start Guide")
    st.write("1. **Upload Documents:** Navigate to the Dashboard and use the sidebar to select your PDFs.")
    st.write("2. **Ingestion:** Upload your files and click 'Upload and process'. Wait for the status indicator to turn to 'Ready'.")
    st.write("3. **Chat:** Once the agent is ready, start asking questions directly in the chat interface.")

with tab2:
    st.header("System Architecture")
    st.write("The system leverages an advanced agentic workflow to provide accurate, context-aware answers:")
        
    
    
    st.write("- **Retrieval:** Fetches relevant document chunks from the Vector Database.")
    st.write("- **Memory:** Maintains conversation state using LangGraph to handle follow-up questions.")
    st.write("- **Generation:** Uses the LLM to synthesize answers based solely on the provided context.")

with tab3:
    st.header("Troubleshooting")
    st.info("If the agent is unresponsive, ensure that the API backend container is running.")
    st.warning("If the answer is inaccurate, verify that your PDFs contain high-quality technical text and try refining your query.")
    st.error("If you encounter a 'Connection error', check your Docker network configuration.")