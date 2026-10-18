"""Phone «Chizma»: a drawing made on the phone becomes a clean AutoCAD DXF + PDF + PNG on the
PC, the PC's drawings can be listed and opened, and nothing outside Chizmalar is readable."""

from __future__ import annotations

from test_remote_v1 import call, env, j, pair  # noqa: F401 - pytest fixture

PHONE_DRAWING = {
    "units": "mm",
    "layers": [{"name": "0", "color": 7, "lineweight": 25, "visible": True}],
    "entities": [
        {"type": "polyline", "layer": "0", "closed": True,
         "points": [[0, 0, 0], [120, 0, 0], [120, 80, 0], [0, 80, 0]]},
        {"type": "circle", "layer": "0", "cx": 60, "cy": 40, "r": 15},
        {"type": "ldim", "layer": "0", "x1": 0, "y1": 0, "x2": 120, "y2": 0, "bx": 60,
         "by": -12, "rot": 0, "label": ""},
        {"type": "text", "layer": "0", "x": 2, "y": 85, "text": "Telefonda chizildi", "h": 3.5},
    ],
}  # fmt: skip


def test_phone_drawing_is_saved_as_dxf_and_opens_on_the_pc(env, tmp_path):  # noqa: F811
    from nexvara import cad

    api, srv, _ = env
    token = pair(srv)
    r = call(srv, "POST", "/api/v1/cad", {"name": "Plastina", "drawing": PHONE_DRAWING}, token)
    assert r[0] == 200, r[1]
    out = j(r)["data"]
    assert (
        out["dxf"].endswith(".dxf") and out["pdf"].endswith(".pdf") and out["png"].endswith(".png")
    )
    assert out["entities"] == 4
    doc = cad.read(out["dxf"])
    assert cad.audit(doc) == [] and cad.summary(doc)["types"]["DIMENSION"] == 1
    assert {"kind": "cad_open", "path": out["dxf"]} in api.ui_events()
    # the list and one drawing back on the phone
    lst = j(call(srv, "GET", "/api/v1/cad", token=token))["data"]["drawings"]
    assert lst[0]["path"] == out["dxf"]
    one = j(call(srv, "GET", f"/api/v1/cad/drawing?path={lst[0]['name']}", token=token))["data"]
    kinds = {e["type"] for e in one["drawing"]["entities"]}
    assert kinds - {"dim", "ldim"} == {"polyline", "circle", "text"} and kinds & {"dim", "ldim"}
    assert j(call(srv, "POST", "/api/v1/cad/open", {"path": out["dxf"]}, token))["data"]["opened"]


def test_phone_cannot_read_files_outside_the_drawings_folder(env, tmp_path):  # noqa: F811
    _api, srv, _ = env
    token = pair(srv)
    secret = tmp_path / "boshqa.dxf"
    secret.write_text("0\nEOF\n", encoding="utf-8")
    for path in (str(secret), "..\\boshqa.dxf", "C:\\Windows\\win.ini"):
        r = call(srv, "GET", f"/api/v1/cad/drawing?path={path}", token=token)
        assert r[0] == 404, (path, r[1])
    r = call(srv, "POST", "/api/v1/cad", {"name": "x", "drawing": {"entities": []}}, token)
    assert r[0] == 400
    bad = {"entities": [{"type": "circle", "cx": 0, "cy": 0, "r": -5}]}
    assert call(srv, "POST", "/api/v1/cad", {"name": "x", "drawing": bad}, token)[0] == 400
    assert call(srv, "GET", "/api/v1/cad")[0] == 401  # a paired phone only
