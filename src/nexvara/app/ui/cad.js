"use strict";

// Model coordinates are DXF millimetres (Y up). Only the canvas has Y down.
const cadCanvas = document.getElementById("cad-canvas");
const cadCtx = cadCanvas.getContext("2d");
const cadWrap = document.getElementById("cad-wrap");
const cadState = {
  doc: { units: "mm", layers: [{ name: "0", color: 7, lineweight: 25, visible: true }], entities: [] },
  path: "", layer: "0", tool: "select", points: [], selected: new Set(),
  undo: [], redo: [], scale: 3, ox: 0, oy: 0, cursor: null, drag: null,
  snap: true, grid: true, ortho: false, dirty: false, ready: false,
};
const cadCommands = { L: "line", PL: "polyline", REC: "rect", C: "circle", A: "arc",
  T: "text", DIM: "dim", M: "move", CO: "copy", RO: "rotate", MI: "mirror",
  O: "offset", DI: "measure", E: "erase", U: "undo", Z: "extents" };
const cadNames = { select: "Tanlash", line: "Chiziq", polyline: "Polichiziq", rect: "To‘rtburchak",
  circle: "Aylana", arc: "Yoy", text: "Matn", dim: "O‘lcham", move: "Ko‘chirish",
  copy: "Nusxa", rotate: "Burish", mirror: "Ko‘zgu", offset: "Parallel nusxa",
  measure: "O‘lchash" };
const cadAci = { 1: "#ef6262", 2: "#f2cf5b", 3: "#55cf8c", 4: "#57c9d9",
  5: "#688bf2", 6: "#d17de5", 7: "#d9e5f6", 8: "#8795ad", 9: "#acb9cc" };
const cadClone = (x) => JSON.parse(JSON.stringify(x));
const cadNum = (x) => Number.isFinite(x) ? +x.toFixed(3) : 0;
const cadDist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const cadAngle = (a, b) => Math.atan2(b.y - a.y, b.x - a.x);
const cadDeg = (r) => (r * 180 / Math.PI + 360) % 360;
const cadPoint = (x, y) => ({ x: cadNum(x), y: cadNum(y) });
const cadScreen = (p) => ({ x: cadState.ox + p.x * cadState.scale,
  y: cadState.oy - p.y * cadState.scale });
const cadModel = (p) => cadPoint((p.x - cadState.ox) / cadState.scale,
  (cadState.oy - p.y) / cadState.scale);
const cadLayer = (name) => cadState.doc.layers.find((x) => x.name === name);
const cadVisible = (e) => !cadLayer(e.layer) || cadLayer(e.layer).visible !== false;
const cadColor = (e) => cadAci[(cadLayer(e.layer) || {}).color] || cadAci[7];

