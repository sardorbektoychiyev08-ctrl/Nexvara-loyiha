"use strict";

// «3D ko‘rinish»: closed shapes of the drawing (polylines, circles, ellipses) are extruded by a
// thickness; shapes inside the biggest one become through-holes. Drawn on a canvas with flat
// shading (painter's algorithm) — enough to see the part; no library, works offline.

function cad3dRings() {
  // closed outlines as point lists (model mm), with their area
  const rings = [];
  const skip = new Set(["RAMKA", "OQ_CHIZIQ", "OLCHAM", "MATN", "INGICHKA", "YASHIRIN", "SHTRIX", "Defpoints"]);
  cadState.doc.entities.forEach((e) => {
    if (!cadVisible(e) || skip.has(e.layer)) return; // frame, axes, thin lines are not the part
    const ly = cadLayer(e.layer);
    if ((e.linetype || (ly && ly.linetype)) === "NX_OQ") return;
    let pts = null;
    if ((e.type === "polyline" && e.closed) || e.type === "circle" || e.type === "ellipse") {
      pts = [];
      cadPrims(e).forEach((pr) => {
        if (pr.k === "seg") pts.push(pr.a);
        else { const n = Math.max(12, Math.ceil((pr.a1 - pr.a0) / (Math.PI / 24))); for (let i = 0; i < n; i++) pts.push(arcPoint(pr, pr.a0 + (pr.a1 - pr.a0) * i / n)); }
      });
    }
    if (pts && pts.length >= 3) rings.push({ pts, area: Math.abs(polyArea(pts)) });
  });
  return rings.sort((a, b) => b.area - a.area);
}

