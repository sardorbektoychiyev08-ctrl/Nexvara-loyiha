"""Drawings ("chizib ber", a photo of a hand-drawn sketch) and the phone security hardening.
Fake AI only: nothing is sent anywhere."""

from __future__ import annotations

import json

import pytest
from test_privacy import Wire, chat_answer
from test_remote_v1 import call, j, pair

from nexvara import drawing
from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import ChatCompletionsProvider, Provider, Reply
from nexvara.core.task import UserError

SPEC = {
    "title": "Plastina <b>",
    "width": 120,
    "height": 80,
    "shapes": [
        {"type": "rect", "x": 10, "y": 10, "width": 100, "height": 60, "w": 0.7},
        {"type": "circle", "cx": 60, "cy": 40, "r": 15},
        {"type": "line", "x1": 60, "y1": 5, "x2": 60, "y2": 75, "style": "center"},
        {"type": "dim", "x1": 10, "y1": 70, "x2": 110, "y2": 70, "offset": 8},
        {"type": "arc", "cx": 60, "cy": 40, "r": 20, "start": 0, "end": 90},
        {"type": "text", "x": 12, "y": 8, "text": "<script>alert(1)</script>", "size": 4},
    ],
}


def _jpeg_with_gps() -> bytes:
    """A real JPEG with an EXIF block that carries a fake GPS marker."""
    import fitz

    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 30), False)
    pix.set_rect(pix.irect, (200, 50, 50))
    jpg = pix.tobytes("jpeg")
    exif = b"Exif\x00\x00" + b"GPSLatitude=41.3111;GPSLongitude=69.2797" * 3
    seg = b"\xff\xe1" + (len(exif) + 2).to_bytes(2, "big") + exif
    return jpg[:2] + seg + jpg[2:]


# ---------------- spec, renderer, export ----------------
def test_validate_rejects_bad_specs():
    for bad in [
        {"shapes": []},
        {"shapes": [{"type": "script", "x": 1}]},
        {"shapes": [{"type": "circle", "cx": float("nan"), "cy": 1, "r": 2}]},
        {"shapes": [{"type": "line", "x1": 0, "y1": 0, "x2": 1e9, "y2": 0}]},
        {"shapes": [{"type": "rect", "x": 0}]},
        {"shapes": [{"type": "line", "x1": 0, "y1": 0, "x2": 1, "y2": 1}] * 401},
        "not a dict",
    ]:
        with pytest.raises(ValueError):
            drawing.validate(bad)


def test_svg_is_our_own_and_escaped(tmp_path):
    svg = drawing.render_svg(SPEC)
    assert "<script" not in svg and "&lt;script&gt;" in svg and "&lt;b&gt;" in svg
    assert svg.count("<circle") == 1 and svg.count("<path") >= 2  # center line, arc
    out = drawing.export(SPEC, tmp_path)
    assert open(out["png"], "rb").read(4) == b"\x89PNG"
    assert open(out["pdf"], "rb").read(4) == b"%PDF"


def test_parse_reply_tolerates_fences_and_rejects_garbage():
    spec = drawing.parse_reply("```json\n" + json.dumps(SPEC) + "\n```")
    assert len(spec["shapes"]) == 6 and "foo" not in spec
    with pytest.raises(UserError):
        drawing.parse_reply("<svg onload=alert(1)></svg>")


def test_photo_loses_exif_and_is_downscaled(tmp_path):
    p = tmp_path / "eskiz.jpg"
    raw = _jpeg_with_gps()
    assert b"GPSLatitude" in raw
    p.write_bytes(raw)
    mime, b64 = drawing.clean_image(p)
    import base64

    clean = base64.b64decode(b64)
    assert mime == "image/jpeg" and clean[:2] == b"\xff\xd8"
    assert b"GPSLatitude" not in clean and b"Exif" not in clean
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(UserError):
        drawing.clean_image(bad)


def test_requests_are_recognised():
    assert drawing.is_drawing_request("Velosiped g‘ildiragi chizmasini chizib ber")
    assert drawing.is_drawing_request("shu rasmdagi qo‘lda chizilgan eskizni mukammal chiz")
    assert not drawing.is_drawing_request("Hisobot.xlsx ni och va PDF qil")


