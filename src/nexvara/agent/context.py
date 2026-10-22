"""What the agent remembers about the current conversation.

Lets the user talk naturally across messages: "Hisobot.xlsx ni PDF qil" → "uni Arxiv papkasiga
ko‘chir" (uni = the PDF just made), "topilgan fayllarni ZIP qil", "xuddi shunday Savdo.xlsx
bilan ham qil". The AI planner also gets the last turns from here.
"""

from __future__ import annotations

import re
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexvara.knowledge.textnorm import fold

# Words that point at "the thing we just talked about".
_REF_RESULT = re.compile(
    r"\b(uni|uning|shuni|natija\w*|yangi fayl\w*|hosil bolgan fayl\w*|tayyor fayl\w*)\b"
)
_REF_FILE = re.compile(r"\b(ushbu fayl\w*|shu fayl\w*|osha fayl\w*|bu fayl\w*)\b")
_REF_FILES = re.compile(r"\b(topilgan\w*|ularni|shularni|osha fayllar\w*|shu fayllar\w*)\b")
_REF_FOLDER = re.compile(r"\b(shu papka\w*|osha papka\w*|bu papka\w*)\b")


@dataclass
class Context:
    file: str = ""  # the file the conversation is about ("shu fayl")
    image: str = ""  # last photo; kept when its Excel/Word result becomes the current file
    result: str = ""  # the last output file a task produced
    files: list[str] = field(default_factory=list)  # last search / list result
    folder: str = ""
    dashboard: str = ""  # saved NEXVARA BI dashboard (file)
    workflow: str = ""  # workflow name
    command: str = ""  # last Office command text ("xuddi shunday ...")
    turns: deque = field(default_factory=lambda: deque(maxlen=12))
    seen_dirs: deque = field(default_factory=lambda: deque(maxlen=8))
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_turn(self, role: str, text: str) -> None:
        if text:
            with self._lock:
                self.turns.append({"role": role, "text": text[:1500]})

    def task_done(self, snap: dict[str, Any]) -> None:
        """Called when any task finishes: its output becomes "uni"/"natija"."""
        if snap.get("status") != "succeeded":
            return
        res = snap.get("result") or {}
        for key in ("pdf", "path", "zip", "out"):
            p = res.get(key)
            if isinstance(p, str) and p and Path(p).exists():
                with self._lock:
                    self.result = p  # "uni", "natijani"; "shu fayl" stays the source file
                return

    def recent_dirs(self) -> list[Path]:
        """Folders of the files and results this conversation used (newest first)."""
        out: list[Path] = []
        for p in (self.file, self.result, *self.files[:5], *self.seen_dirs):
            if not p:
                continue
            d = Path(p) if Path(p).is_dir() else Path(p).parent
            if d not in out and d.is_dir():
                out.append(d)
        if self.folder and Path(self.folder).is_dir() and Path(self.folder) not in out:
            out.insert(1 if out else 0, Path(self.folder))  # after the current file's folder
        return out[:12]

    def remember_dir(self, path: str) -> None:
        d = str(Path(path).parent if Path(path).is_file() else path)
        with self._lock:
            if d in self.seen_dirs:
                self.seen_dirs.remove(d)
            self.seen_dirs.appendleft(d)

    def set_files(self, paths: list[str]) -> None:
        with self._lock:
            self.files = list(paths)
            if len(paths) == 1:
                self.file = paths[0]

    # ----- resolving references -----
    def refers_to_file(self, text: str) -> bool:
        f = fold(text)
        return bool(_REF_FILE.search(f) or _REF_RESULT.search(f))

    def refers_to_files(self, text: str) -> bool:
        return bool(_REF_FILES.search(fold(text)))

    def refers_to_folder(self, text: str) -> bool:
        return bool(_REF_FOLDER.search(fold(text)))

    def current_file(self, text: str = "") -> str:
        """ "uni"/"natijani" -> the last output; "shu fayl" -> the file being worked on."""
        if _REF_RESULT.search(fold(text)) and self.result:
            return self.result
        return self.file or self.result

    def snapshot(self) -> dict[str, Any]:
        """For the AI planner (what "it", "those files", "that folder" mean right now)."""
        return {
            "file": self.file,
            "open_image": self.image,
            "last_result": self.result,
            "files": self.files[:10],
            "folder": self.folder,
            "dashboard": self.dashboard,
            "workflow": self.workflow,
        }