function cad3dOpen() {
  const rings = cad3dRings();
  if (!rings.length) { cadLog("3D uchun yopiq shakl kerak: to‘rtburchak, yopiq polichiziq yoki aylana chizing."); return; }
  const raw = window.prompt("Detal qalinligi, mm:", "10");
  if (raw === null) return;
  const t = Number(String(raw).replace(",", "."));
  if (!(t > 0 && t < 100000)) { cadLog("Qalinlik musbat son bo‘lishi kerak."); return; }
  const outer = rings[0];
  const inside = (p, ring) => cadInside(p, [ring.map((q) => [q.x, q.y])]);
  const holes = rings.slice(1).filter((r) => r.pts.every((p) => inside(p, outer.pts)));
  const others = rings.slice(1).filter((r) => !holes.includes(r)); // separate solids
  const solids = [{ outer: outer.pts, holes: holes.map((h) => h.pts) }, ...others.map((r) => ({ outer: r.pts, holes: [] }))];
  // centre the part
  const all = solids.flatMap((s) => s.outer);
  const cx = (Math.min(...all.map((p) => p.x)) + Math.max(...all.map((p) => p.x))) / 2;
  const cy = (Math.min(...all.map((p) => p.y)) + Math.max(...all.map((p) => p.y))) / 2;
  const size = Math.max(...all.map((p) => Math.hypot(p.x - cx, p.y - cy)), t, 1);
  const faces = [];
  const wall = (ring, flip) => ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length];
    const quad = [[p.x, p.y, 0], [q.x, q.y, 0], [q.x, q.y, t], [p.x, p.y, t]].map(([x, y, z]) => [x - cx, y - cy, z - t / 2]);
    faces.push({ pts: flip ? quad.reverse() : quad, kind: "side" });
  });
  solids.forEach((s) => {
    wall(s.outer, polyArea(s.outer) < 0);
    s.holes.forEach((h) => wall(h, polyArea(h) > 0));
    [0, t].forEach((z) => faces.push({ rings: [s.outer, ...s.holes].map((r) => r.map((p) => [p.x - cx, p.y - cy, z - t / 2])), kind: z ? "top" : "bottom" }));
  });

  const box = document.createElement("div");
  box.className = "cad3d";
  box.innerHTML = `<div class="cad3d-bar"><b>3D ko‘rinish</b><span class="muted small">qalinligi ${fmt(t)} mm · ${holes.length} ta teshik · sichqoncha bilan aylantiring, g‘ildirak — yaqinlashtirish</span><button class="btn" type="button">Yopish</button></div><canvas></canvas>`;
  document.body.appendChild(box);
  const cv = box.querySelector("canvas"), c = cv.getContext("2d");
  let yaw = -0.6, pitch = 0.9, zoom = 1;
  const css = getComputedStyle(document.documentElement);
  const accent = css.getPropertyValue("--accent").trim() || "#6366F1";
  function rgb(hex, k) {
    const n = parseInt(hex.replace("#", ""), 16), r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    return `rgb(${Math.round(r * k)},${Math.round(g * k)},${Math.round(b * k)})`;
  }
  function draw() {
    const w = cv.clientWidth, h = cv.clientHeight, dpr = window.devicePixelRatio || 1;
    cv.width = w * dpr; cv.height = h * dpr; c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.fillStyle = css.getPropertyValue("--cad-bg").trim() || "#0b1325"; c.fillRect(0, 0, w, h);
    const s = Math.min(w, h) * 0.38 / size * zoom;
    const cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const view = ([x, y, z]) => { const x1 = x * cyw - y * syw, y1 = x * syw + y * cyw; return [x1, y1 * cp - z * sp, y1 * sp + z * cp]; };
    const proj = (v) => [w / 2 + v[0] * s, h / 2 - v[2] * s];
    const light = [0.4, -0.5, 0.75];
    const topFront = view([0, 0, 1])[1] < view([0, 0, -1])[1]; // looking from above? ([1] = depth)
    const capOrder = (f) => (f.kind === "side" ? 1 : (f.kind === "top") === topFront ? 2 : 0);
    const list = faces.map((f) => {
      const vs = (f.pts || f.rings[0]).map(view);
      const a = vs[0], b = vs[1], d = vs[2] || vs[1];
      const n = [(b[1] - a[1]) * (d[2] - a[2]) - (b[2] - a[2]) * (d[1] - a[1]), (b[2] - a[2]) * (d[0] - a[0]) - (b[0] - a[0]) * (d[2] - a[2]), (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])];
      const len = Math.hypot(...n) || 1;
      const depth = vs.reduce((acc, v) => acc + v[1], 0) / vs.length;
      let shade = Math.abs((n[0] * light[0] + n[1] * light[1] + n[2] * light[2]) / len);
      if (f.kind !== "side") shade = f.kind === "top" ? 0.95 : 0.55;
      return { f, depth, shade };
    }).sort((p, q) => q.depth - p.depth)
      // caps last/first: the cap facing the viewer hides the walls behind it, and the holes
      // (cut out with even-odd) show the walls through the opening
      .sort((p, q) => capOrder(p.f) - capOrder(q.f));
    list.forEach(({ f, shade }) => {
      c.beginPath();
      (f.rings || [f.pts]).forEach((ring) => ring.map(view).map(proj).forEach(([x, y], i) => (i ? c.lineTo(x, y) : c.moveTo(x, y))));
      c.closePath();
      c.fillStyle = rgb(accent, 0.35 + 0.65 * shade); c.fill("evenodd");
      c.strokeStyle = "rgba(0,0,0,.25)"; c.lineWidth = 0.6; if (f.kind !== "side") c.stroke();
    });
  }
  let drag = null;
  cv.addEventListener("pointerdown", (e) => { drag = [e.clientX, e.clientY, yaw, pitch]; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener("pointermove", (e) => { if (!drag) return; yaw = drag[2] + (e.clientX - drag[0]) / 150; pitch = Math.max(-1.5, Math.min(1.5, drag[3] + (e.clientY - drag[1]) / 150)); draw(); });
  cv.addEventListener("pointerup", () => { drag = null; });
  cv.addEventListener("wheel", (e) => { e.preventDefault(); zoom = Math.max(0.2, Math.min(8, zoom * (e.deltaY < 0 ? 1.15 : 0.87))); draw(); }, { passive: false });
  const close = () => { box.remove(); window.removeEventListener("resize", draw); document.removeEventListener("keydown", esc); };
  const esc = (e) => { if (e.key === "Escape") close(); };
  box.querySelector("button").addEventListener("click", close);
  window.addEventListener("resize", draw); document.addEventListener("keydown", esc);
  requestAnimationFrame(draw);
  window.cad3dFaces = faces.length; // for the window test
  cadLog(`3D: ${solids.length} ta qism, ${holes.length} ta teshik, qalinligi ${fmt(t)} mm.`);
}
