"""Session base for Word and PowerPoint.

Word usually starts a fresh process per DispatchEx, but PowerPoint is single-instance:
DispatchEx attaches to the user's running PowerPoint. So a session only closes the
documents it created/opened, and quits the application only if it started it.
"""

from __future__ import annotations

import logging
from typing import Any

import pythoncom
import win32com.client

log = logging.getLogger(__name__)


class OfficeSession:
    prog_id = ""

    def __init__(self, visible: bool = True, keep_open: bool = False) -> None:
        self.visible = visible
        self.keep_open = keep_open
        self.app: Any = None
        self._owned: list[str] = []  # FullName of documents we created/opened
        self._preexisting = False

    # --- subclass hooks ---
    def _collection(self) -> Any:
        raise NotImplementedError

    def _close_doc(self, doc: Any) -> None:
        raise NotImplementedError

    def _quit(self) -> None:
        self.app.Quit()

    # --- lifecycle ---
    def __enter__(self) -> OfficeSession:
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.DispatchEx(self.prog_id)
            self._preexisting = self._collection().Count > 0
            self._prepare()
        except Exception:
            self.app = None
            pythoncom.CoUninitialize()
            raise
        return self

    def _prepare(self) -> None:
        pass

    def own(self, doc: Any) -> Any:
        self._owned.append(str(doc.FullName))
        return doc

    def disown(self, doc: Any) -> None:
        name = str(doc.FullName)
        if name in self._owned:
            self._owned.remove(name)

    def __exit__(self, *exc: object) -> None:
        try:
            if self.app is not None and not (self.keep_open and self.visible):
                coll = self._collection()
                # Iterate by index from the end; keep no Python reference past Quit().
                for i in range(coll.Count, 0, -1):
                    if str(coll(i).FullName) in self._owned:
                        log.info("%s: closing %s", self.prog_id, coll(i).FullName)
                        self._close_doc(coll(i))
                del coll
                if not self._preexisting and self._collection().Count == 0:
                    log.info("%s: quitting", self.prog_id)
                    self._quit()
                    log.info("%s: quit returned", self.prog_id)
        except Exception:
            log.exception("Error while closing %s", self.prog_id)
        finally:
            self.app = None
            pythoncom.CoUninitialize()

    @property
    def version(self) -> str:
        return str(self.app.Version)
