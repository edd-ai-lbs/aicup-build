# PITCH.md – Move-in Co-pilot

Pitch, research and positioning. Not needed for coding tasks.

## One-liner (draft)

Your whole move-in inventory in five minutes: film each room, talk through what you see, and get a timestamped report that protects your deposit.

## Problem and user

- **User:** LBS and other international students renting in London for the first time.
- **Pain:** they don't know the UK rental system – what to check, what's the landlord's job, what admin to sort – and damage they didn't cause can cost them their deposit at the end.
- **Origin:** a team member's own difficult experience with a landlord.
- **Evidence (collect Saturday morning):** answers from our cohort group chat on move-in problems, plus room videos shared with consent. Aim for 3–5 short quotes for the pitch.

## The full journey (vision) vs what we build

- **Before:** spot red flags in the flat and the contract before signing. *(roadmap, contract check only if time)*
- **During – move-in:** video inventory + admin checklist. **← what we build and demo**
- **During – tenancy:** report a repair, see who's responsible, draft the landlord email, keep a log. *(build if time)*
- **After – move-out:** compare move-in vs move-out evidence and draft a deposit dispute. *(roadmap slide)*

## Why not just ask an LLM?

- **You don't know what to ask.** New arrivals have never heard of deposit protection or inventories. The app leads them step by step.
- **Evidence that lasts.** A chat history isn't proof. A room-by-room report with timestamped frames, sent to the landlord on move-in day, is a dated record.
- **It remembers your situation.** Contract, move-in date, deadlines – with nudges at the right time.
- **Grounded answers.** Based on GOV.UK and Shelter guidance, with links, not an LLM's best guess.

## How the AI adds value (for the 30% criterion)

- Vision model spots and labels damage in video frames.
- Voice notes turn into structured, room-tagged notes.
- Applies UK guidance to the user's own situation (checklist, repair responsibility).
- The user stays in control: one quick review per room, not per item.

## Competitors and our gap

- **Shelter, Citizens Advice:** trusted but generic advice; don't read your contract or record evidence.
- **Fixflo, Goodlord:** repair reporting and lettings tools built for agents and landlords.
- **Checkatrade, MyBuilder, Bark, TaskRabbit:** find tradespeople.
- **Acasa, Fused, Splitwise:** household bills and bill splitting.
- **Gap:** nobody stands on the tenant's side with evidence from day one.

## Limits (say them openly – judges reward this)

- The AI can miss subtle or blurry damage → user reviews each room; close-up photos for key items.
- General guidance, not legal advice → sources cited; hard cases sent to Shelter / Citizens Advice.
- Video processing takes time → short clips per room.
- Check the current status of the Renters' Rights Act changes before mentioning them.

## Adoption and next steps (final round, 15%)

- **First users:** LBS incoming students – pilot via student clubs or the accommodation team before term starts.
- **Costs:** API costs per inventory are small; most cost is in hosting and support.
- **Next steps:** move-out comparison, contract check, multilingual voice.

## Pitch structure

- **Shortlist (2-min pitch + demo, 1-min Q&A):** problem in one story (15 s) → live demo of one room (60 s) → why it beats ChatGPT (20 s) → limits and next step (15 s).
- **Final (5 min + 5-min Q&A):** add user evidence, the full journey, competitors, adoption route and costs.

## Submission checklist (Commfy, by 15:30)

- Project name + one-line elevator pitch
- Problem + target users
- How it works + AI's role
- Tools / tech used (disclose reused libraries and datasets)
- Value + what makes it different
- Demo / prototype link
