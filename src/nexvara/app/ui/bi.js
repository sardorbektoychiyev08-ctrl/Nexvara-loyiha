"use strict";
// NEXVARA BI: dashboards drawn as SVG inside the app (no Power BI, no internet).
// Uses $, el, api, track, show from app.js.

const BI_COLORS = ["#6366F1", "#06B6D4", "#22C55E", "#F59E0B", "#EF4444", "#A855F7", "#EC4899", "#14B8A6", "#84CC16", "#F97316"];
const BI_TYPES = { kpi: "KPI karta", bar: "Ustunli", line: "Chiziqli", pie: "Doiraviy", scatter: "Nuqtali", table: "Jadval" };
const BI_AGGS = { sum: "jami", avg: "o‘rtacha", count: "soni", min: "eng kichik", max: "eng katta" };
const BI_STEPS = {
  dedupe: "Takroriy qatorlarni o‘chirish", drop_empty: "Bo‘sh qatorlarni o‘chirish",
  fill_null: "Bo‘sh qiymatlarni to‘ldirish", drop_null: "Ustunda bo‘sh qatorlarni o‘chirish",
  filter: "Filtr", calc: "Hisoblangan ustun", rename: "Ustun nomini o‘zgartirish",
  drop_col: "Ustunni olib tashlash", set_type: "Ustun turini o‘zgartirish", join: "Boshqa fayl bilan birlashtirish",
};
let bi = { cfg: null, res: null, state: { filters: {}, page: 0 }, file: "" };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function fmtNum(v, digits) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const d = digits ?? (abs >= 100 ? 0 : 2);
  // Uzbek style: 1 234 567,5 (space groups, comma decimals), whatever the PC locale is.
  return v.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: 0 })
    .replace(/,/g, " ").replace(".", ",");
}
function shortNum(v) {
  if (v === null || v === undefined) return "";
  const a = Math.abs(v);
  if (a >= 1e9) return `${fmtNum(v / 1e9, 1)} mlrd`;
  if (a >= 1e6) return `${fmtNum(v / 1e6, 1)} mln`;
  if (a >= 1e4) return `${fmtNum(v / 1e3, 0)} ming`;
  return fmtNum(v);
}
const trunc = (s, n) => (String(s).length > n ? `${String(s).slice(0, n - 1)}…` : String(s));

// ---------- chart renderers: each returns an SVG string of the given size ----------
function axisTicks(max, min = 0) {
  const span = max - min || 1;
  const step = 10 ** Math.floor(Math.log10(span / 4));
  const nice = [1, 2, 5, 10].map((m) => m * step).find((s) => span / s <= 5) || step * 10;
  // From the nice step below the minimum to the first one at or above the maximum,
  // so no bar or point ever goes past the top line.
  const ticks = [];
  const end = Math.ceil(max / nice - 1e-9) * nice;
  for (let v = Math.floor(min / nice + 1e-9) * nice; v <= end + nice * 1e-6; v += nice) ticks.push(Math.round(v / nice) * nice);
  if (ticks.length < 2) ticks.push(ticks[0] + nice);
  return ticks;
}

