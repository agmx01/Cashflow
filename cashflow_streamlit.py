import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(layout="wide", page_title="2-Person Family Cashflow Projection")
st.title("Cash Flow Projection — 2-Person Family")
st.markdown("Enter incomes, expenses, investments and tax settings on the left. The app projects year-by-year cashflows and asset growth.")

# --- Sidebar inputs ---
st.sidebar.header("Projection Settings")
years = st.sidebar.number_input("Projection horizon (years)", min_value=1, max_value=80, value=30)
start_year = st.sidebar.number_input("Start year (e.g. 2025)", min_value=1900, max_value=2100, value=2025)
inflation = st.sidebar.number_input("Annual inflation (for expenses) %", value=4.0, step=0.1) / 100.0
compounding = st.sidebar.selectbox("Compounding frequency for returns", ["annual", "monthly"], index=0)

st.sidebar.markdown("---")
# --- Family incomes ---
st.sidebar.header("Incomes — Two People")
with st.sidebar.expander("Person 1 (Primary)", expanded=True):
    p1_salary = st.number_input("P1: Annual salary (gr
