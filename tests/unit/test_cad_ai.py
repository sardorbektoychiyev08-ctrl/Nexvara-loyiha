"""«AI bilan tuzatish»: a rough sketch becomes a clean drawing — by the AI (fake provider here,
nothing is sent anywhere) or, without AI, by NEXVARA's own tidy-up."""

from __future__ import annotations

import json
import math

from nexvara import cad, cad_ai
from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import Provider, Reply
from nexvara.app.api_cad import json_to_doc

ROUGH = {
    "units": "mm",
    "layers": [{"name": "0", "color": 7}],
    "entities": [  # a wobbly 100 x 60 box (ends do not quite meet) and a hole
        {"type": "line", "layer": "0", "x1": 0.4, "y1": 0.3, "x2": 99.2, "y2": 2.1},
        {"type": "line", "layer": "0", "x1": 100.6, "y1": 1.2, "x2": 101.9, "y2": 59.4},
        {"type": "line", "layer": "0", "x1": 100.8, "y1": 60.2, "x2": 1.1, "y2": 61.3},
        {"type": "line", "layer": "0", "x1": -0.6, "y1": 60.4, "x2": 0.9, "y2": 1.4},
        {"type": "circle", "layer": "0", "cx": 50.6, "cy": 29.7, "r": 9.8},
    ],
}  # fmt: skip

CLEAN = {
    "entities": [
        {
            "type": "polyline",
            "points": [[0, 0, 0], [100, 0, 0], [100, 60, 0], [0, 60, 0]],
            "closed": True,
        },
        {"type": "circle", "cx": 50, "cy": 30, "r": 10},
        {
            "type": "ldim",
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "bx": 50,
            "by": -10,
            "rot": 0,
            "label": "",
        },
        {"type": "rdim", "cx": 50, "cy": 30, "r": 10, "angle": 45, "diameter": True, "label": ""},
    ]
}


def test_offline_tidy_straightens_joins_and_rounds():
    fixed, n = cad_ai.beautify(ROUGH)
    assert n > 5
    lines = [e for e in fixed["entities"] if e["type"] == "line"]
    for e in lines:  # every edge exactly horizontal or vertical
        assert e["x1"] == e["x2"] or e["y1"] == e["y2"], e
    ends = {(e["x1"], e["y1"]) for e in lines} | {(e["x2"], e["y2"]) for e in lines}
    assert len(ends) == 4  # the four corners meet
    hole = next(e for e in fixed["entities"] if e["type"] == "circle")
    assert (hole["cx"], hole["cy"], hole["r"]) == (51, 30, 10)
    assert cad.audit(json_to_doc(fixed)) == []


class Draftsman(Provider):
    def __init__(self, answer):
        self.answer, self.sent = answer, []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.sent.append(messages[0]["content"])
        return Reply(self.answer, model, 2000, 800)

    def list_models(self):
        return []


def _api(tmp_path, answer, keys):
    from nexvara.ai.router import AiRouter, Ledger
    from nexvara.app.api import Api
    from nexvara.appdata import Settings

    pro = Draftsman(answer)
    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(keys), Ledger(tmp_path / "l.db"),
                 factory=lambda n, k: pro)  # fmt: skip
    r.settings.update({"ai": {"enabled": True}})
    return Api(overrides={"ai_router": r}, output_dir=tmp_path), pro


def test_ai_redraws_the_sketch_and_the_answer_is_validated(tmp_path):
    api, pro = _api(tmp_path, "```json\n" + json.dumps(CLEAN) + "\n```",
                    {"gemini": "AIza-test-gemini-1234567"})  # fmt: skip
    out = api.cad_ai_fix(ROUGH, "100x60 plastina, markazida 20 mm teshik")
    assert out["ok"] and out["by"] == "ai" and "bepul" in out["reply"]  # Gemini free mode
    kinds = [e["type"] for e in out["drawing"]["entities"]]
    assert kinds == ["polyline", "circle", "ldim", "rdim"]
    assert "100x60 plastina" in pro.sent[0] and '"x2": 99.2' in pro.sent[0]
    # a broken or hostile answer is refused, not drawn
    api2, _ = _api(tmp_path / "b", '{"entities": [{"type": "circle", "cx": 0, "cy": 0, "r": -3}]}',
                   {"gemini": "AIza-test-gemini-1234567"})  # fmt: skip
    (tmp_path / "b").mkdir(exist_ok=True)
    bad = api2.cad_ai_fix(ROUGH)
    assert not bad["ok"] and "AI javobi" in bad["error"]


def test_without_ai_the_pc_tidies_it_itself(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    out = Api(output_dir=tmp_path).cad_ai_fix(ROUGH, "")
    assert out["ok"] and out["by"] == "offline" and "AI ulanmagan" in out["reply"]
    assert not Api(output_dir=tmp_path).cad_ai_fix({"entities": []})["ok"]


def test_phone_route(tmp_path, monkeypatch):
    from test_remote_v1 import call, j, pair

    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.remote import DeviceStore

    api = Api(TaskRunner(), overrides={"device_store": DeviceStore(tmp_path / "app.db"),
                                       "remote_port": 0})  # fmt: skip
    assert api.devices_start()["ok"]
    try:
        srv = api._server()
        srv.host_url = f"https://127.0.0.1:{srv.port}"
        token = pair(srv)
        r = call(srv, "POST", "/api/v1/cad/ai", {"drawing": ROUGH, "note": ""}, token)
        assert r[0] == 200, r[1]
        data = j(r)["data"]
        assert data["by"] == "offline" and all(
            not math.isnan(e.get("x1", 0)) for e in data["drawing"]["entities"]
        )
        assert call(srv, "POST", "/api/v1/cad/ai", {"drawing": {}}, token)[0] == 400
    finally:
        api.devices_stop()


def test_templates_are_clean_autocad_drawings(tmp_path, monkeypatch):
    import pytest

    from nexvara import cad_templates
    from nexvara.app.api import Api

    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    api = Api(output_dir=tmp_path)
    assert {t["id"] for t in api.cad_templates()} == {
        "A4",
        "A3",
        "bolt",
        "nut",
        "washer",
        "bearing",
    }
    for name, size in (("A4", ""), ("A3", ""), ("bolt", "M10x50"), ("nut", "M12"),
                       ("washer", "m8"), ("bearing", "6204")):  # fmt: skip
        out = api.cad_template(name, size)
        assert out["ok"], (name, out)
        assert cad.audit(json_to_doc(out["drawing"])) == []
    frame = cad_templates.make("A4")["entities"]
    assert frame[0]["points"][2][:2] == [210, 297]  # the A4 sheet itself
    bolt = cad_templates.make("bolt", "M10x50")["entities"]
    assert any(e.get("label") == "M10" for e in bolt)
    assert any("16" == str(int(cad_templates.METRIC[10][0])) for _ in [0])  # s = 16 for M10
    assert not api.cad_template("bolt", "M7")["ok"]
    assert "6200" in api.cad_template("bearing", "9999")["error"]
    with pytest.raises(ValueError):
        cad_templates.make("nimadir")
