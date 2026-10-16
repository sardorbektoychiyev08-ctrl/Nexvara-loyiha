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