function svgBar(w, W, H) {
  const vals = w.values || [];
  if (!vals.length) return emptySvg(W, H);
  const m = { l: 64, r: 12, t: 10, b: 58 };
  const max = Math.max(0, ...vals), min = Math.min(0, ...vals);
  const ticks = axisTicks(max, min);
  const top = ticks[ticks.length - 1], bot = ticks[0];
  const y = (v) => m.t + (H - m.t - m.b) * (1 - (v - bot) / (top - bot || 1));
  const bw = (W - m.l - m.r) / vals.length;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI" font-size="11">`;
  ticks.forEach((t) => { s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}" stroke="#8883" /><text x="${m.l - 6}" y="${y(t) + 4}" text-anchor="end" fill="#8A93B8">${esc(shortNum(t))}</text>`; });
  vals.forEach((v, i) => {
    const x = m.l + i * bw + bw * 0.12, h = Math.abs(y(v) - y(0));
    s += `<rect class="bi-hit" data-label="${esc(w.labels[i])}" data-value="${v}" x="${x}" y="${Math.min(y(v), y(0))}" width="${bw * 0.76}" height="${Math.max(1, h)}" rx="3" fill="${BI_COLORS[0]}"><title>${esc(w.labels[i])}: ${esc(fmtNum(v))}</title></rect>`;
    s += `<text x="${x + bw * 0.38}" y="${H - m.b + 14}" text-anchor="end" transform="rotate(-35 ${x + bw * 0.38} ${H - m.b + 14})" fill="#8A93B8">${esc(trunc(w.labels[i], 14))}</text>`;
  });
  return s + "</svg>";
}

function svgLine(w, W, H) {
  const labels = w.labels || [], series = w.series || [];
  if (!labels.length) return emptySvg(W, H);
  const all = series.flatMap((s) => s.values.filter((v) => v !== null));
  const m = { l: 64, r: 34, t: 26, b: 40 };
  const ticks = axisTicks(Math.max(0, ...all), Math.min(0, ...all));
  const top = ticks[ticks.length - 1], bot = ticks[0];
  const y = (v) => m.t + (H - m.t - m.b) * (1 - (v - bot) / (top - bot || 1));
  const x = (i) => m.l + (labels.length === 1 ? (W - m.l - m.r) / 2 : (i * (W - m.l - m.r)) / (labels.length - 1));
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI" font-size="11">`;
  ticks.forEach((t) => { s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(t)}" y2="${y(t)}" stroke="#8883" /><text x="${m.l - 6}" y="${y(t) + 4}" text-anchor="end" fill="#8A93B8">${esc(shortNum(t))}</text>`; });
  const every = Math.ceil(labels.length / 10);
  labels.forEach((l, i) => { if (i % every === 0) s += `<text x="${x(i)}" y="${H - m.b + 16}" text-anchor="middle" fill="#8A93B8">${esc(l)}</text>`; });
  series.forEach((ser, k) => {
    const c = BI_COLORS[k % BI_COLORS.length];
    const pts = ser.values.map((v, i) => (v === null ? null : [x(i), y(v)]));
    let d = "", pen = false;
    pts.forEach((p) => { if (!p) { pen = false; return; } d += `${pen ? "L" : "M"}${p[0]},${p[1]} `; pen = true; });
    s += `<path d="${d}" fill="none" stroke="${c}" stroke-width="2.5" />`;
    pts.forEach((p, i) => { if (p) s += `<circle class="bi-hit" data-period="${esc(labels[i])}" cx="${p[0]}" cy="${p[1]}" r="4" fill="${c}"><title>${esc(ser.name)} · ${esc(labels[i])}: ${esc(fmtNum(ser.values[i]))}</title></circle>`; });
    s += `<rect x="${m.l + k * 130}" y="6" width="10" height="10" rx="2" fill="${c}"/><text x="${m.l + k * 130 + 14}" y="15" fill="#8A93B8">${esc(trunc(ser.name, 16))}</text>`;
  });
  return s + "</svg>";
}

function svgPie(w, W, H) {
  const vals = (w.values || []).map((v) => Math.max(0, v));
  const total = vals.reduce((a, b) => a + b, 0);
  if (!total) return emptySvg(W, H);
  const r = Math.min(H / 2 - 12, W / 4), cx = r + 16, cy = H / 2;
  let a0 = -Math.PI / 2;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI" font-size="11">`;
  vals.forEach((v, i) => {
    const a1 = a0 + (v / total) * Math.PI * 2;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p = (a, rr) => `${cx + rr * Math.cos(a)},${cy + rr * Math.sin(a)}`;
    const c = BI_COLORS[i % BI_COLORS.length];
    const pct = ((v / total) * 100).toFixed(1);
    const d = vals.length === 1 ? `M${p(0, r)} A${r},${r} 0 1 1 ${p(Math.PI * 1.999, r)} L${p(Math.PI * 1.999, r * 0.58)} A${r * 0.58},${r * 0.58} 0 1 0 ${p(0, r * 0.58)} Z`
      : `M${p(a0, r)} A${r},${r} 0 ${large} 1 ${p(a1, r)} L${p(a1, r * 0.58)} A${r * 0.58},${r * 0.58} 0 ${large} 0 ${p(a0, r * 0.58)} Z`;
    s += `<path class="bi-hit" data-label="${esc(w.labels[i])}" d="${d}" fill="${c}"><title>${esc(w.labels[i])}: ${esc(fmtNum(v))} (${pct}%)</title></path>`;
    s += `<rect x="${cx + r + 20}" y="${16 + i * 20}" width="10" height="10" rx="2" fill="${c}"/><text x="${cx + r + 36}" y="${25 + i * 20}" fill="#8A93B8">${esc(trunc(w.labels[i], 18))} · ${pct}%</text>`;
    a0 = a1;
  });
  return s + `<text x="${cx}" y="${cy + 4}" text-anchor="middle" font-size="13" font-weight="600" fill="#8A93B8">${esc(shortNum(total))}</text></svg>`;
}

function svgScatter(w, W, H) {
  const pts = w.points || [];
  if (!pts.length) return emptySvg(W, H);
  const m = { l: 64, r: 12, t: 10, b: 36 };
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const xt = axisTicks(Math.max(...xs), Math.min(0, ...xs)), yt = axisTicks(Math.max(...ys), Math.min(0, ...ys));
  const X = (v) => m.l + (W - m.l - m.r) * ((v - xt[0]) / (xt[xt.length - 1] - xt[0] || 1));
  const Y = (v) => m.t + (H - m.t - m.b) * (1 - (v - yt[0]) / (yt[yt.length - 1] - yt[0] || 1));
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI" font-size="11">`;
  yt.forEach((t) => { s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(t)}" y2="${Y(t)}" stroke="#8883"/><text x="${m.l - 6}" y="${Y(t) + 4}" text-anchor="end" fill="#8A93B8">${esc(shortNum(t))}</text>`; });
  xt.forEach((t) => { s += `<text x="${X(t)}" y="${H - m.b + 16}" text-anchor="middle" fill="#8A93B8">${esc(shortNum(t))}</text>`; });
  pts.forEach((p) => { s += `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3.5" fill="${BI_COLORS[1]}" fill-opacity=".7"><title>${esc(w.x)}: ${esc(fmtNum(p[0]))}, ${esc(w.y)}: ${esc(fmtNum(p[1]))}</title></circle>`; });
  s += `<text x="${W - m.r}" y="${H - 4}" text-anchor="end" fill="#8A93B8">${esc(w.x)} →</text><text x="4" y="${m.t + 8}" fill="#8A93B8">↑ ${esc(Array.isArray(w.y) ? w.y[0] : w.y)}</text>`;
  return s + "</svg>";
}

function emptySvg(W, H) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI" font-size="13"><text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="#8A93B8">Ma’lumot yo‘q</text></svg>`;
}

function kpiHtml(w) {
  const unit = w.unit || "";
  const g = w.growth;
  const growth = g === undefined || g === null ? "" : `<div class="bi-growth ${g >= 0 ? "up" : "down"}">${g >= 0 ? "▲" : "▼"} ${fmtNum(Math.abs(g), 1)}% <span class="muted">${esc(w.growth_label || "")}</span></div>`;
  return `<div class="bi-kpi-value">${esc(unit === "%" ? fmtNum(w.value, 1) : shortNum(w.value))}${unit}</div>${growth}`;
}

function tableHtml(w) {
  const cols = w.columns || [];
  let h = `<div class="bi-table-wrap"><table class="lib-table"><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>`;
  (w.rows || []).forEach((r) => { h += `<tr>${r.map((v) => `<td>${esc(typeof v === "number" ? fmtNum(v) : v ?? "")}</td>`).join("")}</tr>`; });
  h += "</table></div>";
  if (w.total_rows > (w.rows || []).length && !w.x) h += `<div class="muted small">${(w.rows || []).length} / ${w.total_rows} qator ko‘rsatildi</div>`;
  return h;
}

function chartSvg(w, W, H) {
  return { bar: svgBar, line: svgLine, pie: svgPie, scatter: svgScatter }[w.type](w, W, H);
}

// ---------- page rendering ----------
async function renderBi() {
  if (!api()) return;
  drawBiSaved(await api().bi_list());
  if (bi.cfg) drawBi();
}

function drawBiSaved(list) {
  const sel = $("#bi-saved");
  sel.textContent = "";
  sel.appendChild(el("option", "", list.length ? "— saqlangan dashboardlar —" : "— saqlangan dashboard yo‘q —")).value = "";
  list.forEach((d) => { const o = el("option", "", `${d.name} (${(d.source || "").split(/[\\/]/).pop()})`); o.value = d.file; sel.appendChild(o); });
}

async function biLoad(res) {
  if (!res.ok) { biError(res.error); return; }
  bi.cfg = res.config; bi.res = res.result; bi.state = { filters: {}, page: 0 }; bi.file = "";
  $("#bi-name").value = bi.cfg.name || "";
  biError("");
  drawBi();
}

async function biOpenSource(path) {
  show("bi");
  $("#bi-msg").textContent = "Yuklanmoqda…";
  const sheets = path ? await api().bi_sheets(path) : [];
  const sel = $("#bi-sheet");
  sel.textContent = "";
  sel.hidden = sheets.length < 2;
  sheets.forEach((s) => { const o = el("option", "", s); o.value = s; sel.appendChild(o); });
  await biLoad(await api().bi_auto(path, sheets.length > 1 ? sheets[0] : null));
  $("#bi-msg").textContent = bi.cfg ? `Manba: ${path}` : "";
}

function biError(text) { $("#bi-error").hidden = !text; $("#bi-error").textContent = text || ""; }

async function biRefresh() {
  const r = await api().bi_compute(bi.cfg, bi.state);
  if (!r.ok) { biError(r.error); return; }
  biError("");
  bi.res = r.result;
  drawBi();
}

function drawBi() {
  const res = bi.res;
  $("#bi-board").hidden = !res;
  if (!res) return;
  // page tabs
  const tabs = $("#bi-tabs");
  tabs.textContent = "";
  res.pages.forEach((p, i) => {
    const b = el("button", i === res.page ? "btn primary small-btn" : "btn small-btn", p);
    b.type = "button";
    b.addEventListener("click", () => { bi.state.page = i; biRefresh(); });
    tabs.appendChild(b);
  });
  const add = el("button", "btn small-btn", "+ Sahifa"); add.type = "button";
  add.addEventListener("click", () => {
    const t = prompt("Yangi sahifa nomi:", `Sahifa ${bi.cfg.pages.length + 1}`);
    if (!t) return;
    bi.cfg.pages.push({ title: t, widgets: [] });
    bi.state.page = bi.cfg.pages.length - 1;
    biRefresh();
  });
  tabs.appendChild(add);
  // slicers
  const fl = $("#bi-filters");
  fl.textContent = "";
  Object.entries(res.slicers).forEach(([col, values]) => {
    const lab = el("label", "", col);
    const sel = el("select");
    sel.appendChild(el("option", "", "Barchasi")).value = "";
    values.forEach((v) => { const o = el("option", "", v); o.value = v; sel.appendChild(o); });
    sel.addEventListener("change", () => {
      if (!sel.value) return;
      const cur = new Set(bi.state.filters[col] || []);
      cur.add(sel.value);
      bi.state.filters[col] = [...cur];
      biRefresh();
    });
    lab.appendChild(sel);
    fl.appendChild(lab);
  });
  if (res.date_range) {
    const from = el("label", "", "Sanadan"), to = el("label", "", "Sanagacha");
    const fi = el("input"); fi.type = "date"; fi.min = res.date_range[0]; fi.max = res.date_range[1]; fi.value = bi.state.date_from || "";
    const ti = el("input"); ti.type = "date"; ti.min = res.date_range[0]; ti.max = res.date_range[1]; ti.value = bi.state.date_to || "";
    fi.addEventListener("change", () => { bi.state.date_from = fi.value; biRefresh(); });
    ti.addEventListener("change", () => { bi.state.date_to = ti.value; biRefresh(); });
    from.appendChild(fi); to.appendChild(ti);
    fl.append(from, to);
  }
  // active filter chips
  const chips = $("#bi-chips");
  chips.textContent = "";
  Object.entries(bi.state.filters).forEach(([col, vals]) => vals.forEach((v) => {
    const c = el("button", "chip", `${col}: ${v} ✕`); c.type = "button";
    c.addEventListener("click", () => { bi.state.filters[col] = vals.filter((x) => x !== v); biRefresh(); });
    chips.appendChild(c);
  }));
  if (bi.state.date_from || bi.state.date_to) {
    const c = el("button", "chip", `Sana: ${bi.state.date_from || "…"} — ${bi.state.date_to || "…"} ✕`); c.type = "button";
    c.addEventListener("click", () => { bi.state.date_from = bi.state.date_to = ""; biRefresh(); });
    chips.appendChild(c);
  }
  $("#bi-rows").textContent = `${res.rows} / ${res.total_rows} qator${res.notes.length ? " · " + res.notes.join(" · ") : ""}`;
  if (res.problems.length) biError(`Ba’zi vidjetlar chizilmadi: ${res.problems.join("; ")}`);
  // widgets
  const grid = $("#bi-grid"), kpis = $("#bi-kpis");
  grid.textContent = ""; kpis.textContent = "";
  res.widgets.forEach((w, idx) => (w.type === "kpi" ? kpis : grid).appendChild(widgetCard(w, idx)));
  drawCharts();
}

// Charts are drawn at the size of their card, so text stays readable in any layout.
function drawCharts() {
  document.querySelectorAll("#bi-grid .bi-body[data-chart]").forEach((b) => {
    const W = Math.max(260, Math.floor(b.clientWidth));
    b.innerHTML = chartSvg(b._widget, W, b._widget.type === "line" ? 300 : 260);
  });
  biTooltips();
}
let biResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(biResizeTimer);
  biResizeTimer = setTimeout(() => { if (bi.res && $("#page-bi").classList.contains("active")) drawCharts(); }, 150);
});

