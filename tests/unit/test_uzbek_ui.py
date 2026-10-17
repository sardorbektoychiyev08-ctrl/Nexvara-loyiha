"""The static UI text (index.html, mobile.html) and the central dictionary are Uzbek."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from tests.uzbek_check import english_words

UI = Path(__file__).resolve().parents[2] / "src" / "nexvara" / "app" / "ui"


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        for k, v in attrs:
            if k in ("placeholder", "title", "aria-label", "alt") and v:
                self.items.append(v)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.items.append(" ".join(data.split()))


def _texts(name: str) -> list[str]:
    p = _Text()
    p.feed((UI / name).read_text(encoding="utf-8"))
    return p.items


def test_static_pages_have_no_english():
    bad = [(f, s, english_words(s)) for f in ("index.html", "mobile.html") for s in _texts(f)
           if english_words(s)]  # fmt: skip
    assert bad == []


def test_menu_uses_the_agreed_names_from_the_dictionary():
    src = (UI / "i18n.js").read_text(encoding="utf-8")
    names = dict(re.findall(r'"(nav\.\w+)": "([^"]+)"', src))
    assert names == {
        "nav.home": "Bosh sahifa", "nav.chat": "AI suhbat", "nav.office": "Office yordamchisi",
        "nav.library": "Darsliklar va testlar", "nav.files": "Fayllar", "nav.bi": "NEXVARA BI",
        "nav.workflows": "Ish jarayonlari", "nav.teach": "NEXVARA’ga o‘rgatish",
        "nav.memory": "Xotira", "nav.history": "Vazifalar va tarix", "nav.devices": "Qurilmalar",
        "nav.settings": "Sozlamalar",
    }  # fmt: skip
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert (
        len(re.findall(r'class="nav-item[^"]*" data-page="\w+"[^>]*data-i18n="nav\.', html)) == 12
    )
    for value in re.findall(r'"[\w.]+": "([^"]+)"', src):
        assert english_words(value) == [], value


def test_status_words_are_uzbek():
    src = (UI / "i18n.js").read_text(encoding="utf-8")
    for key, word in [("status.pending", "Kutilmoqda"), ("status.running", "Bajarilmoqda"),
                      ("status.succeeded", "Bajarildi"), ("status.failed", "Xatolik yuz berdi"),
                      ("status.cancelled", "Bekor qilindi")]:  # fmt: skip
        assert f'"{key}": "{word}"' in src
