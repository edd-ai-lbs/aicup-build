"""Move-in Co-pilot – main screen. Run from the project folder with:
    python3 -m streamlit run app/main.py
"""

import json
import sys
import tempfile
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # so we can import from the report/ folder
from report.make_report import make_pdf  # noqa: E402

ROOMS = ["Kitchen", "Living room", "Bedroom 1", "Bedroom 2", "Bathroom", "Hallway"]
SEVERITY = ["Minor", "Moderate", "Major"]
COLUMNS = ["room", "item", "issue", "severity", "frame_time_s", "responsibility", "note", "confirmed"]
RESPONSIBILITY = ["Landlord to repair", "Tenant to sort", "Not tenant's – cosmetic", "Unsure – ask landlord"]
FRAMES_DIR = Path(tempfile.gettempdir()) / "movein_frames"


def cap(text):
    """Capital first letter, rest unchanged ('tv stand' -> 'Tv stand', 'TV stand' stays)."""
    text = str(text).strip()
    return text[:1].upper() + text[1:]


def analyse_room(video_path, room):
    # PLACEHOLDER until Francesca's pipeline is ready: returns made-up issues,
    # spread evenly across the video so each one has a photo.
    # Later this becomes: from pipeline.<module> import analyse_room
    issues = json.loads((ROOT / "app" / "sample_issues.json").read_text())
    cap_ = cv2.VideoCapture(video_path)
    fps, frames = cap_.get(cv2.CAP_PROP_FPS), cap_.get(cv2.CAP_PROP_FRAME_COUNT)
    cap_.release()
    duration = frames / fps if fps > 0 and frames > 0 else 0
    for n, issue in enumerate(issues, start=1):
        issue["room"] = room
        if duration:
            issue["frame_time_s"] = round(duration * n / (len(issues) + 1), 1)
    return issues


def guess_responsibility(issue):
    """First guess for the app screen only (not printed in the report). The user can change it."""
    text = f"{issue.get('item', '')} {issue.get('issue', '')}".lower()
    if any(w in text for w in ["bulb", "shower curtain", "batter", "missing"]):
        return "Tenant to sort"
    if str(issue.get("severity")).lower() == "major" or any(
        w in text for w in ["boiler", "heating", "tap", "leak", "water", "socket", "electric", "damp", "mould", "toilet"]
    ):
        return "Landlord to repair"
    return "Not tenant's – cosmetic"


@st.cache_data
def grab_frame(video_path, seconds):
    """Save the video frame at `seconds` as a JPG and return its path ('' if it can't)."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, float(seconds) * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return ""
    FRAMES_DIR.mkdir(exist_ok=True)
    path = FRAMES_DIR / f"{Path(video_path).stem}_{int(seconds):04d}.jpg"
    cv2.imwrite(str(path), frame)
    return str(path)


def add_frames(issues):
    """Give each issue a photo from its room's video, unless it already has one."""
    for issue in issues:
        has_frame = issue.get("frame_path") and Path(str(issue["frame_path"])).exists()
        video_path = st.session_state.videos.get(issue.get("room"))
        if not has_frame and video_path and pd.notna(issue.get("frame_time_s")):
            issue["frame_path"] = grab_frame(video_path, issue["frame_time_s"])
    return issues


st.set_page_config(page_title="Move-in Co-pilot", page_icon="🏠", layout="wide")
st.title("Move-in Co-pilot")
st.write("Film each room, check what the AI found, and download a dated report for your landlord.")

if "issues" not in st.session_state:
    st.session_state.issues = []   # the list shown in the table
    st.session_state.version = 0   # bumped when new issues arrive, so the table refreshes
    st.session_state.videos = {}   # room -> saved video file, used for the report photos
    st.session_state.rooms = list(ROOMS)  # grows when the user types a new room name

# 1. Your details
st.header("1. Your details")
tenant_name = st.text_input("Your name")
property_address = st.text_input("Property address")