function widgetCard(w, idx) {
  const card = el("div", `card bi-widget bi-${w.type}`);
  const head = el("div", "bi-widget-head");
  head.appendChild(el("div", "card-label", w.title || BI_TYPES[w.type]));
  const tools = el("div", "bi-tools");
  const ed = el("button", "icon-btn", "✎"); ed.title = "Tahrirlash"; ed.type = "button";
  ed.addEventListener("click", () => widgetForm(idx));
  const rm = el("button", "icon-btn", "✕"); rm.title = "Olib tashlash"; rm.type = "button";
  rm.addEventListener("click", () => { if (!confirm("Vidjet olib tashlansinmi?")) return; bi.cfg.pages[bi.res.page].widgets.splice(idx, 1); biRefresh(); });
  tools.append(ed, rm);
  head.appendChild(tools);
  card.appendChild(head);
  const body = el("div", "bi-body");
  if (w.type === "kpi") body.innerHTML = kpiHtml(w);
  else if (w.type === "table") body.innerHTML = tableHtml(w);
  else {
    body.dataset.chart = "1";
    body._widget = w; // drawn at the card's real width once it is on the page
    body.addEventListener("click", (e) => {
      const hit = e.target.closest(".bi-hit");
      if (!hit) return;
      if (hit.dataset.label && w.x) { // drill-down: filter by the clicked category
        if (hit.dataset.label === "Boshqalar") return;
        const cur = new Set(bi.state.filters[w.x] || []);
        cur.add(hit.dataset.label);
        bi.state.filters[w.x] = [...cur];
        biRefresh();
      } else if (hit.dataset.period) { // a month/day on a line: limit the dates to it
        const [from, to] = periodRange(hit.dataset.period);
        if (from) { bi.state.date_from = from; bi.state.date_to = to; biRefresh(); }
      }
    });
  }
  card.appendChild(body);
  return card;
}

