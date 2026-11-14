# CLAUDE.md – Move-in Co-pilot (LBS AI Cup 2026)

This file gives Claude (and us) shared context. Keep it short and update it as we go.
Pitch, research and competitors live in `PITCH.md` – don't load it for coding tasks.

## Project

- **Track:** A – Productivity & Work.
- **Idea:** A move-in co-pilot for people renting in the UK for the first time. The tenant films each room in a short clip (~1 min) and talks through any issues. AI pulls frames, spots visible damage and produces an editable, timestamped inventory report they can send to their landlord as evidence for getting their deposit back. A move-in admin checklist and repair requests are added on top if time allows.
- **Target user:** LBS (and other international) students renting in London for the first time, who don't know the UK system and risk losing deposit money to damage they didn't cause.
- **What the demo must show (in priority order):**
  1. Upload a room video → AI lists issues per room → user edits the list → timestamped report downloads.
  2. Voice note while filming is transcribed and attached to the report.
  3. Personalised move-in admin checklist (deposit protection, council tax, energy, GP, TV licence) with links to GOV.UK.
- **Judging (shortlist):** 40% Pain & Impact, 30% Build & Live Demo, 30% AI Value & Integration. Judges mark down mock-ups and "a chatbot bolted onto an app" – the AI must do real work.
- **Deadline:** submit on Commfy by **Sat 14 Nov, 15:30**. Feature freeze at **14:30**.

## Team

- **Anant** – most technical. Owns the **AI pipeline**: video → frames, vision model → issues JSON, voice → text. Final say on technical decisions; checks merges into `main`.
- **Emma** – analytics and consumer insight. Owns the **app and report**: Streamlit screens, editable issue list, report export, admin checklist screen.
- **Francesca** – business strategy. Owns **content and pitch**: UK rules file, checklist content, repair-request prompts, user research, pitch and demo script.

## Shared data format (agree first – lets us work in parallel)

Every module passes issues in this shape. Don't change it without telling the team.

```json
{
  "room": "kitchen",
  "item": "oven door",
  "issue": "scratch",
  "severity": "minor | moderate | major",
  "frame_time_s": 12.0,
  "frame_path": "data/frames/kitchen_012.jpg",
  "note": "user's spoken or typed comment",
  "confirmed": true
}
```

The report adds `property_address`, `tenant_name` and `created_at` (ISO timestamp).

Added Sat 14 Nov (pipeline fills them): `confidence` ("high" | "medium"), `uncertainty_reason` (what to double-check, "" when high), `responsibility` (same options as the app's "Who sorts it?" column), `responsibility_reason`, `responsibility_source`, `responsibility_url` (from `content/responsibility.json`), `box` ([x0, y0, x1, y1] as 0–1 fractions of the photo, around the problem; null if none).

## Tech stack

- **Language / framework:** Python + Streamlit.
- **Libraries (allowed):** `streamlit`, `opencv-python-headless` (frame extraction), `anthropic` (vision), `elevenlabs` (speech-to-text), `python-dotenv`, `fpdf2` (PDF report). Ask before adding anything else.
- **AI:** Claude API with images for damage detection (one frame every ~2 s, max ~30 frames per clip). ElevenLabs speech-to-text for voice notes. No model training.
- **Data:** our own videos, consented videos from classmates, free stock images (Unsplash/Pexels), public GOV.UK and Shelter guidance. Public, synthetic or consented data only.
- **Hosting:** Streamlit Community Cloud. Test a deploy early.

## Folder structure

```
/app        Streamlit UI (Emma)
/pipeline   frames, vision, voice (Anant)
/content    UK rules, checklist, prompts (Francesca)
/data       sample videos and frames (not committed if large)
/report     report generation
PITCH.md    pitch and research (not for coding)
```

## Build order

1. **Core loop (by ~11:00):** one room video → issues JSON → editable list → report download. Must work before anything else.
2. **Voice notes (late morning).**
3. **Admin checklist (around lunch).**
4. **Report a repair (early afternoon):** describe/photo a problem → who is responsible → draft landlord email → logged.
5. **Contract red-flag check (only if time).**
6. **Move-out deposit comparison:** now being built (see decisions log): move-in vs move-out video per room.

A feature only counts once it works in the demo flow. Otherwise it goes on the roadmap slide.

## How we work

- Pull before you start; commit and push small and often.
- **One short-lived branch per small feature** (e.g. `feat/frame-extraction`, `fix/report-date`). Merge into `main` as soon as it runs, then open a new branch. Don't let branches pile up overlapping edits.
- Stay in your own folder so we don't collide. Anant checks merges into `main`.
- Check-ins every ~3 hours: done / blocked / next.
- Feature freeze at 14:30; record a backup demo video.

## Rules for Claude

**1. Think before coding.** State assumptions. If something is unclear or there are several readings, ask rather than pick silently. If a simpler approach exists, say so.

**2. Simplicity first.** Minimum code that makes the demo work – this is an MVP, not production code. No speculative features, abstractions or configurability. If 200 lines could be 50, write 50.

**3. Surgical changes.** Only touch what the task needs. Only edit files in the current person's folder unless asked. Don't refactor or "improve" neighbouring code. Remove only the leftovers your own change created.

Also:
- Don't add libraries or services without asking first.
- Never put API keys in code; read them from `.env` (in `.gitignore`).
- Keep AI outputs as JSON in the shared format above.
- The app gives general guidance, not legal advice: cite GOV.UK/Shelter and point hard cases to Shelter or Citizens Advice.
- Before big changes, propose a short plan and wait for a go-ahead. Afterwards, explain briefly what you changed.

## Models and tokens

- Use the strongest model (Opus 5.5 high/max, or Fable) for planning and big-picture decisions.
- Have it spawn sub-agents on lighter settings (e.g. Opus 5.5 medium) for the actual coding, to save context and tokens.

## Decisions log

- Fri 13 Nov – Track A, Move-in Co-pilot, Python + Streamlit, roles as above – team.
- Sat 14 Nov – Build the move-out comparison for real (was slide only): `pipeline/moveout.py` + a Move-out tab – team.

## Current status

- *(update at each check-in: done / in progress / blocked)*