# ---------------- providers: pictures ----------------
def test_openai_and_deepseek_image_input_shape():
    wire = Wire(chat_answer("{}"))
    msgs = [{"role": "user", "content": "chiz", "images": [{"mime": "image/jpeg", "data": "QUJD"}]}]
    ChatCompletionsProvider("openai", "k", opener=wire).complete("m", "s", msgs, 100)
    body = json.loads(wire.bodies[0])
    parts = body["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "chiz"}
    assert parts[1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
    ChatCompletionsProvider("deepseek", "k", opener=wire).complete("deepseek-flash", "s", msgs, 100)
    assert json.loads(wire.bodies[-1])["messages"][1]["content"][1] == parts[1]


# ---------------- in chat ----------------
class Draftsman(Provider):
    def __init__(self):
        self.calls = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append(messages)
        return Reply(json.dumps(SPEC), model, 3000, 1500)

    def list_models(self):
        return []


def _api(tmp_path, keys):
    from nexvara.ai.router import AiRouter, Ledger
    from nexvara.app.api import Api
    from nexvara.appdata import Settings

    pro = Draftsman()
    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(keys), Ledger(tmp_path / "l.db"),
                 factory=lambda n, k: pro)  # fmt: skip
    r.settings.update({"ai": {"enabled": True}})
    return Api(overrides={"ai_router": r}, output_dir=tmp_path / "out"), pro


def test_photo_sketch_is_redrawn_after_consent(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    api, pro = _api(tmp_path, {"openai": "sk-test-openai-123456"})
    photo = tmp_path / "eskiz.jpg"
    photo.write_bytes(_jpeg_with_gps())
    api.set_context_file(str(photo))
    out = api.chat("Shu rasmdagi qo‘lda chizilgan chala chizmani mukammal chizib ber")
    assert out.get("confirm") and "GPS" in out["reply"] and "shaxsiy" in out["reply"]
    assert pro.calls == []  # nothing is sent before "Ha"
    done = api.confirm_ai(out["confirm"], True)
    task = api._runner.get(done["task"]["id"])
    assert task.wait(30) and task.status == "succeeded", task.error
    res = task.result
    assert res["path"].endswith(".png") and res["pdf"].endswith(".pdf")
    img = pro.calls[0][0]["images"][0]
    assert img["mime"] == "image/jpeg" and "GPSLatitude" not in img["data"]
    assert api._router().ledger.recent()[0]["purpose"] == "Chizma"


def test_text_drawing_without_picture_and_refusals(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    api, pro = _api(tmp_path, {"anthropic": "sk-ant-test-1234567890"})
    out = api.chat("Gayka chizmasini chizib ber")
    assert out.get("confirm") and "Rasm" not in out["reply"]
    assert api.confirm_ai(out["confirm"], False)["reply"].startswith("Bekor")
    assert pro.calls == []
    # DeepSeek Flash has vision, but this powerful drawing task needs a stronger tier.
    (tmp_path / "b").mkdir()
    api2, _pro2 = _api(tmp_path / "b", {"deepseek": "sk-deepseek-test-123456"})
    photo = tmp_path / "e.png"
    photo.write_bytes(b"\x89PNG fake")
    api2.set_context_file(str(photo))
    out = api2.chat("shu rasmdagi eskizni chizib ber")
    assert "mos" in out["reply"] and not out.get("confirm") and not _pro2.calls
    # A school subject is a test request, not a drawing.
    assert drawing.is_drawing_request("7-sinf chizmachilik 20 ta test")
    assert "Chizmani AI tuzadi" not in api.chat("7-sinf chizmachilik 20 ta test")["reply"]


def test_drawing_needs_ai():
    from nexvara.app.api import Api

    out = Api().chat("Uy chizmasini chizib ber")
    assert "AI kerak" in out["reply"]


# ---------------- phone security hardening ----------------
def test_blocked_uploads():
    from nexvara.remote import blocked_upload

    for bad in ("virus.exe", "hisobot.pdf.exe", "a.PS1", "b.bat ", "c.lnk.", "x.vbs", "y.msi"):
        assert blocked_upload(bad), bad
    for good in ("Hisobot.xlsx", "rasm.jpg", "kitob.pdf", "arxiv.zip", "xat.docx"):
        assert not blocked_upload(good), good


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.remote import DeviceStore

    api = Api(TaskRunner(), overrides={"device_store": DeviceStore(tmp_path / "app.db"),
                                       "remote_port": 0})  # fmt: skip
    assert api.devices_start()["ok"]
    srv = api._server()
    srv.host_url = f"https://127.0.0.1:{srv.port}"
    yield api, srv
    api.devices_stop()


def test_phone_cannot_upload_programs_and_token_guessing_is_throttled(server):
    import hashlib
    from urllib.parse import quote

    _api, srv = server
    token = pair(srv)
    body = b"MZ"
    h = {
        "X-Filename": quote("hisobot.pdf.exe"),
        "X-Content-SHA256": hashlib.sha256(body).hexdigest(),
    }
    r = call(srv, "POST", "/api/v1/files", token=token, raw=body, headers=h)
    assert r[0] == 400 and "qabul qilinmaydi" in j(r)["error"]["message"]
    assert r[2]["X-Frame-Options"] == "DENY" and r[2]["Referrer-Policy"] == "no-referrer"
    codes = [call(srv, "GET", "/api/v1/session", token=f"guess-{i}")[0] for i in range(22)]
    assert codes[:20] == [401] * 20 and codes[-1] == 429
    assert call(srv, "GET", "/api/v1/session", token=token)[0] == 200  # the real phone still works