function periodRange(p) {
  let m;
  if ((m = p.match(/^(\d{4})-(\d{2})-(\d{2})$/))) return [p, p];
  if ((m = p.match(/^(\d{4})-(\d{2})$/))) { const last = new Date(+m[1], +m[2], 0).getDate(); return [`${p}-01`, `${p}-${String(last).padStart(2, "0")}`]; }
  if ((m = p.match(/^(\d{4})-Q(\d)$/))) { const q = +m[2]; const s = String(q * 3 - 2).padStart(2, "0"), e = String(q * 3).padStart(2, "0"); const last = new Date(+m[1], q * 3, 0).getDate(); return [`${m[1]}-${s}-01`, `${m[1]}-${e}-${last}`]; }
  if ((m = p.match(/^(\d{4})$/))) return [`${p}-01-01`, `${p}-12-31`];
  return [null, null];
}

function biTooltips() {
  const tip = $("#bi-tip");
  $("#bi-grid").querySelectorAll("svg [class~='bi-hit'], svg circle").forEach((n) => {
    const t = n.querySelector("title");
    if (!t) return;
    const text = t.textContent;
    n.addEventListener("mousemove", (e) => { tip.hidden = false; tip.textContent = text; tip.style.left = `${e.clientX + 14}px`; tip.style.top = `${e.clientY + 10}px`; });
    n.addEventListener("mouseleave", () => { tip.hidden = true; });
  });
}

