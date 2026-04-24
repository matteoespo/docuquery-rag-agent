'''
file upload
'''
import streamlit as st
import time

def render_uploadingbar():
    with st.container(border=True):

        st.file_uploader("Load the PDF file")
        '''
        with st.spinner("Wait until the file is processed...", show_time=True):
            time.sleep(5)
            #here add a dynamic circular loading and then write done when finished
        st.success("Manual processed successfully")
        st.error("Uploading or processing failed. Retry!")
        '''