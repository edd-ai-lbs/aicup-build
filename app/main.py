"""Edd.AI – app entry point: theme, logo and the tabs across the top. Run from the project folder with:
    python3 -m streamlit run app/main.py
Each tab is its own file: home.py, report.py (move-in report), pages/move_out.py, pages/checklist.py.
"""

from pathlib import Path

import streamlit as st

from ui import apply_theme

HERE = Path(__file__).parent

st.set_page_config(page_title="Edd.AI", page_icon=str(HERE / "assets" / "icon.svg"), layout="wide")
apply_theme()
st.logo(str(HERE / "assets" / "logo.svg"), icon_image=str(HERE / "assets" / "icon.svg"), size="large")

page = st.navigation(
    [
        st.Page("home.py", title="Home", default=True),
        st.Page("report.py", title="Move-in report"),
        st.Page("pages/move_out.py", title="Move-out check"),
        st.Page("pages/checklist.py", title="Admin checklist"),
    ],
    position="top",
)
page.run()