// ---------- widget editor ----------
function widgetForm(idx) {
  const page = bi.cfg.pages[bi.res.page];
  const w = idx === undefined ? { type: "bar", agg: "sum", top: 12, period: "month" } : JSON.parse(JSON.stringify(page.widgets[idx]));
  const box = $("#bi-wform");
  box.hidden = false;
  box.textContent = "";
  box.appendChild(el("div", "card-label", idx === undefined ? "Yangi vidjet" : "Vidjetni tahrirlash"));
  const cols = bi.res.columns;
  const colOpts = (filter) => ["", ...cols.filter(filter).map((c) => c.name)];
  const grid = el("div", "form-grid");
  const field = (label, node) => { const l = el("label", "", label); l.appendChild(node); grid.appendChild(l); return node; };
  const select = (opts, val, labels) => { const s = el("select"); opts.forEach((o) => { const op = el("option", "", labels?.[o] ?? (o || "—")); op.value = o; s.appendChild(op); }); s.value = val ?? ""; return s; };
  const type = field("Turi", select(Object.keys(BI_TYPES), w.type, BI_TYPES));
  const title = field("Sarlavha", el("input")); title.value = w.title || "";
  const x = field("Guruhlash / X ustuni", select(colOpts(() => true), w.x));
  const ys = Array.isArray(w.y) ? w.y : w.y ? [w.y] : [];
  const y = field("Qiymat ustuni (Ctrl bilan bir nechta)", select(colOpts((c) => c.type === "number").slice(1), ""));
  y.multiple = true; y.size = Math.min(5, Math.max(2, y.options.length));
  [...y.options].forEach((o) => { o.selected = ys.includes(o.value); });
  const agg = field("Hisoblash", select(Object.keys(BI_AGGS), w.agg === "margin" ? "sum" : w.agg || "sum", BI_AGGS));
  const period = field("Davr (sana uchun)", select(["day", "month", "quarter", "year"], w.period || "month", { day: "kun", month: "oy", quarter: "chorak", year: "yil" }));
  const top = field("Eng ko‘pi bilan (ustun/bo‘lak)", el("input")); top.type = "number"; top.min = 2; top.max = 50; top.value = w.top || 12;
  const growth = field("KPI: oylik o‘sish", el("input")); growth.type = "checkbox"; growth.checked = !!w.growth;
  box.appendChild(grid);
  const err = el("div", "error"); err.hidden = true;
  const row = el("div", "row");
  const ok = el("button", "btn primary", "Saqlash"); ok.type = "button";
  const cancel = el("button", "btn", "Bekor"); cancel.type = "button";
  cancel.addEventListener("click", () => { box.hidden = true; });
  ok.addEventListener("click", async () => {
    const yv = [...y.selectedOptions].map((o) => o.value);
    const nw = { ...w, type: type.value, title: title.value.trim(), x: x.value || undefined, agg: agg.value, period: period.value, top: Number(top.value), growth: growth.checked };
    if (!nw.id) nw.id = `w${Date.now()}`;
    if (nw.type === "kpi" && w.agg === "margin" && agg.value === "sum") nw.agg = "margin";
    nw.y = nw.type === "line" || nw.type === "table" ? yv : yv[0];
    const need = { bar: ["x"], pie: ["x"], line: ["x", "y"], scatter: ["x", "y"], kpi: [], table: [] }[nw.type];
    if (need.includes("x") && !nw.x) { err.hidden = false; err.textContent = "X ustunini tanlang"; return; }
    if (need.includes("y") && (!nw.y || !nw.y.length)) { err.hidden = false; err.textContent = "Qiymat ustunini tanlang"; return; }
    if (nw.type === "kpi" && nw.agg !== "count" && !nw.y) { err.hidden = false; err.textContent = "KPI uchun qiymat ustunini tanlang (yoki «soni»)"; return; }
    if (!nw.title) nw.title = `${BI_TYPES[nw.type]}${nw.x ? `: ${nw.x}` : ""}`;
    if (idx === undefined) page.widgets.push(nw); else page.widgets[idx] = nw;
    box.hidden = true;
    biRefresh();
  });
  row.append(ok, cancel);
  box.append(err, row);
  box.scrollIntoView({ block: "nearest" });
}

