"""SmartArt diagrams for Word and PowerPoint, chosen by their stable layout Id (the names are
translated in Russian or Uzbek Office, the Ids are not).

Layouts (Microsoft's built-in Ids): process1 = Basic Process, cycle2 = Basic Cycle,
hierarchy1 = Hierarchy, default = Basic Block List. In a hierarchy the first item is the top
and the others go below it; in the other layouts every item is one shape, in order.
"""

from __future__ import annotations

from typing import Any

LAYOUTS = {
    "process": "urn:microsoft.com/office/officeart/2005/8/layout/process1",
    "cycle": "urn:microsoft.com/office/officeart/2005/8/layout/cycle2",
    "hierarchy": "urn:microsoft.com/office/officeart/2005/8/layout/hierarchy1",
    "list": "urn:microsoft.com/office/officeart/2005/8/layout/default",
}
LABELS = {"process": "jarayon", "cycle": "aylana", "hierarchy": "ierarxiya", "list": "ro‘yxat"}
NODE_BELOW = 5  # msoSmartArtNodeBelow


def find_layout(app: Any, kind: str) -> Any:
    want = LAYOUTS[kind]
    layouts = app.SmartArtLayouts
    for i in range(1, int(layouts.Count) + 1):
        lay = layouts.Item(i)
        if str(lay.Id) == want:
            return lay
    raise LookupError(f"Office’da «{LABELS[kind]}» SmartArt maketi topilmadi")


def fill(smart: Any, kind: str, items: list[str]) -> list[str]:
    """Replace the sample nodes with `items`; returns the texts read back from the diagram."""
    nodes = smart.AllNodes
    while int(nodes.Count) > 1:
        nodes.Item(int(nodes.Count)).Delete()
    root = nodes.Item(1)
    root.TextFrame2.TextRange.Text = items[0]
    for text in items[1:]:
        node = root.AddNode(NODE_BELOW) if kind == "hierarchy" else smart.Nodes.Add()
        node.TextFrame2.TextRange.Text = text
    return [str(smart.AllNodes.Item(i).TextFrame2.TextRange.Text)
            for i in range(1, int(smart.AllNodes.Count) + 1)]  # fmt: skip
