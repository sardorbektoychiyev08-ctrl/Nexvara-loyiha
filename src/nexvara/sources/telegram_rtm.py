"""New textbooks from the Republican Education Centre's official Telegram channel.

The channel attaches PDFs as Telegram documents, which only a logged-in client can fetch.
The user logs in once with their own account (api_id/api_hash from my.telegram.org, a
code sent to their phone). The session stays in the NEXVARA data folder, never in Git.
NEXVARA only READS the public channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexvara.knowledge.catalog import detect_grade
from nexvara.knowledge.textnorm import fold

log = logging.getLogger(__name__)

CHANNEL = "rtm_metodik_xizmat"
SOURCE_DIR = "rtm"
# Not textbooks for Uzbek-language schools: other languages, plans, programmes.
_EXCLUDE = (
    "qardosh", "rus", "qoraqalpoq", "qozoq", "qirgiz", "tojik", "turkman", "literatura",
    "dastur", "taqvim", "reja", "metodik", "qollanma", "ishchi", "daftar", "test",
    "русск", "литер", "тожик", "киргиз",
)  # fmt: skip


def is_uzbek_textbook(file_name: str, caption: str = "") -> bool:
    """PDF textbooks for Uzbek-language schools: "_uzb" in the name, or an Uzbek-school
    caption with a grade in it."""
    n, c = fold(file_name), fold(caption)
    if not n.endswith(".pdf") or any(x in n for x in _EXCLUDE):
        return False
    if re.search(r"(?:^|[_\-\s.])uzb(?:[_\-\s.]|$)", n):
        return True
    uzbek_school = "ozbek tilida" in c or "uzbek tilida" in c
    return uzbek_school and detect_grade(file_name + " " + caption) is not None


def grade_of(file_name: str, caption: str = "") -> int | None:
    return detect_grade(file_name) or detect_grade(caption)


def safe_name(file_name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", file_name).strip(" .")
    return name or "darslik.pdf"


@dataclass
class TgReport:
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    ignored: int = 0
    failed: list[str] = field(default_factory=list)
    bytes: int = 0

    def summary(self) -> str:
        mb = self.bytes / 1_048_576
        out = f"{len(self.downloaded)} ta yangi darslik yuklandi ({mb:.0f} MB)"
        out += f", {len(self.skipped)} ta bor edi"
        return out + (f", {len(self.failed)} ta xato" if self.failed else "")


class _Loop:
    """One asyncio loop in a background thread: Telethon clients must stay on one loop
    across the multi-step login (send code -> sign in -> download)."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="telegram-loop", daemon=True).start()

    def run(self, coro, timeout: float | None = 600):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


class TelegramRtm:
    def __init__(self, data_dir: Path, client_factory: Callable[..., Any] | None = None) -> None:
        self.dir = data_dir / "telegram"
        self.api_file = self.dir / "api.json"
        self.session = self.dir / "nexvara"
        self._factory = client_factory
        self._loop = _Loop()
        self._client = None
        self._phone = ""
        self._code_hash = ""

    # ----- configuration -----
    def api(self) -> tuple[int, str] | None:
        try:
            data = json.loads(self.api_file.read_text(encoding="utf-8"))
            return int(data["api_id"]), str(data["api_hash"])
        except (OSError, ValueError, KeyError):
            return None

    def save_api(self, api_id: str | int, api_hash: str) -> None:
        api_id = int(str(api_id).strip())
        api_hash = str(api_hash).strip()
        if not re.fullmatch(r"[0-9a-f]{32}", api_hash):
            raise ValueError("API hash 32 ta belgidan (0-9, a-f) iborat bo‘lishi kerak")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.api_file.write_text(json.dumps({"api_id": api_id, "api_hash": api_hash}), "utf-8")

    def _make_client(self):
        api = self.api()
        if api is None:
            raise RuntimeError("Avval Telegram API ID va API hash kiriting")
        if self._factory is not None:
            return self._factory(str(self.session), *api)
        from telethon import TelegramClient

        self.dir.mkdir(parents=True, exist_ok=True)
        return TelegramClient(str(self.session), *api)

    async def _connected(self):
        if self._client is None:
            self._client = self._make_client()
        if not self._client.is_connected():
            await self._client.connect()
        return self._client

    # ----- login -----
    def status(self) -> dict[str, Any]:
        if self.api() is None:
            return {"configured": False, "authorized": False}

        async def check():
            c = await self._connected()
            return await c.is_user_authorized()

        try:
            ok = bool(self._loop.run(check(), timeout=60))
        except Exception as e:
            return {"configured": True, "authorized": False, "error": str(e)}
        return {"configured": True, "authorized": ok}

    def send_code(self, phone: str) -> None:
        phone = re.sub(r"[^\d+]", "", phone)
        if not re.fullmatch(r"\+?\d{9,15}", phone):
            raise ValueError("Telefon raqamini +998901234567 ko‘rinishida yozing")

        async def send():
            c = await self._connected()
            sent = await c.send_code_request(phone)
            return sent.phone_code_hash

        self._phone, self._code_hash = phone, self._loop.run(send(), timeout=120)

    def sign_in(self, code: str, password: str = "") -> None:
        if not self._code_hash:
            raise RuntimeError("Avval kod so‘rang")

        async def sign():
            c = await self._connected()
            try:
                await c.sign_in(self._phone, code.strip(), phone_code_hash=self._code_hash)
            except Exception as e:  # two-step verification
                if type(e).__name__ != "SessionPasswordNeededError":
                    raise
                if not password:
                    raise RuntimeError(
                        "Hisobda ikki bosqichli parol bor: parolni ham kiriting"
                    ) from None
                await c.sign_in(password=password)

        self._loop.run(sign(), timeout=120)

    # ----- download -----
    def download(
        self,
        root: Path,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> TgReport:
        return self._loop.run(self._download(root, progress, cancelled), timeout=None)

    async def _download(self, root, progress, cancelled) -> TgReport:
        c = await self._connected()
        if not await c.is_user_authorized():
            raise RuntimeError("Telegram'ga kirilmagan")
        report = TgReport()
        seen = 0
        async for msg in c.iter_messages(CHANNEL, filter=_document_filter()):
            if cancelled and cancelled():
                break
            f = getattr(msg, "file", None)
            name = getattr(f, "name", None) or ""
            caption = getattr(msg, "message", "") or ""
            seen += 1
            if not is_uzbek_textbook(name, caption):
                report.ignored += 1
                continue
            grade = grade_of(name, caption)
            folder = f"{grade}-sinf" if grade else "sinfi-noma’lum"
            dest = root / SOURCE_DIR / folder / safe_name(name)
            if progress:
                progress(seen, f"{folder}/{dest.name}")
            if dest.is_file() and dest.stat().st_size == (getattr(f, "size", None) or -1):
                report.skipped.append(dest.name)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_suffix(".part")
            try:
                await msg.download_media(file=str(part))
                with part.open("rb") as fh:
                    if fh.read(5) != b"%PDF-":
                        raise OSError("PDF emas")
                report.bytes += part.stat().st_size
                part.replace(dest)
                report.downloaded.append(dest.name)
            except Exception as e:
                part.unlink(missing_ok=True)
                report.failed.append(f"{name}: {e}")
        return report


def _document_filter():
    try:
        from telethon.tl.types import InputMessagesFilterDocument

        return InputMessagesFilterDocument
    except ImportError:  # tests without telethon
        return None
