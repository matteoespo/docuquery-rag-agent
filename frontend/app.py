'''
The entrypoint
'''
import streamlit as st
from utils import state

st.set_page_config(layout="wide")
state.init_session_state()

st.title("DocuQuery RAG Agent")

# If NOT logged in, only show login page
if not st.session_state.get("is_logged_in", False):
    login = st.Page("pages/login.py", title="Login", icon=":material/login:", default=True)
    pg = st.navigation([login])
else:
    # If logged in, show all pages with logout option
    dashboard = st.Page("pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True)
    documentation = st.Page("pages/manual.py", title="Quick Reference", icon=":material/quick_reference:")
    analytics = st.Page("pages/analytics.py", title="Analytics", icon=":material/analytics:")
    
    # Logout button in sidebar
    if st.sidebar.button("Logout"):
        st.session_state["is_logged_in"] = False
        st.rerun()
    
    pg = st.navigation({
        "Pages": [dashboard, analytics, documentation]
    })

pg.run()


