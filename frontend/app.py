'''
The entrypoint
'''
import streamlit as st
from utils import state

st.set_page_config(layout="wide")
state.init_session_state()

st.title("DocuQuery RAG Agent")

dashboard = st.Page(
    "pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True
)
documentation = st.Page("pages/manual.py", title="Quick Reference", icon=":material/quick_reference:")
analytics = st.Page("pages/analytics.py", title="Analytics", icon=":material/analytics:")

pg = st.navigation(
    {
    "Pages": [dashboard, analytics, documentation]
    }
)

pg.run()