// ---------- data preparation (ETL) ----------
async function drawEtl() {
  const r = await api().bi_preview(bi.cfg);
  const box = $("#bi-etl-body");
  box.textContent = "";
  if (!r.ok) { box.appendChild(el("div", "error", r.error)); return; }
  const steps = el("ol", "bi-steps");
  (bi.cfg.steps || []).forEach((s, i) => {
    const li = el("li", "item-row");
    li.append(el("span", "grow", r.steps[i]));
    const rm = el("button", "btn small-btn", "✕"); rm.type = "button";
    rm.addEventListener("click", async () => { bi.cfg.steps.splice(i, 1); await biRefresh(); drawEtl(); });
    li.appendChild(rm);
    steps.appendChild(li);
  });
  if (!bi.cfg.steps.length) steps.appendChild(el("li", "muted", "Bosqich yo‘q — ma’lumot fayldagidek ishlatiladi"));
  box.appendChild(steps);
  // add-step form
  const grid = el("div", "form-grid");
  const sel = (opts, labels) => { const s = el("select"); opts.forEach((o) => { const op = el("option", "", labels?.[o] ?? o); op.value = o; s.appendChild(op); }); return s; };
  const lab = (t, n) => { const l = el("label", "", t); l.appendChild(n); grid.appendChild(l); return l; };
  const op = sel(Object.keys(BI_STEPS), BI_STEPS); lab("Bosqich", op);
  const colNames = r.columns.map((c) => c.name);
  const col = sel(colNames); const colL = lab("Ustun", col);
  const cmp = sel(["=", "!=", ">", ">=", "<", "<=", "contains"], { contains: "ichida bor" }); const cmpL = lab("Taqqoslash", cmp);
  const val = el("input"); const valL = lab("Qiymat", val);
  const name = el("input"); const nameL = lab("Yangi nom", name);
  const expr = el("input"); expr.placeholder = "[Daromad] - [Xarajat]"; const exprL = lab("Formula", expr);
  const typ = sel(["number", "date", "text"], { number: "son", date: "sana", text: "matn" }); const typL = lab("Tur", typ);
  const file = el("input"); file.readOnly = true; file.placeholder = "fayl tanlang"; const fileL = lab("Fayl", file);
  const pick = el("button", "btn small-btn", "Tanlash"); pick.type = "button"; fileL.appendChild(pick);
  pick.addEventListener("click", async () => { const p = await api().bi_pick_source(); if (p) file.value = p; });
  const sync = () => {
    const o = op.value;
    colL.hidden = ["dedupe", "drop_empty", "calc"].includes(o);
    cmpL.hidden = o !== "filter";
    valL.hidden = !["filter", "fill_null"].includes(o);
    nameL.hidden = !["calc", "rename"].includes(o);
    exprL.hidden = o !== "calc";
    typL.hidden = o !== "set_type";
    fileL.hidden = o !== "join";
    val.placeholder = o === "fill_null" ? "masalan 0 (bo‘sh qoldirilsa 0)" : "";
  };
  op.addEventListener("change", sync); sync();
  box.appendChild(grid);
  const add = el("button", "btn primary", "Bosqich qo‘shish"); add.type = "button";
  const err = el("div", "error"); err.hidden = true;
  add.addEventListener("click", async () => {
    const step = { op: op.value };
    if (!colL.hidden) step.col = col.value;
    if (!cmpL.hidden) step.cmp = cmp.value;
    if (!valL.hidden) step.value = val.value;
    if (!nameL.hidden) step.name = name.value.trim();
    if (!exprL.hidden) step.expr = expr.value.trim();
    if (!typL.hidden) step.type = typ.value;
    if (!fileL.hidden) { step.file = file.value; step.on = col.value; }
    bi.cfg.steps = [...(bi.cfg.steps || []), step];
    const test = await api().bi_preview(bi.cfg);
    if (!test.ok) { bi.cfg.steps.pop(); err.hidden = false; err.textContent = test.error; return; }
    await biRefresh();
    drawEtl();
  });
  box.append(add, err);
  // preview table
  const t = el("table", "lib-table");
  const head = el("tr");
  const TYPES = { number: "son", date: "sana", text: "matn" };
  r.columns.forEach((c) => head.appendChild(el("th", "", `${c.name} · ${TYPES[c.type]}`)));
  t.appendChild(head);
  r.rows.forEach((row) => { const tr = el("tr"); row.forEach((v) => tr.appendChild(el("td", "", typeof v === "number" ? fmtNum(v) : v ?? ""))); t.appendChild(tr); });
  const wrap = el("div", "bi-table-wrap"); wrap.appendChild(t);
  box.append(el("div", "muted small", `Ko‘rinish: ${r.rows.length} / ${r.total} qator`), wrap);
}

