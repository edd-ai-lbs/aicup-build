"""Admin checklist page: a personal move-in to-do list with GOV.UK links.
Content and rules come from content/checklist.json (Francesca)."""

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[2]))  # project folder, so we can import content/
from content.checklist import CHECKLIST, checklist_for  # noqa: E402

st.set_page_config(page_title="Admin checklist", page_icon="✅")
st.sidebar.page_link("main.py", label="Move-in report", icon="🏠")
st.sidebar.page_link("pages/checklist.py", label="Admin checklist", icon="✅")

st.title("Move-in admin checklist")
st.write("Your personal to-do list for the first weeks in a UK rental.")
st.caption(CHECKLIST["applies_to"])

# 1. A few questions to personalise the list. "Not sure" keeps the item on the list, to be safe.
st.header("A few quick questions")
answers = {}
for q in CHECKLIST["questions"]:
    choice = st.radio(q["question"], ["Not sure", "Yes", "No"], horizontal=True, help=q.get("help"), key=q["id"])
    if choice != "Not sure":
        answers[q["id"]] = choice == "Yes"

# 2. The to-dos that apply, each with a tick box
items = checklist_for(answers)
st.header("Your to-dos")
done = sum(st.session_state.get(f"done_{item['id']}", False) for item in items)
st.progress(done / len(items), text=f"{done} of {len(items)} done")

for item in items:
    ticked = st.session_state.get(f"done_{item['id']}", False)
    with st.expander(f"{'✅ ' if ticked else ''}**{item['title']}** – {item['when']}"):
        st.write(item["why"])
        st.markdown("\n".join(f"- {step}" for step in item["steps"]))
        st.markdown("  \n".join(f"🔗 [{link['label']}]({link['url']})" for link in item["links"]))
        st.checkbox("Done", key=f"done_{item['id']}")

# 3. Disclaimer and where to get help
st.divider()
st.caption(CHECKLIST["disclaimer"])
st.caption("Need help? " + " · ".join(f"[{l['label']}]({l['url']})" for l in CHECKLIST["help_links"]))
st.caption(f"Content checked on {CHECKLIST['checked_on']}.")
