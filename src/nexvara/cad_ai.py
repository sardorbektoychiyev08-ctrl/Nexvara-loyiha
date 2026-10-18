"""«AI bilan tuzatish»: a rough drawing (finger or mouse) becomes the clean drawing the user meant.

With AI: the drawing's own JSON (no picture: texts are masked like any other request) and the
user's note go to the AI, which returns a clean drawing in the same JSON; it is validated by
api_cad.json_to_doc (nothing the AI writes is trusted blindly) before the user sees it.
Without AI (no key, or no internet): `beautify()` does what a draughtsman does by hand —
straight angles, joined ends, round sizes, concentric circles.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

KINDS = {"line", "polyline", "circle", "arc", "ellipse", "text", "dim", "ldim", "rdim", "hatch"}

PROMPT = """You are a precise technical draftsman. The user drew a rough sketch by hand (finger or
mouse). Lines are wobbly, angles are almost right, ends almost meet, sizes are not round.
Redraw it as the clean, complete technical drawing the user MEANT:
- straight lines exactly horizontal/vertical (or exactly 30/45/60 degrees) when they are close;
- parallel and perpendicular where intended; ends that almost meet meet exactly;
- round sizes (nearest 1 mm, or 5 mm for big sizes); circles that should share a centre share it;
- symmetric parts symmetric; finish obviously unfinished shapes; keep the size and position;
- add linear dimensions (type "ldim") for the main sizes and radius/diameter ("rdim") for circles.
Return ONLY one JSON object, no prose: {"entities": [...]} in millimetres, Y axis UP, with:
 {"type":"line","x1","y1","x2","y2"}
 {"type":"polyline","points":[[x,y,0],...],"closed":true|false}
 {"type":"circle","cx","cy","r"}  {"type":"arc","cx","cy","r","start","end"}  (degrees, CCW)
 {"type":"text","x","y","text","h"}
 {"type":"ldim","x1","y1","x2","y2","bx","by","rot":0|90,"label":""}   (bx,by: where the
   dimension line goes, about 10 mm outside the part)
 {"type":"rdim","cx","cy","r","angle","diameter":true|false,"label":""}
Texts and labels in Uzbek (Latin). At most 400 entities."""


def ai_messages(drawing: dict[str, Any], note: str) -> tuple[str, list[dict[str, str]]]:
    ents = [e for e in drawing.get("entities") or [] if isinstance(e, dict)][:600]
    slim = [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.items() if k != "layer"}
            for e in ents]  # fmt: skip
    task = (f"What the user wanted to draw: {note.strip() or '(not said — infer it)'}\n"
            "The rough sketch: " + json.dumps({"entities": slim}, ensure_ascii=False))  # fmt: skip
    return PROMPT, [{"role": "user", "content": task}]


def parse_reply(text: str, layers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The AI's JSON as an editor drawing, checked by the DXF writer (ValueError if bad)."""
    from nexvara.app.api_cad import json_to_doc

    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("AI chizma qaytarmadi")
    data = json.loads(m.group(0))
    ents = [
        e for e in (data.get("entities") or []) if isinstance(e, dict) and e.get("type") in KINDS
    ]
    if not ents:
        raise ValueError("AI chizmasida obyekt yo‘q")
    if len(ents) > 600:
        raise ValueError("AI juda ko‘p obyekt qaytardi")
    for e in ents:
        e["layer"] = "0"
    base = [{"name": "0", "color": 7, "lineweight": 35, "visible": True}]
    drawing = {"units": "mm", "layers": layers or base, "entities": ents}
    json_to_doc(drawing)  # raises ValueError on anything invalid
    return drawing


# ---------------- without AI ----------------
def _round(v: float, step: float) -> float:
    return round(round(v / step) * step, 4)


