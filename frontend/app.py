'''
The entrypoint
'''
import streamlit as st
import requests
from utils import state

st.set_page_config(layout="wide")

titleclmn, statusclmn, memoryclmn, historyclmn = st.columns([3,1,1,1])
with titleclmn:
    with st.container(horizontal_alignment="center"):
        st.title("DocuQuery RAG Agent")
with statusclmn:
    st.write("**Status**")
    st.write("...")
with memoryclmn:
    st.write("**Memory**")
    st.write("...")
with historyclmn:
    st.write("**History**")
    st.write("...")
    

state.init_session_state()

dashboard = st.Page(
    "pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True
)
documentation = st.Page("pages/manual.py", title="Quick Reference", icon=":material/quick_reference:")


pg = st.navigation(
    {
    "Pages": [dashboard, documentation]
    }
)

pg.run()


