"""Edd.AI – app entry point: theme, logo and the tabs across the top. Run from the project folder with:
    python3 -m streamlit run app/main.py
Each tab is its own file: home.py, move_in.py (move-in report), pages/move_out.py, pages/checklist.py.
"""

from pathlib import Path

import streamlit as st

from ui import apply_theme

HERE = Path(__file__).parent

st.set_page_config(page_title="Edd.AI", page_icon=str(HERE / "assets" / "icon.svg"), layout="wide")
apply_theme()
st.logo(str(HERE / "assets" / "logo.svg"), size="large")

pages = [
    st.Page("home.py", title="Home", default=True),
    st.Page("move_in.py", title="Move-in report"),
    st.Page("pages/move_out.py", title="Move-out check"),
    st.Page("pages/checklist.py", title="Admin checklist"),
]
page = st.navigation(pages, position="top")

# On phones the tabs above fold into a small "»" menu, so show a row of tab buttons too (hidden on computers, see ui.py).
with st.container(key="mobile_nav"):
    for col, p, label in zip(st.columns(4), pages, ["Home", "Move-in", "Move-out", "Checklist"]):
        if p.url_path == page.url_path:
            col.markdown(f'<div class="edd-tab-current">{label}</div>', unsafe_allow_html=True)
        else:
            col.page_link(p, label=label)
page.run()
