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
    p1_salary = st.number_input("P1: Annual salary (gross)", value=1200000.0, step=10000.0, format="%.2f")
    p1_growth = st.number_input("P1: Annual salary growth %", value=7.0, step=0.1) / 100.0
    p1_other = st.number_input("P1: Other annual income (rent etc.)", value=0.0, step=1000.0)

with st.sidebar.expander("Person 2 (Secondary)", expanded=True):
    p2_salary = st.number_input("P2: Annual salary (gross)", value=600000.0, step=10000.0, format="%.2f")
    p2_growth = st.number_input("P2: Annual salary growth %", value=5.0, step=0.1) / 100.0
    p2_other = st.number_input("P2: Other annual income (rent etc.)", value=0.0, step=1000.0)

st.sidebar.markdown("---")
# --- Expenses ---
st.sidebar.header("Expenses")
monthly_expenses = st.sidebar.number_input("Total monthly recurring expenses", value=60000.0, step=1000.0)
annual_irregular = st.sidebar.number_input("Total annual irregular expenses", value=200000.0, step=1000.0)
expense_growth_override = st.sidebar.checkbox("Use a separate expense growth rate (instead of inflation)")
if expense_growth_override:
    expense_growth = st.sidebar.number_input("Expense growth % per year", value=4.0, step=0.1) / 100.0
else:
    expense_growth = inflation

st.sidebar.markdown("---")
# --- Taxes ---
st.sidebar.header("Tax Settings")
salary_tax_rate = st.sidebar.number_input("Effective tax rate on salaries %", value=20.0, step=0.5) / 100.0
other_income_tax_rate = st.sidebar.number_input("Tax on other income %", value=10.0, step=0.5) / 100.0

st.sidebar.markdown("---")
# --- Investments: allow multiple predefined slots ---
st.sidebar.header("Investments (up to 6 slots)")
inv_slots = []
for i in range(1, 7):
    with st.sidebar.expander(f"Investment slot {i}", expanded=(i==1)):
        name = st.text_input(f"Name (slot {i})", value=("Equity" if i==1 else ""), key=f"name_{i}")
        principal = st.number_input(f"Initial principal (slot {i})", value=(1000000.0 if i==1 else 0.0), step=1000.0, key=f"principal_{i}")
        annual_contrib = st.number_input(f"Annual contribution (slot {i})", value=(120000.0 if i==1 else 0.0), step=1000.0, key=f"contrib_{i}")
        ret = st.number_input(f"Expected annual return % (slot {i})", value=(10.0 if i==1 else 7.0), step=0.1, key=f"ret_{i}")/100.0
        tax_on_returns = st.number_input(f"Tax on returns % (slot {i})", value=(10.0 if i==1 else 20.0), step=0.5, key=f"tax_{i}")/100.0
        reinvest = st.checkbox(f"Reinvest returns? (slot {i})", value=True if i==1 else False, key=f"reinvest_{i}")
        inv_slots.append({
            "name": name or f"Inv {i}",
            "principal": principal,
            "annual_contrib": annual_contrib,
            "ret": ret,
            "tax": tax_on_returns,
            "reinvest": reinvest
        })

st.sidebar.markdown("---")
# --- Simulation controls ---
st.sidebar.header("Simulation Controls")
start_savings = st.sidebar.number_input("Cash / savings on hand (start)", value=200000.0, step=1000.0)
rebalancing = st.sidebar.selectbox("When contributions are applied", ["start_of_year", "end_of_year"], index=0)

# --- Helper functions ---

def apply_return(balance, rate, freq="annual"):
    if freq == "monthly":
        return balance * ((1 + rate / 12) ** 12 - 1)
    return balance * rate

# Format number in Indian style
def inr_format(x):
    if x >= 1e7:
        return f'{x/1e7:,.2f} Cr'
    elif x >= 1e5:
        return f'{x/1e5:,.2f} L'
    else:
        return f'{x:,.0f}'

# --- Projection engine ---

