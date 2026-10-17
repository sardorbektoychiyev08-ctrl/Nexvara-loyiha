"""Finds English words in user-visible UI text (shared by the static and the live checks).

Allowed: brand and product names, API/file-format acronyms and the exact names of buttons on
other companies' websites that the help text quotes so the user can find them there.
"""

from __future__ import annotations

import re

ENGLISH = set(
    """
about account add agent all and any apply approval approve archive are at back backup balance
be billing button by cancel cancelled change chart chat check choose clear close code column
columns completed connect connected copy cost costs create credit credits daily dashboard
delete details device devices disconnected done download edit email empty enabled error errors
export failed file files filter filters find folder for free from help hide history home import
info is item items key keys language left limit limits list loading login logout manage memory
model models month monthly more move my name new next no none of offline ok on online open or
page pages paid pause payment pending phone plan plans please preview previous price prices
processing provider queue queued ready refresh reload remove rename reset restore resume retry
row rows run running save search select send setting settings show sign source start status step
steps stop subscription succeeded success summary sync table task tasks teach the this title to
today total trial type update upload usage value values version view wait warning watch with
workbook workflow workflows yes you your
""".split()
)

# Exact phrases allowed although they contain English words (brands, quoted foreign UI).
ALLOWED_PHRASES = [
    "NEXVARA BI",
    "Power BI",
    "Credential Manager",
    "Windows Credential Manager",
    "Google Cloud",
    "Google Drive",
    "Google One",
    "Gemini Advanced",
    "Google AI Studio",
    "AI Studio",
    "Claude Console",
    "ChatGPT Plus",
    "Claude Pro",
    "Desktop app",
    "Clients",
    "Client JSON",
    "Not private",
    "API development tools",
    "App api_id",
    "App api_hash",
    "API ID",
    "API hash",
    "PivotTable",
    "Free Tier",
    "Recycle Bin",
    "my.telegram.org",
    "docs/GOOGLE_LOGIN.md",
    "Android SDK",
    "Wi-Fi",
    "Plus/Pro",
    "Pro/Max",
    "Pro",
    "Max",
    "Plan information",
    "Billing",
    "Buy credits",
]
# Words that are Uzbek too (or a unit) and must not count as English.
UZBEK_TOO = {"test", "testlar", "limit", "panel", "model", "real", "on", "in"}


def english_words(text: str) -> list[str]:
    s = text
    for p in sorted(ALLOWED_PHRASES, key=len, reverse=True):
        s = s.replace(p, " ")
    s = re.sub(r"https?://\S+|[\w.-]+\.(?:com|org|uz|md|dev|ai)\b|\S+\.(?:xlsx|docx|pptx|pdf|csv|json|db)\b",
               " ", s)  # fmt: skip
    # Official model ids ("gemini-3.1-pro-preview", "gpt-6-luna") are identifiers, not text.
    s = re.sub(
        r"\b[a-z]+(?:[-.][a-z0-9]+)*-\d[\w.-]*\b|\b[a-z]+-[a-z0-9]+(?:-[a-z0-9]+)+\b", " ", s
    )
    # o‘, g‘ and the tutuq belgisi are part of Uzbek words: "to‘lov" is one word, not "to".
    words = re.findall(r"[A-Za-z][A-Za-z‘’'ʻʼ`]*[A-Za-z]", s)
    out = []
    for w in words:
        lw = w.lower()
        if lw in UZBEK_TOO:
            continue
        # "dashboardlar", "workflowni": an English word with an Uzbek ending is still English.
        base = re.sub(r"(lari|lar|ni|ning|ga|da|dan|ingiz|imiz|i|si)$", "", lw)
        if lw in ENGLISH or (len(base) >= 5 and base in ENGLISH and base not in UZBEK_TOO):
            out.append(w)
    return out
