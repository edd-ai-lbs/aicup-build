# Move-in Co-pilot 🏠

**Film your rented flat. Get an evidence-grade report that protects your deposit.**

Built for the **LBS AI Cup 2026** (Track A – Productivity & Work).

**Live app:** https://movein-copilot.streamlit.app

---

## The problem

Students and international renters in the UK often lose deposit money for damage they didn't cause. They don't know the rules, and a proper inventory takes hours. Move-in Co-pilot turns a one-minute phone video per room into a dated, photo-backed report, and then helps at every step until the deposit comes back.

## What it does

### 🏠 Move-in report
1. **Film a room** (or the whole flat) and talk through anything you notice.
2. **The AI finds visible damage.** Claude looks at the key moments of the video and lists each issue with the room, item, problem, severity and the exact second it appears.
3. **It listens too.** Your spoken comments (via ElevenLabs speech-to-text) go into the right issue's note. Problems a picture can't show ("this window doesn't work") are added as issues.
4. **Check the list.** Each issue shows an **AI check** (🟢 sure / 🟠 "check this", with the reason), a **rewatch** button that plays that moment, and **who sorts it** (landlord / tenant / not the tenant's), with the **GOV.UK or Shelter source**.
5. **Forgot something?** Record a voice note, and the AI adds new problems or comments on existing ones.
6. **Compare with your agency's inventory.** Upload their PDF and see what it leaves out (raise these!), what it mentions that you didn't film, and get a ready-to-send reply to the agent.
7. **Download the PDF report**, with your address, the date, a photo and timestamp for every issue, and your notes.

### 📦 Move-out check
Film each room again when you leave. The AI compares **move-in vs move-out** side by side:
🔴 new since move-in · 🧽 clean before you leave · 🛡️ already there at move-in (you shouldn't pay) · ✅ fixed. You also get a "to do before you leave" list.

### ✅ Admin checklist
A personalised move-in to-do list for England (deposit protection, right to rent, council tax, energy, TV licence, GP, voting), with GOV.UK and NHS links, based on four quick questions.

> General guidance, not legal advice. Hard cases: [Shelter](https://england.shelter.org.uk/housing_advice) or [Citizens Advice](https://www.citizensadvice.org.uk/housing/renting-privately/).

## How the AI works

```
phone video ──► pipeline/media.py   ffmpeg: sound only (~0.4 MB) + keyframes only (≈1 per second)
                 │
                 ├─► pipeline/voice.py    ElevenLabs speech-to-text → sentences with timestamps
                 └─► pipeline/frames.py   drops blurry, dark and repeated moments → ≤30 pictures
                          │
                          ▼
                 pipeline/vision.py   Claude (one request, all pictures + transcript)
                                       → issues in a shared JSON format, with confidence and
                                         a responsibility rule from content/responsibility.json
```

| Module | What it does |
|---|---|
| `pipeline/analyse.py` | `analyse_room(video, room)`: the one call the app makes; saves results for a demo fallback |
| `pipeline/vision.py` | Damage detection with strict "not a false alarm" rules (blur, glare, reflections, grout lines aren't damage) |
| `pipeline/voice_note.py` | "Forgot something?" voice notes → new issues or comments |
| `pipeline/inventory.py` | Agency inventory PDF (text via pypdf) vs the video findings → disagreements + draft reply |
| `pipeline/moveout.py` | Move-in vs move-out video → before/after findings |
| `content/` | Checklist and landlord/tenant rules, each with its GOV.UK / Shelter / NHS source (checked 14 Nov 2026) |
| `report/make_report.py` | The PDF report |
| `app/` | Streamlit screens (move-in report, move-out check, admin checklist) |

**Speed and cost** (65 s, 500 MB 4K phone video): about **16 s** end to end and about **$0.15** of Claude usage.

## Run it locally

You need Python 3.12 and two API keys: [Anthropic](https://console.anthropic.com) (Claude) and [ElevenLabs](https://elevenlabs.io) (speech-to-text only).

```bash
git clone https://github.com/edd-ai-lbs/aicup-build.git
cd aicup-build
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create a file called `.env` in the project folder (it's in `.gitignore`, so it is never uploaded):

```
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=sk_...
```

Then start the app and open http://localhost:8501:

```bash
.venv/bin/python -m streamlit run app/main.py
```

**Deploying on Streamlit Community Cloud:** main file `app/main.py`, Python 3.12, and the two keys in the app's **Secrets** box (TOML format, with quotes: `ANTHROPIC_API_KEY = "sk-ant-..."`).

## Data and privacy

- Videos, pictures and inventories stay in `data/`, which `.gitignore` keeps out of the repo (only the pre-saved demo results in `data/demo_cache/` are committed).
- API keys live only in `.env` / Streamlit Secrets.
- Only our own videos, consented videos from classmates, and public GOV.UK / Shelter / NHS guidance were used.

## Team

- **Anant**: technical lead
- **Emma**: app and report screens
- **Francesca**: content and pitch, and the AI pipeline (video, vision, voice, inventory, move-out)

Built with [Claude](https://www.anthropic.com/claude), [ElevenLabs](https://elevenlabs.io), [Streamlit](https://streamlit.io), OpenCV, ffmpeg, fpdf2 and pypdf.
