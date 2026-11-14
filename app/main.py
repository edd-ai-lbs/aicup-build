"""Move-in Co-pilot – main screen. Run from the project folder with:
    python3 -m streamlit run app/main.py
"""

import re
import sys
import tempfile
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # so we can import from the report/ and pipeline/ folders
from pipeline.analyse import analyse_room  # noqa: E402  (Francesca's AI: video -> issues)
from pipeline.voice_note import add_voice_note  # noqa: E402  (Francesca's AI: voice note -> issues)
from report.make_report import make_pdf  # noqa: E402

ROOMS = ["Kitchen", "Living room", "Bedroom 1", "Bedroom 2", "Bathroom", "Hallway"]
SEVERITY = ["Minor", "Moderate", "Major"]
COLUMNS = ["room", "item", "issue", "severity", "frame_time_s", "responsibility", "note", "ai_check", "confirmed"]
RESPONSIBILITY = ["Landlord to repair", "Tenant to sort", "Not tenant's – cosmetic", "Unsure – ask landlord"]
FRAMES_DIR = Path(tempfile.gettempdir()) / "movein_frames"


def cap(text):
    """Capital first letter, rest unchanged ('tv stand' -> 'Tv stand', 'TV stand' stays)."""
    text = str(text).strip()
    return text[:1].upper() + text[1:]


def text_or_blank(value):
    """'' for missing values (the table turns empty cells into NaN)."""
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def ai_check(issue):
    """What the 'AI check' column shows: how sure the AI was about this issue."""
    confidence = text_or_blank(issue.get("confidence"))
    if confidence == "high":
        return "🟢 Sure"
    if confidence == "medium":
        reason = text_or_blank(issue.get("uncertainty_reason"))
        return f"🟠 Check: {reason}" if reason else "🟠 Check"
    return "Added by you"  # voice-note and hand-added rows have no AI confidence


def video_time(seconds):
    """32.0 -> '0:32'."""
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


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
st.sidebar.page_link("main.py", label="Move-in report", icon="🏠")
st.sidebar.page_link("pages/checklist.py", label="Admin checklist", icon="✅")
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
col_flat, col_street = st.columns([1, 3])
flat = col_flat.text_input("Flat number", key="flat", placeholder="e.g. Flat 4B")
street = col_street.text_input("Street address", key="street", placeholder="e.g. 12 Regent's Park Road")
col_city, col_postcode = st.columns([3, 1])
city = col_city.text_input("Town or city", key="city", value="London")
postcode = col_postcode.text_input("Postcode", key="postcode", placeholder="e.g. NW1 4SA").strip().upper()
if postcode and not re.fullmatch(r"[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}", postcode):
    st.warning("That doesn't look like a UK postcode. Please check it (e.g. NW1 4SA).")
property_address = ", ".join(part.strip() for part in [flat, street, city, postcode] if part.strip())

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
        try:
            with st.spinner("Looking for damage and listening to your comments – this takes about a minute..."):
                new_issues = analyse_room(f.name, room)
        except Exception as e:  # e.g. missing API key, no internet – show a message instead of crashing
            st.error(f"Sorry, the analysis didn't work: {e}. Please try again.")
            st.stop()
        st.session_state.videos[room] = f.name
        if room not in st.session_state.rooms:  # added here, not on typing, so the dropdown doesn't jump back
            st.session_state.rooms.append(room)
        for issue in new_issues:
            issue.setdefault("responsibility", guess_responsibility(issue))  # keep the AI's sourced answer
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
        pd.DataFrame([dict(i, ai_check=ai_check(i)) for i in st.session_state.issues]),
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
            "ai_check": st.column_config.TextColumn(
                "AI check", disabled=True, default="Added by you", width="medium",
                help="🟢 the AI is sure. 🟠 have a quick look yourself – it says what to check.",
            ),
            "confirmed": st.column_config.CheckboxColumn("Confirmed", default=True),
        },
    )
    st.session_state.edited = edited.to_dict("records")

    # Rewatch: play a room's video from the moment an issue was seen
    with_time = [
        i for i in st.session_state.edited
        if i.get("room") in st.session_state.videos and pd.notna(i.get("frame_time_s"))
    ]
    if with_time:
        st.subheader("Rewatch an issue")
        n = st.selectbox(
            "Pick an issue to see it in your video",
            range(len(with_time)),
            format_func=lambda n: f"{with_time[n]['room']} – {text_or_blank(with_time[n].get('item'))} "
                                  f"({video_time(with_time[n]['frame_time_s'])})",
        )
        pick = with_time[n]
        # Fixed width so upright phone videos don't fill the whole screen
        st.video(st.session_state.videos[pick["room"]], start_time=int(pick["frame_time_s"]), width=400)

    # Forgot something? Add it with a voice note
    st.subheader("Forgot something?")
    st.caption("Record a short voice note, e.g. \"In the bathroom the hot tap drips\". "
               "New problems are added to the list; comments on ones already there go in their note.")
    voice = st.audio_input("Record a voice note", key=f"voice_{st.session_state.version}")
    if voice and st.button("Add to report"):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(voice.getbuffer())
        try:
            with st.spinner("Listening to your note..."):
                current = st.session_state.edited
                updated, said = add_voice_note(f.name, current, st.session_state.rooms)
        except Exception as e:  # e.g. missing API key, no internet
            st.error(f"Sorry, the voice note didn't work: {e}. Please try again.")
            st.stop()
        for issue in updated[len(current):]:  # only the new rows
            issue.setdefault("responsibility", guess_responsibility(issue))  # voice notes have no AI answer yet
            for field in ["item", "issue", "severity"]:
                issue[field] = cap(issue.get(field, ""))
        st.session_state.issues = updated
        st.session_state.last_note = said
        st.session_state.version += 1
        st.rerun()
    if st.session_state.get("last_note"):
        st.success(f"Added from your note: \"{st.session_state.last_note}\"")

    # Why? Sources – who sorts each issue, and where that rule comes from (not included in the report)
    with st.expander("Why? Sources – who sorts each issue (for your information, not in the report)"):
        lines, sources = [], {}
        for i in st.session_state.edited:
            if i.get("confirmed") != True:  # noqa: E712 (also works for the table's numpy True)
                continue
            who = text_or_blank(i.get("responsibility")) or "Not set"
            reason = text_or_blank(i.get("responsibility_reason"))
            source, url = text_or_blank(i.get("responsibility_source")), text_or_blank(i.get("responsibility_url"))
            line = f"- **{text_or_blank(i.get('item')) or 'Item'}** → {who}"
            if reason and source and url:
                line += f": {reason} [{source}]({url})"
                sources[source] = url
            else:
                line += " _(the app's own guess – check with your landlord)_"
            lines.append(line)
        st.markdown("\n".join(lines) or "No confirmed issues yet.")
        if sources:
            st.markdown("**Sources used:**\n" + "\n".join(f"- [{s}]({u})" for s, u in sources.items()))
        st.caption(
            "You can change 'Who sorts it?' in the table if it's wrong. General guidance, not legal advice. "
            "For help: [Shelter – housing advice](https://england.shelter.org.uk/housing_advice) · "
            "[Citizens Advice – renting privately](https://www.citizensadvice.org.uk/housing/renting-privately/)"
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
