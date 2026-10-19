"use strict";

// NEXVARA «Chizmalar» — the built-in CAD editor (no AutoCAD needed).
// Model coordinates are DXF millimetres with Y up; only the canvas has Y down.
// Angles in the JSON are degrees, counter-clockwise (as in DXF). Python side: app/api_cad.py.

const cadCanvas = document.getElementById("cad-canvas");
const cadCtx = cadCanvas.getContext("2d");
const cadWrap = document.getElementById("cad-wrap");
const CAD_EMPTY = () => ({ units: "mm", layers: [{ name: "0", color: 7, lineweight: 25, linetype: "Continuous", visible: true, locked: false }], entities: [] });
const cadState = {
  doc: CAD_EMPTY(), path: "", layer: "0", tool: "select", points: [], selected: new Set(),
  undo: [], redo: [], scale: 3, ox: 0, oy: 0, cursor: null, raw: null, snapHit: null, drag: null,
  snap: true, grid: true, ortho: false, dirty: false, ready: false, ask: null, opts: {},
  clipboard: null, lastTool: "line", hover: -1, color: 256,  // colour of new objects (256 = by layer)
};
const CAD_TOOLS = {
  select: "Tanlash", line: "Chiziq", polyline: "Polichiziq", rect: "To‘rtburchak", circle: "Aylana",
  arc: "Yoy", ellipse: "Ellips", polygon: "Ko‘pburchak", text: "Matn", hatch: "Shtrixlash",
  dim: "Chiziqli o‘lcham", dimali: "Qiya o‘lcham", dimrad: "Radius o‘lchami", dimdia: "Diametr o‘lchami",
  move: "Ko‘chirish", copy: "Nusxa", rotate: "Burish", mirror: "Ko‘zgu", scale: "Masshtab",
  offset: "Parallel nusxa", trim: "Kesish", extend: "Uzaytirish", fillet: "Yumaloqlash",
  chamfer: "Faska", array: "Massiv (qator)", parray: "Massiv (aylana)", explode: "Bo‘laklash",
  measure: "Masofa", area: "Yuza", zoomwin: "Oyna bilan kattalashtirish", paste: "Qo‘yish",
};
const CAD_ALIASES = {
  L: "line", PL: "polyline", REC: "rect", C: "circle", A: "arc", EL: "ellipse", POL: "polygon",
  T: "text", H: "hatch", DIM: "dim", DLI: "dim", DAL: "dimali", DRA: "dimrad", DDI: "dimdia",
  M: "move", CO: "copy", CP: "copy", RO: "rotate", MI: "mirror", SC: "scale", O: "offset",
  TR: "trim", EX: "extend", F: "fillet", CHA: "chamfer", AR: "array", ARP: "parray",
  X: "explode", DI: "measure", AA: "area", ZW: "zoomwin",
  // Uzbek words work too
  CHIZIQ: "line", AYLANA: "circle", YOY: "arc", MATN: "text", KESISH: "trim", NUSXA: "copy",
};
const CAD_ACTIONS = { E: "erase", U: "undo", REDO: "redo", Z: "extents", ZE: "extents", N: "new" };
// AutoCAD colour index 1..9 (7 = white on dark, black on light paper)
const CAD_ACI = { 1: "#ef4444", 2: "#facc15", 3: "#22c55e", 4: "#22d3ee", 5: "#3b82f6", 6: "#d946ef", 7: null, 8: "#8b95a8", 9: "#c0c8d4" };
const CAD_ACI_NAMES = { 1: "Qizil", 2: "Sariq", 3: "Yashil", 4: "Havorang", 5: "Ko‘k", 6: "Pushti", 7: "Oq/qora", 8: "Kulrang", 9: "Och kulrang",
  30: "To‘q sariq", 34: "Jigarrang", 82: "Och yashil", 150: "To‘q ko‘k", 200: "Binafsha", 250: "To‘q kulrang" };
// The full AutoCAD colour index 10..249 (24 hues × 10 shades) and the greys 250..255, as in
// AutoCAD's «Select Color» window: even = full colour, odd = pastel; darker down the column.
(function cadFillAci() {
  const hsv = (h, s, v) => {
    const f = (n) => { const k = (n + h / 60) % 6; return v - v * s * Math.max(0, Math.min(k, 4 - k, 1)); };
    return "#" + [f(5), f(3), f(1)].map((x) => Math.round(x * 255).toString(16).padStart(2, "0")).join("");
  };
  const bright = [1, 1, 0.8, 0.8, 0.6, 0.6, 0.5, 0.5, 0.3, 0.3];
  for (let i = 10; i <= 249; i++) CAD_ACI[i] = hsv(((Math.floor(i / 10) - 1) * 15) % 360, i % 2 ? 0.5 : 1, bright[i % 10]);
  [51, 91, 132, 173, 214, 255].forEach((g, k) => { CAD_ACI[250 + k] = "#" + g.toString(16).padStart(2, "0").repeat(3); });
})();
const cadColorName = (i) => (+i === 256 ? "Qatlam bo‘yicha" : CAD_ACI_NAMES[i] || `Rang ${i}`);
const cadSwatchColor = (i) => (+i === 256 ? "transparent" : CAD_ACI[i] || cadInk());
const CAD_LINETYPES = { Continuous: "Uzluksiz", NX_SHTRIX: "Shtrix", NX_OQ: "O‘q (shtrix-punktir)" };
const CAD_LT_PATTERN = { NX_SHTRIX: [4, 2], NX_OQ: [12, 2, 0.5, 2] }; // mm, as in cad.py
const CAD_WEIGHTS = [13, 18, 25, 35, 50, 70, 100];
const TAU = Math.PI * 2;

// ---------------- small helpers ----------------
const cadClone = (x) => JSON.parse(JSON.stringify(x));
const cadNum = (x) => (Number.isFinite(x) ? +x.toFixed(4) : 0);
const P = (x, y) => ({ x, y });
const cadDist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const cadAng = (a, b) => Math.atan2(b.y - a.y, b.x - a.x);
const toDeg = (r) => ((r * 180 / Math.PI) % 360 + 360) % 360;
const toRad = (d) => d * Math.PI / 180;
const normA = (a) => ((a % TAU) + TAU) % TAU;
const fmt = (v) => String(cadNum(v)).replace(".", ",");
const cadScreen = (p) => P(cadState.ox + p.x * cadState.scale, cadState.oy - p.y * cadState.scale);
const cadModel = (p) => P((p.x - cadState.ox) / cadState.scale, (cadState.oy - p.y) / cadState.scale);
const cadLayer = (name) => cadState.doc.layers.find((x) => x.name === name);
const cadVisible = (e) => { const l = cadLayer(e.layer); return !l || l.visible !== false; };
const cadLocked = (e) => { const l = cadLayer(e.layer); return !!(l && l.locked); };
function cadInk() { return getComputedStyle(document.documentElement).getPropertyValue("--cad-ink").trim() || "#e2e8f0"; }
function cadColorOf(e) {
  const aci = e.color && e.color !== 256 ? e.color : (cadLayer(e.layer) || {}).color || 7;
  return CAD_ACI[aci] || cadInk();
}

// ---------------- geometry: every entity as primitives ----------------
// seg: {k:"seg", a, b}; arc: {k:"arc", c, r, a0, a1} counter-clockwise from a0 to a1 (radians,
// a1 > a0, a full circle has a1 - a0 = TAU).
function bulgeArc(p, q, b) {
  const c = cadDist(p, q); if (!c || !b) return null;
  const n = P(-(q.y - p.y) / c, (q.x - p.x) / c);
  const m = P((p.x + q.x) / 2, (p.y + q.y) / 2);
  const k = (1 - b * b) / (4 * b) * c;
  const center = P(m.x + n.x * k, m.y + n.y * k);
  const r = cadDist(center, p);
  let a0 = cadAng(center, p), a1 = cadAng(center, q);
  if (b < 0) [a0, a1] = [a1, a0];
  a0 = normA(a0); a1 = normA(a1); if (a1 <= a0) a1 += TAU;
  return { k: "arc", c: center, r, a0, a1 };
}
function polyPts(e) { return (e.points || []).map((v) => P(v[0], v[1])); }
function cadPrims(e) {
  const t = e.type;
  if (t === "line") return [{ k: "seg", a: P(e.x1, e.y1), b: P(e.x2, e.y2) }];
  if (t === "polyline" || t === "hatch") {
    const rings = t === "hatch" ? e.paths.map((r) => r.map((v) => [v[0], v[1], v[2] || 0])) : [e.points];
    const out = [];
    rings.forEach((pts) => {
      const n = pts.length, closed = t === "hatch" || e.closed;
      for (let i = 0; i < (closed ? n : n - 1); i++) {
        const p = P(pts[i][0], pts[i][1]), q = P(pts[(i + 1) % n][0], pts[(i + 1) % n][1]);
        const arc = bulgeArc(p, q, pts[i][2] || 0);
        out.push(arc || { k: "seg", a: p, b: q });
      }
    });
    return out;
  }
  if (t === "circle") return [{ k: "arc", c: P(e.cx, e.cy), r: e.r, a0: 0, a1: TAU }];
  if (t === "arc") {
    const a0 = normA(toRad(e.start)); let a1 = normA(toRad(e.end)); if (a1 <= a0) a1 += TAU;
    return [{ k: "arc", c: P(e.cx, e.cy), r: e.r, a0, a1 }];
  }
  if (t === "ellipse") {
    const out = [], n = 96, rot = toRad(e.rot || 0);
    let prev = null;
    for (let i = 0; i <= n; i++) {
      const u = TAU * i / n, x = e.rx * Math.cos(u), y = e.ry * Math.sin(u);
      const q = P(e.cx + x * Math.cos(rot) - y * Math.sin(rot), e.cy + x * Math.sin(rot) + y * Math.cos(rot));
      if (prev) out.push({ k: "seg", a: prev, b: q });
      prev = q;
    }
    return out;
  }
  return [];
}
function arcHas(pr, ang) { return pr.a1 - pr.a0 >= TAU - 1e-9 || normA(ang - pr.a0) <= pr.a1 - pr.a0 + 1e-9; }
function arcPoint(pr, a) { return P(pr.c.x + pr.r * Math.cos(a), pr.c.y + pr.r * Math.sin(a)); }
function nearestOn(pr, p) {
  if (pr.k === "seg") {
    const dx = pr.b.x - pr.a.x, dy = pr.b.y - pr.a.y, L = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((p.x - pr.a.x) * dx + (p.y - pr.a.y) * dy) / L));
    return P(pr.a.x + dx * t, pr.a.y + dy * t);
  }
  const ang = cadAng(pr.c, p);
  if (arcHas(pr, ang)) return arcPoint(pr, ang);
  const e0 = arcPoint(pr, pr.a0), e1 = arcPoint(pr, pr.a1);
  return cadDist(p, e0) < cadDist(p, e1) ? e0 : e1;
}
// Intersections of two primitives; `infA`/`infB` treat a segment as an infinite line.
function intersect(A, B, infA = false, infB = false) {
  if (A.k === "seg" && B.k === "seg") {
    const r = P(A.b.x - A.a.x, A.b.y - A.a.y), s = P(B.b.x - B.a.x, B.b.y - B.a.y);
    const den = r.x * s.y - r.y * s.x; if (Math.abs(den) < 1e-12) return [];
    const t = ((B.a.x - A.a.x) * s.y - (B.a.y - A.a.y) * s.x) / den;
    const u = ((B.a.x - A.a.x) * r.y - (B.a.y - A.a.y) * r.x) / den;
    const eps = 1e-9;
    if ((!infA && (t < -eps || t > 1 + eps)) || (!infB && (u < -eps || u > 1 + eps))) return [];
    return [P(A.a.x + r.x * t, A.a.y + r.y * t)];
  }
  if (A.k === "arc" && B.k === "seg") return intersect(B, A, infB, infA);
  if (A.k === "seg" && B.k === "arc") {
    const d = P(A.b.x - A.a.x, A.b.y - A.a.y), f = P(A.a.x - B.c.x, A.a.y - B.c.y);
    const a = d.x * d.x + d.y * d.y, b = 2 * (f.x * d.x + f.y * d.y), c = f.x * f.x + f.y * f.y - B.r * B.r;
    const disc = b * b - 4 * a * c; if (disc < 0 || !a) return [];
    const sq = Math.sqrt(disc), out = [];
    [(-b - sq) / (2 * a), (-b + sq) / (2 * a)].forEach((t, i) => {
      if (i && disc < 1e-18) return;
      if (!infA && (t < -1e-9 || t > 1 + 1e-9)) return;
      const q = P(A.a.x + d.x * t, A.a.y + d.y * t);
      if (arcHas(B, cadAng(B.c, q))) out.push(q);
    });
    return out;
  }
  const d = cadDist(A.c, B.c);
  if (!d || d > A.r + B.r + 1e-9 || d < Math.abs(A.r - B.r) - 1e-9) return [];
  const a = (A.r * A.r - B.r * B.r + d * d) / (2 * d), h = Math.sqrt(Math.max(0, A.r * A.r - a * a));
  const m = P(A.c.x + a * (B.c.x - A.c.x) / d, A.c.y + a * (B.c.y - A.c.y) / d);
  const pts = [P(m.x + h * (B.c.y - A.c.y) / d, m.y - h * (B.c.x - A.c.x) / d),
    P(m.x - h * (B.c.y - A.c.y) / d, m.y + h * (B.c.x - A.c.x) / d)];
  return pts.filter((q, i) => (!i || h > 1e-9) && arcHas(A, cadAng(A.c, q)) && arcHas(B, cadAng(B.c, q)));
}
function polyArea(pts) {
  let s = 0; for (let i = 0; i < pts.length; i++) { const a = pts[i], b = pts[(i + 1) % pts.length]; s += a.x * b.y - b.x * a.y; }
  return s / 2;
}
function entityLength(e) {
  return cadPrims(e).reduce((s, pr) => s + (pr.k === "seg" ? cadDist(pr.a, pr.b) : pr.r * (pr.a1 - pr.a0)), 0);
}
function entityArea(e) {
  if (e.type === "circle") return Math.PI * e.r * e.r;
  if (e.type === "ellipse") return Math.PI * e.rx * e.ry;
  if ((e.type === "polyline" && e.closed) || e.type === "hatch") {
    // polygon area + the circular segments of bulged edges
    const rings = e.type === "hatch" ? e.paths : [e.points];
    return rings.reduce((tot, pts) => {
      let a = polyArea(pts.map((v) => P(v[0], v[1])));
      pts.forEach((v, i) => {
        const b = v[2] || 0; if (!b) return;
        const q = pts[(i + 1) % pts.length], c = cadDist(P(v[0], v[1]), P(q[0], q[1]));
        const th = 4 * Math.atan(b), r = c / (2 * Math.abs(Math.sin(th / 2)));
        a += Math.sign(th) * (r * r / 2) * (Math.abs(th) - Math.sin(Math.abs(th)));
      });
      return tot + Math.abs(a);
    }, 0);
  }
  return null;
}

