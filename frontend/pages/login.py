import streamlit as st
import requests

st.header("Login")

username = st.text_input("Username")
password = st.text_input("Password", type="password")

if st.button("Login"):
    response = requests.post("http://api:8000/api/login", data={"username": username, "password": password})
    if response.status_code == 200:
        st.session_state["is_logged_in"] = response.json().get("access_token") 
        st.success("Login successful")
        st.rerun()
    else:
        st.error("Invalid username or password")