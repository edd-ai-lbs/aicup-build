"""Edd.AI homepage: what the app does and where to start."""

import streamlit as st

with st.container(key="hero"):
    st.markdown('<p class="edd-eyebrow">Edd.AI · Move-in co-pilot</p>', unsafe_allow_html=True)
    st.markdown("# Protect your deposit from day one.")
    st.markdown("Film each room, let AI spot the damage, and get a dated report for your landlord in minutes.")
    if st.button("Start my move-in report  →", key="start"):
        st.switch_page("move_in.py")

st.write("")
st.markdown("## How it works")
steps = [
    ("Film each room", "A one-minute clip per room. Say anything you notice out loud."),
    ("AI checks it", "Spots scratches, stains and broken fittings, with a photo of each."),
    ("Get your report", "A dated PDF to send your landlord as evidence on move-in day."),
]
for n, (col, (title, text)) in enumerate(zip(st.columns(3), steps), start=1):
    with col.container(key=f"how_{n}"):
        st.markdown(f'<span class="edd-num">{n}</span>', unsafe_allow_html=True)
        st.markdown(f"### {title}")
        st.write(text)

st.write("")
st.markdown("## Also in Edd.AI")
left, right = st.columns(2)
with left.container(key="tool_moveout"):
    st.markdown("### Move-out check")
    st.write("Compare your move-in and move-out videos room by room, before the deposit is decided.")
    st.page_link("pages/move_out.py", label="Open move-out check →")
with right.container(key="tool_checklist"):
    st.markdown("### Admin checklist")
    st.write("Deposit protection, council tax, TV licence and more – personalised, with GOV.UK links.")
    st.page_link("pages/checklist.py", label="Open checklist →")

st.divider()
st.caption("Based on GOV.UK and Shelter guidance · General guidance, not legal advice · "
           "For help, contact Shelter or Citizens Advice")
