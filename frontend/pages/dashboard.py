import streamlit as st
from components import uploadingbar, chat
import time

left, right = st.columns([1,3])
with left:
    uploadingbar.render_uploadingbar()
with right:
    chat.render_chat_window()