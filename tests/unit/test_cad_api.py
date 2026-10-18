"""DXF ↔ the editable CAD page format, using only throwaway files."""

from __future__ import annotations

import pytest

from nexvara import cad, drawing_offline
from nexvara.app.api import Api
from nexvara.app.api_cad import doc_to_json, json_to_doc


def test_generated_part_opens_in_editor_and_saves_as_clean_dxf(tmp_path):
    spec = drawing_offline.build_spec(
        drawing_offline.parse("120x80 plastina, markazida 20 mm teshik chiz")
    )
    source = tmp_path / "asl.dxf"
    cad.build(spec).saveas(source)
    api = Api(output_dir=tmp_path)
    opened = api.cad_open(str(source))
    assert opened["ok"] and opened["drawing"]["units"] == "mm"
    assert opened["drawing"]["entities"]
    kinds = {e["type"] for e in opened["drawing"]["entities"]}
    assert {"circle", "polyline", "dim", "text"} <= kinds
    target = tmp_path / "tahrir.dxf"
    saved = api.cad_save(opened["drawing"], str(target))
    assert saved["ok"] and target.exists()
    back = cad.read(target)
    assert cad.audit(back) == []
    assert saved["entities"] == len(back.modelspace())
    assert len(doc_to_json(back)["entities"]) == len(opened["drawing"]["entities"])


def test_editor_entities_round_trip_and_invalid_data_is_rejected(tmp_path):
    api = Api(output_dir=tmp_path)
    data = {
        "units": "mm",
        "layers": [{"name": "KONTUR", "color": 3, "lineweight": 35, "visible": True}],
        "entities": [
            {"type": "line", "layer": "KONTUR", "x1": 0, "y1": 0, "x2": 100, "y2": 0},
            {
                "type": "polyline",
                "layer": "KONTUR",
                "points": [[0, 0, 0], [20, 0, 0], [20, 10, 0]],
                "closed": True,
            },
            {"type": "circle", "layer": "KONTUR", "cx": 10, "cy": 10, "r": 5},
            {"type": "arc", "layer": "KONTUR", "cx": 20, "cy": 20, "r": 4, "start": 0, "end": 90},
            {
                "type": "text",
                "layer": "KONTUR",
                "x": 0,
                "y": 15,
                "text": "O‘lcham",
                "h": 2.5,
                "rot": 0,
            },
            {
                "type": "dim",
                "layer": "KONTUR",
                "x1": 0,
                "y1": 0,
                "x2": 100,
                "y2": 0,
                "offset": 10,
                "label": "",
            },
        ],
    }
    path = tmp_path / "chizma.dxf"
    assert api.cad_save(data, str(path))["ok"]
    result = api.cad_open(str(path))
    assert result["ok"]
    assert [e["type"] for e in result["drawing"]["entities"]] == [
        e["type"] for e in data["entities"]
    ]
    assert cad.audit(json_to_doc(result["drawing"])) == []
    assert not api.cad_save(
        {"entities": [{"type": "circle", "cx": 0, "cy": 0, "r": -1}]}, str(tmp_path / "bad.dxf")
    )["ok"]
    assert not api.cad_save({"entities": [{"type": "unknown"}]}, str(tmp_path / "bad.dxf"))["ok"]
    assert not (tmp_path / "bad.dxf").exists()


@pytest.mark.parametrize("bad", [None, [], {"entities": "line"}, {"entities": [{"type": "line"}]}])
def test_bad_editor_data_rejected(bad):
    with pytest.raises(ValueError):
        json_to_doc(bad)
