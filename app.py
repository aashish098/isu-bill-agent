"""Streamlit demo UI for the IS-U Bill Anomaly Explainer.

Run:  streamlit run app.py
"""
import json

import pandas as pd
import streamlit as st

from isu_agent import config
from isu_agent.agent import BillAgent
from isu_agent.repository import get_repository

st.set_page_config(page_title="IS-U Bill Explainer", page_icon="⚡", layout="wide")


@st.cache_resource
def repo():
    return get_repository()


@st.cache_data
def demo_accounts():
    return json.loads(config.GROUND_TRUTH_PATH.read_text())


r = repo()
st.title("⚡ SAP IS-U Bill Anomaly Explainer")
st.caption(f"Data source: {config.DATA_SOURCE} · Agent mode: {config.LLM_PROVIDER}"
           + (f" ({config.LLM_MODEL})" if config.LLM_PROVIDER != "offline" else ""))

accounts = demo_accounts()
labels = {f'{a["vkont"]} - {a["name"]}': a for a in accounts}
with st.sidebar:
    st.header("Customer")
    choice = st.selectbox("Contract account", list(labels))
    sel = labels[choice]
    show_truth = st.toggle("Show planted scenario (demo only)", value=False)
    if show_truth:
        st.info(sel["scenario"])

vkont = sel["vkont"]
acc = r.account(vkont)
docs = r.billing_documents(vkont)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Business partner", acc["partner"])
c2.metric("Installation", acc["anlage"])
c3.metric("Rate category", acc["tariftyp"])
c4.metric("Billing documents", len(docs))

df = pd.DataFrame(docs)
df["period_end"] = pd.to_datetime(df["abrdate"])
df["days"] = (pd.to_datetime(df["abrdate"]) - pd.to_datetime(df["abrdats"])).dt.days
df["kwh_per_day"] = (df["kwh"] / df["days"]).round(2)
valid = df[df["stokz"] != "X"]

left, right = st.columns([3, 2])
with left:
    st.subheader("Consumption per day (valid bills)")
    st.bar_chart(valid.set_index("period_end")["kwh_per_day"], height=240)
with right:
    st.subheader("Recent billing documents")
    st.dataframe(df[["belnr", "abrdats", "abrdate", "kwh", "gross_amount", "stokz"]].tail(6),
                 hide_index=True, width="stretch")

st.divider()
question = st.text_input("Ask about this customer's bill", value=sel["question"])
belnr = st.selectbox("Billing document (optional)", ["latest"] + list(valid["belnr"][::-1]))

if st.button("Explain bill", type="primary"):
    with st.spinner("Reading IS-U data and analysing..."):
        res = BillAgent(r).ask(question, vkont, None if belnr == "latest" else belnr)
    st.session_state["result"] = res

res = st.session_state.get("result")
if res:
    st.markdown(res.answer)
    for i, case in enumerate(res.proposed_cases):
        with st.container(border=True):
            st.markdown(f'**Proposed clarification case** · `{case["category"]}` · document `{case["belnr"]}`')
            st.write(case["summary"])
            if st.button("Approve and create case", key=f"approve{i}"):
                case_id = r.create_clarification_case(case["vkont"], case["belnr"], case["category"], case["summary"])
                st.success(f"Clarification case {case_id} created.")
    with st.expander("Agent trace (tools called)"):
        st.caption(f"Mode: {res.mode}")
        for c in res.tool_calls:
            st.code(f'{c["tool"]}({json.dumps(c["input"], default=str)})', language="python")
        if res.analysis:
            st.json(res.analysis, expanded=False)