// ---------- export: the page is redrawn as one SVG, then turned into PNG ----------
function pageSvg(res, title) {
  const W = 1200, cell = 580, gap = 20;
  const kpis = res.widgets.filter((w) => w.type === "kpi");
  const others = res.widgets.filter((w) => w.type !== "kpi");
  const kh = kpis.length ? 96 : 0;
  const rows = Math.ceil(others.length / 2);
  const H = 60 + kh + rows * (300 + gap) + 20;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" font-family="Segoe UI"><rect width="100%" height="100%" fill="#ffffff"/>`;
  s += `<text x="20" y="34" font-size="20" font-weight="700" fill="#121933">${esc(title)}</text><text x="${W - 20}" y="34" font-size="12" text-anchor="end" fill="#5B6488">${esc(res.pages[res.page])} · ${res.rows} qator · ${new Date().toLocaleString()}</text>`;
  const kw = kpis.length ? (W - 40 - gap * (kpis.length - 1)) / kpis.length : 0;
  kpis.forEach((w, i) => {
    const x = 20 + i * (kw + gap);
    const g = w.growth === undefined || w.growth === null ? "" : `${w.growth >= 0 ? "▲" : "▼"} ${fmtNum(Math.abs(w.growth), 1)}%`;
    s += `<rect x="${x}" y="52" width="${kw}" height="84" rx="12" fill="#F5F7FB" stroke="#DCE1EE"/><text x="${x + 14}" y="74" font-size="12" fill="#5B6488">${esc(trunc(w.title, 34))}</text><text x="${x + 14}" y="108" font-size="24" font-weight="700" fill="#121933">${esc(w.unit === "%" ? fmtNum(w.value, 1) : shortNum(w.value))}${w.unit || ""}</text><text x="${x + 14}" y="128" font-size="12" fill="${(w.growth ?? 0) >= 0 ? "#16A34A" : "#DC2626"}">${esc(g)}</text>`;
  });
  others.forEach((w, i) => {
    const x = 20 + (i % 2) * (cell + gap), y = 60 + kh + Math.floor(i / 2) * (300 + gap);
    s += `<rect x="${x}" y="${y}" width="${cell}" height="300" rx="12" fill="#ffffff" stroke="#DCE1EE"/><text x="${x + 14}" y="${y + 24}" font-size="13" font-weight="600" fill="#121933">${esc(trunc(w.title, 60))}</text>`;
    if (w.type === "table") {
      const cols = (w.columns || []).slice(0, 5);
      cols.forEach((c, j) => { s += `<text x="${x + 14 + j * 110}" y="${y + 50}" font-size="11" font-weight="600" fill="#5B6488">${esc(trunc(c, 16))}</text>`; });
      (w.rows || []).slice(0, 12).forEach((r, k) => r.slice(0, 5).forEach((v, j) => { s += `<text x="${x + 14 + j * 110}" y="${y + 70 + k * 18}" font-size="11" fill="#121933">${esc(trunc(typeof v === "number" ? fmtNum(v) : v ?? "", 16))}</text>`; }));
    } else {
      const inner = chartSvg(w, cell - 20, 260).replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "").replace(/<title>.*?<\/title>/g, "");
      s += `<g transform="translate(${x + 10},${y + 34})" font-family="Segoe UI" font-size="11">${inner}</g>`;
    }
  });
  return s + "</svg>";
}