# 2. Upload a room video – repeat for every room; each one adds to the list below
st.header("2. Film a room")
st.write("Do this once per room. Each room's issues are added to the list below, so the report covers the whole flat.")
done = st.session_state.videos.keys()
if done:
    st.success("Rooms done so far: " + ", ".join(done))
room = st.selectbox(
    "Which room?", st.session_state.rooms, accept_new_options=True,
    help="Pick a room, or type a new name (e.g. 'Bedroom 3') and press Enter.",
)
room = cap(room or "")
video = st.file_uploader("Upload the video", type=["mp4", "mov", "m4v"], key=f"upload_{st.session_state.version}")
if video and room:
    st.video(video)
    if st.button(f"Find issues in: {room}", type="primary"):
        with tempfile.NamedTemporaryFile(suffix=Path(video.name).suffix, delete=False) as f:
            f.write(video.getbuffer())
        with st.spinner("Looking for damage..."):
            new_issues = analyse_room(f.name, room)
        st.session_state.videos[room] = f.name
        if room not in st.session_state.rooms:  # added here, not on typing, so the dropdown doesn't jump back
            st.session_state.rooms.append(room)
        for issue in new_issues:
            issue["responsibility"] = guess_responsibility(issue)
            issue["room"] = room
            for field in ["item", "issue", "severity"]:
                issue[field] = cap(issue.get(field, ""))
        # Keep your edits for other rooms; replace any earlier results for this room.
        current = st.session_state.get("edited", st.session_state.issues)
        st.session_state.issues = [i for i in current if i.get("room") != room] + new_issues
        st.session_state.version += 1
        st.rerun()

# 3. Check and edit the issues
st.header("3. Check the issues")
if not st.session_state.issues:
    st.info("Upload a room video above to see what the AI finds.")
else:
    st.caption("Click a cell to edit it. Untick 'Confirmed' to leave an issue out. Add or delete rows at the bottom.")
    edited = st.data_editor(
        pd.DataFrame(st.session_state.issues),
        key=f"editor_{st.session_state.version}",
        num_rows="dynamic",
        hide_index=True,
        column_order=COLUMNS,
        column_config={
            "room": st.column_config.SelectboxColumn("Room", options=st.session_state.rooms),
            "item": "Item",
            "issue": "Issue",
            "severity": st.column_config.SelectboxColumn("Severity", options=SEVERITY),
            "frame_time_s": st.column_config.NumberColumn("Time in video (s)", format="%.0f"),
            "responsibility": st.column_config.SelectboxColumn("Who sorts it?", options=RESPONSIBILITY),
            "note": "Your note",
            "confirmed": st.column_config.CheckboxColumn("Confirmed", default=True),
        },
    )
    st.session_state.edited = edited.to_dict("records")

    with st.expander("Who sorts what? (for your information – not included in the report)"):
        st.markdown(
            "- **Landlord to repair:** heating, hot water, plumbing, electrics, damp and the structure of the home.\n"
            "- **Tenant to sort:** small everyday items like lightbulbs, a shower curtain or batteries.\n"
            "- **Not tenant's – cosmetic:** scratches, marks, wear. The landlord may not fix them, "
            "but because they're in your move-in report you shouldn't be charged for them later.\n\n"
            "The 'Who sorts it?' column is a first guess – change it if it's wrong. General guidance, not legal advice: "
            "see [GOV.UK – private renting repairs](https://www.gov.uk/private-renting/repairs) and "
            "[Shelter – repairs](https://england.shelter.org.uk/housing_advice/repairs)."
        )

    # 4. Download the report
    st.header("4. Download your report")
    st.caption("Each issue in the report includes a photo taken from your video at that moment.")
    st.download_button(
        "Download PDF report",
        data=make_pdf(add_frames(st.session_state.edited), tenant_name, property_address),
        file_name="move-in-report.pdf",
        mime="application/pdf",
        type="primary",
    )

st.caption("General guidance, not legal advice. See GOV.UK, Shelter or Citizens Advice for help with deposits.")