// ---------------- dimension geometry (shared by drawing and hit testing) ----------------
function dimGeometry(e) {
  if (e.type === "dim") {
    const p1 = P(e.x1, e.y1), p2 = P(e.x2, e.y2), L = cadDist(p1, p2) || 1;
    const n = P(-(p2.y - p1.y) / L, (p2.x - p1.x) / L);
    const a = P(p1.x + n.x * e.offset, p1.y + n.y * e.offset), b = P(p2.x + n.x * e.offset, p2.y + n.y * e.offset);
    return { p1, p2, a, b, value: L };
  }
  if (e.type === "ldim") {
    const p1 = P(e.x1, e.y1), p2 = P(e.x2, e.y2), base = P(e.bx, e.by), r = toRad(e.rot || 0);
    const u = P(Math.cos(r), Math.sin(r));
    const proj = (p) => { const t = (p.x - base.x) * u.x + (p.y - base.y) * u.y; return P(base.x + u.x * t, base.y + u.y * t); };
    const a = proj(p1), b = proj(p2);
    return { p1, p2, a, b, value: cadDist(a, b) };
  }
  if (e.type === "rdim") {
    const c = P(e.cx, e.cy), r = toRad(e.angle || 45), on = P(c.x + e.r * Math.cos(r), c.y + e.r * Math.sin(r));
    const from = e.diameter ? P(c.x - e.r * Math.cos(r), c.y - e.r * Math.sin(r)) : c;
    return { a: from, b: on, value: e.diameter ? 2 * e.r : e.r, prefix: e.diameter ? "Ø" : "R" };
  }
  return null;
}

// ---------------- drawing ----------------
function cadLineStyle(c, e, sel) {
  const ly = cadLayer(e.layer) || {};
  const lw = e.lineweight || ly.lineweight || 25;
  c.lineWidth = sel ? 2.4 : Math.max(1, Math.min(4, Math.round(lw / 25)));
  const lt = e.linetype || ly.linetype;
  const pat = CAD_LT_PATTERN[lt];
  if (sel) c.setLineDash([7, 4]);
  else if (pat && pat[0] * cadState.scale > 3) c.setLineDash(pat.map((v) => Math.max(1, v * cadState.scale)));
  else c.setLineDash([]);
}
function tracePrim(c, pr, move = true) {
  if (pr.k === "seg") {
    const a = cadScreen(pr.a), b = cadScreen(pr.b);
    if (move) c.moveTo(a.x, a.y); c.lineTo(b.x, b.y);
  } else {
    const s = cadScreen(pr.c);
    if (move) { const st = cadScreen(arcPoint(pr, pr.a0)); c.moveTo(st.x, st.y); }
    c.arc(s.x, s.y, pr.r * cadState.scale, -pr.a0, -pr.a1, true);
  }
}
function arrowHead(c, tip, from, size) {
  const a = Math.atan2(tip.y - from.y, tip.x - from.x);
  c.beginPath(); c.moveTo(tip.x, tip.y);
  c.lineTo(tip.x - size * Math.cos(a - 0.3), tip.y - size * Math.sin(a - 0.3));
  c.lineTo(tip.x - size * Math.cos(a + 0.3), tip.y - size * Math.sin(a + 0.3));
  c.closePath(); c.fill();
}
function drawDim(c, e) {
  const g = dimGeometry(e); if (!g) return;
  const s = cadState.scale, A = cadScreen(g.a), B = cadScreen(g.b);
  const txt = e.label || `${g.prefix || ""}${fmt(g.value)}`;
  c.setLineDash([]); c.lineWidth = 1;
  c.beginPath();
  if (g.p1) {
    const P1 = cadScreen(g.p1), P2 = cadScreen(g.p2);
    const ext = (from, to) => { const L = Math.hypot(to.x - from.x, to.y - from.y) || 1; c.moveTo(from.x, from.y); c.lineTo(to.x + (to.x - from.x) / L * 2 * s, to.y + (to.y - from.y) / L * 2 * s); };
    ext(P1, A); ext(P2, B);
  }
  c.moveTo(A.x, A.y); c.lineTo(B.x, B.y); c.stroke();
  const size = Math.max(5, 2.5 * s);
  if (g.p1 || e.diameter) arrowHead(c, A, B, size);
  arrowHead(c, B, A, size);
  let ang = Math.atan2(B.y - A.y, B.x - A.x);
  if (ang > Math.PI / 2 || ang < -Math.PI / 2) ang += Math.PI;
  const h = Math.max(9, 3.5 * s);
  c.save(); c.translate((A.x + B.x) / 2, (A.y + B.y) / 2); c.rotate(ang);
  c.font = `${h}px Arial, sans-serif`; c.textAlign = "center"; c.textBaseline = "bottom";
  c.fillText(txt, 0, -2); c.restore();
}
function drawHatch(c, e, sel) {
  c.beginPath();
  (e.paths || []).forEach((ring) => {
    cadPrims({ type: "hatch", paths: [ring] }).forEach((pr, k) => tracePrim(c, pr, k === 0));
    c.closePath();
  });
  if ((e.pattern || "SOLID") === "SOLID") {
    c.globalAlpha = sel ? 0.55 : 0.35; c.fill("evenodd"); c.globalAlpha = 1;
    return;
  }
  c.save(); c.clip("evenodd");
  const gap = Math.max(4, 3.175 * (e.scale || 1) * cadState.scale);
  const w = cadWrap.clientWidth, hgt = cadWrap.clientHeight;
  c.lineWidth = 1; c.setLineDash([]); c.beginPath();
  for (let x = -hgt; x < w; x += gap) { c.moveTo(x, hgt); c.lineTo(x + hgt, 0); }
  c.stroke(); c.restore();
}
function cadDrawEntity(e, sel = false, hover = false) {
  const c = cadCtx;
  c.save();
  c.strokeStyle = sel ? "#fbbf24" : (hover ? "#7dd3fc" : cadColorOf(e));
  c.fillStyle = c.strokeStyle;
  if (["dim", "ldim", "rdim"].includes(e.type)) { drawDim(c, e); c.restore(); return; }
  if (e.type === "hatch") { drawHatch(c, e, sel); c.restore(); return; }
  if (e.type === "text") {
    const p = cadScreen(P(e.x, e.y));
    c.translate(p.x, p.y); c.rotate(-toRad(e.rot || 0));
    c.font = `${Math.max(6, e.h * cadState.scale / 0.7)}px Arial, sans-serif`;
    c.textBaseline = "alphabetic"; c.fillText(e.text || "", 0, 0);
    c.restore(); return;
  }
  cadLineStyle(c, e, sel);
  c.beginPath();
  const prims = cadPrims(e);
  let last = null;
  prims.forEach((pr) => {
    const start = pr.k === "seg" ? pr.a : arcPoint(pr, pr.a0);
    tracePrim(c, pr, !last || cadDist(last, start) > 1e-7);
    last = pr.k === "seg" ? pr.b : arcPoint(pr, pr.a1);
  });
  if (e.type === "polyline" && e.closed) c.closePath();
  c.stroke(); c.restore();
}
function cadGridStep() {
  const n = Math.pow(10, Math.floor(Math.log10(75 / cadState.scale)));
  return [1, 2, 5, 10].map((x) => x * n).find((x) => x * cadState.scale >= 35) || n * 10;
}
function drawSnapMark(c, hit) {
  const s = cadScreen(hit.p), r = 6;
  c.save(); c.strokeStyle = "#22d3ee"; c.lineWidth = 2; c.setLineDash([]); c.beginPath();
  if (hit.kind === "end") c.rect(s.x - r, s.y - r, 2 * r, 2 * r);
  else if (hit.kind === "mid") { c.moveTo(s.x, s.y - r); c.lineTo(s.x + r, s.y + r); c.lineTo(s.x - r, s.y + r); c.closePath(); }
  else if (hit.kind === "center") c.arc(s.x, s.y, r, 0, TAU);
  else if (hit.kind === "quad") { c.moveTo(s.x, s.y - r); c.lineTo(s.x + r, s.y); c.lineTo(s.x, s.y + r); c.lineTo(s.x - r, s.y); c.closePath(); }
  else if (hit.kind === "int") { c.moveTo(s.x - r, s.y - r); c.lineTo(s.x + r, s.y + r); c.moveTo(s.x + r, s.y - r); c.lineTo(s.x - r, s.y + r); }
  else if (hit.kind === "perp") { c.moveTo(s.x - r, s.y + r); c.lineTo(s.x + r, s.y + r); c.moveTo(s.x - r, s.y + r); c.lineTo(s.x - r, s.y - r); c.moveTo(s.x - r, s.y); c.lineTo(s.x, s.y); c.lineTo(s.x, s.y + r); }
  else if (hit.kind === "near") { c.moveTo(s.x - r, s.y - r); c.lineTo(s.x + r, s.y - r); c.lineTo(s.x - r, s.y + r); c.lineTo(s.x + r, s.y + r); c.closePath(); }
  else if (hit.kind === "grid") { c.arc(s.x, s.y, 2, 0, TAU); }
  c.stroke();
  const names = { end: "uchi", mid: "o‘rtasi", center: "markaz", quad: "chorak", int: "kesishish", perp: "perpendikulyar", near: "yaqin nuqta" };
  if (names[hit.kind]) { c.font = "11px Segoe UI"; c.fillStyle = "#22d3ee"; c.fillText(names[hit.kind], s.x + 10, s.y - 10); }
  c.restore();
}
function cadGrips(e) {
  const t = e.type;
  if (t === "line") return [P(e.x1, e.y1), P(e.x2, e.y2), P((e.x1 + e.x2) / 2, (e.y1 + e.y2) / 2)];
  if (t === "polyline") return polyPts(e);
  if (t === "circle") return [P(e.cx, e.cy), ...[0, 90, 180, 270].map((a) => P(e.cx + e.r * Math.cos(toRad(a)), e.cy + e.r * Math.sin(toRad(a))))];
  if (t === "arc") return [P(e.cx, e.cy), ...cadPrims(e).flatMap((pr) => [arcPoint(pr, pr.a0), arcPoint(pr, pr.a1)])];
  if (t === "ellipse") return [P(e.cx, e.cy)];
  if (t === "text") return [P(e.x, e.y)];
  if (t === "dim" || t === "ldim") { const g = dimGeometry(e); return [g.p1, g.p2, P((g.a.x + g.b.x) / 2, (g.a.y + g.b.y) / 2)]; }
  if (t === "rdim") return [P(e.cx, e.cy), dimGeometry(e).b];
  if (t === "hatch") return [];
  return [];
}
function cadRender() {
  if (!cadState.ready) return;
  const w = cadWrap.clientWidth, h = cadWrap.clientHeight;
  const dpr = window.devicePixelRatio || 1;
  if (cadCanvas.width !== Math.round(w * dpr) || cadCanvas.height !== Math.round(h * dpr)) {
    cadCanvas.width = Math.round(w * dpr); cadCanvas.height = Math.round(h * dpr);
    cadCanvas.style.width = `${w}px`; cadCanvas.style.height = `${h}px`;
  }
  const c = cadCtx, css = getComputedStyle(document.documentElement);
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.fillStyle = css.getPropertyValue("--cad-bg").trim() || "#0b1325"; c.fillRect(0, 0, w, h);
  if (cadState.grid) {
    const step = cadGridStep() * cadState.scale;
    c.strokeStyle = css.getPropertyValue("--cad-grid").trim() || "#213050"; c.lineWidth = 1; c.beginPath();
    for (let x = ((cadState.ox % step) + step) % step; x < w; x += step) { c.moveTo(x, 0); c.lineTo(x, h); }
    for (let y = ((cadState.oy % step) + step) % step; y < h; y += step) { c.moveTo(0, y); c.lineTo(w, y); }
    c.stroke();
  }
  c.strokeStyle = "#526888"; c.lineWidth = 1; c.beginPath();
  c.moveTo(cadState.ox, 0); c.lineTo(cadState.ox, h); c.moveTo(0, cadState.oy); c.lineTo(w, cadState.oy); c.stroke();
  // UCS icon
  c.save(); c.strokeStyle = "#ef4444"; c.beginPath(); c.moveTo(16, h - 16); c.lineTo(46, h - 16); c.stroke();
  c.strokeStyle = "#22c55e"; c.beginPath(); c.moveTo(16, h - 16); c.lineTo(16, h - 46); c.stroke();
  c.fillStyle = "#94a3b8"; c.font = "10px Segoe UI"; c.fillText("X", 49, h - 12); c.fillText("Y", 12, h - 50); c.restore();
  cadState.doc.entities.forEach((e, i) => { if (cadVisible(e)) cadDrawEntity(e, cadState.selected.has(i), i === cadState.hover); });
  // grips of the selection
  if (cadState.tool === "select" && cadState.selected.size && cadState.selected.size <= 50) {
    c.fillStyle = "#3b82f6"; c.strokeStyle = "#dbeafe"; c.lineWidth = 1; c.setLineDash([]);
    cadState.selected.forEach((i) => (cadGrips(cadState.doc.entities[i]) || []).forEach((g) => {
      const s = cadScreen(g); c.fillRect(s.x - 4, s.y - 4, 8, 8); c.strokeRect(s.x - 4, s.y - 4, 8, 8);
    }));
  }
  cadDrawPreview(c);
  if (cadState.drag && (cadState.drag.kind === "select" || cadState.drag.kind === "zoomwin")) {
    const a = cadState.drag.from, b = cadState.drag.to, win = b.x >= a.x || cadState.drag.kind === "zoomwin";
    c.fillStyle = win ? "#3b82f630" : "#22c55e30"; c.strokeStyle = win ? "#3b82f6" : "#22c55e";
    c.setLineDash(win ? [] : [6, 4]);
    c.fillRect(a.x, a.y, b.x - a.x, b.y - a.y); c.strokeRect(a.x, a.y, b.x - a.x, b.y - a.y); c.setLineDash([]);
  }
  if (cadState.snapHit && cadState.tool !== "select") drawSnapMark(c, cadState.snapHit);
  if (cadState.cursor && cadState.tool !== "select") {
    const s = cadScreen(cadState.cursor); c.strokeStyle = "#cbd5e1"; c.lineWidth = 1; c.beginPath();
    c.moveTo(s.x - 14, s.y); c.lineTo(s.x + 14, s.y); c.moveTo(s.x, s.y - 14); c.lineTo(s.x, s.y + 14); c.stroke();
  }
  document.getElementById("cad-count").textContent = `${cadState.doc.entities.length} obyekt · ${cadState.selected.size} tanlangan · qatlam: ${cadState.layer}`;
  document.getElementById("cad-file").textContent = `${cadState.path || "Yangi chizma"}${cadState.dirty ? " •" : ""}`;
}
// What the current tool would create, drawn under the cursor.
function cadDrawPreview(c) {
  const pts = cadState.points, cur = cadState.cursor, t = cadState.tool;
  if (!cur) return;
  const ghost = cadPreviewEntities();
  c.save(); c.globalAlpha = 0.85;
  ghost.forEach((e) => { cadDrawEntity(Object.assign({ layer: cadState.layer }, e), false, true); });
  c.restore();
  if (pts.length && !["select"].includes(t) && !ghost.length) {
    c.save(); c.strokeStyle = "#67e8f9"; c.setLineDash([5, 4]); c.beginPath();
    const a = cadScreen(pts[pts.length - 1]), b = cadScreen(cur); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke(); c.restore();
  }
}
function cadPreviewEntities() {
  const pts = cadState.points, p = cadState.cursor, t = cadState.tool, o = cadState.opts;
  if (!p || !pts.length) return [];
  const a = pts[0];
  if (t === "line") return [{ type: "line", x1: pts.at(-1).x, y1: pts.at(-1).y, x2: p.x, y2: p.y }];
  if (t === "polyline") return [{ type: "polyline", points: [...pts, p].map((q) => [q.x, q.y, 0]), closed: false }];
  if (t === "rect") return [rectEntity(a, p)];
  if (t === "circle") return [{ type: "circle", cx: a.x, cy: a.y, r: Math.max(1e-6, cadDist(a, p)) }];
  if (t === "arc" && pts.length === 2) return [arcEntity(a, pts[1], p)];
  if (t === "arc") return [{ type: "line", x1: a.x, y1: a.y, x2: p.x, y2: p.y }];
  if (t === "ellipse" && pts.length === 1) return [{ type: "line", x1: a.x, y1: a.y, x2: p.x, y2: p.y }];
  if (t === "ellipse" && pts.length === 2) return [ellipseEntity(a, pts[1], p)];
  if (t === "polygon") return [polygonEntity(a, p, o.sides || 6)];
  if (t === "dim" && pts.length === 2) return [ldimEntity(a, pts[1], p)];
  if (t === "dimali" && pts.length === 2) return [dimEntity(a, pts[1], p)];
  if (["move", "copy", "paste"].includes(t)) return cadSelectedTransformed((q) => P(q.x + p.x - a.x, q.y + p.y - a.y));
  if (t === "rotate") return cadSelectedTransformed(rotFn(a, cadAng(a, p) - (o.refAngle || 0)), cadAng(a, p) - (o.refAngle || 0));
  if (t === "mirror" && pts.length === 1) return cadSelectedTransformed(mirFn(a, p), null, true);
  if (t === "scale") { const f = cadDist(a, p) / (o.refLen || 1); return f ? cadSelectedTransformed(sclFn(a, f), null, false, f) : []; }
  if (t === "zoomwin") return [rectEntity(a, p)];
  return [];
}

