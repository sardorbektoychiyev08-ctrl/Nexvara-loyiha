"""Personal data never leaves this PC in clear text.

Before any request goes to an external AI, the user-originated text (the message, chat
history, remembered facts, Teach rules, file paths in the context) is scanned locally and
every personal item is replaced by a placeholder such as ⟦ISM_1⟧, ⟦TEL_1⟧, ⟦JSHSHIR_1⟧. The
mapping stays in memory for that one request only; the AI's answer is restored locally, so
the user sees the real values again. Nothing about the mapping is stored or logged.

Detected: full names (Uzbek surname/patronymic forms, common first names, "F.I.Sh.:" fields),
JSHSHIR/PINFL (14 digits), passport and ID-card numbers (AA1234567), phone numbers (+998…,
local 9-digit), e-mail, bank cards (Luhn), addresses (ko‘cha/mahalla/uy/kvartira…), birth
dates, INN/STIR (9 digits after the keyword).

If detection is unreliable — a personal-data keyword ("pasport", "telefon", "JSHSHIR",
"manzil", "familiyasi"…) without a recognised value next to it, or a long digit run that
fits no known format — the request is BLOCKED instead of sent (`PrivacyBlocked`).

Public text (textbook passages, NEXVARA's own prompts) is passed between PUBLIC markers and
is not masked: it contains historical names ("Amir Temur") that the answer needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from nexvara.core.task import UserError

PUBLIC_START = "⟪PUBLIC⟫"
PUBLIC_END = "⟪/PUBLIC⟫"


def public(text: str) -> str:
    """Mark text that is public (textbook passages) so it is not masked."""
    return f"{PUBLIC_START}{text}{PUBLIC_END}"


class PrivacyBlocked(UserError):
    """Shown to the user; nothing was sent."""


_APOS = "‘’'ʻʼ`"
_L = rf"[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ{_APOS}]"
_CAP = r"[A-ZА-ЯЁЎҚҒҲ]"
# Uzbek / Russian surname and patronymic endings.
_SURNAME = re.compile(
    rf"\b{_CAP}{_L}+?(?:ov|ova|ev|eva|yev|yeva|iyev|iyeva|ovna|evna|ovich|evich|xo[{_APOS}]?jayev"
    rf"|xo[{_APOS}]?jayeva|bekov|bekova|jonov|jonova|zoda)\b"
)
_PATRONYMIC = re.compile(rf"\b{_CAP}{_L}+\s+(?:o[{_APOS}]?g[{_APOS}]?li|qizi)\b")
# Common first names (a person's first name alone is personal too).
FIRST_NAMES = set(
    """
