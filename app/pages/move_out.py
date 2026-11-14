"""Move-out check page: compare a room's move-in and move-out videos (before/after).
The comparison itself is Francesca's pipeline/moveout.py."""

import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[2]))  # project folder, so we can import pipeline/
from pipeline.moveout import compare_room_videos  # noqa: E402
from report.moveout_report import make_moveout_pdf  # noqa: E402
from ui import box_of, outlined  # noqa: E402  (app/ui.py: draws the AI's box on a photo)

DEFAULT_ROOMS = ["Kitchen", "Living room", "Bedroom 1", "Bedroom 2", "Bathroom", "Hallway"]  # same as the move-in page
VIDEO_TYPES = ["mp4", "mov", "m4v"]



def video_time(seconds):
    """14.0 -> '0:14'."""
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def save_upload(upload):
    """Save an uploaded video to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(suffix=Path(upload.name).suffix, delete=False) as f:
        f.write(upload.getbuffer())
    return f.name


st.title("Move-out check")
st.write("Moving out? Film each room again. We'll compare it with your move-in video, show what to fix "
         "before you leave, and give you before/after proof for your deposit.")

# Pick the room and the two videos
videos = st.session_state.get("videos", {})  # move-in videos analysed on the move-in page this session
room = st.selectbox("Which room?", st.session_state.get("rooms", DEFAULT_ROOMS))
use_session_video = room in videos and st.checkbox("Use the move-in video from this session", value=True)
move_in_upload = None if use_session_video else st.file_uploader(
    "Move-in video", type=VIDEO_TYPES, key=f"move_in_{room}")
move_out_upload = st.file_uploader("Move-out video", type=VIDEO_TYPES, key=f"move_out_{room}")

if (use_session_video or move_in_upload) and move_out_upload and st.button("Compare", type="primary"):
    move_in_path = videos[room] if use_session_video else save_upload(move_in_upload)
    move_out_path = save_upload(move_out_upload)
    try:
        with st.spinner("Comparing before and after, about 30 seconds..."):
            result = compare_room_videos(
                move_in_path, move_out_path, room,
                move_in_issues=[i for i in st.session_state.get("edited", []) if i.get("room") == room],
            )
    except Exception as e:  # e.g. missing API key, no internet, unreadable video
        st.error(f"Sorry, the comparison didn't work: {e}. Please try again.")
        st.stop()
    st.session_state.setdefault("moveout", {})[room] = result

# Results for the selected room
result = st.session_state.get("moveout", {}).get(room)
if result:
    st.info(result["summary"])

    todo = [f for f in result["findings"] if f.get("fix_before_leaving")]
    if todo:
        st.subheader("To do before you leave")
        for n, f in enumerate(todo):
            st.checkbox(f"**{f['item']}**: {f['description']}", key=f"todo_{room}_{n}")

    groups = [
        ("new_damage", "🔴 New since move-in"),
        ("cleaning_needed", "🧽 Clean before you leave"),
        ("already_recorded", "🛡️ Already there at move-in (you shouldn't pay for these)"),
        ("fixed", "✅ Fixed"),
    ]
    for status, title in groups:
        found = [f for f in result["findings"] if f["status"] == status]
        if not found:
            continue
        st.subheader(f"{title} ({len(found)})")
        for f in found:
            with st.container(border=True):
                st.markdown(f"**{f['item']}**")
                st.write(f["description"])
                before_col, after_col = st.columns(2)
                if f.get("before_path"):
                    before_col.image(outlined(f["before_path"], box_of({"box": f.get("before_box")})), width=220, caption=f"Move-in {video_time(f['before_time_s'])}")
                if f.get("after_path"):
                    after_col.image(outlined(f["after_path"], box_of({"box": f.get("after_box")})), width=220, caption=f"Move-out {video_time(f['after_time_s'])}")
                ai_check = "🟢 Sure" if f.get("confidence") == "high" else f"🟠 Check: {f.get('uncertainty_reason') or 'have a look yourself'}"
                st.markdown(
                    f"**AI check:** {ai_check}  \n"
                    f"**Who sorts it?** {f['responsibility']} – {f['responsibility_reason']} "
                    f"[{f['responsibility_source']}]({f['responsibility_url']})"
                )

# PDF of every room compared so far
all_results = st.session_state.get("moveout", {})
if all_results:
    st.divider()
    st.subheader("Your move-out report")
    st.caption(f"Before/after photos for every finding. Rooms compared: {', '.join(all_results)}.")
    st.download_button("Download move-out report (PDF)", data=make_moveout_pdf({  # same outlines as on screen
                           room: dict(r, findings=[dict(
                               f, before_path=outlined(f.get("before_path") or "", box_of({"box": f.get("before_box")})),
                               after_path=outlined(f.get("after_path") or "", box_of({"box": f.get("after_box")})))
                               for f in r["findings"]]) for room, r in all_results.items()}),
                       file_name="move-out-report.pdf", mime="application/pdf", type="primary")

st.divider()
st.caption("General guidance, not legal advice. For help with deposits: "
           "[Shelter – housing advice](https://england.shelter.org.uk/housing_advice) · "
           "[Citizens Advice – renting privately](https://www.citizensadvice.org.uk/housing/renting-privately/)")
