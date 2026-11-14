"""Edd.AI look and feel: one CSS block for every page, plus small HTML helpers (badges, step bar).

Streamlit containers given a `key` get the CSS class `st-key-<key>`; that's how the styles below
reach the hero, the cards and the download button. Animations only play when a container's key
changes (new issues arrive, the step moves on), not on every click.
"""

import html

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

.stApp { font-family: 'Inter', 'Source Sans Pro', sans-serif; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; color: #0B2E24; letter-spacing: -0.01em;
}
.stButton button, .stDownloadButton button, [data-testid="stPageLink"] a { border-radius: 999px; }

/* Homepage hero: dark green panel, mint button */
.st-key-hero { background: #0B2E24; border-radius: 24px; padding: 56px 48px; animation: edd-rise .5s ease-out both; }
.st-key-hero h1 { color: #FFFFFF; font-size: 3.2rem; line-height: 1.05; font-weight: 800; }
.st-key-hero p { color: #B6D4C8; font-size: 1.2rem; }
.st-key-hero .edd-eyebrow { color: #34D399; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; font-size: .9rem; }
.st-key-hero .stButton button {
  background: #34D399; color: #0B2E24; border: none; font-weight: 700; font-size: 1.1rem; padding: .7rem 1.8rem;
  transition: transform .15s ease, box-shadow .15s ease;
}
.st-key-hero .stButton button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(52, 211, 153, .35); color: #0B2E24; }

/* Homepage tiles */
[class*="st-key-how_"] { background: #F4F7F6; border: 1px solid #E5E9E8; border-radius: 16px; padding: 24px; animation: edd-rise .5s ease-out both; }
[class*="st-key-tool_"] { border: 1px solid #E5E9E8; border-radius: 16px; padding: 24px; transition: transform .15s ease, box-shadow .15s ease; }
[class*="st-key-tool_"]:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(11, 46, 36, .08); }
.edd-num {
  display: inline-flex; width: 36px; height: 36px; border-radius: 50%; background: #047857; color: #FFFFFF;
  align-items: center; justify-content: center; font-weight: 700;
}

/* Step bar */
.edd-steps { list-style: none; margin: 0 0 8px; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.edd-steps li { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 14px; font-weight: 600; margin: 0; }
.edd-steps .dot { width: 32px; height: 32px; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; }
.edd-steps .done { background: #D1FAE5; border: 1px solid #A7F3D0; color: #065F46; }
.edd-steps .done .dot { background: #047857; color: #FFFFFF; }
.edd-steps .current { background: #0B2E24; color: #FFFFFF; }
.edd-steps .current .dot { background: #34D399; color: #0B2E24; }
.edd-steps .todo { background: #F4F7F6; border: 1px solid #E5E9E8; color: #4B5563; }
.edd-steps .todo .dot { border: 2px solid #9CA3AF; color: #4B5563; }
.edd-steps .pop { animation: edd-pop .7s cubic-bezier(.34, 1.56, .64, 1) .1s both; }

/* Issue cards */
[class*="st-key-card_"], [class*="st-key-fresh_"] {
  border: 1px solid #E5E9E8; border-radius: 16px; padding: 18px; background: #FFFFFF;
  box-shadow: 0 1px 3px rgba(11, 46, 36, .06); transition: transform .15s ease, box-shadow .15s ease;
}
[class*="st-key-card_"]:hover, [class*="st-key-fresh_"]:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(11, 46, 36, .08); }
[class*="st-key-fresh_"] { animation: edd-rise .5s ease-out both; }
[class*="st-key-fresh_"]:nth-child(2) { animation-delay: .07s; }
[class*="st-key-fresh_"]:nth-child(3) { animation-delay: .14s; }
[class*="st-key-fresh_"]:nth-child(4) { animation-delay: .21s; }
[class*="st-key-fresh_"]:nth-child(n+5) { animation-delay: .28s; }
[class*="st-key-card_off_"], [class*="st-key-fresh_off_"] { background: #F8FAF9; opacity: .7; }
[class*="st-key-card_"] img, [class*="st-key-fresh_"] img { max-height: 220px; width: auto !important; max-width: 100%; object-fit: contain; border-radius: 10px; }
[class*="st-key-card_"] h4, [class*="st-key-fresh_"] h4 { font-size: 1.1rem; line-height: 1.35; padding: 0; }
.edd-photo-missing {
  height: 120px; border-radius: 10px; background: #E8EDEB; color: #4B5563; font-size: .85rem;
  display: flex; align-items: center; justify-content: center; text-align: center; padding: 8px;
}

/* Badges */
.edd-badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 6px; }
.edd-badge { padding: 3px 10px; border-radius: 999px; font-size: .8rem; font-weight: 600; }
.edd-badge.minor { background: #EEF0F3; color: #3D4652; }
.edd-badge.moderate { background: #FEF3C7; color: #92400E; }
.edd-badge.major { background: #FEE2E2; color: #991B1B; }
.edd-badge.sure { background: #D1FAE5; color: #065F46; }
.edd-badge.check { background: #FFEDD5; color: #9A3412; }
.edd-badge.you { background: #E8EDEB; color: #374151; }

/* Report download: one gentle pulse when it appears */
.st-key-download .stDownloadButton button { animation: edd-pulse 1.6s ease-out .4s 1; }

@keyframes edd-rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes edd-pop { 0% { transform: scale(.96); } 45% { transform: scale(1.05); } 100% { transform: scale(1); } }
@keyframes edd-pulse { 0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, .6); } 100% { box-shadow: 0 0 0 16px rgba(52, 211, 153, 0); } }

@media (prefers-reduced-motion: reduce) {
  .stApp *, .stApp *::before, .stApp *::after { animation: none !important; transition: none !important; }
}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def badges(*pairs):
    """badges(("Moderate", "moderate"), ("AI: Sure", "sure")) -> one row of coloured pills."""
    spans = "".join(f'<span class="edd-badge {kind}">{html.escape(text)}</span>' for text, kind in pairs)
    st.markdown(f'<div class="edd-badges">{spans}</div>', unsafe_allow_html=True)


def step_bar(current, pop=False):
    """The three steps; `current` is 1, 2 or 3 (4 = all done). `pop` bounces the current step once."""
    labels = ["Film your rooms", "Check what the AI found", "Get your report"]
    items = []
    for n, label in enumerate(labels, start=1):
        if n < current:
            state, dot = "done", "✓"
        elif n == current:
            state, dot = "current" + (" pop" if pop else ""), str(n)
        else:
            state, dot = "todo", str(n)
        items.append(f'<li class="{state}"><span class="dot">{dot}</span>{label}</li>')
    st.markdown(f'<ol class="edd-steps">{"".join(items)}</ol>', unsafe_allow_html=True)