Abbos Abdulla Abdurahmon Abror Akmal Akbar Alisher Ali Anvar Aziz Azizbek Bahodir Baxtiyor
Bekzod Bobur Botir Davron Diyor Doniyor Elyor Eldor Farhod Farrux Fayzulla Hasan Husan
Ibrohim Ilhom Islom Jahongir Jamshid Javlon Jasur Kamol Komil Laziz Mansur Mirzo Muhammad
Murod Nodir Nurbek Odil Oybek Otabek Rahim Rustam Sanjar Sardor Sardorbek Sarvar Sherzod Shohruh
Sobir Sunnat Temur Ulug‘bek Umid Vali Xurshid Yusuf Zafar Zohid Abdulaziz Asadbek Azamat
Aziza Barno Dildora Dilnoza Dilshoda Durdona Feruza Gavhar Gulnora Gulchehra Gulsanam Hilola
Iroda Kamola Lola Madina Malika Mahliyo Marjona Mohira Muslima Nargiza Nasiba Nigora Nilufar
Nodira Oysha Ozoda Robiya Rayhona Saida Sevara Shahlo Shahzoda Shoira Sitora Umida Xadicha
Yulduz Zarina Zebo Zulfiya Zuhra Ziyoda Mohinur Munisa Nozima Sabina Shaxnoza
""".split()
)
_FIRST = re.compile(r"\b(" + "|".join(sorted(map(re.escape, FIRST_NAMES), key=len, reverse=True))
                    + r")\b")  # fmt: skip
# Capitalised words that are never names (sentence starts, subjects, places, brands).
_NOT_NAMES = {
    "Amir",
    "Temur",
    "Toshkent",
    "Samarqand",
    "Buxoro",
    "Xiva",
    "Andijon",
    "Namangan",
    "Farg‘ona",
    "Qarshi",
    "Nukus",
    "Termiz",
    "Jizzax",
    "Navoiy",
    "Guliston",
    "Urganch",
    "O‘zbekiston",
    "Excel",
    "Word",
    "PowerPoint",
    "Google",
    "OneDrive",
    "NEXVARA",
    "Windows",
}

# Public figures from textbooks and history are not personal data: "Alisher Navoiy kim?"
# must reach the AI as it is.
PUBLIC_FIGURES = {
    "alisher navoiy",
    "amir temur",
    "mirzo ulug‘bek",
    "ulug‘bek",
    "zahiriddin muhammad bobur",
    "bobur",
    "abdulla qodiriy",
    "ibn sino",
    "abu ali ibn sino",
    "abu rayhon beruniy",
    "beruniy",
    "al-xorazmiy",
    "muhammad al-xorazmiy",
    "abdulla oripov",
    "cho‘lpon",
    "hamza",
    "furqat",
    "mashrab",
    "ogahiy",
    "muqimiy",
    "zavqiy",
    "jaloliddin manguberdi",
    "najmiddin kubro",
    "imom buxoriy",
    "imom termiziy",
    "islom karimov",
    "shavkat mirziyoyev",
    "abdulla avloniy",
    "mahmudxo‘ja behbudiy",
    "behbudiy",
    "munavvar qori",
    "fitrat",
    "abdurauf fitrat",
    "erkin vohidov",
    "said ahmad",
    "o‘tkir hoshimov",
    "gafur g‘ulom",
    "g‘afur g‘ulom",
    "isaak nyuton",
    "nyuton",
    "pushkin",
    "lomonosov",
    "mendeleyev",
    "dmitriy mendeleyev",
}
_FIGS = sorted(PUBLIC_FIGURES, key=len, reverse=True)
_PUBLIC_RE = re.compile(
    r"(?i)\b(?:" + "|".join(re.escape(f).replace("‘", f"[{_APOS}]") for f in _FIGS) + r")\b"
)
_DIGITS = r"\d[\d\s\-–]*\d"
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # JSHSHIR / PINFL: 14 digits (spaces allowed), first digit 1-6.
    ("JSHSHIR", re.compile(r"(?<!\d)[1-6](?:[\s-]?\d){13}(?!\d)")),
    ("KARTA", re.compile(r"(?<!\d)(?:\d[\s-]?){15}\d(?!\d)")),
    (
        "TEL",
        re.compile(
            r"(?<![\w+])(?:\+?998[\s\-()]*)?\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"
        ),
    ),
    ("PASPORT", re.compile(r"\b[A-Z]{2}\s?\d{7}\b")),
    ("SANA", re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:19|20)\d{2}\b")),
    ("STIR", re.compile(r"(?i)(?:\b(?:inn|stir)[\s:№#]{0,3})\d{9}\b")),
]
_ADDRESS = re.compile(
    rf"(?i)(?:\b{_L}+\s+){{0,3}}(?:ko[{_APOS}]?chasi|ko[{_APOS}]?cha|mahallasi|mahalla|"
    rf"mavzesi|massivi|tumani|shaharchasi|ulitsa|ul\.|prospekti|shoh\s+ko[{_APOS}]?chasi)"
    rf"(?:[\s,]+(?:\d+[\w/-]*|uy|kv\.?|kvartira|xonadon|dom|{_L}+){{0,6}})?"
)
_UY = re.compile(r"(?i)\b(?:\d+[-\s]?uy|uy[\s:№]*\d+|kv\.?\s*\d+|\d+[-\s]?xonadon)\b")

# Keywords that announce personal data; each expects a value of these kinds nearby.
_KEYWORDS: list[tuple[re.Pattern, set[str]]] = [
    (re.compile(r"(?i)\b(jshshir|pinfl|shaxsiy\s+raqam\w*)\b"), {"JSHSHIR"}),
    (re.compile(r"(?i)\b(pasport\w*|passport\w*|id[-\s]?karta\w*)\b"), {"PASPORT"}),
    (re.compile(r"(?i)\b(telefon\w*|tel\.|nomer\w*|raqami)\b"), {"TEL"}),
    (re.compile(r"(?i)\b(manzil\w*|yashash\s+joyi\w*|adres\w*)\b"), {"MANZIL"}),
    (
        re.compile(rf"(?i)\b(f\.?\s?i\.?\s?sh\.?|familiya\w*|ism[{_APOS}]?i\b|ism-familiya\w*)"),
        {"ISM"},
    ),  # fmt: skip
    (re.compile(r"(?i)\b(karta\s+raqam\w*|plastik\s+karta\w*)\b"), {"KARTA"}),
    (re.compile(r"(?i)\b(tug[‘’']?ilgan\s+(sana|kun)\w*)\b"), {"SANA"}),
]
_NEAR = 60  # characters after a keyword where its value must be


def _norm(name: str) -> str:
    """Lower case, one space, Uzbek o‘/g‘ written with the same apostrophe."""
    s = re.sub(r"\s+", " ", name.strip().lower())
    return re.sub(f"[{_APOS}]", "‘", s)


def _luhn(digits: str) -> bool:
    d = [int(c) for c in digits][::-1]
    return (
        sum(x if i % 2 == 0 else (x * 2 - 9 if x * 2 > 9 else x * 2) for i, x in enumerate(d)) % 10
        == 0
    )


@dataclass
class Guard:
    """One request: mask outgoing text, restore incoming text."""

    values: dict[str, str] = field(default_factory=dict)  # token -> original
    _by_value: dict[tuple[str, str], str] = field(default_factory=dict)
    _counts: dict[str, int] = field(default_factory=dict)

    def _token(self, kind: str, value: str) -> str:
        key = (kind, re.sub(r"\s+", " ", value.strip()).lower())
        tok = self._by_value.get(key)
        if tok is None:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            tok = f"⟦{kind}_{self._counts[kind]}⟧"
            self._by_value[key] = tok
            self.values[tok] = value.strip()
        return tok

    # ----- masking -----
    def _mask_part(self, text: str) -> tuple[str, list[str]]:
        found: list[tuple[int, int, str]] = []

        def take(kind: str, m: re.Match) -> None:
            a, b = m.span()
            if any(a < y and x < b for x, y, _k in found):
                return
            found.append((a, b, kind))

        for kind, pat in _PATTERNS:
            for m in pat.finditer(text):
                if kind == "KARTA" and not _luhn(re.sub(r"\D", "", m.group())):
                    continue
                take(kind, m)
        for m in _ADDRESS.finditer(text):
            take("MANZIL", m)
        for m in _UY.finditer(text):
            take("MANZIL", m)
        # Name parts: surnames, patronymics, known first names and the words after a name
        # field ("F.I.Sh.: Karimov Botirjon", "ismi Botirjon"). Parts that touch each other,
        # or have one capitalised word between them, form one full name.
        spans = [m.span() for m in _SURNAME.finditer(text)]
        spans += [m.span() for m in _FIRST.finditer(text)]
        spans += [m.span() for m in _PATRONYMIC.finditer(text)]
        fld = (
            rf"(?i:\b(?:f\.?\s?i\.?\s?sh\.?|ism-familiya\w*|ismi\s+va\s+familiyasi|"
            rf"ismi|familiyasi|o[{_APOS}]?quvchi(?:si)?|ota-onasi|onasi|otasi|"
            rf"o[{_APOS}]?qituvchi(?:si)?))"
        )
        spans += [m.span(1) for m in re.finditer(
            fld + rf"\s*[:\-–]?\s*((?:{_CAP}{_L}+\s?){{1,3}})", text)]  # fmt: skip
        public_spans = [m.span() for m in _PUBLIC_RE.finditer(text)]
        spans = sorted(
            (a, b) for a, b in spans
            if text[a:b].strip() not in _NOT_NAMES
            and not any(a < y and x < b for x, y in public_spans)
        )  # fmt: skip
        merged: list[list[int]] = []
        for a, b in spans:
            gap = text[merged[-1][1] : a] if merged else ""
            joins = merged and (a <= merged[-1][1] or re.fullmatch(
                rf"\s+|\s+{_CAP}{_L}+\s+", gap))  # fmt: skip
            if joins:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged:
            while b > a and text[b - 1].isspace():
                b -= 1
            if _norm(text[a:b]) in PUBLIC_FIGURES:
                continue
            if not any(a < y and x < b for x, y, _k in found):
                found.append((a, b, "ISM"))
        found.sort()
        # One address, not three tokens: join address parts separated only by , or spaces.
        joined: list[tuple[int, int, str]] = []
        for a, b, kind in found:
            if (joined and kind == "MANZIL" and joined[-1][2] == "MANZIL"
                    and re.fullmatch(r"[\s,]*", text[joined[-1][1]:a])):  # fmt: skip
                joined[-1] = (joined[-1][0], b, kind)
            else:
                joined.append((a, b, kind))
        found = joined
        out, last, kinds = [], 0, []
        for a, b, kind in found:
            out.append(text[last:a])
            out.append(self._token(kind, text[a:b]))
            kinds.append(kind)
            last = b
        out.append(text[last:])
        return "".join(out), kinds

    def _check(self, original: str, masked: str) -> None:
        """Block when detection is unreliable."""
        for pat, kinds in _KEYWORDS:
            for m in pat.finditer(original):
                window = masked_window(original, masked, m.end(), _NEAR)
                if window is None:
                    continue
                has_value = any(f"⟦{k}_" in window for k in kinds)
                after = original[m.end() : m.end() + _NEAR]
                looks_like_value = re.search(r"[:\-–]\s*\S|\d", after) or (
                    "ISM" in kinds and re.match(rf"\s+{_CAP}", after)
                )
                if looks_like_value and not has_value:
                    raise PrivacyBlocked(
                        f"So‘rov yuborilmadi: «{m.group(0)}» yonidagi shaxsiy ma’lumotni "
                        "ishonchli aniqlab bo‘lmadi. Uni matndan olib tashlang yoki "
                        "«[yashirilgan]» deb yozing."
                    )
        for m in re.finditer(r"\d[\d\s\-]{7,}\d", masked):
            if re.fullmatch(r"\d{1,3}(?:[\s.,]\d{3})+", m.group().strip()):
                continue  # an amount like 15 000 000 (so‘m), not a document number
            if len(re.sub(r"\D", "", m.group())) >= 8:
                raise PrivacyBlocked(
                    "So‘rov yuborilmadi: matnda tanilmagan uzun raqam bor (hujjat, telefon yoki "
                    "hisob raqami bo‘lishi mumkin). Uni olib tashlang yoki qisqartiring."
                )

    def mask(self, text: str) -> str:
        """Mask everything outside PUBLIC markers; the markers themselves are removed."""
        parts = re.split(f"({re.escape(PUBLIC_START)}.*?{re.escape(PUBLIC_END)})", text, flags=re.S)
        out = []
        for part in parts:
            if part.startswith(PUBLIC_START) and part.endswith(PUBLIC_END):
                out.append(part[len(PUBLIC_START) : -len(PUBLIC_END)])
                continue
            masked, _kinds = self._mask_part(part)
            self._check(part, masked)
            out.append(masked)
        return "".join(out)

    # ----- restoring -----
    def restore(self, text: str) -> str:
        """Put the real values back (also when the model wrote the token slightly differently)."""
        if not self.values:
            return text
        for tok, value in self.values.items():
            kind_n = tok[1:-1]  # ISM_1
            pat = re.compile(r"[⟦\[\{<«]{1,2}\s*" + re.escape(kind_n) + r"\s*[⟧\]\}>»]{1,2}")
            text = pat.sub(lambda _m, v=value: v, text)
        return text

    @property
    def count(self) -> int:
        return len(self.values)


def masked_window(original: str, masked: str, pos: int, width: int) -> str | None:
    """The masked text that corresponds to original[pos:pos+width] (approximately: the
    original prefix is masked again to find where it ends)."""
    g = Guard()
    try:
        prefix, _ = g._mask_part(original[:pos])
    except Exception:  # noqa: BLE001 - only a locator
        return None
    start = len(prefix)
    # Tokens can be longer or shorter than the text they replace; give some slack.
    return masked[max(0, start - 2) : start + width + 40]