// ---------------- entity builders ----------------
function rectEntity(a, b) { return { type: "polyline", points: [[a.x, a.y, 0], [b.x, a.y, 0], [b.x, b.y, 0], [a.x, b.y, 0]], closed: true }; }
function arcEntity(c, s, e) { return { type: "arc", cx: c.x, cy: c.y, r: cadNum(cadDist(c, s)), start: cadNum(toDeg(cadAng(c, s))), end: cadNum(toDeg(cadAng(c, e))) }; }
function ellipseEntity(c, major, minor) {
  const rx = cadDist(c, major), rot = toDeg(cadAng(c, major));
  const u = P(Math.cos(toRad(rot)), Math.sin(toRad(rot)));
  const ry = Math.abs(-(minor.x - c.x) * u.y + (minor.y - c.y) * u.x) || rx / 2;
  return { type: "ellipse", cx: c.x, cy: c.y, rx: cadNum(rx), ry: cadNum(ry), rot: cadNum(rot) };
}
function polygonEntity(c, p, n) {
  const r = cadDist(c, p), a0 = cadAng(c, p);
  return { type: "polyline", closed: true, points: Array.from({ length: n }, (_, i) => [cadNum(c.x + r * Math.cos(a0 + TAU * i / n)), cadNum(c.y + r * Math.sin(a0 + TAU * i / n)), 0]) };
}
function dimEntity(a, b, p) {
  const L = cadDist(a, b) || 1;
  return { type: "dim", x1: a.x, y1: a.y, x2: b.x, y2: b.y, label: "", offset: cadNum((-(b.y - a.y) * (p.x - a.x) + (b.x - a.x) * (p.y - a.y)) / L) };
}
// AutoCAD DIMLINEAR: the third point decides horizontal (0°) or vertical (90°).
function ldimEntity(a, b, p) {
  const minx = Math.min(a.x, b.x), maxx = Math.max(a.x, b.x), miny = Math.min(a.y, b.y), maxy = Math.max(a.y, b.y);
  const vertical = (p.x < minx || p.x > maxx) && p.y >= miny && p.y <= maxy;
  return { type: "ldim", x1: a.x, y1: a.y, x2: b.x, y2: b.y, bx: cadNum(p.x), by: cadNum(p.y), rot: vertical ? 90 : 0, label: "" };
}

// ---------------- transforms ----------------
const rotFn = (c, t) => (p) => P(c.x + (p.x - c.x) * Math.cos(t) - (p.y - c.y) * Math.sin(t), c.y + (p.x - c.x) * Math.sin(t) + (p.y - c.y) * Math.cos(t));
const mirFn = (a, b) => { const t = cadAng(a, b), co = Math.cos(2 * t), si = Math.sin(2 * t); return (p) => P(a.x + (p.x - a.x) * co + (p.y - a.y) * si, a.y + (p.x - a.x) * si - (p.y - a.y) * co); };
const sclFn = (c, f) => (p) => P(c.x + (p.x - c.x) * f, c.y + (p.y - c.y) * f);
// fn maps points; rot (radians) for rotations; mirror flips orientation; f scales sizes.
function cadTransform(e, fn, rot = null, mirror = false, f = 1) {
  const o = cadClone(e);
  const pt = (x, y) => fn(P(x, y));
  const set = (kx, ky) => { const q = pt(o[kx], o[ky]); o[kx] = cadNum(q.x); o[ky] = cadNum(q.y); };
  const angOf = (deg) => { const c = pt(0, 0), d = pt(Math.cos(toRad(deg)), Math.sin(toRad(deg))); return toDeg(cadAng(c, d)); };
  if (o.type === "line") { set("x1", "y1"); set("x2", "y2"); }
  else if (o.type === "polyline") o.points = o.points.map((v) => { const q = pt(v[0], v[1]); return [cadNum(q.x), cadNum(q.y), mirror ? -(v[2] || 0) : (v[2] || 0)]; });
  else if (o.type === "hatch") o.paths = o.paths.map((r) => r.map((v) => { const q = pt(v[0], v[1]); return [cadNum(q.x), cadNum(q.y), mirror ? -(v[2] || 0) : (v[2] || 0)]; }));
  else if (o.type === "circle") { set("cx", "cy"); o.r = cadNum(o.r * f); }
  else if (o.type === "arc") {
    set("cx", "cy"); o.r = cadNum(o.r * f);
    let s = angOf(o.start), en = angOf(o.end); if (mirror) [s, en] = [en, s];
    o.start = cadNum(s); o.end = cadNum(en);
  } else if (o.type === "ellipse") { set("cx", "cy"); o.rx = cadNum(o.rx * f); o.ry = cadNum(o.ry * f); o.rot = cadNum(angOf(o.rot || 0)); }
  else if (o.type === "text") { set("x", "y"); o.h = cadNum(o.h * f); if (!mirror) o.rot = cadNum(angOf(o.rot || 0)); }
  else if (o.type === "dim") { set("x1", "y1"); set("x2", "y2"); o.offset = cadNum((mirror ? -1 : 1) * o.offset * f); }
  else if (o.type === "ldim") { set("x1", "y1"); set("x2", "y2"); set("bx", "by"); o.rot = cadNum(angOf(o.rot || 0) % 180); }
  else if (o.type === "rdim") { set("cx", "cy"); o.r = cadNum(o.r * f); o.angle = cadNum(angOf(o.angle || 45)); }
  return o;
}
function cadSelectedTransformed(fn, rot = null, mirror = false, f = 1) {
  const src = cadState.tool === "paste" ? (cadState.clipboard || []) : [...cadState.selected].map((i) => cadState.doc.entities[i]);
  return src.slice(0, 400).map((e) => cadTransform(e, fn, rot, mirror, f));
}

// ---------------- snapping ----------------
function cadSnapPoints(e) {
  const out = [];
  if (e.type === "text") return [{ p: P(e.x, e.y), kind: "end" }];
  if (["dim", "ldim", "rdim"].includes(e.type)) return [];
  cadPrims(e).forEach((pr) => {
    if (pr.k === "seg") {
      out.push({ p: pr.a, kind: "end" }, { p: pr.b, kind: "end" }, { p: P((pr.a.x + pr.b.x) / 2, (pr.a.y + pr.b.y) / 2), kind: "mid" });
    } else {
      out.push({ p: pr.c, kind: "center" });
      [0, Math.PI / 2, Math.PI, 1.5 * Math.PI].forEach((a) => { if (arcHas(pr, a)) out.push({ p: arcPoint(pr, a), kind: "quad" }); });
      if (pr.a1 - pr.a0 < TAU - 1e-9) {
        out.push({ p: arcPoint(pr, pr.a0), kind: "end" }, { p: arcPoint(pr, pr.a1), kind: "end" }, { p: arcPoint(pr, (pr.a0 + pr.a1) / 2), kind: "mid" });
      }
    }
  });
  return out;
}
function cadFindSnap(raw, base) {
  const tol = 12 / cadState.scale;
  let best = null, bestD = tol;
  const near = [];
  cadState.doc.entities.forEach((e) => {
    if (!cadVisible(e)) return;
    const prims = cadPrims(e);
    if (prims.some((pr) => cadDist(nearestOn(pr, raw), raw) < tol * 3)) near.push(prims);
    cadSnapPoints(e).forEach((s) => { const d = cadDist(s.p, raw); if (d < bestD) { bestD = d; best = s; } });
  });
  if (!best) { // intersections of what is under the cursor
    const prims = near.flat();
    for (let i = 0; i < prims.length && i < 300; i++) for (let j = i + 1; j < prims.length && j < 300; j++) {
      intersect(prims[i], prims[j]).forEach((q) => { const d = cadDist(q, raw); if (d < bestD) { bestD = d; best = { p: q, kind: "int" }; } });
    }
  }
  if (!best && base) { // perpendicular from the last point
    near.flat().forEach((pr) => {
      if (pr.k !== "seg") return;
      const dx = pr.b.x - pr.a.x, dy = pr.b.y - pr.a.y, L = dx * dx + dy * dy || 1;
      const t = ((base.x - pr.a.x) * dx + (base.y - pr.a.y) * dy) / L;
      if (t < 0 || t > 1) return;
      const q = P(pr.a.x + dx * t, pr.a.y + dy * t), d = cadDist(q, raw);
      if (d < bestD) { bestD = d; best = { p: q, kind: "perp" }; }
    });
  }
  if (!best) {
    let nd = tol * 0.6;
    near.flat().forEach((pr) => { const q = nearestOn(pr, raw), d = cadDist(q, raw); if (d < nd) { nd = d; best = { p: q, kind: "near" }; } });
  }
  return best;
}
function cadSnap(raw, base = null) {
  let hit = null;
  if (cadState.snap) hit = cadFindSnap(raw, base);
  if (!hit && cadState.grid && cadState.snap) {
    const step = cadGridStep() / 5 >= 1 ? cadGridStep() / 5 : cadGridStep();
    const g = P(Math.round(raw.x / step) * step, Math.round(raw.y / step) * step);
    if (cadDist(g, raw) < 6 / cadState.scale) hit = { p: g, kind: "grid" };
  }
  let q = hit ? hit.p : raw;
  if (cadState.ortho && base && (!hit || hit.kind === "grid" || hit.kind === "near")) {
    q = Math.abs(q.x - base.x) >= Math.abs(q.y - base.y) ? P(q.x, base.y) : P(base.x, q.y);
    hit = null;
  }
  cadState.snapHit = hit;
  return P(cadNum(q.x), cadNum(q.y));
}