def beautify(drawing: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """(cleaner drawing, number of fixes) — what a draughtsman does by hand: ends that almost
    meet become one corner, nearly level/upright edges become exactly level/upright (their
    corners share one X or Y), sizes are rounded, near-concentric circles share a centre."""
    ents = [json.loads(json.dumps(e)) for e in drawing.get("entities") or [] if isinstance(e, dict)]
    refs: list[tuple[dict[str, Any], Any]] = []  # (entity, ("x1","y1") or point index)
    for e in ents:
        if e.get("type") == "line":
            refs += [(e, ("x1", "y1")), (e, ("x2", "y2"))]
        elif e.get("type") == "polyline":
            refs += [(e, i) for i in range(len(e.get("points") or []))]

    def get(r: tuple[dict[str, Any], Any]) -> tuple[float, float]:
        e, k = r
        return (e[k[0]], e[k[1]]) if isinstance(k, tuple) else tuple(e["points"][k][:2])

    pts = [get(r) for r in refs]
    for e in ents:
        if e.get("type") in ("circle", "arc"):
            pts += [(e["cx"] - e["r"], e["cy"] - e["r"]), (e["cx"] + e["r"], e["cy"] + e["r"])]
    if not pts:
        return drawing, 0
    size = max(max(p[0] for p in pts) - min(p[0] for p in pts),
               max(p[1] for p in pts) - min(p[1] for p in pts), 1.0)  # fmt: skip
    step = 5.0 if size > 400 else 1.0
    join = max(size * 0.03, 1.5)
    fixes = 0

    # 1) corners: end points that almost meet become one node
    node_of: list[int] = []
    nodes: list[list[float]] = []
    members: list[list[int]] = []
    for i, p in enumerate(pts[: len(refs)]):
        hit = next((n for n, q in enumerate(nodes) if math.dist(p, q) <= join), None)
        if hit is None:
            nodes.append(list(p))
            members.append([i])
            node_of.append(len(nodes) - 1)
        else:
            members[hit].append(i)
            k = len(members[hit])
            nodes[hit] = [
                (nodes[hit][0] * (k - 1) + p[0]) / k,
                (nodes[hit][1] * (k - 1) + p[1]) / k,
            ]
            node_of.append(hit)
            fixes += 1
    # 2) edges between nodes; nearly level edges share Y, nearly upright ones share X
    edges: list[tuple[int, int]] = []
    for e in ents:
        if e.get("type") == "line":
            i = next(k for k, r in enumerate(refs) if r[0] is e and r[1] == ("x1", "y1"))
            edges.append((node_of[i], node_of[i + 1]))
        elif e.get("type") == "polyline":
            idx = [k for k, r in enumerate(refs) if r[0] is e]
            pairs = list(zip(idx, idx[1:], strict=False))
            if e.get("closed") and len(idx) > 2:
                pairs.append((idx[-1], idx[0]))
            edges += [(node_of[a], node_of[b]) for a, b in pairs]
    parent_x = list(range(len(nodes)))
    parent_y = list(range(len(nodes)))

    def find(par: list[int], a: int) -> int:
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a, b in edges:
        if a == b:
            continue
        ang = abs(math.degrees(math.atan2(nodes[b][1] - nodes[a][1], nodes[b][0] - nodes[a][0])))
        ang = min(ang, 180 - ang)  # 0 = level, 90 = upright
        if ang <= 7:
            parent_y[find(parent_y, a)] = find(parent_y, b)
            fixes += ang > 1e-6
        elif ang >= 83:
            parent_x[find(parent_x, a)] = find(parent_x, b)
            fixes += ang < 90 - 1e-6
    for par, axis in ((parent_x, 0), (parent_y, 1)):
        groups: dict[int, list[int]] = {}
        for n in range(len(nodes)):
            groups.setdefault(find(par, n), []).append(n)
        for g in groups.values():
            v = _round(sum(nodes[n][axis] for n in g) / len(g), step)
            for n in g:
                nodes[n][axis] = v
    for i, r in enumerate(refs):  # write the nodes back
        x, y = nodes[node_of[i]]
        e, k = r
        if isinstance(k, tuple):
            e[k[0]], e[k[1]] = x, y
        else:
            e["points"][k][0], e["points"][k][1] = x, y
    # 3) a polyline whose ends now meet is a closed shape
    for e in ents:
        p = e.get("points") or []
        if (
            e.get("type") == "polyline"
            and len(p) > 3
            and not e.get("closed")
            and p[0][:2] == p[-1][:2]
        ):
            e["points"], e["closed"] = p[:-1], True
            fixes += 1
    # 4) circles: concentric, round centre and radius
    circles = [e for e in ents if e.get("type") in ("circle", "arc")]
    for i, c in enumerate(circles):
        for d in circles[:i]:
            if (c["cx"], c["cy"]) != (d["cx"], d["cy"]) and math.dist(
                (c["cx"], c["cy"]), (d["cx"], d["cy"])
            ) <= join:
                c["cx"], c["cy"] = d["cx"], d["cy"]
                fixes += 1
        c["cx"], c["cy"] = _round(c["cx"], step), _round(c["cy"], step)
        r = max(_round(c["r"], 0.5 if c["r"] < 20 else step), 0.5)
        fixes += r != c["r"]
        c["r"] = r
    return {**drawing, "entities": ents}, int(fixes)
