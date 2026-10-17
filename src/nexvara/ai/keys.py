"""API keys live in Windows Credential Manager, never in files or Git."""

from __future__ import annotations

PREFIX = "NEXVARA/ai/"


class KeyStore:
    def __init__(self, prefix: str = PREFIX) -> None:
        self.prefix = prefix

    def _target(self, provider: str) -> str:
        return self.prefix + provider

    def save(self, provider: str, key: str) -> None:
        import win32cred

        key = key.strip()
        if not key:
            raise ValueError("kalit bo‘sh")
        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": self._target(provider),
                "UserName": "nexvara",
                "CredentialBlob": key,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
            },
            0,
        )

    def load(self, provider: str) -> str | None:
        import pywintypes
        import win32cred

        try:
            cred = win32cred.CredRead(self._target(provider), win32cred.CRED_TYPE_GENERIC)
        except pywintypes.error:
            return None
        blob = cred["CredentialBlob"]
        return blob.decode("utf-16-le") if isinstance(blob, bytes) else str(blob)

    def delete(self, provider: str) -> None:
        import pywintypes
        import win32cred

        try:
            win32cred.CredDelete(self._target(provider), win32cred.CRED_TYPE_GENERIC)
        except pywintypes.error:
            pass


class MemoryKeyStore(KeyStore):
    """For tests."""

    def __init__(self, keys: dict[str, str] | None = None) -> None:
        super().__init__()
        self.keys = dict(keys or {})

    def save(self, provider: str, key: str) -> None:
        if not key.strip():
            raise ValueError("kalit bo‘sh")
        self.keys[provider] = key.strip()

    def load(self, provider: str) -> str | None:
        return self.keys.get(provider)

    def delete(self, provider: str) -> None:
        self.keys.pop(provider, None)


def mask(key: str | None) -> str:
    if not key:
        return ""
    return key[:4] + "…" + key[-4:] if len(key) > 12 else "…"


_SECRET = None


def redact(text: str) -> str:
    """Hide anything that looks like an API key or token ("sk-...", "AIza...", "GOCSPX-...")."""
    global _SECRET
    import re

    if _SECRET is None:
        _SECRET = re.compile(
            r"(sk-ant-[A-Za-z0-9_\-]{6,}|sk-[A-Za-z0-9_\-]{12,}|AIza[0-9A-Za-z_\-]{20,}"
            r"|GOCSPX-[A-Za-z0-9_\-]{8,}|ghp_[A-Za-z0-9]{16,}|ya29\.[A-Za-z0-9_\-]{10,}"
            r"|Bearer\s+[A-Za-z0-9._\-]{12,})"
        )
    return _SECRET.sub(lambda m: m.group(0)[:4] + "…[yashirildi]", str(text))


class RedactingFilter:
    """logging filter: secrets never reach a log file or the console."""

    def filter(self, record) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 - a bad format string must not break logging
            return True
        clean = redact(msg)
        if clean != msg:
            record.msg, record.args = clean, ()
        return True