function svgToPng(svg) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width * 2; c.height = img.height * 2;
      const ctx = c.getContext("2d");
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      resolve(c.toDataURL("image/png"));
    };
    img.onerror = () => reject(new Error("rasmga aylantirib bo‘lmadi"));
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  });
}

async function biExport(kind) {
  if (!bi.cfg) return;
  const name = $("#bi-name").value || bi.cfg.name;
  let r;
  if (kind === "csv" || kind === "xlsx") r = await api().bi_export(bi.cfg, bi.state, kind);
  if (kind === "png") r = await api().bi_export_png(bi.cfg, await svgToPng(pageSvg(bi.res, name)));
  if (kind === "pdf") {
    const urls = [];
    for (let i = 0; i < bi.cfg.pages.length; i++) {
      const pr = await api().bi_compute(bi.cfg, { ...bi.state, page: i });
      if (pr.ok) urls.push(await svgToPng(pageSvg(pr.result, name)));
    }
    r = await api().bi_export_pdf({ ...bi.cfg, name }, urls);
  }
  $("#bi-msg").textContent = r.ok ? `Saqlandi: ${r.path}` : `Xato: ${r.error}`;
  if (r.ok) api().reveal_file(r.path);
}

// ---------- toolbar ----------
$("#bi-source").addEventListener("click", async () => { const p = await api().bi_pick_source(); if (p) biOpenSource(p); });
$("#bi-folder").addEventListener("click", async () => { const p = await api().files_pick_folder(); if (p) biOpenSource(p); });
$("#bi-sheet").addEventListener("change", async () => {
  const src = bi.cfg && bi.cfg.source;
  if (src) await biLoad(await api().bi_auto(src, $("#bi-sheet").value));
});
// The chat asked for a saved dashboard (optionally filtered, optionally exported).
async function biFromChat(ui) {
  show("bi");
  if (ui.open) {
    await biLoad(await api().bi_open(ui.open));
    bi.file = ui.open;
  }
  if (!bi.cfg) return;
  if (ui.state) { bi.state = { ...bi.state, ...ui.state }; await biRefresh(); }
  $("#bi-msg").textContent = `Ochildi: ${bi.cfg.name}`;
  if (ui.export) await biExport(ui.export);
}

$("#bi-open").addEventListener("click", async () => {
  const f = $("#bi-saved").value;
  if (!f) return;
  await biLoad(await api().bi_open(f));
  bi.file = f;
  $("#bi-msg").textContent = `Ochildi: ${bi.cfg.name}`;
});
$("#bi-del").addEventListener("click", async () => {
  const f = $("#bi-saved").value;
  if (!f || !confirm("Saqlangan dashboard o‘chirilsinmi? (Ma’lumot fayli o‘chmaydi)")) return;
  drawBiSaved(await api().bi_delete(f));
});
$("#bi-save").addEventListener("click", async () => {
  if (!bi.cfg) return;
  bi.cfg.name = $("#bi-name").value.trim();
  const r = await api().bi_save(bi.cfg);
  $("#bi-msg").textContent = r.ok ? `Saqlandi ✓ ${r.file}` : `Xato: ${r.error}`;
  if (r.ok) drawBiSaved(r.list);
});
$("#bi-add-widget").addEventListener("click", () => bi.cfg && widgetForm());
$("#bi-clear").addEventListener("click", () => { bi.state.filters = {}; bi.state.date_from = bi.state.date_to = ""; biRefresh(); });
$("#bi-etl-toggle").addEventListener("click", () => {
  const b = $("#bi-etl-body");
  b.hidden = !b.hidden;
  if (!b.hidden && bi.cfg) drawEtl();
});
document.querySelectorAll("[data-bi-export]").forEach((b) => b.addEventListener("click", () => biExport(b.dataset.biExport)));