// ---------------- hit testing ----------------
function cadHit(e, p, tol) {
  if (e.type === "text") {
    const w = (e.text || "").length * e.h * 0.62, r = -toRad(e.rot || 0);
    const dx = p.x - e.x, dy = p.y - e.y, lx = dx * Math.cos(r) - dy * Math.sin(r), ly = dx * Math.sin(r) + dy * Math.cos(r);
    return lx >= -tol && lx <= w + tol && ly >= -tol && ly <= e.h + tol;
  }
  if (["dim", "ldim", "rdim"].includes(e.type)) {
    const g = dimGeometry(e);
    return cadDist(nearestOn({ k: "seg", a: g.a, b: g.b }, p), p) <= tol;
  }
  if (e.type === "hatch") {
    const pts = e.paths.flat().map((v) => P(v[0], v[1]));
    return cadInside(p, e.paths) || pts.some((q) => cadDist(q, p) < tol);
  }
  return cadPrims(e).some((pr) => cadDist(nearestOn(pr, p), p) <= tol);
}
function cadInside(p, rings) {
  let inside = false;
  rings.forEach((r) => {
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const a = r[i], b = r[j];
      if ((a[1] > p.y) !== (b[1] > p.y) && p.x < (b[0] - a[0]) * (p.y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
  });
  return inside;
}
function cadPick(p, types = null) {
  const tol = 7 / cadState.scale;
  for (let i = cadState.doc.entities.length - 1; i >= 0; i--) {
    const e = cadState.doc.entities[i];
    if (types && !types.includes(e.type)) continue;
    if (cadVisible(e) && !cadLocked(e) && cadHit(e, p, tol)) return i;
  }
  return -1;
}
function cadBounds(e) {
  let pts = [];
  if (e.type === "text") { const w = (e.text || "").length * e.h * 0.62; pts = [P(e.x, e.y), P(e.x + w, e.y + e.h)]; }
  else if (["dim", "ldim", "rdim"].includes(e.type)) { const g = dimGeometry(e); pts = [g.a, g.b, ...(g.p1 ? [g.p1, g.p2] : [])]; }
  else cadPrims(e).forEach((pr) => {
    if (pr.k === "seg") pts.push(pr.a, pr.b);
    else { pts.push(arcPoint(pr, pr.a0), arcPoint(pr, pr.a1)); [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5].forEach((m) => { const a = m * Math.PI; if (arcHas(pr, a)) pts.push(arcPoint(pr, a)); }); }
  });
  if (!pts.length) return null;
  return { x1: Math.min(...pts.map((q) => q.x)), y1: Math.min(...pts.map((q) => q.y)), x2: Math.max(...pts.map((q) => q.x)), y2: Math.max(...pts.map((q) => q.y)) };
}
function cadZoomTo(x1, y1, x2, y2) {
  const w = cadWrap.clientWidth || 800, h = cadWrap.clientHeight || 500;
  cadState.scale = Math.min(2000, Math.max(0.0005, Math.min((w - 60) / (x2 - x1 || 1), (h - 60) / (y2 - y1 || 1))));
  cadState.ox = w / 2 - (x1 + x2) / 2 * cadState.scale;
  cadState.oy = h / 2 + (y1 + y2) / 2 * cadState.scale;
  cadRender();
}
function cadExtents() {
  const boxes = cadState.doc.entities.filter(cadVisible).map(cadBounds).filter(Boolean);
  if (!boxes.length) { cadState.scale = 3; cadState.ox = (cadWrap.clientWidth || 800) / 2; cadState.oy = (cadWrap.clientHeight || 500) / 2; cadRender(); return; }
  cadZoomTo(Math.min(...boxes.map((b) => b.x1)), Math.min(...boxes.map((b) => b.y1)), Math.max(...boxes.map((b) => b.x2)), Math.max(...boxes.map((b) => b.y2)));
}

// ---------------- log, prompt, undo ----------------
function cadLog(message) {
  const log = document.getElementById("cad-log");
  const line = document.createElement("div"); line.textContent = message; log.appendChild(line);
  while (log.children.length > 40) log.firstChild.remove();
  log.scrollTop = log.scrollHeight;
}
function cadPrompt(message) {
  document.getElementById("cad-prompt").textContent = message || "Buyruq:";
  document.getElementById("cad-hint").textContent = message && message !== "Buyruq:" ? message : "";
}
function cadSnapshot() {
  cadState.undo.push(cadClone(cadState.doc));
  if (cadState.undo.length > 100) cadState.undo.shift();
  cadState.redo.length = 0; cadState.dirty = true;
}
function cadAdd(entities, keepPoints = false) {
  const own = cadState.color !== 256 ? { color: cadState.color } : {};
  const list = entities.filter(Boolean).map((e) => Object.assign({ layer: cadState.layer }, own, e));
  if (!list.length) return;
  cadSnapshot(); cadState.doc.entities.push(...list);
  if (!keepPoints) cadState.points = [];
  cadRender(); cadRenderProps();
}
function cadRestore(from, to) {
  if (!from.length) { cadLog("Bekor qiladigan amal yo‘q."); return; }
  to.push(cadClone(cadState.doc)); cadState.doc = from.pop();
  cadState.selected.clear(); cadState.points = []; cadState.dirty = true;
  if (!cadLayer(cadState.layer)) cadState.layer = cadState.doc.layers[0].name;
  cadRenderLayers(); cadRender(); cadRenderProps();
}

// ---------------- tools ----------------
const NEEDS_SELECTION = ["move", "copy", "rotate", "mirror", "scale", "array", "parray", "explode"];
const TOOL_PROMPTS = {
  line: "birinchi nuqta", polyline: "birinchi nuqta", rect: "birinchi burchak", circle: "markaz",
  arc: "markaz", ellipse: "markaz", polygon: "markaz", text: "matn joyi", hatch: "yopiq shakl ichiga bosing",
  dim: "birinchi nuqta", dimali: "birinchi nuqta", dimrad: "aylana yoki yoyni tanlang", dimdia: "aylana yoki yoyni tanlang",
  move: "tayanch nuqta", copy: "tayanch nuqta", rotate: "burish markazi", mirror: "ko‘zgu chizig‘ining 1-nuqtasi",
  scale: "tayanch nuqta", trim: "kesib tashlanadigan qismni bosing", extend: "uzaytiriladigan chiziq uchini bosing",
  fillet: "birinchi chiziqni tanlang", chamfer: "birinchi chiziqni tanlang", array: "qatorlar sonini yozing",
  parray: "aylana markazi", measure: "birinchi nuqta", area: "yopiq shaklni bosing yoki nuqtalarni ko‘rsating",
  zoomwin: "oynaning birinchi burchagi", offset: "masofani yozing", paste: "qo‘yish nuqtasi",
};
function cadSetTool(tool) {
  if (NEEDS_SELECTION.includes(tool) && !cadState.selected.size) {
    cadLog(`${CAD_TOOLS[tool]}: avval obyekt(lar)ni tanlang, keyin buyruqni bering.`); tool = "select";
  }
  if (tool !== "select" && tool !== "measure" && tool !== "zoomwin") cadState.lastTool = tool;
  cadState.tool = tool; cadState.points = []; cadState.opts = {}; cadState.ask = null; cadState.drag = null;
  document.querySelectorAll("#cad-toolbar [data-tool]").forEach((b) => b.classList.toggle("active", b.dataset.tool === tool));
  if (tool === "select") cadPrompt("Buyruq:");
  else cadPrompt(`${CAD_TOOLS[tool]}: ${TOOL_PROMPTS[tool] || "nuqta"}:`);
  if (tool === "polygon") cadAsk("number", "Ko‘pburchak: tomonlar soni <6>:", (n) => { cadState.opts.sides = Math.max(3, Math.min(64, Math.round(n || 6))); cadPrompt("Ko‘pburchak: markaz:"); }, 6);
  if (tool === "offset") cadAsk("number", `Parallel nusxa: masofa <${cadState.opts.dist || 10}>:`, (n) => { cadState.opts.dist = n || 10; cadPrompt("Parallel nusxa: obyektni bosing:"); }, 10);
  if (tool === "fillet") { cadState.opts.radius = cadState.filletR ?? 5; cadPrompt(`Yumaloqlash (radius ${fmt(cadState.opts.radius)}; «R 10» — o‘zgartirish): birinchi chiziq:`); }
  if (tool === "chamfer") { cadState.opts.dist = cadState.chamferD ?? 5; cadPrompt(`Faska (${fmt(cadState.opts.dist)} mm; «D 3» — o‘zgartirish): birinchi chiziq:`); }
  if (tool === "array") cadArrayAsk();
  if (tool === "explode") { cadExplode(); return; }
  cadRender();
}
function cadAsk(type, label, handler, def = null) { cadState.ask = { type, label, handler, def }; cadPrompt(label); }
function cadArrayAsk() {
  const o = cadState.opts;
  cadAsk("number", "Massiv: qatorlar soni <3>:", (r) => {
    o.rows = Math.max(1, Math.min(200, Math.round(r || 3)));
    cadAsk("number", "Massiv: ustunlar soni <3>:", (c) => {
      o.cols = Math.max(1, Math.min(200, Math.round(c || 3)));
      cadAsk("number", "Massiv: qatorlar oralig‘i (mm) <20>:", (dy) => {
        o.dy = dy || 20;
        cadAsk("number", "Massiv: ustunlar oralig‘i (mm) <20>:", (dx) => {
          o.dx = dx || 20;
          const src = [...cadState.selected].map((i) => cadState.doc.entities[i]), out = [];
          for (let i = 0; i < o.rows; i++) for (let j = 0; j < o.cols; j++) {
            if (!i && !j) continue;
            src.forEach((e) => out.push(cadTransform(e, (q) => P(q.x + j * o.dx, q.y + i * o.dy))));
          }
          if (out.length > 20000) { cadLog("Juda ko‘p nusxa (20 000 gacha)."); cadSetTool("select"); return; }
          cadAdd(out); cadLog(`Massiv: ${o.rows} × ${o.cols}, ${out.length} ta yangi obyekt.`); cadSetTool("select");
        }, 20);
      }, 20);
    }, 3);
  }, 3);
}
function cadTakePoint(p) {
  const t = cadState.tool, pts = cadState.points, o = cadState.opts;
  if (cadState.ask && cadState.ask.type !== "point") { cadLog("Avval so‘ralgan qiymatni yozing (yoki Enter)."); return; }
  if (t === "select") return;
  // tools that pick objects instead of free points
  if (["trim", "extend", "fillet", "chamfer", "dimrad", "dimdia", "hatch", "offset"].includes(t) || (t === "area" && !pts.length && cadPick(p) >= 0)) {
    cadPickTool(t, p); return;
  }
  pts.push(p);
  const n = pts.length, a = pts[0];
  if (t === "line" && n >= 2) {
    if (cadDist(pts[n - 2], p)) cadAdd([{ type: "line", x1: pts[n - 2].x, y1: pts[n - 2].y, x2: p.x, y2: p.y }], true);
    cadState.points = [pts[0], p].slice(-1);
    cadState.opts.chain = (o.chain || [a]).concat([p]);
    cadPrompt("Chiziq: keyingi nuqta (Enter — tugatish, «Y» — yopish, «U» — orqaga):"); cadRender(); return;
  }
  if (t === "polyline") { cadPrompt("Polichiziq: keyingi nuqta (Enter — tugatish, «Y» — yopish):"); cadRender(); return; }
  if (t === "rect" && n === 2) { cadAdd([rectEntity(a, p)]); cadSetTool(t); return; }
  if (t === "circle" && n === 2) { if (cadDist(a, p)) cadAdd([{ type: "circle", cx: a.x, cy: a.y, r: cadNum(cadDist(a, p)) }]); cadSetTool(t); return; }
  if (t === "circle" && n === 1) { cadPrompt("Aylana: radius (raqam) yoki nuqta:"); cadRender(); return; }
  if (t === "arc" && n === 3) { cadAdd([arcEntity(a, pts[1], p)]); cadSetTool(t); return; }
  if (t === "arc") { cadPrompt(n === 1 ? "Yoy: boshlanish nuqtasi:" : "Yoy: tugash nuqtasi (soat strelkasiga teskari):"); cadRender(); return; }
  if (t === "ellipse" && n === 3) { cadAdd([ellipseEntity(a, pts[1], p)]); cadSetTool(t); return; }
  if (t === "ellipse") { cadPrompt(n === 1 ? "Ellips: katta o‘q uchi:" : "Ellips: kichik o‘q uzunligi (nuqta):"); cadRender(); return; }
  if (t === "polygon" && n === 2) { cadAdd([polygonEntity(a, p, o.sides || 6)]); cadSetTool(t); return; }
  if (t === "polygon") { cadPrompt("Ko‘pburchak: uchi (radius):"); cadRender(); return; }
  if (t === "text" && n === 1) {
    cadAsk("text", `Matn: balandligi ${fmt(cadState.textH || 3.5)} mm — matnni yozing va Enter:`, (s) => {
      if (s) cadAdd([{ type: "text", x: p.x, y: p.y, text: s, h: cadState.textH || 3.5, rot: 0 }]);
      cadSetTool("text");
    });
    return;
  }
  if ((t === "dim" || t === "dimali") && n === 3) { cadAdd([t === "dim" ? ldimEntity(a, pts[1], p) : dimEntity(a, pts[1], p)]); cadSetTool(t); return; }
  if (t === "dim" || t === "dimali") { cadPrompt(n === 1 ? "O‘lcham: ikkinchi nuqta:" : "O‘lcham: o‘lcham chizig‘i joyi:"); cadRender(); return; }
  if (t === "measure" && n === 2) {
    const d = cadDist(a, p), ang = toDeg(cadAng(a, p));
    cadLog(`Masofa: ${fmt(d)} mm · burchak ${fmt(ang)}° · ΔX ${fmt(p.x - a.x)} · ΔY ${fmt(p.y - a.y)}`); cadSetTool("select"); return;
  }
  if (t === "area") { cadPrompt("Yuza: keyingi nuqta (Enter — hisoblash):"); cadRender(); return; }
  if (t === "zoomwin" && n === 2) { cadZoomTo(Math.min(a.x, p.x), Math.min(a.y, p.y), Math.max(a.x, p.x), Math.max(a.y, p.y)); cadSetTool("select"); return; }
  if (t === "move" || t === "copy" || t === "paste") {
    if (n === 1 && t !== "paste") { cadPrompt(`${CAD_TOOLS[t]}: yangi joy (yoki @dx,dy):`); cadRender(); return; }
    const base = t === "paste" ? o.base : a;
    const moved = cadSelectedTransformed((q) => P(q.x + p.x - base.x, q.y + p.y - base.y));
    if (t === "move") { cadSnapshot(); [...cadState.selected].forEach((i, k) => { cadState.doc.entities[i] = moved[k]; }); cadLog("Ko‘chirildi."); cadState.selected.clear(); cadSetTool("select"); }
    else { cadAdd(moved, true); cadState.points = t === "copy" ? [a] : []; cadLog(t === "copy" ? "Nusxa qo‘yildi (yana joy ko‘rsating yoki Enter)." : "Qo‘yildi."); if (t === "paste") cadSetTool("select"); }
    cadRender(); return;
  }
  if (t === "rotate") {
    if (n === 1) { cadPrompt("Burish: burchak (raqam, gradus) yoki nuqta:"); cadRender(); return; }
    cadRotateBy(a, cadAng(a, p) - (o.refAngle || 0)); return;
  }
  if (t === "scale") {
    if (n === 1) { o.refLen = 1; cadPrompt("Masshtab: koeffitsient (masalan 2 yoki 0,5):"); cadRender(); return; }
    cadScaleBy(a, cadDist(a, p) / (o.refLen || 1)); return;
  }
  if (t === "mirror" && n === 2) {
    const out = cadSelectedTransformed(mirFn(a, p), null, true);
    cadAsk("text", "Ko‘zgu: asl obyektlar o‘chirilsinmi? (H/Y) <Y>:", (s) => {
      const del = /^h/i.test(s || "");
      cadSnapshot();
      if (del) cadState.doc.entities = cadState.doc.entities.filter((_, i) => !cadState.selected.has(i));
      cadState.doc.entities.push(...out); cadState.selected.clear(); cadLog("Ko‘zgu bajarildi."); cadSetTool("select");
    });
    return;
  }
  if (t === "mirror") { cadPrompt("Ko‘zgu: chiziqning ikkinchi nuqtasi:"); cadRender(); return; }
  if (t === "parray" && n === 1) {
    cadAsk("number", "Aylana massiv: nusxalar soni (asli bilan) <6>:", (k) => {
      const cnt = Math.max(2, Math.min(360, Math.round(k || 6)));
      cadAsk("number", "Aylana massiv: umumiy burchak <360>:", (ang) => {
        const total = toRad(ang || 360), step = Math.abs(total - TAU) < 1e-9 ? total / cnt : total / (cnt - 1), out = [];
        const src = [...cadState.selected].map((i) => cadState.doc.entities[i]);
        for (let i = 1; i < cnt; i++) src.forEach((e) => out.push(cadTransform(e, rotFn(a, step * i), step * i)));
        cadAdd(out); cadLog(`Aylana massiv: ${cnt} ta.`); cadSetTool("select");
      }, 360);
    }, 6);
    return;
  }
  cadRender();
}
function cadRotateBy(c, t) {
  const out = cadSelectedTransformed(rotFn(c, t), t);
  cadSnapshot(); [...cadState.selected].forEach((i, k) => { cadState.doc.entities[i] = out[k]; });
  cadLog(`Burildi: ${fmt(toDeg(t))}°.`); cadState.selected.clear(); cadSetTool("select");
}
function cadScaleBy(c, f) {
  if (!(f > 0)) { cadLog("Koeffitsient musbat bo‘lishi kerak."); return; }
  const out = cadSelectedTransformed(sclFn(c, f), null, false, f);
  cadSnapshot(); [...cadState.selected].forEach((i, k) => { cadState.doc.entities[i] = out[k]; });
  cadLog(`Masshtab: ×${fmt(f)}.`); cadState.selected.clear(); cadSetTool("select");
}

// ---------------- tools that pick objects ----------------
function cadOthersPrims(skip) {
  const out = [];
  cadState.doc.entities.forEach((e, i) => { if (i !== skip && cadVisible(e) && !["text", "dim", "ldim", "rdim", "hatch"].includes(e.type)) out.push(...cadPrims(e)); });
  return out;
}
const CAD_PICK_TYPES = {
  trim: ["line", "circle", "arc", "polyline"], extend: ["line", "arc"], fillet: ["line"], chamfer: ["line"],
  dimrad: ["circle", "arc"], dimdia: ["circle", "arc"], offset: ["line", "circle", "arc", "polyline"],
};
function cadPickTool(t, p) {
  const i = cadPick(p, CAD_PICK_TYPES[t] || null);
  if (t === "hatch") { cadHatchAt(p, i); return; }
  if (i < 0) { cadLog("Bu yerda obyekt yo‘q."); return; }
  const e = cadState.doc.entities[i];
  if (t === "trim") { cadTrim(i, p); return; }
  if (t === "extend") { cadExtend(i, p); return; }
  if (t === "dimrad" || t === "dimdia") {
    if (e.type !== "circle" && e.type !== "arc") { cadLog("Aylana yoki yoyni tanlang."); return; }
    const ang = cadNum(toDeg(cadAng(P(e.cx, e.cy), p)));
    cadAdd([{ type: "rdim", cx: e.cx, cy: e.cy, r: e.r, angle: ang, diameter: t === "dimdia", label: "" }]);
    return;
  }
  if (t === "offset") {
    if (!["line", "circle", "arc", "polyline"].includes(e.type)) { cadLog("Chiziq, aylana, yoy yoki polichiziqni tanlang."); return; }
    cadState.opts.target = i; cadState.tool = "offset-side"; cadPrompt("Parallel nusxa: qaysi tomonga? (bosing)"); return;
  }
  if (t === "area") { const A = entityArea(e); cadLog(A == null ? "Bu obyekt yopiq emas." : `Yuza: ${fmt(A)} mm² (${fmt(A / 100)} sm²) · perimetr ${fmt(entityLength(e))} mm`); cadSetTool("select"); return; }
  if (t === "fillet" || t === "chamfer") {
    if (e.type !== "line") { cadLog("Hozircha ikki chiziq (LINE) uchun. Polichiziqni avval bo‘laklang (X)."); return; }
    const o = cadState.opts;
    if (o.first == null) { o.first = i; o.p1 = p; cadPrompt(`${CAD_TOOLS[t]}: ikkinchi chiziq:`); cadState.selected = new Set([i]); cadRender(); return; }
    if (o.first === i) return;
    cadCorner(t, o.first, o.p1, i, p); return;
  }
}
// AutoCAD-style quick trim: every other object cuts; the clicked piece disappears.
function cadTrim(i, p) {
  const e = cadState.doc.entities[i];
  if (!["line", "circle", "arc", "polyline"].includes(e.type)) { cadLog("Bu obyekt kesilmaydi."); return; }
  let list = [e];
  if (e.type === "polyline") list = cadExplodeOne(e);
  const others = cadOthersPrims(i);
  const keep = [];
  let done = false;
  list.forEach((part) => {
    const pr = cadPrims(part)[0];
    const hit = !done && cadDist(nearestOn(pr, p), p) <= 8 / cadState.scale;
    if (!hit) { keep.push(part); return; }
    done = true;
    const cuts = [];
    // other parts of the same exploded polyline also cut
    const own = list.filter((q) => q !== part).flatMap(cadPrims);
    [...others, ...own].forEach((o) => intersect(pr, o).forEach((q) => cuts.push(q)));
    if (pr.k === "seg") {
      const L = cadDist(pr.a, pr.b), ts = cuts.map((q) => cadDist(pr.a, q) / L).filter((t) => t > 1e-6 && t < 1 - 1e-6).sort((a, b) => a - b);
      const tc = cadDist(pr.a, nearestOn(pr, p)) / L;
      const lo = Math.max(0, ...ts.filter((t) => t < tc)), hi = Math.min(1, ...ts.filter((t) => t > tc));
      const at = (t) => P(pr.a.x + (pr.b.x - pr.a.x) * t, pr.a.y + (pr.b.y - pr.a.y) * t);
      if (lo > 0) keep.push(Object.assign(cadClone(part), { type: "line", x1: pr.a.x, y1: pr.a.y, x2: at(lo).x, y2: at(lo).y }));
      if (hi < 1) keep.push(Object.assign(cadClone(part), { type: "line", x1: at(hi).x, y1: at(hi).y, x2: pr.b.x, y2: pr.b.y }));
      if (!ts.length) cadLog("Kesuvchi obyekt yo‘q — butun chiziq o‘chirildi.");
    } else {
      const full = pr.a1 - pr.a0 >= TAU - 1e-9;
      const rel = (a) => normA(a - pr.a0);
      const ac = rel(cadAng(pr.c, p));
      let angs = cuts.map((q) => rel(cadAng(pr.c, q))).filter((a) => a > 1e-7 && a < (full ? TAU : pr.a1 - pr.a0) - 1e-7).sort((x, y) => x - y);
      angs = angs.filter((a, k) => !k || a - angs[k - 1] > 1e-7);
      if (!angs.length) { if (!full) cadLog("Kesuvchi obyekt yo‘q — yoy o‘chirildi."); else { keep.push(part); cadLog("Aylanani kesish uchun kamida ikkita kesishish kerak."); } return; }
      const base = { cx: cadNum(pr.c.x), cy: cadNum(pr.c.y), r: cadNum(pr.r), layer: part.layer, color: part.color };
      if (full) {
        if (angs.length < 2) { keep.push(part); cadLog("Aylanani kesish uchun kamida ikkita kesishish kerak."); return; }
        const after = angs.find((a) => a > ac) ?? angs[0] + TAU, before = [...angs].reverse().find((a) => a < ac) ?? angs.at(-1) - TAU;
        keep.push(Object.assign({}, base, { type: "arc", start: cadNum(toDeg(pr.a0 + after)), end: cadNum(toDeg(pr.a0 + before)) }));
      } else {
        const lo = Math.max(0, ...angs.filter((a) => a < ac)), hi = Math.min(pr.a1 - pr.a0, ...angs.filter((a) => a > ac));
        if (lo > 0) keep.push(Object.assign({}, base, { type: "arc", start: cadNum(toDeg(pr.a0)), end: cadNum(toDeg(pr.a0 + lo)) }));
        if (hi < pr.a1 - pr.a0) keep.push(Object.assign({}, base, { type: "arc", start: cadNum(toDeg(pr.a0 + hi)), end: cadNum(toDeg(pr.a1)) }));
      }
    }
  });
  cadSnapshot();
  cadState.doc.entities.splice(i, 1, ...keep.map((k) => { Object.keys(k).forEach((x) => k[x] === undefined && delete k[x]); return k; }));
  cadState.selected.clear(); cadRender();
}
function cadExtend(i, p) {
  const e = cadState.doc.entities[i];
  if (e.type !== "line" && e.type !== "arc") { cadLog("Chiziq yoki yoyni tanlang."); return; }
  const others = cadOthersPrims(i);
  if (e.type === "line") {
    const a = P(e.x1, e.y1), b = P(e.x2, e.y2), endB = cadDist(p, b) < cadDist(p, a);
    const from = endB ? a : b, to = endB ? b : a, L = cadDist(from, to);
    const ray = { k: "seg", a: from, b: to };
    let best = null;
    others.forEach((o) => intersect(ray, o, true, false).forEach((q) => {
      const t = ((q.x - from.x) * (to.x - from.x) + (q.y - from.y) * (to.y - from.y)) / (L * L);
      if (t > 1 + 1e-9 && (!best || t < best.t)) best = { t, q };
    }));
    if (!best) { cadLog("Uzaytiradigan chegara topilmadi."); return; }
    cadSnapshot();
    const o = cadState.doc.entities[i];
    if (endB) { o.x2 = cadNum(best.q.x); o.y2 = cadNum(best.q.y); } else { o.x1 = cadNum(best.q.x); o.y1 = cadNum(best.q.y); }
  } else {
    const pr = cadPrims(e)[0], endEnd = cadDist(p, arcPoint(pr, pr.a1)) < cadDist(p, arcPoint(pr, pr.a0));
    const circle = { k: "arc", c: pr.c, r: pr.r, a0: 0, a1: TAU };
    let best = null;
    others.forEach((o) => intersect(circle, o).forEach((q) => {
      const a = cadAng(pr.c, q);
      const d = endEnd ? normA(a - pr.a1) : normA(pr.a0 - a);
      if (d > 1e-7 && !arcHas(pr, a) && (!best || d < best.d)) best = { d, a };
    }));
    if (!best) { cadLog("Uzaytiradigan chegara topilmadi."); return; }
    cadSnapshot();
    const o = cadState.doc.entities[i];
    if (endEnd) o.end = cadNum(toDeg(best.a)); else o.start = cadNum(toDeg(best.a));
  }
  cadRender(); cadLog("Uzaytirildi.");
}
// Fillet (radius) or chamfer (equal distances) between two lines; R = 0 makes a sharp corner.
function cadCorner(t, i1, p1, i2, p2) {
  const e1 = cadState.doc.entities[i1], e2 = cadState.doc.entities[i2];
  const L1 = { k: "seg", a: P(e1.x1, e1.y1), b: P(e1.x2, e1.y2) }, L2 = { k: "seg", a: P(e2.x1, e2.y1), b: P(e2.x2, e2.y2) };
  const X = intersect(L1, L2, true, true)[0];
  if (!X) { cadLog("Chiziqlar parallel — burchak yo‘q."); cadSetTool(t); return; }
  const keepEnd = (L, pick) => { // the end of the line on the side the user clicked
    const da = cadDist(L.a, X), db = cadDist(L.b, X);
    const side = (q) => Math.sign((q.x - X.x) * (L.b.x - L.a.x) + (q.y - X.y) * (L.b.y - L.a.y));
    if (side(pick) === side(L.a) && da > 1e-9) return L.a;
    if (side(pick) === side(L.b) && db > 1e-9) return L.b;
    return da > db ? L.a : L.b;
  };
  const f1 = keepEnd(L1, p1), f2 = keepEnd(L2, p2);
  const u1 = P((f1.x - X.x) / cadDist(f1, X), (f1.y - X.y) / cadDist(f1, X)), u2 = P((f2.x - X.x) / cadDist(f2, X), (f2.y - X.y) / cadDist(f2, X));
  const theta = Math.acos(Math.max(-1, Math.min(1, u1.x * u2.x + u1.y * u2.y)));
  let T1 = X, T2 = X, extra = null;
  if (t === "fillet") {
    const R = cadState.opts.radius || 0;
    if (R > 0) {
      const d = R / Math.tan(theta / 2);
      if (d > cadDist(f1, X) + 1e-9 || d > cadDist(f2, X) + 1e-9) { cadLog("Radius juda katta: chiziqlarga sig‘maydi."); cadSetTool(t); return; }
      T1 = P(X.x + u1.x * d, X.y + u1.y * d); T2 = P(X.x + u2.x * d, X.y + u2.y * d);
      const bis = P(u1.x + u2.x, u1.y + u2.y), bl = Math.hypot(bis.x, bis.y);
      const C = P(X.x + bis.x / bl * R / Math.sin(theta / 2), X.y + bis.y / bl * R / Math.sin(theta / 2));
      let s = cadAng(C, T1), en = cadAng(C, T2);
      if (normA(en - s) > Math.PI) [s, en] = [en, s];
      extra = { type: "arc", layer: e1.layer, cx: cadNum(C.x), cy: cadNum(C.y), r: cadNum(R), start: cadNum(toDeg(s)), end: cadNum(toDeg(en)) };
    }
  } else {
    const d = cadState.opts.dist || 0;
    if (d > cadDist(f1, X) || d > cadDist(f2, X)) { cadLog("Faska juda katta."); cadSetTool(t); return; }
    T1 = P(X.x + u1.x * d, X.y + u1.y * d); T2 = P(X.x + u2.x * d, X.y + u2.y * d);
    if (d > 0) extra = { type: "line", layer: e1.layer, x1: cadNum(T1.x), y1: cadNum(T1.y), x2: cadNum(T2.x), y2: cadNum(T2.y) };
  }
  cadSnapshot();
  Object.assign(e1, { x1: cadNum(f1.x), y1: cadNum(f1.y), x2: cadNum(T1.x), y2: cadNum(T1.y) });
  Object.assign(e2, { x1: cadNum(f2.x), y1: cadNum(f2.y), x2: cadNum(T2.x), y2: cadNum(T2.y) });
  if (extra) cadState.doc.entities.push(extra);
  cadState.selected.clear(); cadLog(`${CAD_TOOLS[t]} bajarildi.`); cadSetTool(t);
}
function cadHatchAt(p, picked) {
  // innermost closed shape that contains the point (closed polylines and circles)
  let best = null;
  cadState.doc.entities.forEach((e, i) => {
    if (!cadVisible(e)) return;
    let ring = null;
    if (e.type === "polyline" && e.closed) ring = e.points.map((v) => [v[0], v[1], v[2] || 0]);
    if (e.type === "circle") ring = [[e.cx + e.r, e.cy, 1], [e.cx - e.r, e.cy, 1]];
    if (e.type === "ellipse") ring = cadPrims(e).map((pr) => [cadNum(pr.a.x), cadNum(pr.a.y), 0]);
    if (!ring) return;
    const flat = cadPrims({ type: "hatch", paths: [ring] }).flatMap((pr) => (pr.k === "seg" ? [pr.a] : [0, 1, 2, 3, 4, 5, 6, 7, 8].map((k) => arcPoint(pr, pr.a0 + (pr.a1 - pr.a0) * k / 8))));
    if (!cadInside(p, [flat.map((q) => [q.x, q.y])])) return;
    const A = Math.abs(polyArea(flat));
    if (!best || A < best.A) best = { A, ring, i };
  });
  if (!best) { cadLog(picked >= 0 ? "Bu shakl yopiq emas." : "Yopiq shakl topilmadi: yopiq polichiziq, to‘rtburchak yoki aylana ichiga bosing."); return; }
  // shapes inside the chosen one become holes
  const holes = [];
  cadState.doc.entities.forEach((e, i) => {
    if (i === best.i || !cadVisible(e)) return;
    if (e.type === "circle" && cadInside(P(e.cx, e.cy), [best.ring.map((v) => [v[0], v[1]])]) && e.r * e.r * Math.PI < best.A) holes.push([[e.cx + e.r, e.cy, 1], [e.cx - e.r, e.cy, 1]]);
    if (e.type === "polyline" && e.closed && e.points.every((v) => cadInside(P(v[0], v[1]), [best.ring.map((w) => [w[0], w[1]])]))) holes.push(e.points.map((v) => [v[0], v[1], v[2] || 0]));
  });
  const pattern = cadState.hatchPattern || "ANSI31";
  cadAdd([{ type: "hatch", paths: [best.ring, ...holes], pattern, scale: cadState.hatchScale || 1 }], true);
  cadLog(`Shtrixlandi (${pattern === "SOLID" ? "to‘liq bo‘yoq" : "qiya chiziqlar"}). «SOLID» yoki «ANSI31» deb yozib turini almashtirish mumkin.`);
}
function cadExplodeOne(e) {
  const base = { layer: e.layer }; if (e.color) base.color = e.color;
  if (e.type === "polyline") return cadPrims(e).map((pr) => (pr.k === "seg"
    ? Object.assign({}, base, { type: "line", x1: cadNum(pr.a.x), y1: cadNum(pr.a.y), x2: cadNum(pr.b.x), y2: cadNum(pr.b.y) })
    : Object.assign({}, base, { type: "arc", cx: cadNum(pr.c.x), cy: cadNum(pr.c.y), r: cadNum(pr.r), start: cadNum(toDeg(pr.a0)), end: cadNum(toDeg(pr.a1)) })));
  if (["dim", "ldim", "rdim"].includes(e.type)) {
    const g = dimGeometry(e), out = [Object.assign({}, base, { type: "line", x1: g.a.x, y1: g.a.y, x2: g.b.x, y2: g.b.y })];
    out.push(Object.assign({}, base, { type: "text", x: (g.a.x + g.b.x) / 2, y: (g.a.y + g.b.y) / 2 + 1, h: 2.5, rot: 0, text: e.label || `${g.prefix || ""}${fmt(g.value)}` }));
    return out;
  }
  return [e];
}
function cadExplode() {
  const ids = [...cadState.selected];
  cadSnapshot();
  const keep = cadState.doc.entities.filter((_, i) => !cadState.selected.has(i));
  const parts = ids.flatMap((i) => cadExplodeOne(cadState.doc.entities[i]));
  cadState.doc.entities = keep.concat(parts);
  cadState.selected.clear(); cadLog(`Bo‘laklandi: ${parts.length} ta obyekt.`); cadSetTool("select");
}
function cadOffsetSide(p) {
  const i = cadState.opts.target, e = cadState.doc.entities[i], d = cadState.opts.dist;
  let out = null;
  if (e.type === "line") {
    const a = P(e.x1, e.y1), b = P(e.x2, e.y2), L = cadDist(a, b) || 1, n = P(-(b.y - a.y) / L, (b.x - a.x) / L);
    const s = Math.sign((p.x - a.x) * n.x + (p.y - a.y) * n.y) || 1;
    out = Object.assign(cadClone(e), { x1: cadNum(a.x + n.x * d * s), y1: cadNum(a.y + n.y * d * s), x2: cadNum(b.x + n.x * d * s), y2: cadNum(b.y + n.y * d * s) });
  } else if (e.type === "circle" || e.type === "arc") {
    const outside = cadDist(P(e.cx, e.cy), p) > e.r, r = e.r + (outside ? d : -d);
    if (r <= 0) { cadLog("Ichkariga sig‘maydi."); return; }
    out = Object.assign(cadClone(e), { r: cadNum(r) });
  } else if (e.type === "polyline") {
    out = cadOffsetPolyline(e, d, p);
  }
  if (out) { cadAdd([out], true); cadLog("Parallel nusxa qo‘shildi."); }
  cadState.tool = "offset"; cadPrompt("Parallel nusxa: keyingi obyektni bosing (Esc — tugatish):");
}
function cadOffsetPolyline(e, d, p) {
  // straight-edged polylines: shift every edge and join the neighbours at their intersection
  const pts = polyPts(e); const n = pts.length; const closed = e.closed;
  if ((e.points || []).some((v) => v[2])) { cadLog("Yoyli polichiziqni avval bo‘laklang (X)."); return null; }
  const area = polyArea(pts);
  let side = 1;
  if (closed) side = (cadInside(p, [e.points]) ? -1 : 1) * (area > 0 ? -1 : 1);
  else { const a = pts[0], b = pts[1], L = cadDist(a, b) || 1; side = Math.sign((p.x - a.x) * -(b.y - a.y) / L + (p.y - a.y) * (b.x - a.x) / L) || 1; }
  const segs = [];
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const a = pts[i], b = pts[(i + 1) % n], L = cadDist(a, b) || 1, nn = P(-(b.y - a.y) / L * d * side, (b.x - a.x) / L * d * side);
    segs.push({ k: "seg", a: P(a.x + nn.x, a.y + nn.y), b: P(b.x + nn.x, b.y + nn.y) });
  }
  const res = [];
  for (let i = 0; i < n; i++) {
    if (!closed && (i === 0)) { res.push(segs[0].a); continue; }
    if (!closed && i === n - 1) { res.push(segs[n - 2].b); continue; }
    const s1 = segs[(i - 1 + segs.length) % segs.length], s2 = segs[i % segs.length];
    const x = intersect(s1, s2, true, true)[0] || s2.a; res.push(x);
  }
  return Object.assign(cadClone(e), { points: res.map((q) => [cadNum(q.x), cadNum(q.y), 0]) });
}

// ---------------- command line ----------------
function cadParsePoint(input) {
  const s = input.trim().replace(/\s+/g, "");
  const last = cadState.points.at(-1) || P(0, 0);
  const num = "(-?(?:\\d+(?:\\.\\d*)?|\\.\\d+))";
  let m = new RegExp(`^(@?)${num},${num}$`).exec(s);
  if (m) return m[1] ? P(last.x + +m[2], last.y + +m[3]) : P(+m[2], +m[3]);
  m = new RegExp(`^@?${num}<${num}$`).exec(s);
  if (m) return P(last.x + +m[1] * Math.cos(toRad(+m[2])), last.y + +m[1] * Math.sin(toRad(+m[2])));
  return null;
}
function cadNumber(s) {
  const v = Number(String(s).trim().replace(",", "."));
  return Number.isFinite(v) ? v : null;
}
function cadFinish() {
  const t = cadState.tool, pts = cadState.points;
  if (cadState.ask) { const a = cadState.ask; cadState.ask = null; if (a.handler) a.handler(a.type === "text" ? "" : a.def); return; }
  if (t === "polyline" && pts.length >= 2) cadAdd([{ type: "polyline", points: pts.map((q) => [q.x, q.y, 0]), closed: false }]);
  if (t === "area" && pts.length >= 3) {
    const A = Math.abs(polyArea(pts)), per = pts.reduce((s, q, i) => s + cadDist(q, pts[(i + 1) % pts.length]), 0);
    cadLog(`Yuza: ${fmt(A)} mm² (${fmt(A / 100)} sm²) · perimetr ${fmt(per)} mm`);
  }
  if (t === "select") { cadSetTool(cadState.lastTool || "line"); return; } // Enter repeats, like AutoCAD
  cadSetTool("select");
}
function cadExec(value) {
  const input = String(value ?? "").trim();
  const t = cadState.tool;
  if (!input) { cadFinish(); return true; }
  // a pending question (text, number)
  if (cadState.ask) {
    const a = cadState.ask;
    if (a.type === "text") { cadState.ask = null; a.handler(input); return true; }
    const v = cadNumber(input);
    if (a.type === "number" && v != null) { cadState.ask = null; a.handler(v); return true; }
  }
  const cmd = input.toUpperCase().replace(/^_/, "");
  // options inside a running tool
  if ((t === "polyline" || t === "line") && /^(Y|C|YOP|YOPISH|CLOSE)$/.test(cmd)) {
    if (t === "polyline" && cadState.points.length >= 3) cadAdd([{ type: "polyline", points: cadState.points.map((q) => [q.x, q.y, 0]), closed: true }]);
    if (t === "line" && (cadState.opts.chain || []).length >= 3) { const ch = cadState.opts.chain; cadAdd([{ type: "line", x1: ch.at(-1).x, y1: ch.at(-1).y, x2: ch[0].x, y2: ch[0].y }]); }
    cadSetTool("select"); return true;
  }
  if (t === "line" && cmd === "U" && (cadState.opts.chain || []).length >= 2) { cadRestore(cadState.undo, cadState.redo); cadState.opts.chain.pop(); cadState.points = [cadState.opts.chain.at(-1)]; cadState.tool = "line"; cadRender(); return true; }
  if (t === "fillet" && /^R\s*\d/.test(cmd)) { cadState.filletR = cadState.opts.radius = cadNumber(cmd.slice(1)) || 0; cadLog(`Radius: ${fmt(cadState.opts.radius)} mm`); return true; }
  if (t === "chamfer" && /^D\s*\d/.test(cmd)) { cadState.chamferD = cadState.opts.dist = cadNumber(cmd.slice(1)) || 0; cadLog(`Faska: ${fmt(cadState.opts.dist)} mm`); return true; }
  if (t === "hatch" && /^(SOLID|ANSI31)$/.test(cmd)) { cadState.hatchPattern = cmd; cadLog(`Shtrix turi: ${cmd === "SOLID" ? "to‘liq bo‘yoq" : "qiya chiziqlar"}`); return true; }
  if (t === "text" && /^H\s*\d/.test(cmd)) { cadState.textH = cadNumber(cmd.slice(1)) || 3.5; cadLog(`Matn balandligi: ${fmt(cadState.textH)} mm`); return true; }
  const col = cmd.match(/^(COLOR|COL|RANG)\s*(\d{1,3}|BYLAYER|QATLAM)?$/);
  if (col) {
    if (!col[2]) { cadColorPicker(document.getElementById("cad-color") || document.getElementById("cad-cmd"), cadState.color, true, cadSetColor); return true; }
    const i = /^\d/.test(col[2]) ? +col[2] : 256;
    if (i < 1 || i > 256) { cadLog("Rang raqami 1–255 (256 — qatlam bo‘yicha)."); return true; }
    cadSetColor(i); return true;
  }
  if (CAD_ALIASES[cmd]) { cadSetTool(CAD_ALIASES[cmd]); return true; }
  if (CAD_ACTIONS[cmd]) { cadAction(CAD_ACTIONS[cmd]); return true; }
  const pt = cadParsePoint(input);
  if (pt && t !== "select") { cadTakePoint(P(cadNum(pt.x), cadNum(pt.y))); return true; }
  const v = cadNumber(input);
  if (v != null && t !== "select") {
    const pts = cadState.points, last = pts.at(-1);
    if (t === "circle" && pts.length === 1) { cadTakePoint(P(pts[0].x + v, pts[0].y)); return true; }
    if (t === "rotate" && pts.length === 1) { cadRotateBy(pts[0], toRad(v)); return true; }
    if (t === "scale" && pts.length === 1) { cadScaleBy(pts[0], v); return true; }
    if (t === "polygon" && pts.length === 1) { cadTakePoint(P(pts[0].x + v, pts[0].y)); return true; }
    if (last) { // direct distance entry along the cursor direction (ortho respected)
      let ang = cadState.cursor ? cadAng(last, cadState.cursor) : 0;
      if (cadState.ortho) ang = Math.round(ang / (Math.PI / 2)) * (Math.PI / 2);
      cadTakePoint(P(cadNum(last.x + v * Math.cos(ang)), cadNum(last.y + v * Math.sin(ang)))); return true;
    }
  }
  cadLog(`Noma’lum buyruq yoki nuqta: «${input}». Masalan: L, PL, C, REC, TR, F, M, CO; nuqta: 10,20 yoki @50,0 yoki @50<30.`);
  return false;
}

// ---------------- side panels ----------------
function cadEl(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
function cadSelect(options, value, onChange, label) {
  const s = cadEl("select"); s.setAttribute("aria-label", label || "");
  Object.entries(options).forEach(([v, t]) => { const o = cadEl("option", "", t); o.value = v; s.appendChild(o); });
  s.value = String(value); s.addEventListener("change", () => onChange(s.value)); return s;
}
// «Rang tanlash» window: by layer, the 9 basic colours, the full 10..249 palette, greys.
function cadColorPicker(anchor, current, byLayer, onPick) {
  document.querySelectorAll(".cad-palette").forEach((n) => n.remove());
  const pop = cadEl("div", "cad-palette"); pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Rang tanlash");
  const info = cadEl("div", "cad-pal-info small", `Tanlangan: ${cadColorName(current)}`);
  const sw = (i, cls = "") => {
    const b = cadEl("button", `cad-pal-sw${cls}${+i === +current ? " on" : ""}`); b.type = "button";
    b.style.background = cadSwatchColor(i); b.title = `${cadColorName(i)} (${i})`; b.dataset.aci = i;
    b.addEventListener("mouseenter", () => { info.textContent = `${cadColorName(i)} · ${i}`; });
    b.addEventListener("click", (ev) => { ev.stopPropagation(); pop.remove(); onPick(+i); });
    return b;
  };
  const basic = cadEl("div", "cad-pal-row");
  if (byLayer) basic.appendChild(sw(256, " bylayer"));
  for (let i = 1; i <= 9; i++) basic.appendChild(sw(i, " big"));
  const grid = cadEl("div", "cad-pal-grid");
  for (let k = 0; k < 10; k++) for (let h = 1; h <= 24; h++) grid.appendChild(sw(h * 10 + k));
  const greys = cadEl("div", "cad-pal-row");
  for (let i = 250; i <= 255; i++) greys.appendChild(sw(i));
  pop.append(cadEl("div", "cad-pal-title", "Rang tanlash"), basic, grid, greys, info);
  document.body.appendChild(pop);
  const r = anchor.getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  pop.style.left = `${Math.max(8, Math.min(r.left, innerWidth - w - 8))}px`;
  pop.style.top = `${r.bottom + h + 8 < innerHeight ? r.bottom + 4 : Math.max(8, r.top - h - 4)}px`;
  const close = (ev) => { if (!pop.contains(ev.target)) { pop.remove(); document.removeEventListener("mousedown", close, true); } };
  setTimeout(() => document.addEventListener("mousedown", close, true), 0);
  const esc = (ev) => { if (ev.key === "Escape") { pop.remove(); document.removeEventListener("keydown", esc, true); } };
  document.addEventListener("keydown", esc, true);
  return pop;
}
function cadColorButton(current, byLayer, onPick, label = "Rang") {
  const b = cadEl("button", "cad-color-btn"); b.type = "button"; b.setAttribute("aria-label", label);
  const s = cadEl("span", "cad-swatch"); s.style.background = cadSwatchColor(current);
  if (+current === 256) s.classList.add("bylayer");
  b.append(s, cadEl("span", "", cadColorName(current)));
  b.addEventListener("click", () => cadColorPicker(b, current, byLayer, onPick));
  return b;
}
// The toolbar colour: new objects get it; with objects selected it recolours them too.
function cadSetColor(i) {
  cadState.color = i;
  if (cadState.selected.size) {
    cadSnapshot();
    cadState.selected.forEach((k) => { const e = cadState.doc.entities[k]; if (i === 256) delete e.color; else e.color = i; });
    cadRenderProps();
  }
  cadShowColor(); cadRender();
  cadLog(`Rang: ${cadColorName(i)}${cadState.selected.size ? ` — ${cadState.selected.size} ta obyekt bo‘yaldi` : " (yangi obyektlar)"}`);
}
function cadShowColor() {
  const b = document.getElementById("cad-color"); if (!b) return;
  const s = b.querySelector(".cad-swatch"); s.style.background = cadSwatchColor(cadState.color);
  s.classList.toggle("bylayer", cadState.color === 256);
  b.querySelector(".cad-color-name").textContent = cadColorName(cadState.color);
}
function cadRenderLayers() {
  const root = document.getElementById("cad-layers"); root.replaceChildren();
  cadState.doc.layers.forEach((ly) => {
    const row = cadEl("div", `cad-layer${ly.name === cadState.layer ? " active" : ""}`);
    const eye = cadEl("button", "cad-mini", ly.visible === false ? "◌" : "◉"); eye.title = "Ko‘rinadi / yashirin";
    eye.addEventListener("click", () => { cadSnapshot(); ly.visible = ly.visible === false; cadRenderLayers(); cadRender(); });
    const lock = cadEl("button", "cad-mini", ly.locked ? "🔒" : "🔓"); lock.title = "Qulflash (tahrirlab bo‘lmaydi)";
    lock.addEventListener("click", () => { cadSnapshot(); ly.locked = !ly.locked; cadRenderLayers(); });
    const sw = cadEl("span", "cad-swatch"); sw.style.background = cadSwatchColor(ly.color || 7);
    const name = cadEl("button", "cad-layer-name", ly.name); name.title = "Joriy qatlam (ikki marta bosing — nomini o‘zgartirish)";
    name.addEventListener("click", () => { cadState.layer = ly.name; cadRenderLayers(); cadRender(); });
    name.addEventListener("dblclick", () => cadRenameLayer(ly));
    row.append(eye, lock, sw, name);
    const det = cadEl("div", "cad-layer-props");
    det.append(
      cadColorButton(ly.color || 7, false, (v) => { cadSnapshot(); ly.color = v; cadRenderLayers(); cadRender(); }, "Qatlam rangi"),
      cadSelect(Object.fromEntries(CAD_WEIGHTS.map((w) => [w, `${fmt(w / 100)} mm`])), CAD_WEIGHTS.includes(ly.lineweight) ? ly.lineweight : 25, (v) => { cadSnapshot(); ly.lineweight = +v; cadRender(); }, "Qalinlik"),
      cadSelect(CAD_LINETYPES, ly.linetype in CAD_LINETYPES ? ly.linetype : "Continuous", (v) => { cadSnapshot(); ly.linetype = v; cadRender(); }, "Chiziq turi"),
    );
    if (ly.name !== "0") {
      const del = cadEl("button", "cad-mini", "✕"); del.title = "Qatlamni o‘chirish (bo‘sh bo‘lsa)";
      del.addEventListener("click", () => {
        if (cadState.doc.entities.some((e) => e.layer === ly.name)) { cadLog(`«${ly.name}» qatlamida obyektlar bor — avval ularni boshqa qatlamga o‘tkazing.`); return; }
        cadSnapshot(); cadState.doc.layers = cadState.doc.layers.filter((x) => x !== ly);
        if (cadState.layer === ly.name) cadState.layer = "0"; cadRenderLayers(); cadRender();
      });
      det.appendChild(del);
    }
    root.append(row, det);
  });
}
function cadRenameLayer(ly) {
  if (ly.name === "0") { cadLog("«0» qatlami nomini o‘zgartirib bo‘lmaydi."); return; }
  const name = (window.prompt("Qatlamning yangi nomi:", ly.name) || "").trim();
  if (!name || name === ly.name) return;
  if (/[<>/\\":;?*|=`]/.test(name) || name.length > 60 || cadLayer(name)) { cadLog("Nom noto‘g‘ri yoki band."); return; }
  cadSnapshot(); cadState.doc.entities.forEach((e) => { if (e.layer === ly.name) e.layer = name; });
  if (cadState.layer === ly.name) cadState.layer = name;
  ly.name = name; cadRenderLayers(); cadRender();
}
const CAD_FIELDS = {
  line: [["x1", "X1"], ["y1", "Y1"], ["x2", "X2"], ["y2", "Y2"]],
  circle: [["cx", "Markaz X"], ["cy", "Markaz Y"], ["r", "Radius"]],
  arc: [["cx", "Markaz X"], ["cy", "Markaz Y"], ["r", "Radius"], ["start", "Boshlanish °"], ["end", "Tugash °"]],
  ellipse: [["cx", "Markaz X"], ["cy", "Markaz Y"], ["rx", "Katta yarim o‘q"], ["ry", "Kichik yarim o‘q"], ["rot", "Burchak °"]],
  text: [["x", "X"], ["y", "Y"], ["h", "Balandlik"], ["rot", "Burchak °"]],
  dim: [["offset", "Masofa"]], ldim: [["rot", "Yo‘nalish °"]], rdim: [["angle", "Burchak °"]],
  hatch: [["scale", "Shtrix masshtabi"]],
};
const CAD_TYPE_NAMES = { line: "Chiziq", polyline: "Polichiziq", circle: "Aylana", arc: "Yoy", ellipse: "Ellips", text: "Matn", dim: "Qiya o‘lcham", ldim: "Chiziqli o‘lcham", rdim: "Radius/diametr o‘lchami", hatch: "Shtrix" };
function cadRenderProps() {
  const root = document.getElementById("cad-props"); root.replaceChildren();
  const ids = [...cadState.selected];
  if (!ids.length) { root.appendChild(cadEl("span", "muted small", "Obyekt tanlanmagan. Bosib tanlang yoki ramka torting.")); return; }
  const ents = ids.map((i) => cadState.doc.entities[i]);
  root.appendChild(cadEl("div", "cad-prop-title", ids.length === 1 ? CAD_TYPE_NAMES[ents[0].type] || ents[0].type : `${ids.length} ta obyekt`));
  const apply = (fn) => { cadSnapshot(); ents.forEach(fn); cadRender(); cadRenderProps(); };
  const field = (label, node) => { const l = cadEl("label", "cad-field"); l.append(cadEl("span", "", label), node); root.appendChild(l); };
  field("Qatlam", cadSelect(Object.fromEntries(cadState.doc.layers.map((l) => [l.name, l.name])), ents[0].layer || "0", (v) => apply((e) => { e.layer = v; }), "Qatlam"));
  field("Rang", cadColorButton(ents[0].color || 256, true, (v) => apply((e) => { if (v === 256) delete e.color; else e.color = v; }), "Obyekt rangi"));
  if (ids.length !== 1) return;
  const e = ents[0];
  (CAD_FIELDS[e.type] || []).forEach(([k, label]) => {
    const inp = cadEl("input"); inp.type = "text"; inp.value = fmt(e[k] ?? 0); inp.setAttribute("aria-label", label);
    inp.addEventListener("change", () => { const v = cadNumber(inp.value); if (v == null || ((k === "r" || k === "h" || k === "rx" || k === "ry") && v <= 0)) { cadLog("Noto‘g‘ri qiymat."); inp.value = fmt(e[k]); return; } apply((x) => { x[k] = v; }); });
    field(label, inp);
  });
  if (e.type === "text" || ["dim", "ldim", "rdim"].includes(e.type)) {
    const inp = cadEl("input"); inp.type = "text"; inp.value = e.type === "text" ? e.text : (e.label || ""); inp.placeholder = e.type === "text" ? "" : "o‘lchov (avtomatik)";
    inp.setAttribute("aria-label", "Matn");
    inp.addEventListener("change", () => apply((x) => { if (x.type === "text") x.text = inp.value; else x.label = inp.value; }));
    field(e.type === "text" ? "Matn" : "Yozuv", inp);
  }
  if (e.type === "polyline") {
    const chk = cadEl("input"); chk.type = "checkbox"; chk.checked = !!e.closed;
    chk.addEventListener("change", () => apply((x) => { x.closed = chk.checked; })); field("Yopiq", chk);
  }
  if (e.type === "hatch") field("Turi", cadSelect({ SOLID: "To‘liq bo‘yoq", ANSI31: "Qiya chiziqlar" }, e.pattern || "SOLID", (v) => apply((x) => { x.pattern = v; }), "Turi"));
  const info = [];
  if (!["text", "dim", "ldim", "rdim", "hatch"].includes(e.type)) info.push(`Uzunlik: ${fmt(entityLength(e))} mm`);
  const A = entityArea(e); if (A != null) info.push(`Yuza: ${fmt(A)} mm²`);
  if (e.type === "line") info.push(`Burchak: ${fmt(toDeg(cadAng(P(e.x1, e.y1), P(e.x2, e.y2))))}°`);
  if (["dim", "ldim", "rdim"].includes(e.type)) info.push(`O‘lchov: ${fmt(dimGeometry(e).value)} mm`);
  if (info.length) root.appendChild(cadEl("div", "muted small", info.join(" · ")));
}

// ---------------- file and view actions ----------------
function cadLoad(result) {
  if (!result || !result.ok) { if (result && !result.cancelled) cadLog(result.error || "Chizma ochilmadi."); return false; }
  cadState.doc = cadClone(result.drawing);
  if (!cadState.doc.layers || !cadState.doc.layers.length) cadState.doc.layers = CAD_EMPTY().layers;
  cadState.doc.layers.forEach((l) => { if (!l.linetype) l.linetype = "Continuous"; });
  cadState.path = result.path || ""; cadState.layer = cadState.doc.layers[0].name;
  cadState.undo = []; cadState.redo = []; cadState.selected.clear(); cadState.dirty = false;
  cadSetTool("select"); cadRenderLayers(); cadRenderProps(); cadExtents();
  const skipped = Object.entries(cadState.doc.skipped || {});
  if (skipped.length) cadLog(`Ko‘rsatilmagan obyektlar: ${skipped.map(([k, v]) => `${k} ${v}`).join(", ")}`);
  cadLog(`${result.name || "Chizma"} ochildi.`); return true;
}
async function cadAction(action) {
  if (action === "color") { cadColorPicker(document.getElementById("cad-color"), cadState.color, true, cadSetColor); return; }
  if (action === "undo") { cadRestore(cadState.undo, cadState.redo); return; }
  if (action === "redo") { cadRestore(cadState.redo, cadState.undo); return; }
  if (action === "extents") { cadExtents(); return; }
  if (action === "view3d") { cad3dOpen(); return; }
  if (action === "zoomin" || action === "zoomout") {
    const f = action === "zoomin" ? 1.25 : 0.8, cx = (cadWrap.clientWidth || 800) / 2, cy = (cadWrap.clientHeight || 500) / 2;
    const before = cadModel(P(cx, cy));
    cadState.scale = Math.max(0.0005, Math.min(2000, cadState.scale * f));
    cadState.ox = cx - before.x * cadState.scale; cadState.oy = cy + before.y * cadState.scale;
    cadRender(); return;
  }
  if (action === "compact") {
    const on = document.body.classList.toggle("cad-compact");
    try { localStorage.setItem("nexvara-cad-compact", on ? "1" : ""); } catch (_) { /* storage off */ }
    requestAnimationFrame(cadRender); return;
  }
  if (action === "erase") {
    if (!cadState.selected.size) { cadLog("O‘chirish uchun obyekt tanlang."); return; }
    cadSnapshot(); const n = cadState.selected.size;
    cadState.doc.entities = cadState.doc.entities.filter((_, i) => !cadState.selected.has(i));
    cadState.selected.clear(); cadRender(); cadRenderProps(); cadLog(`${n} ta obyekt o‘chirildi.`); return;
  }
  if (action === "selectall") { cadState.doc.entities.forEach((e, i) => { if (cadVisible(e) && !cadLocked(e)) cadState.selected.add(i); }); cadRender(); cadRenderProps(); return; }
  if (action === "copyclip") { cadState.clipboard = [...cadState.selected].map((i) => cadClone(cadState.doc.entities[i])); cadLog(`${cadState.clipboard.length} ta obyekt nusxalandi.`); return; }
  if (action === "paste") {
    if (!cadState.clipboard || !cadState.clipboard.length) { cadLog("Bufer bo‘sh."); return; }
    const boxes = cadState.clipboard.map(cadBounds).filter(Boolean);
    cadSetTool("paste"); cadState.opts.base = P(Math.min(...boxes.map((b) => b.x1)), Math.min(...boxes.map((b) => b.y1))); cadState.points = [cadState.opts.base]; return;
  }
  if (action === "new") {
    if (cadState.dirty && !window.confirm("Saqlanmagan chizma bor. Yangi chizma ochilsinmi?")) return;
    cadLoad({ ok: true, drawing: CAD_EMPTY(), name: "Yangi chizma" }); return;
  }
  if (!api()) { cadLog("NEXVARA bilan aloqa yo‘q."); return; }
  try {
    if (action === "open" || action === "last") {
      if (cadState.dirty && !window.confirm("Saqlanmagan chizma bor. Boshqa chizma ochilsinmi?")) return;
      cadLoad(await (action === "open" ? api().cad_open() : api().cad_last_drawing())); return;
    }
    if (action === "save" || action === "saveas") {
      const r = await api().cad_save(cadState.doc, action === "save" ? cadState.path : "");
      if (r.ok) { cadState.path = r.path; cadState.dirty = false; cadRender(); cadLog(`Saqlandi: ${r.name} (${r.entities} obyekt, AutoCAD DXF)`); }
      else if (!r.cancelled) cadLog(r.error || "Saqlab bo‘lmadi.");
      return;
    }
    if (action === "ai") {
      if (!cadState.doc.entities.length) { cadLog("Avval biror narsa chizing — AI uni to‘g‘irlab beradi."); return; }
      const note = window.prompt("Nimani chizmoqchi edingiz? (masalan: 100x60 plastina, markazida 20 mm teshik). Bo‘sh qoldirsangiz ham bo‘ladi.", "");
      if (note === null) return;
      cadLog("AI chizmani tuzatmoqda…");
      let r = await api().cad_ai_fix(cadState.doc, note, false);
      if (r.confirm) {
        if (!window.confirm(`${r.confirm}. Davom etaymi?`)) { cadLog("Bekor qilindi, pul sarflanmadi."); return; }
        r = await api().cad_ai_fix(cadState.doc, note, true);
      }
      if (!r.ok) { cadLog(r.error || "Tuzatib bo‘lmadi."); return; }
      cadSnapshot();
      cadState.doc.entities = r.drawing.entities;
      cadState.selected.clear(); cadExtents(); cadRenderProps();
      cadLog(`${r.reply} Yoqmasa — «Orqaga» (Ctrl+Z).`);
      return;
    }
    if (action === "pdf" || action === "png" || action === "word") {
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
  try { if (localStorage.getItem("nexvara-cad-compact")) document.body.classList.add("cad-compact"); } catch (_) { /* storage off */ }
  if (!cadState.ready) {
    cadState.ready = true;
    cadState.ox = (cadWrap.clientWidth || 800) / 2; cadState.oy = (cadWrap.clientHeight || 500) / 2;
    cadRenderLayers(); cadSetTool("select"); cadRenderProps();
    cadLoadTemplates();
    cadLog("Maslahat: buyruqni yozing (L — chiziq, C — aylana, TR — kesish, F — yumaloqlash), sichqoncha g‘ildiragi — yaqinlashtirish, o‘ng tugma bilan sudrash — surish.");
  }
  requestAnimationFrame(cadRender);
}

// ---------------- templates (frame, bolt, nut, washer, bearing) ----------------
let cadTemplateList = [];
async function cadLoadTemplates() {
  if (cadTemplateList.length || !api() || !api().cad_templates) return;
  cadTemplateList = await api().cad_templates();
  const sel = document.getElementById("cad-template");
  cadTemplateList.forEach((t) => { const o = document.createElement("option"); o.value = t.id; o.textContent = t.title; sel.appendChild(o); });
}
async function cadInsertTemplate(id) {
  const t = cadTemplateList.find((x) => x.id === id); if (!t) return;
  let size = "";
  if (t.ask) { size = window.prompt(`${t.title}: ${t.ask}`, t.ask.split("masalan ")[1] || ""); if (size === null) return; }
  const r = await api().cad_template(id, size);
  if (!r.ok) { cadLog(r.error || "Shablon qo‘shilmadi."); return; }
  cadSnapshot();
  (r.drawing.layers || []).forEach((l) => { if (!cadLayer(l.name)) cadState.doc.layers.push(l); });
  cadState.doc.entities.push(...r.drawing.entities);
  cadRenderLayers(); cadExtents(); cadLog(`Qo‘shildi: ${t.title}${size ? ` (${size})` : ""}. Kerakli joyga «Ko‘chirish» (M) bilan suring.`);
}
document.getElementById("cad-template").addEventListener("change", (e) => {
  const v = e.target.value; e.target.value = ""; if (v) cadInsertTemplate(v);
});

// ---------------- grips (drag a selected object's point) ----------------
function cadGripAt(s) {
  if (cadState.tool !== "select") return null;
  for (const i of cadState.selected) {
    const grips = cadGrips(cadState.doc.entities[i]) || [];
    for (let k = 0; k < grips.length; k++) {
      const g = cadScreen(grips[k]);
      if (Math.abs(g.x - s.x) <= 6 && Math.abs(g.y - s.y) <= 6) return { i, k };
    }
  }
  return null;
}
function cadMoveGrip(e, k, q) {
  const t = e.type;
  if (t === "line") { if (k === 0) { e.x1 = q.x; e.y1 = q.y; } else if (k === 1) { e.x2 = q.x; e.y2 = q.y; } else { const dx = q.x - (e.x1 + e.x2) / 2, dy = q.y - (e.y1 + e.y2) / 2; e.x1 += dx; e.x2 += dx; e.y1 += dy; e.y2 += dy; } }
  else if (t === "polyline") { e.points[k][0] = q.x; e.points[k][1] = q.y; }
  else if (t === "circle" || t === "arc") {
    if (k === 0) { e.cx = q.x; e.cy = q.y; }
    else if (t === "circle") e.r = cadNum(cadDist(P(e.cx, e.cy), q));
    else { const a = cadNum(toDeg(cadAng(P(e.cx, e.cy), q))); if (k === 1) e.start = a; else e.end = a; e.r = cadNum(cadDist(P(e.cx, e.cy), q)); }
  } else if (t === "ellipse") { e.cx = q.x; e.cy = q.y; }
  else if (t === "text") { e.x = q.x; e.y = q.y; }
  else if (t === "dim") { if (k === 0) { e.x1 = q.x; e.y1 = q.y; } else if (k === 1) { e.x2 = q.x; e.y2 = q.y; } else Object.assign(e, { offset: dimEntity(P(e.x1, e.y1), P(e.x2, e.y2), q).offset }); }
  else if (t === "ldim") { if (k === 0) { e.x1 = q.x; e.y1 = q.y; } else if (k === 1) { e.x2 = q.x; e.y2 = q.y; } else { e.bx = q.x; e.by = q.y; } }
  else if (t === "rdim") { if (k === 0) { e.cx = q.x; e.cy = q.y; } else e.angle = cadNum(toDeg(cadAng(P(e.cx, e.cy), q))); }
}

// ---------------- events ----------------
document.getElementById("cad-toolbar").addEventListener("click", (event) => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.tool) cadSetTool(button.dataset.tool);
  if (button.dataset.cad) cadAction(button.dataset.cad);
  cadCanvas.focus();
});
document.getElementById("cad-cmd-form").addEventListener("submit", (event) => {
  event.preventDefault(); const input = document.getElementById("cad-cmd");
  const v = input.value; input.value = ""; cadExec(v);
});
document.getElementById("cad-layer-add").addEventListener("click", () => {
  const name = (window.prompt("Yangi qatlam nomi:", `Qatlam ${cadState.doc.layers.length}`) || "").trim();
  if (!name) return;
  if (/[<>/\\":;?*|=`]/.test(name) || name.length > 60 || cadLayer(name)) { cadLog("Qatlam nomi noto‘g‘ri yoki mavjud."); return; }
  cadSnapshot(); cadState.doc.layers.push({ name, color: 7, lineweight: 25, linetype: "Continuous", visible: true, locked: false });
  cadState.layer = name; cadRenderLayers(); cadRender();
});
document.querySelectorAll("#page-cad [data-toggle]").forEach((button) => button.addEventListener("click", () => {
  const key = button.dataset.toggle; cadState[key] = !cadState[key];
  button.classList.toggle("on", cadState[key]); cadRender();
}));
cadCanvas.addEventListener("contextmenu", (event) => event.preventDefault());
cadCanvas.addEventListener("wheel", (event) => {
  event.preventDefault();
  const box = cadCanvas.getBoundingClientRect(), p = P(event.clientX - box.left, event.clientY - box.top);
  const before = cadModel(p);
  cadState.scale = Math.max(0.0005, Math.min(2000, cadState.scale * (event.deltaY < 0 ? 1.18 : 1 / 1.18)));
  cadState.ox = p.x - before.x * cadState.scale; cadState.oy = p.y + before.y * cadState.scale;
  cadRender();
}, { passive: false });
cadCanvas.addEventListener("pointerdown", (event) => {
  const box = cadCanvas.getBoundingClientRect(), s = P(event.clientX - box.left, event.clientY - box.top);
  cadCanvas.setPointerCapture(event.pointerId); cadCanvas.focus();
  if (event.button === 1 || (event.button === 2 && cadState.tool === "select")) { cadState.drag = { kind: "pan", from: s, ox: cadState.ox, oy: cadState.oy, moved: false }; return; }
  if (event.button === 2) { cadFinish(); return; } // right click = Enter, like AutoCAD
  if (event.button !== 0) return;
  const raw = cadModel(s);
  if (cadState.tool === "offset-side") { cadOffsetSide(raw); return; }
  if (cadState.tool === "zoomwin" && !cadState.points.length) { cadState.drag = { kind: "zoomwin", from: s, to: s }; cadState.points = [raw]; return; }
  if (cadState.tool !== "select") { cadTakePoint(cadSnap(raw, cadState.points.at(-1))); return; }
  const grip = cadGripAt(s);
  if (grip) { cadSnapshot(); cadState.drag = { kind: "grip", ...grip }; return; }
  const hit = cadPick(raw);
  if (hit >= 0) {
    if (event.shiftKey && cadState.selected.has(hit)) cadState.selected.delete(hit);
    else { if (!event.shiftKey && !event.ctrlKey) cadState.selected.clear(); cadState.selected.add(hit); }
    cadState.drag = null;
  } else {
    if (!event.shiftKey) cadState.selected.clear();
    cadState.drag = { kind: "select", from: s, to: s };
  }
  cadRender(); cadRenderProps();
});
cadCanvas.addEventListener("pointermove", (event) => {
  const box = cadCanvas.getBoundingClientRect(), s = P(event.clientX - box.left, event.clientY - box.top);
  const d = cadState.drag, raw = cadModel(s);
  if (d && d.kind === "pan") { cadState.ox = d.ox + s.x - d.from.x; cadState.oy = d.oy + s.y - d.from.y; d.moved = true; }
  else if (d && (d.kind === "select" || d.kind === "zoomwin")) d.to = s;
  else if (d && d.kind === "grip") { const q = cadSnap(raw); cadMoveGrip(cadState.doc.entities[d.i], d.k, q); }
  cadState.raw = raw;
  cadState.cursor = cadState.tool === "select" ? raw : cadSnap(raw, cadState.points.at(-1));
  if (cadState.tool === "select" && !d) { const h = cadPick(raw); if (h !== cadState.hover) cadState.hover = h; }
  document.getElementById("cad-xy").textContent = `X ${fmt(cadState.cursor.x)} · Y ${fmt(cadState.cursor.y)} mm`;
  cadRender();
});
cadCanvas.addEventListener("pointerup", (event) => {
  const d = cadState.drag;
  if (d && d.kind === "select" && Math.hypot(d.to.x - d.from.x, d.to.y - d.from.y) > 5) {
    const a = cadModel(d.from), b = cadModel(d.to), contain = d.to.x >= d.from.x;
    const box = { x1: Math.min(a.x, b.x), x2: Math.max(a.x, b.x), y1: Math.min(a.y, b.y), y2: Math.max(a.y, b.y) };
    cadState.doc.entities.forEach((e, i) => {
      if (!cadVisible(e) || cadLocked(e)) return;
      const v = cadBounds(e); if (!v) return;
      const inside = v.x1 >= box.x1 && v.x2 <= box.x2 && v.y1 >= box.y1 && v.y2 <= box.y2;
      const overlap = v.x1 <= box.x2 && v.x2 >= box.x1 && v.y1 <= box.y2 && v.y2 >= box.y1;
      if (contain ? inside : overlap) cadState.selected.add(i);
    });
  }
  if (d && d.kind === "zoomwin") {
    const a = cadModel(d.from), b = cadModel(d.to);
    if (Math.hypot(d.to.x - d.from.x, d.to.y - d.from.y) > 5) { cadZoomTo(Math.min(a.x, b.x), Math.min(a.y, b.y), Math.max(a.x, b.x), Math.max(a.y, b.y)); cadSetTool("select"); }
  }
  if (d && d.kind === "grip") cadState.dirty = true;
  cadState.drag = null; cadRender(); cadRenderProps();
  if (cadCanvas.hasPointerCapture(event.pointerId)) cadCanvas.releasePointerCapture(event.pointerId);
});
cadCanvas.addEventListener("dblclick", () => { if (cadState.tool === "polyline") cadFinish(); else if (cadState.tool === "select" && !cadState.selected.size) cadExtents(); });
document.addEventListener("keydown", (event) => {
  if (!document.getElementById("page-cad").classList.contains("active")) return;
  const tag = document.activeElement.tagName, inCmd = document.activeElement.id === "cad-cmd";
  const editing = ["INPUT", "TEXTAREA", "SELECT"].includes(tag) && !inCmd;
  const key = event.key.toLowerCase();
  if (["F3", "F7", "F8"].includes(event.key)) { event.preventDefault(); document.querySelector(`#page-cad [data-toggle=${{ F3: "snap", F7: "grid", F8: "ortho" }[event.key]}]`).click(); return; }
  if (editing) return;
  if (event.ctrlKey && ["z", "y", "s", "a", "c", "v"].includes(key)) {
    if (inCmd && ["a", "c", "v"].includes(key) && document.getElementById("cad-cmd").value) return;
    event.preventDefault(); cadAction({ z: "undo", y: "redo", s: "save", a: "selectall", c: "copyclip", v: "paste" }[key]); return;
  }
  if (event.key === "Escape") { event.preventDefault(); document.getElementById("cad-cmd").value = ""; cadState.selected.clear(); cadSetTool("select"); cadRenderProps(); return; }
  if (inCmd) return; // the command line handles its own Enter
  if (event.key === "Delete") { event.preventDefault(); cadAction("erase"); }
  else if (event.key === "Enter" || event.key === " ") { event.preventDefault(); cadFinish(); }
  else if (event.key === "+" || event.key === "=") { event.preventDefault(); cadAction("zoomin"); }
  else if (event.key === "-") { event.preventDefault(); cadAction("zoomout"); }
  else if (event.key.length === 1 && !event.ctrlKey && !event.altKey) { const cmd = document.getElementById("cad-cmd"); cmd.focus(); }
});
window.addEventListener("resize", () => { if (cadState.ready) cadRender(); });
window.cad = {
  exec: cadExec, load: cadLoad, action: cadAction, setTool: cadSetTool,
  get doc() { return cadState.doc; }, get selected() { return [...cadState.selected]; },
  select(ids) { cadState.selected = new Set(ids); cadRender(); cadRenderProps(); },
  click(x, y) { cadTakePoint(cadSnap(P(x, y), cadState.points.at(-1))); }, // model coordinates
  pick(x, y) { if (cadState.tool === "offset-side") cadOffsetSide(P(x, y)); else cadPickTool(cadState.tool, P(x, y)); },
};