years_list = list(range(start_year, start_year + years))
rows = []
inv_balances = [float(s['principal']) for s in inv_slots]
cash = float(start_savings)

for yi, year in enumerate(years_list):
    p1_inc = p1_salary * ((1 + p1_growth) ** yi) + p1_other * ((1 + p1_growth) ** yi)
    p2_inc = p2_salary * ((1 + p2_growth) ** yi) + p2_other * ((1 + p2_growth) ** yi)
    gross_income = p1_inc + p2_inc

    salary_tax = (p1_salary * ((1 + p1_growth) ** yi)) * salary_tax_rate + (p2_salary * ((1 + p2_growth) ** yi)) * salary_tax_rate
    other_income = p1_other * ((1 + p1_growth) ** yi) + p2_other * ((1 + p2_growth) ** yi)
    other_income_tax = other_income * other_income_tax_rate

    monthly = monthly_expenses * ((1 + expense_growth) ** yi)
    annual = annual_irregular * ((1 + expense_growth) ** yi)
    total_expenses = monthly * 12 + annual

    total_contrib = sum([s['annual_contrib'] * ((1 + 0) ** yi) for s in inv_slots])
    if rebalancing == 'start_of_year':
        cash -= total_contrib
        for i, s in enumerate(inv_slots):
            inv_balances[i] += s['annual_contrib']

    investment_income_before_tax = 0.0
    investment_tax_paid = 0.0
    for i, s in enumerate(inv_slots):
        bal = inv_balances[i]
        gain = apply_return(bal, s['ret'], freq=compounding)
        tax = gain * s['tax']
        if s['reinvest']:
            inv_balances[i] += (gain - tax)
        else:
            cash += (gain - tax)
        investment_income_before_tax += gain
        investment_tax_paid += tax

    if rebalancing == 'end_of_year':
        for i, s in enumerate(inv_slots):
            inv_balances[i] += s['annual_contrib']
        cash -= total_contrib

    taxes = salary_tax + other_income_tax + investment_tax_paid
    net_savings = gross_income - taxes - total_expenses
    cash += net_savings

    total_investment_value = sum(inv_balances)
    net_worth = cash + total_investment_value

    rows.append({
        'year': year,
        'gross_income': inr_format(gross_income),
        'salary_tax': inr_format(salary_tax),
        'other_income_tax': inr_format(other_income_tax),
        'investment_gain_before_tax': inr_format(investment_income_before_tax),
        'investment_tax_paid': inr_format(investment_tax_paid),
        'total_taxes': inr_format(taxes),
        'total_expenses': inr_format(total_expenses),
        'net_savings': inr_format(net_savings),
        'cash': inr_format(cash),
        'investment_value': inr_format(total_investment_value),
        'net_worth': inr_format(net_worth)
    })

results = pd.DataFrame(rows).set_index('year')

# --- Display outputs ---
st.subheader("Projection summary")
col1, col2 = st.columns([2, 1])
with col1:
    st.dataframe(results, height=400)
with col2:
    st.metric("Net worth (last year)", results['net_worth'].iloc[-1])
    st.metric("Investment value (last year)", results['investment_value'].iloc[-1])
    st.metric("Cash (last year)", results['cash'].iloc[-1])

st.subheader("Investment balances (final year)")
inv_df = pd.DataFrame({
    'name': [s['name'] for s in inv_slots],
    'balance': [inr_format(bal) for bal in inv_balances],
    'annual_contrib': [inr_format(s['annual_contrib']) for s in inv_slots],
    'return_%': [s['ret']*100 for s in inv_slots],
    'tax_%': [s['tax']*100 for s in inv_slots],
    'reinvest': [s['reinvest'] for s in inv_slots]
})
st.dataframe(inv_df)

@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='projection')
    writer.save()
    return output.getvalue()

excel_data = convert_df_to_excel(results.reset_index())
st.download_button(label="Download projection (Excel)", data=excel_data, file_name='cashflow_projection.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

st.markdown("---")
st.caption("Tip: tweak inputs in the left panel. This model is a starting point — for tax-accurate or legally binding planning consult a professional.")
