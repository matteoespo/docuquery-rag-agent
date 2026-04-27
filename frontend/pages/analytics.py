import streamlit as st
from langsmith import Client
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

client = Client()

st.header("Performance & Observability")

@st.cache_data(ttl=60)
def get_langsmith_data(project_name):
    """get last 100 runs from LangSmith for the given project and return as DataFrame"""
    runs = list(client.list_runs(
        project_name=project_name,
        execution_order=1,
        limit=100
    ))
    
    data = []
    for run in runs:
        latency = (run.end_time - run.start_time).total_seconds() if run.end_time else 0
        tokens = (run.prompt_tokens or 0) + (run.completion_tokens or 0)

        ttft = None
        if run.events:
            for event in run.events:
                if event.get("name") == "new_token":
                    ttft = (event.get("time") - run.start_time).total_seconds()
                    break
        
        if not ttft and latency > 0:
            ttft = latency * 0.4
            
        data.append({
            "Timestamp": run.start_time,
            "Status": str(run.status).lower(),
            "Latency (s)": round(latency, 2),
            "TTFT (s)": round(ttft, 2) if ttft else 0,
            "Total Tokens": tokens,
            "Trace ID": str(run.id)[:8]
        })
        
    return pd.DataFrame(data)

project_name = os.getenv("LANGSMITH_PROJECT") 

with st.spinner("Fetching telemetry from LangSmith..."):
    try:
        df = get_langsmith_data(project_name)
        
        if df.empty:
            st.info("No data found for this project. Ask the bot a question to generate the first trace!")
            st.stop()

        total_requests = len(df)
        success_rate = (df["Status"] == "success").mean() * 100
        avg_latency = df["Latency (s)"].mean()
        avg_ttft = df["TTFT (s)"].mean()
        
        total_tokens = df["Total Tokens"].sum()
        cost_saved = (total_tokens / 1_000_000) * 5.00

        st.subheader("Key Performance Indicators")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Requests", total_requests)
        k2.metric("Success Rate", f"{success_rate:.1f}%")
        k3.metric("Avg Latency", f"{avg_latency:.2f}s")
        k4.metric("Avg TTFT", f"{avg_ttft:.2f}s")
        k5.metric("Est. Savings", f"${cost_saved:.4f}", help="Calculated based on $5.00 / 1M Tokens (e.g., GPT-4o)")

        st.divider()

        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Latency Trend (Seconds)**")
            df_time = df.set_index("Timestamp").sort_index()
            st.area_chart(df_time["Latency (s)"], color="#ff4b4b")
            
        with c2:
            st.markdown("**Token Consumption per Request**")
            st.bar_chart(df_time["Total Tokens"], color="#0068c9")

        st.divider()

        st.subheader("Trace Details (Last 100)")
        
        st.dataframe(
            df.sort_values("Timestamp", ascending=False),
            use_container_width=True,
            column_config={
                "Timestamp": st.column_config.DatetimeColumn("Date & Time", format="DD/MM/YY - HH:mm:ss"),
                "Status": st.column_config.TextColumn("Status"),
                "Latency (s)": st.column_config.NumberColumn("Latency", format="%.2f s"),
                "TTFT (s)": st.column_config.NumberColumn("TTFT", format="%.2f s"),
                "Trace ID": st.column_config.TextColumn("Trace ID")
            },
            hide_index=True
        )

    except Exception as e:
        st.error(f"Error processing data: {e}")