function cadLog(message) {
  const log = document.getElementById("cad-log");
  const line = document.createElement("div");
  line.textContent = message;
  log.appendChild(line);
  while (log.children.length > 5) log.firstChild.remove();
  log.scrollTop = log.scrollHeight;
}
function cadPrompt(message) {
  document.getElementById("cad-prompt").textContent = message || "Buyruq:";
  document.getElementById("cad-hint").textContent = message || "";
}
function cadSnapshot() {
  cadState.undo.push(cadClone(cadState.doc));
  if (cadState.undo.length > 80) cadState.undo.shift();
  cadState.redo.length = 0;
  cadState.dirty = true;
}
function cadCommit(entities) {
  if (!entities.length) return;
  cadSnapshot();
  cadState.doc.entities.push(...entities);
  cadState.points = [];
  cadRender();
}
function cadRestore(from, to) {
  if (!from.length) return;
  to.push(cadClone(cadState.doc));
  cadState.doc = from.pop();
  cadState.selected.clear();
  cadState.points = [];
  cadState.dirty = true;
  cadRender();
}
function cadSetTool(tool) {
  cadState.tool = tool;
  cadState.points = [];
  document.querySelectorAll("#cad-toolbar [data-tool]").forEach((b) =>
    b.classList.toggle("active", b.dataset.tool === tool));
  cadPrompt(tool === "select" ? "Tanlang yoki buyruq kiriting:" : `${cadNames[tool]}: birinchi nuqta:`);
  cadRender();
}
function cadNormalize(a) { return ((a % 360) + 360) % 360; }
function cadArcContains(a, start, end) {
  const sweep = cadNormalize(end - start) || 360;
  return cadNormalize(a - start) <= sweep + 0.001;
}
function cadDrawEntity(e, selected = false) {
  const c = cadCtx;
  c.save();
  c.strokeStyle = selected ? "#ffbd61" : cadColor(e);
  c.fillStyle = c.strokeStyle;
  c.lineWidth = selected ? 2.5 : 1.4;
  if (selected) c.setLineDash([7, 4]);
  c.beginPath();
  if (e.type === "line" || e.type === "dim") {
    const p = cadScreen({ x: e.x1, y: e.y1 }), q = cadScreen({ x: e.x2, y: e.y2 });
    if (e.type === "dim") {
      const d = Math.hypot(q.x - p.x, q.y - p.y) || 1;
      const nx = (q.y - p.y) / d * e.offset * cadState.scale;
      const ny = -(q.x - p.x) / d * e.offset * cadState.scale;
      c.moveTo(p.x, p.y); c.lineTo(p.x + nx, p.y + ny);
      c.moveTo(q.x, q.y); c.lineTo(q.x + nx, q.y + ny);
      c.moveTo(p.x + nx, p.y + ny); c.lineTo(q.x + nx, q.y + ny);
      c.stroke(); c.setLineDash([]);
      c.font = "12px Segoe UI";
      c.fillText(e.label || cadNum(d / cadState.scale).toString(),
        (p.x + q.x) / 2 + nx + 4, (p.y + q.y) / 2 + ny - 4);
    } else { c.moveTo(p.x, p.y); c.lineTo(q.x, q.y); c.stroke(); }
  } else if (e.type === "polyline") {
    const pts = e.points || [];
    pts.forEach((p, i) => {
      const s = cadScreen({ x: p[0], y: p[1] });
      if (!i) c.moveTo(s.x, s.y); else c.lineTo(s.x, s.y);
    });
    if (e.closed) c.closePath();
    c.stroke();
  } else if (e.type === "circle" || e.type === "arc") {
    const p = cadScreen({ x: e.cx, y: e.cy });
    const r = e.r * cadState.scale;
    if (e.type === "circle") c.arc(p.x, p.y, r, 0, 2 * Math.PI);
    else c.arc(p.x, p.y, r, -e.start * Math.PI / 180,
      -e.end * Math.PI / 180, true);
    c.stroke();
  } else if (e.type === "ellipse") {
    const p = cadScreen({ x: e.cx, y: e.cy });
    c.ellipse(p.x, p.y, e.rx * cadState.scale, e.ry * cadState.scale,
      -e.rot * Math.PI / 180, 0, 2 * Math.PI);
    c.stroke();
  } else if (e.type === "text") {
    const p = cadScreen(e);
    c.setLineDash([]);
    c.translate(p.x, p.y); c.rotate(-e.rot * Math.PI / 180);
    c.font = `${Math.max(8, e.h * cadState.scale)}px Segoe UI`;
    c.fillText(e.text || "", 0, 0);
  }
  c.restore();
}
function cadGridStep() {
  const n = Math.pow(10, Math.floor(Math.log10(75 / cadState.scale)));
  return [1, 2, 5, 10].map((x) => x * n).find((x) => x * cadState.scale >= 35) || n * 10;
}
function cadRender() {
  if (!cadState.ready) return;
  const w = cadWrap.clientWidth, h = cadWrap.clientHeight;
  const dpr = window.devicePixelRatio || 1;
  if (cadCanvas.width !== Math.round(w * dpr) || cadCanvas.height !== Math.round(h * dpr)) {
    cadCanvas.width = Math.round(w * dpr); cadCanvas.height = Math.round(h * dpr);
    cadCanvas.style.width = `${w}px`; cadCanvas.style.height = `${h}px`;
  }
  cadCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  cadCtx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--cad-bg") || "#0b1325";
  cadCtx.fillRect(0, 0, w, h);
  if (cadState.grid) {
    const step = cadGridStep() * cadState.scale;
    cadCtx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--cad-grid") || "#213050";
    cadCtx.lineWidth = 1;
    cadCtx.beginPath();
    for (let x = ((cadState.ox % step) + step) % step; x < w; x += step) {
      cadCtx.moveTo(x, 0); cadCtx.lineTo(x, h);
    }
    for (let y = ((cadState.oy % step) + step) % step; y < h; y += step) {
      cadCtx.moveTo(0, y); cadCtx.lineTo(w, y);
    }
    cadCtx.stroke();
  }
  cadCtx.strokeStyle = "#526888"; cadCtx.beginPath();
  cadCtx.moveTo(cadState.ox, 0); cadCtx.lineTo(cadState.ox, h);
  cadCtx.moveTo(0, cadState.oy); cadCtx.lineTo(w, cadState.oy); cadCtx.stroke();
  cadState.doc.entities.forEach((e, i) => { if (cadVisible(e)) cadDrawEntity(e, cadState.selected.has(i)); });
  if (cadState.points.length && cadState.cursor) {
    cadCtx.save(); cadCtx.strokeStyle = "#67d5eb"; cadCtx.setLineDash([5, 4]);
    cadCtx.beginPath();
    const a = cadScreen(cadState.points[cadState.points.length - 1]);
    const b = cadScreen(cadState.cursor);
    cadCtx.moveTo(a.x, a.y); cadCtx.lineTo(b.x, b.y); cadCtx.stroke(); cadCtx.restore();
  }
  if (cadState.drag && cadState.drag.kind === "select") {
    const a = cadState.drag.from, b = cadState.drag.to;
    cadCtx.fillStyle = b.x >= a.x ? "#5d9fff30" : "#67d5eb30";
    cadCtx.strokeStyle = b.x >= a.x ? "#5d9fff" : "#67d5eb";
    cadCtx.fillRect(a.x, a.y, b.x - a.x, b.y - a.y);
    cadCtx.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y);
  }
  document.getElementById("cad-count").textContent = `${cadState.doc.entities.length} obyekt · ${cadState.selected.size} tanlangan`;
  document.getElementById("cad-file").textContent = `${cadState.path || "Yangi chizma"}${cadState.dirty ? " •" : ""}`;
  cadRenderProps();
}
function cadAnchors(e) {
  if (e.type === "line" || e.type === "dim") {
    return [cadPoint(e.x1, e.y1), cadPoint(e.x2, e.y2), cadPoint((e.x1 + e.x2) / 2, (e.y1 + e.y2) / 2)];
  }
  if (e.type === "polyline") {
    const p = e.points.map((v) => cadPoint(v[0], v[1]));
    const mids = p.slice(1).map((v, i) => cadPoint((v.x + p[i].x) / 2, (v.y + p[i].y) / 2));
    return p.concat(mids);
  }
  if (e.type === "circle" || e.type === "arc" || e.type === "ellipse") {
    const r = e.r || e.rx;
    return [cadPoint(e.cx, e.cy), ...[0, 90, 180, 270].map((a) =>
      cadPoint(e.cx + r * Math.cos(a * Math.PI / 180), e.cy + r * Math.sin(a * Math.PI / 180)))];
  }
  if (e.type === "text") return [cadPoint(e.x, e.y)];
  return [];
}
function cadSnap(p, base = null) {
  let q = p;
  if (cadState.snap) {
    let best = 11;
    cadState.doc.entities.forEach((e) => {
      if (!cadVisible(e)) return;
      cadAnchors(e).forEach((a) => {
        const d = cadDist(cadScreen(a), cadScreen(p));
        if (d < best) { best = d; q = a; }
      });
    });
    if (best === 11 && cadState.grid) {
      const step = cadGridStep();
      const g = cadPoint(Math.round(p.x / step) * step, Math.round(p.y / step) * step);
      if (cadDist(cadScreen(g), cadScreen(p)) < 8) q = g;
    }
  }
  if (cadState.ortho && base) {
    q = Math.abs(q.x - base.x) >= Math.abs(q.y - base.y) ? cadPoint(q.x, base.y) : cadPoint(base.x, q.y);
  }
  return q;
}
function cadSegments(e) {
  const p = e.type === "polyline" ? e.points.map((a) => cadPoint(a[0], a[1])) :
    [cadPoint(e.x1, e.y1), cadPoint(e.x2, e.y2)];
  if (e.type === "polyline" && e.closed) p.push(p[0]);
  return p.slice(1).map((q, i) => [p[i], q]);
}
function cadHit(e, p) {
  const tol = 8 / cadState.scale;
  if (e.type === "line" || e.type === "polyline" || e.type === "dim") {
    return cadSegments(e).some(([a, b]) => {
      const dx = b.x - a.x, dy = b.y - a.y;
      const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy || 1)));
      return cadDist(p, cadPoint(a.x + dx * t, a.y + dy * t)) <= tol;
    });
  }
  if (e.type === "circle" || e.type === "arc") {
    const d = cadDist(p, cadPoint(e.cx, e.cy));
    return Math.abs(d - e.r) <= tol && (e.type === "circle" ||
      cadArcContains(cadDeg(Math.atan2(p.y - e.cy, p.x - e.cx)), e.start, e.end));
  }
  if (e.type === "ellipse") {
    const a = -e.rot * Math.PI / 180, dx = p.x - e.cx, dy = p.y - e.cy;
    const x = dx * Math.cos(a) - dy * Math.sin(a), y = dx * Math.sin(a) + dy * Math.cos(a);
    return Math.abs(Math.hypot(x / e.rx, y / e.ry) - 1) < tol / Math.min(e.rx, e.ry);
  }
  if (e.type === "text") return cadDist(p, e) < Math.max(tol, e.h * (e.text || "").length * 0.3);
  return false;
}
function cadBounds(e) {
  const pts = cadAnchors(e);
  if (e.type === "circle" || e.type === "arc" || e.type === "ellipse") {
    const r = Math.max(e.r || 0, e.rx || 0, e.ry || 0);
    pts.push(cadPoint(e.cx - r, e.cy - r), cadPoint(e.cx + r, e.cy + r));
  }
  if (e.type === "text") pts.push(cadPoint(e.x + e.h * (e.text || "").length * 0.6, e.y + e.h));
  return { x1: Math.min(...pts.map((p) => p.x)), y1: Math.min(...pts.map((p) => p.y)),
    x2: Math.max(...pts.map((p) => p.x)), y2: Math.max(...pts.map((p) => p.y)) };
}
function cadExtents() {
  const boxes = cadState.doc.entities.filter(cadVisible).map(cadBounds);
  const w = cadWrap.clientWidth, h = cadWrap.clientHeight;
  if (!boxes.length) { cadState.scale = 3; cadState.ox = w / 2; cadState.oy = h / 2; cadRender(); return; }
  const x1 = Math.min(...boxes.map((b) => b.x1)), x2 = Math.max(...boxes.map((b) => b.x2));
  const y1 = Math.min(...boxes.map((b) => b.y1)), y2 = Math.max(...boxes.map((b) => b.y2));
  cadState.scale = Math.min(100, Math.max(0.01, Math.min((w - 80) / (x2 - x1 || 1),
    (h - 80) / (y2 - y1 || 1))));
  cadState.ox = w / 2 - (x1 + x2) / 2 * cadState.scale;
  cadState.oy = h / 2 + (y1 + y2) / 2 * cadState.scale;
  cadRender();
}
function cadTransform(e, fn) {
  const out = cadClone(e);
  const point = (x, y) => fn(cadPoint(x, y));
  if (out.type === "line" || out.type === "dim") {
    const a = point(out.x1, out.y1), b = point(out.x2, out.y2);
    Object.assign(out, { x1: a.x, y1: a.y, x2: b.x, y2: b.y });
  } else if (out.type === "polyline") {
    out.points = out.points.map((p) => { const q = point(p[0], p[1]); return [q.x, q.y, p[2] || 0]; });
  } else if (out.type === "text") {
    Object.assign(out, point(out.x, out.y));
  } else {
    const p = point(out.cx, out.cy); out.cx = p.x; out.cy = p.y;
  }
  return out;
}
function cadApplyEdit(tool, pts) {
  const ids = [...cadState.selected];
  if (!ids.length) { cadLog("Avval obyekt tanlang."); cadSetTool("select"); return; }
  const [a, b] = pts;
  const vec = cadPoint(b.x - a.x, b.y - a.y);
  let change;
  if (tool === "move" || tool === "copy") change = (e) => cadTransform(e, (p) => cadPoint(p.x + vec.x, p.y + vec.y));
  if (tool === "rotate") {
    const t = cadAngle(a, b);
    change = (e) => {
      const out = cadTransform(e, (p) => cadPoint(a.x + (p.x - a.x) * Math.cos(t) - (p.y - a.y) * Math.sin(t),
        a.y + (p.x - a.x) * Math.sin(t) + (p.y - a.y) * Math.cos(t)));
      if (out.type === "text" || out.type === "ellipse") out.rot = cadNum((out.rot || 0) + cadDeg(t));
      if (out.type === "arc") { out.start = cadDeg(out.start * Math.PI / 180 + t); out.end = cadDeg(out.end * Math.PI / 180 + t); }
      return out;
    };
  }
  if (tool === "mirror") {
    const t = cadAngle(a, b), co = Math.cos(2 * t), si = Math.sin(2 * t);
    change = (e) => {
      const out = cadTransform(e, (p) => cadPoint(a.x + (p.x - a.x) * co + (p.y - a.y) * si,
        a.y + (p.x - a.x) * si - (p.y - a.y) * co));
      if (out.type === "arc") [out.start, out.end] = [cadNormalize(cadDeg(2 * t) - out.end), cadNormalize(cadDeg(2 * t) - out.start)];
      if (out.type === "text" || out.type === "ellipse") out.rot = cadNormalize(cadDeg(2 * t) - (out.rot || 0));
      if (out.type === "polyline") out.points.forEach((p) => { p[2] = -(p[2] || 0); });
      return out;
    };
  }
  if (tool === "offset") {
    const amount = cadDist(a, b);
    change = (e) => {
      const out = cadClone(e);
      if (out.type === "circle" || out.type === "arc") out.r = cadNum(out.r + amount);
      else if (out.type === "ellipse") { out.rx = cadNum(out.rx + amount); out.ry = cadNum(out.ry + amount); }
      else if (out.type === "line") {
        const d = Math.hypot(out.x2 - out.x1, out.y2 - out.y1) || 1;
        const x = -(out.y2 - out.y1) / d * amount, y = (out.x2 - out.x1) / d * amount;
        out.x1 += x; out.x2 += x; out.y1 += y; out.y2 += y;
      } else return null;
      return out;
    };
  }
  const edits = ids.map((i) => [i, change(cadState.doc.entities[i])]).filter((v) => v[1]);
  if (!edits.length) { cadLog("Bu obyektga amal qo‘llanmaydi."); cadSetTool("select"); return; }
  cadSnapshot();
  if (["copy", "mirror", "offset"].includes(tool)) cadState.doc.entities.push(...edits.map((v) => v[1]));
  else edits.forEach(([i, e]) => { cadState.doc.entities[i] = e; });
  cadState.selected.clear(); cadLog(`${cadNames[tool]} bajarildi.`);
  cadSetTool("select");
}
function cadTakePoint(p) {
  const tool = cadState.tool, pts = cadState.points;
  if (["move", "copy", "rotate", "mirror", "offset"].includes(tool) && !cadState.selected.size) {
    cadLog("Avval obyekt tanlang."); cadSetTool("select"); return;
  }
  pts.push(p);
  const layer = cadState.layer;
  if (tool === "line" && pts.length >= 2) {
    if (cadDist(pts[0], pts[1])) cadCommit([{ type: "line", layer, x1: pts[0].x, y1: pts[0].y, x2: p.x, y2: p.y }]);
    cadState.points = [p]; cadPrompt("Chiziq: keyingi nuqta yoki Enter:"); return;
  }
  if (tool === "polyline") { cadPrompt("Polichiziq: keyingi nuqta yoki Enter:"); cadRender(); return; }
  if (tool === "rect" && pts.length === 2) {
    cadCommit([{ type: "polyline", layer, points: [[pts[0].x, pts[0].y, 0], [p.x, pts[0].y, 0],
      [p.x, p.y, 0], [pts[0].x, p.y, 0]], closed: true }]); cadSetTool("select"); return;
  }
  if (tool === "circle" && pts.length === 2) {
    const r = cadDist(pts[0], p);
    if (r) cadCommit([{ type: "circle", layer, cx: pts[0].x, cy: pts[0].y, r: cadNum(r) }]);
    cadSetTool("select"); return;
  }
  if (tool === "arc" && pts.length === 3) {
    const r = cadDist(pts[0], pts[1]);
    if (r) cadCommit([{ type: "arc", layer, cx: pts[0].x, cy: pts[0].y, r: cadNum(r),
      start: cadNum(cadDeg(cadAngle(pts[0], pts[1]))), end: cadNum(cadDeg(cadAngle(pts[0], p))) }]);
    cadSetTool("select"); return;
  }
  if (tool === "text" && pts.length === 1) {
    const value = window.prompt("Matnni yozing:", "");
    if (value) cadCommit([{ type: "text", layer, x: p.x, y: p.y, text: value, h: 2.5, rot: 0 }]);
    cadSetTool("select"); return;
  }
  if (tool === "dim" && pts.length === 3) {
    const a = pts[0], b = pts[1], d = cadDist(a, b) || 1;
    const offset = cadNum((-(b.y - a.y) * (p.x - b.x) + (b.x - a.x) * (p.y - b.y)) / d);
    cadCommit([{ type: "dim", layer, x1: a.x, y1: a.y, x2: b.x, y2: b.y, offset, label: "" }]);
    cadSetTool("select"); return;
  }
  if (tool === "measure" && pts.length === 2) {
    cadLog(`Masofa: ${cadNum(cadDist(pts[0], pts[1]))} mm`); cadSetTool("select"); return;
  }
  if (["move", "copy", "rotate", "mirror", "offset"].includes(tool) && pts.length === 2) {
    cadApplyEdit(tool, pts); return;
  }
  cadPrompt(`${cadNames[tool]}: keyingi nuqta:`); cadRender();
}
function cadParsePoint(input) {
  const s = input.trim().replace(/\s+/g, "");
  const last = cadState.points[cadState.points.length - 1] || cadPoint(0, 0);
  let m = /^@?(-?(?:\d+(?:\.\d*)?|\.\d+)),(-?(?:\d+(?:\.\d*)?|\.\d+))$/.exec(s);
  if (m) return s.startsWith("@") ? cadPoint(last.x + +m[1], last.y + +m[2]) : cadPoint(+m[1], +m[2]);
  m = /^@(-?(?:\d+(?:\.\d*)?|\.\d+))<(-?(?:\d+(?:\.\d*)?|\.\d+))$/.exec(s);
  if (m) return cadPoint(last.x + +m[1] * Math.cos(+m[2] * Math.PI / 180),
    last.y + +m[1] * Math.sin(+m[2] * Math.PI / 180));
  m = /^-?(?:\d+(?:\.\d*)?|\.\d+)$/.exec(s);
  if (m && cadState.points.length) {
    const distance = +s;
    const angle = cadState.cursor ? cadAngle(last, cadState.cursor) : 0;
    return cadPoint(last.x + distance * Math.cos(angle), last.y + distance * Math.sin(angle));
  }
  return null;
}
function cadFinish() {
  if (cadState.tool === "polyline" && cadState.points.length >= 2) {
    cadCommit([{ type: "polyline", layer: cadState.layer,
      points: cadState.points.map((p) => [p.x, p.y, 0]), closed: false }]);
  }
  cadSetTool("select");
}
function cadExec(value) {
  const input = String(value || "").trim();
  if (!input) { cadFinish(); return true; }
  const cmd = input.toUpperCase();
  if (cadCommands[cmd]) {
    const action = cadCommands[cmd];
    if (action === "erase") cadAction("erase");
    else if (action === "undo" || action === "extents") cadAction(action);
    else cadSetTool(action);
    return true;
  }
  const point = cadParsePoint(input);
  if (point && cadState.tool !== "select") {
    cadTakePoint(cadState.ortho && cadState.points.length ? cadSnap(point, cadState.points.at(-1)) : point);
    return true;
  }
  cadLog(`Noma’lum buyruq yoki nuqta: ${input}`);
  return false;
}
function cadRenderLayers() {
  const root = document.getElementById("cad-layers"); root.replaceChildren();
  cadState.doc.layers.forEach((ly) => {
    const row = document.createElement("div"); row.className = `cad-layer${ly.name === cadState.layer ? " active" : ""}`;
    const pick = document.createElement("button"); pick.className = "cad-layer-name";
    pick.textContent = ly.name; pick.title = "Joriy qatlam";
    pick.addEventListener("click", () => { cadState.layer = ly.name; cadRenderLayers(); });
    const eye = document.createElement("button"); eye.className = "cad-mini";
    eye.textContent = ly.visible === false ? "○" : "●"; eye.title = "Ko‘rinishni almashtirish";
    eye.style.color = cadAci[ly.color] || cadAci[7];
    eye.addEventListener("click", () => { cadSnapshot(); ly.visible = ly.visible === false; cadRenderLayers(); cadRender(); });
    row.append(eye, pick); root.appendChild(row);
  });
}
function cadRenderProps() {
  const root = document.getElementById("cad-props"); root.replaceChildren();
  const ids = [...cadState.selected];
  if (!ids.length) { root.textContent = "Obyekt tanlanmagan"; return; }
  root.textContent = `${ids.length} obyekt tanlandi`;
  if (ids.length !== 1) return;
  const e = cadState.doc.entities[ids[0]];
  const type = document.createElement("div"); type.textContent = `Tur: ${e.type}`; root.appendChild(type);
  const label = document.createElement("label"); label.textContent = "Qatlam: ";
  const select = document.createElement("select");
  cadState.doc.layers.forEach((ly) => { const opt = document.createElement("option"); opt.value = ly.name;
    opt.textContent = ly.name; select.appendChild(opt); });
  select.value = e.layer || "0";
  select.addEventListener("change", () => { cadSnapshot(); e.layer = select.value; cadRender(); });
  label.appendChild(select); root.appendChild(label);
  if (e.type === "text") {
    const input = document.createElement("input"); input.value = e.text; input.setAttribute("aria-label", "Matn");
    input.addEventListener("change", () => { cadSnapshot(); e.text = input.value; cadRender(); }); root.appendChild(input);
  }
}
function cadLoad(result) {
  if (!result || !result.ok) { if (result && !result.cancelled) cadLog(result.error || "Chizma ochilmadi."); return false; }
  cadState.doc = cadClone(result.drawing);
  if (!cadState.doc.layers.length) cadState.doc.layers = [{ name: "0", color: 7, visible: true }];
  cadState.path = result.path || ""; cadState.layer = cadState.doc.layers[0].name;
  cadState.undo = []; cadState.redo = []; cadState.selected.clear(); cadState.dirty = false;
  cadSetTool("select"); cadRenderLayers(); cadExtents();
  const skipped = Object.entries(cadState.doc.skipped || {});
  if (skipped.length) cadLog(`Ochilmadi: ${skipped.map(([k, v]) => `${k} ${v}`).join(", ")}`);
  cadLog(`${result.name || "Chizma"} ochildi.`); return true;
}
async function cadAction(action) {
  if (action === "undo") { cadRestore(cadState.undo, cadState.redo); return; }
  if (action === "redo") { cadRestore(cadState.redo, cadState.undo); return; }
  if (action === "extents") { cadExtents(); return; }
  if (action === "erase") {
    if (!cadState.selected.size) return;
    cadSnapshot(); cadState.doc.entities = cadState.doc.entities.filter((_, i) => !cadState.selected.has(i));
    cadState.selected.clear(); cadRender(); return;
  }
  if (action === "new") {
    if (cadState.dirty && !window.confirm("Saqlanmagan chizma bor. Yangi chizma ochilsinmi?")) return;
    cadLoad({ ok: true, drawing: { units: "mm", layers: [{ name: "0", color: 7, lineweight: 25, visible: true }], entities: [] }, name: "Yangi chizma" }); return;
  }
  if (!api()) { cadLog("NEXVARA bilan aloqa yo‘q."); return; }
  try {
    if (action === "open" || action === "last") {
      if (cadState.dirty && !window.confirm("Saqlanmagan chizma bor. Boshqa chizma ochilsinmi?")) return;
      cadLoad(await (action === "open" ? api().cad_open() : api().cad_last_drawing())); return;
    }
    if (action === "save" || action === "saveas") {
      const r = await api().cad_save(cadState.doc, action === "save" ? cadState.path : "");
      if (r.ok) { cadState.path = r.path; cadState.dirty = false; cadRender(); cadLog(`Saqlandi: ${r.name}`); }
      else if (!r.cancelled) cadLog(r.error || "Saqlab bo‘lmadi.");
      return;
    }
    if (action === "pdf" || action === "png") {
      const r = await api().cad_export(cadState.doc, action);
      cadLog(r.ok ? `Tayyor: ${r.path}` : (r.error || "Eksport bajarilmadi."));
    }
  } catch (e) { cadLog(`Xato: ${e.message || e}`); }
}
function cadConfirmDirty() { return !cadState.dirty || window.confirm("Saqlanmagan o‘zgarishlar bor. Davom etilsinmi?"); }
function addCadOpen(path) {
  const row = document.createElement("div"); row.className = "row";
  const button = document.createElement("button"); button.className = "btn primary";
  button.textContent = "Chizmalarda ochish";
  button.addEventListener("click", async () => {
    if (!cadConfirmDirty()) return;
    show("cad");
    try { cadLoad(await api().cad_open(path)); } catch (e) { cadLog(`Xato: ${e.message || e}`); }
  });
  row.appendChild(button); document.getElementById("chat-log").appendChild(row);
}
function renderCad() {
  if (!cadState.ready) {
    cadState.ready = true;
    cadState.ox = cadWrap.clientWidth / 2; cadState.oy = cadWrap.clientHeight / 2;
    cadRenderLayers(); cadSetTool("select");
  }
  requestAnimationFrame(cadRender);
}

