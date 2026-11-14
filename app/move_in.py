"""Edd.AI – move-in report tab (opened from app/main.py, which runs the whole app)."""

import re
from urllib.parse import quote
import sys
import tempfile
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # so we can import from the report/ and pipeline/ folders
sys.path.append(str(ROOT / "app"))  # and app/ui.py
from pipeline.analyse import analyse_room  # noqa: E402  (Francesca's AI: video -> issues)
from pipeline.voice_note import add_voice_note  # noqa: E402  (Francesca's AI: voice note -> issues)
from pipeline.landlord_email import write_email  # noqa: E402
from pipeline.inventory import compare_inventory  # noqa: E402  (Francesca's AI: agency inventory vs videos)
from report.make_report import make_pdf  # noqa: E402
from ui import badges, step_bar  # noqa: E402  (app/ui.py: Edd.AI theme helpers)

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


@st.cache_data
def outlined(photo, box):
    """Copy of the photo with the problem outlined in Edd.AI green; the photo itself if there's no box."""
    image = cv2.imread(photo)
    if image is None or not box:
        return photo
    h, w = image.shape[:2]
    pad = 0.02  # a little room around the damage
    x0, y0 = int(max(0, box[0] - pad) * w), int(max(0, box[1] - pad) * h)
    x1, y1 = int(min(1, box[2] + pad) * w), int(min(1, box[3] + pad) * h)
    thick = max(3, w // 160)
    cv2.rectangle(image, (x0, y0), (x1, y1), (153, 211, 52), thick + 4)  # mint halo (BGR)
    cv2.rectangle(image, (x0, y0), (x1, y1), (87, 120, 4), thick)        # emerald line
    FRAMES_DIR.mkdir(exist_ok=True)
    out = FRAMES_DIR / f"{Path(photo).stem}_box_{abs(hash(tuple(box)))}.jpg"
    cv2.imwrite(str(out), image)
    return str(out)


def box_of(issue):
    """The issue's box as a tuple of 4 numbers, or None (missing, empty or broken by the table)."""
    box = issue.get("box")
    try:
        box = tuple(float(v) for v in box)
    except (TypeError, ValueError):
        return None
    return box if len(box) == 4 and box[2] > box[0] and box[3] > box[1] else None


def add_frames(issues):
    """Give each issue a photo from its room's video, unless it already has one."""
    for issue in issues:
        has_frame = issue.get("frame_path") and Path(str(issue["frame_path"])).exists()
        video_path = st.session_state.videos.get(issue.get("room"))
        if not has_frame and video_path and pd.notna(issue.get("frame_time_s")):
            issue["frame_path"] = grab_frame(video_path, issue["frame_time_s"])
    return issues


if "issues" not in st.session_state:
    st.session_state.issues = []   # the list shown in the table
    st.session_state.version = 0   # bumped when new issues arrive, so the table refreshes
    st.session_state.videos = {}   # room -> saved video file, used for the report photos
    st.session_state.rooms = list(ROOMS)  # grows when the user types a new room name

if st.session_state.get("toast"):  # e.g. "Kitchen done", set just before the rerun
    st.toast(st.session_state.pop("toast"), icon="✅")

st.title("Your move-in report")
issues_now = st.session_state.get("edited", st.session_state.issues)
kept = sum(1 for i in issues_now if i.get("confirmed") == True)  # noqa: E712 (numpy True too)
st.write(f"{len(st.session_state.videos)} rooms filmed · {len(issues_now)} issues found · {kept} kept in report"
         if st.session_state.issues else "Film each room, check what the AI found, and download a dated report.")
step = 1 if not st.session_state.issues else 4 if st.session_state.get("downloaded") else 2
step_bar(step, pop=step != st.session_state.get("last_step"))
st.session_state.last_step = step

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
    st.video(video, width=360)
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
        st.session_state.toast = f"{room} done: {len(new_issues)} issues found"
        st.rerun()

# 3. Check and edit the issues
st.header("3. Check the issues")
if not st.session_state.issues:
    st.info("Upload a room video above to see what the AI finds.")
else:
    as_table = st.toggle("Edit as table", key="as_table",
                         help="Change item names or times, or add and delete rows.")
    if as_table:
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
        st.session_state.table_used = True
    else:
        if st.session_state.pop("table_used", False):  # back from the table: keep its edits
            st.session_state.issues = st.session_state.edited
            st.session_state.cards_v = st.session_state.get("cards_v", 0) + 1
        issues = add_frames(st.session_state.issues)
        cv = st.session_state.get("cards_v", 0)
        # Cards rise in only the first time they're shown (new issues or edits from the table)
        fresh = (st.session_state.version, cv) != st.session_state.get("cards_seen")
        st.session_state.cards_seen = (st.session_state.version, cv)

        rooms_in_order = list(dict.fromkeys(text_or_blank(i.get("room")) for i in issues))
        for room_name in rooms_in_order:
            in_room = [(n, i) for n, i in enumerate(issues) if text_or_blank(i.get("room")) == room_name]
            st.markdown(f"### {room_name or 'Room not set'} · {len(in_room)} issue{'s' if len(in_room) != 1 else ''}")
            for n, issue in in_room:
                k = f"{st.session_state.version}_{cv}_{n}"
                keep = issue.get("confirmed") == True  # noqa: E712
                prefix = ("fresh_" if fresh else "card_") + ("" if keep else "off_")
                with st.container(key=f"{prefix}{k}"):
                    photo_col, body = st.columns([1, 4], gap="medium")
                    photo = text_or_blank(issue.get("frame_path"))
                    if photo and Path(photo).exists():
                        photo_col.image(outlined(photo, box_of(issue)), width=200)
                    else:
                        photo_col.markdown('<div class="edd-photo-missing">No photo – added by you</div>',
                                           unsafe_allow_html=True)
                    title_col, keep_col = body.columns([3, 1], vertical_alignment="center")
                    title = " – ".join(x for x in [text_or_blank(issue.get("item")), text_or_blank(issue.get("issue"))] if x)
                    title_col.markdown(f"#### {title or 'Issue'}")
                    issue["confirmed"] = keep_col.toggle("Keep in report", value=keep, key=f"keep_{k}")
                    if not issue["confirmed"]:
                        body.caption("Removed – won't appear in your report.")
                        continue
                    with body:
                        severity = cap(text_or_blank(issue.get("severity"))) or "Minor"
                        confidence = text_or_blank(issue.get("confidence"))
                        reason = text_or_blank(issue.get("uncertainty_reason"))
                        check = (("AI: Sure", "sure") if confidence == "high" else
                                 (f"AI: Check – {reason}" if reason else "AI: Check", "check") if confidence == "medium"
                                 else ("Added by you", "you"))
                        badges((severity, severity.lower() if severity in SEVERITY else "minor"), check)
                    sev_col, who_col = body.columns(2)
                    issue["severity"] = sev_col.selectbox(
                        "Severity", SEVERITY, key=f"sev_{k}",
                        index=SEVERITY.index(severity) if severity in SEVERITY else 0)
                    who = text_or_blank(issue.get("responsibility"))
                    issue["responsibility"] = who_col.selectbox(
                        "Who sorts it?", RESPONSIBILITY, key=f"who_{k}",
                        index=RESPONSIBILITY.index(who) if who in RESPONSIBILITY else len(RESPONSIBILITY) - 1)
                    issue["note"] = body.text_input("Your note", value=text_or_blank(issue.get("note")),
                                                    key=f"note_{k}", placeholder="Add a note (optional)")
                    seconds = issue.get("frame_time_s")
                    if room_name in st.session_state.videos and seconds is not None and pd.notna(seconds):
                        if body.toggle(f"▶ Rewatch at {video_time(seconds)}", key=f"rw_{k}"):
                            # Fixed width so upright phone videos don't fill the whole screen
                            body.video(st.session_state.videos[room_name], start_time=int(seconds), width=400)
        st.session_state.edited = issues

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
            "You can change 'Who sorts it?' on each issue if it's wrong. General guidance, not legal advice. "
            "For help: [Shelter – housing advice](https://england.shelter.org.uk/housing_advice) · "
            "[Citizens Advice – renting privately](https://www.citizensadvice.org.uk/housing/renting-privately/)"
        )

    # Compare with your agency's inventory (the check-in inventory the letting agency sends)
    st.subheader("Compare with your agency's inventory")
    st.write("Got a check-in inventory from your letting agency? "
             "Upload it and we'll show where it disagrees with your videos.")
    inventory = st.file_uploader("Agency inventory (PDF)", type=["pdf"])
    st.caption("Word files need to be saved as PDF first (in Word: File → Save As → PDF).")
    if inventory and st.button("Compare"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(inventory.getbuffer())
        try:
            with st.spinner("Reading your inventory..."):
                st.session_state.inventory_result = compare_inventory(
                    f.name, st.session_state.edited, list(st.session_state.videos.keys()))
        except Exception as e:  # e.g. missing API key, no internet, unreadable PDF
            st.error(f"Sorry, the comparison didn't work: {e}. Please try again.")
            st.stop()
        st.session_state.inventory_version = st.session_state.get("inventory_version", 0) + 1

    result = st.session_state.get("inventory_result")
    if result:
        def show_finding(finding, key):
            """One finding: Room – Item, both sides, small photo and a Rewatch option when we have them."""
            with st.container(border=True):
                photo = text_or_blank(finding.get("frame_path"))
                text_col, photo_col = st.columns([3, 1]) if photo and Path(photo).exists() else (st.container(), None)
                text_col.markdown(f"**{text_or_blank(finding.get('room'))} – {text_or_blank(finding.get('item'))}**")
                text_col.markdown(f"Inventory says: _{text_or_blank(finding.get('inventory_says')) or 'nothing'}_  \n"
                                  f"Your video shows: _{text_or_blank(finding.get('video_shows')) or 'nothing'}_")
                if photo_col:
                    photo_col.image(photo, width=160)
                # Rewatch: find the video via the matching issue's photo (room names can differ slightly)
                seconds = finding.get("frame_time_s")
                room = next((i["room"] for i in st.session_state.edited
                             if photo and text_or_blank(i.get("frame_path")) == photo), finding.get("room"))
                if seconds is not None and pd.notna(seconds) and room in st.session_state.videos:
                    if text_col.toggle(f"Rewatch at {video_time(seconds)}", key=f"inv_rewatch_{key}"):
                        st.video(st.session_state.videos[room], start_time=int(seconds), width=400)

        groups = [
            ("missing_from_inventory", "🔴 Not in the inventory: raise these with your agency"),
            ("inventory_only", "🟠 In the inventory but not in your videos: check these"),
            ("not_filmed", "⚪ Rooms you haven't filmed"),
            ("agrees", "🟢 Agrees"),
        ]
        for status, title in groups:
            found = [f for f in result["findings"] if f["status"] == status]
            if not found:
                continue
            if status == "agrees":  # least important, so folded away
                with st.expander(f"{title} ({len(found)})"):
                    for n, finding in enumerate(found):
                        show_finding(finding, f"{status}_{n}")
            else:
                st.markdown(f"#### {title} ({len(found)})")
                for n, finding in enumerate(found):
                    show_finding(finding, f"{status}_{n}")

        reply = st.text_area("Your reply to the agency", value=result["reply"], height=250,
                             key=f"inventory_reply_{st.session_state.get('inventory_version', 0)}")
        st.download_button("Save reply as a text file", data=reply, file_name="reply-to-agency.txt",
                           mime="text/plain")
        st.caption("Agencies usually ask for comments within a few days. Send this soon, and keep a copy.")

    # 4. Download the report
    st.header("4. Download your report")
    st.caption("Each issue in the report includes a photo taken from your video at that moment.")
    with st.container(key="download"):
        st.download_button(
            "Download PDF report",
            data=make_pdf([dict(i, frame_path=outlined(text_or_blank(i.get("frame_path")), box_of(i)))
                           for i in add_frames(st.session_state.edited)], tenant_name, property_address),
            file_name="move-in-report.pdf",
            mime="application/pdf",
            type="primary",
            on_click=lambda: st.session_state.update(downloaded=True),
        )

    # 5. Email your landlord: AI-written, citing the GOV.UK / Shelter source of each rule
    st.header("5. Email your landlord")
    st.caption("Send the report on move-in day, so there's a dated record. Attach the PDF you just downloaded.")
    landlord_col, to_col = st.columns(2)
    landlord_name = landlord_col.text_input("Landlord or agent's name", placeholder="e.g. Mr Patel / Foxtons")
    landlord_email = to_col.text_input("Their email address", placeholder="e.g. lettings@agency.co.uk")
    if st.button("Write the email for me", type="primary"):
        try:
            with st.spinner("Writing your email..."):
                st.session_state.email = write_email(st.session_state.edited, tenant_name, property_address,
                                                     landlord_name)
        except Exception as e:  # e.g. missing API key, no internet
            st.error(f"Sorry, the email didn't work: {e}. Please try again.")
            st.stop()
        st.session_state.email_version = st.session_state.get("email_version", 0) + 1
    email = st.session_state.get("email")
    if email:
        ev = st.session_state.get("email_version", 0)
        subject = st.text_input("Subject", value=email["subject"], key=f"email_subject_{ev}")
        body = st.text_area("Email", value=email["body"], height=420, key=f"email_body_{ev}")
        mailto = (f"mailto:{quote(landlord_email.strip())}?subject={quote(subject)}&body={quote(body)}")
        st.link_button("Open in your email app", mailto, type="primary")
        st.caption("Your email app opens with this text filled in. Attach the PDF report before sending. "
                   "General guidance, not legal advice.")

st.caption("General guidance, not legal advice. See GOV.UK, Shelter or Citizens Advice for help with deposits.")