document.getElementById("cad-toolbar").addEventListener("click", (event) => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.tool) cadSetTool(button.dataset.tool);
  if (button.dataset.cad) cadAction(button.dataset.cad);
});
document.getElementById("cad-cmd-form").addEventListener("submit", (event) => {
  event.preventDefault(); const input = document.getElementById("cad-cmd");
  cadExec(input.value); input.value = "";
});
document.getElementById("cad-layer-add").addEventListener("click", () => {
  const name = (window.prompt("Yangi qatlam nomi:", "Qatlam") || "").trim();
  if (!name) return;
  if (/[<>/\\":;?*|=`]/.test(name) || name.length > 60 || cadLayer(name)) {
    cadLog("Qatlam nomi noto‘g‘ri yoki mavjud."); return;
  }
  cadSnapshot(); cadState.doc.layers.push({ name, color: 7, lineweight: 25, visible: true });
  cadState.layer = name; cadRenderLayers(); cadRender();
});
document.querySelectorAll("#page-cad [data-toggle]").forEach((button) => button.addEventListener("click", () => {
  const key = button.dataset.toggle; cadState[key] = !cadState[key];
  button.classList.toggle("on", cadState[key]); cadRender();
}));
cadCanvas.addEventListener("contextmenu", (event) => event.preventDefault());
cadCanvas.addEventListener("wheel", (event) => {
  event.preventDefault();
  const box = cadCanvas.getBoundingClientRect();
  const p = { x: event.clientX - box.left, y: event.clientY - box.top };
  const before = cadModel(p);
  cadState.scale = Math.max(0.005, Math.min(1000, cadState.scale * (event.deltaY < 0 ? 1.15 : 1 / 1.15)));
  cadState.ox = p.x - before.x * cadState.scale;
  cadState.oy = p.y + before.y * cadState.scale;
  cadRender();
}, { passive: false });
cadCanvas.addEventListener("pointerdown", (event) => {
  const box = cadCanvas.getBoundingClientRect();
  const p = { x: event.clientX - box.left, y: event.clientY - box.top };
  cadCanvas.setPointerCapture(event.pointerId);
  if (event.button === 1 || event.button === 2) {
    cadState.drag = { kind: "pan", from: p, ox: cadState.ox, oy: cadState.oy }; return;
  }
  if (event.button !== 0) return;
  const model = cadModel(p);
  if (cadState.tool !== "select") { cadTakePoint(cadSnap(model, cadState.points.at(-1))); return; }
  let hit = -1;
  for (let i = cadState.doc.entities.length - 1; i >= 0; i--) {
    if (cadVisible(cadState.doc.entities[i]) && cadHit(cadState.doc.entities[i], model)) { hit = i; break; }
  }
  if (hit >= 0) {
    if (event.shiftKey) { if (cadState.selected.has(hit)) cadState.selected.delete(hit); else cadState.selected.add(hit); }
    else { cadState.selected.clear(); cadState.selected.add(hit); }
    cadState.drag = null;
  } else {
    if (!event.shiftKey) cadState.selected.clear();
    cadState.drag = { kind: "select", from: p, to: p };
  }
  cadRender();
});
cadCanvas.addEventListener("pointermove", (event) => {
  const box = cadCanvas.getBoundingClientRect();
  const p = { x: event.clientX - box.left, y: event.clientY - box.top };
  if (cadState.drag && cadState.drag.kind === "pan") {
    cadState.ox = cadState.drag.ox + p.x - cadState.drag.from.x;
    cadState.oy = cadState.drag.oy + p.y - cadState.drag.from.y;
  } else if (cadState.drag && cadState.drag.kind === "select") cadState.drag.to = p;
  cadState.cursor = cadSnap(cadModel(p), cadState.points.at(-1));
  document.getElementById("cad-xy").textContent = `X ${cadNum(cadState.cursor.x)} · Y ${cadNum(cadState.cursor.y)} mm`;
  cadRender();
});
cadCanvas.addEventListener("pointerup", (event) => {
  const drag = cadState.drag;
  if (drag && drag.kind === "select") {
    const a = cadModel(drag.from), b = cadModel(drag.to);
    if (cadDist(drag.from, drag.to) > 5) {
      const bounds = { x1: Math.min(a.x, b.x), x2: Math.max(a.x, b.x),
        y1: Math.min(a.y, b.y), y2: Math.max(a.y, b.y) };
      const contain = drag.to.x >= drag.from.x;
      cadState.doc.entities.forEach((e, i) => {
        if (!cadVisible(e)) return;
        const v = cadBounds(e);
        const inside = v.x1 >= bounds.x1 && v.x2 <= bounds.x2 && v.y1 >= bounds.y1 && v.y2 <= bounds.y2;
        const overlap = v.x1 <= bounds.x2 && v.x2 >= bounds.x1 && v.y1 <= bounds.y2 && v.y2 >= bounds.y1;
        if (contain ? inside : overlap) cadState.selected.add(i);
      });
    }
  }
  cadState.drag = null; cadRender();
  if (cadCanvas.hasPointerCapture(event.pointerId)) cadCanvas.releasePointerCapture(event.pointerId);
});
document.addEventListener("keydown", (event) => {
  if (!document.getElementById("page-cad").classList.contains("active")) return;
  const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  const key = event.key.toLowerCase();
  if (event.key === "F3" || event.key === "F7" || event.key === "F8") {
    event.preventDefault(); document.querySelector(`[data-toggle=${{ F3: "snap", F7: "grid", F8: "ortho" }[event.key]}]`).click(); return;
  }
  if (event.ctrlKey && ["z", "y", "s"].includes(key)) {
    event.preventDefault(); cadAction({ z: "undo", y: "redo", s: "save" }[key]); return;
  }
  if (event.key === "Escape") { event.preventDefault(); cadSetTool("select"); return; }
  if (editing) return;
  if (event.key === "Delete") { event.preventDefault(); cadAction("erase"); }
  else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); cadFinish(); }
  else if (event.key.length === 1 && /[a-z]/i.test(event.key)) document.getElementById("cad-cmd").focus();
});
window.addEventListener("resize", () => { if (cadState.ready) cadRender(); });
window.cad = { exec: cadExec, load: cadLoad, get doc() { return cadState.doc; },
  get selected() { return [...cadState.selected]; }, action: cadAction, setTool: cadSetTool };
