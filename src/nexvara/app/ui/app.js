"use strict";

// Script errors are collected so the smoke test can fail on them.
window.__errors = [];
window.addEventListener("error", (e) => window.__errors.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => window.__errors.push(String(e.reason)));

const $ = (sel) => document.querySelector(sel);
const STATUS_LABEL = {
  pending: i18n("status.pending"), running: i18n("status.running"), succeeded: i18n("status.succeeded"),
  failed: i18n("status.failed"), cancelled: i18n("status.cancelled"), paused: i18n("status.paused"),
};
const PAGES = new Set(["home", "chat", "office", "library", "history", "settings", "memory", "teach", "files", "workflows", "bi", "cad", "devices"]);

let currentTaskId = null;
let pollTimer = null;

function api() {
  return window.pywebview && window.pywebview.api;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

// ---- navigation ----
function show(page) {
  document.body.classList.toggle("cad-mode", page === "cad");
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  if (PAGES.has(page)) {
    $(`#page-${page}`).classList.add("active");
  } else {
    const btn = document.querySelector(`.nav-item[data-page="${page}"]`);
    $("#placeholder-title").textContent = btn.textContent;
    $("#placeholder-text").textContent = `Bu bo'lim ${btn.dataset.milestone || "keyingi"} bosqichida qo'shiladi.`;
    $("#page-placeholder").classList.add("active");
  }
  if (page === "home") renderAiMoney();
  if (page === "history") renderHistory();
  if (page === "library") renderLibrary();
  if (page === "settings") renderSettings();
  if (page === "memory") renderMemory();
  if (page === "teach") renderTeach();
  if (page === "files") renderFiles();
  if (page === "workflows") renderWorkflows();
  if (page === "bi") renderBi();
  if (page === "devices") renderDevices();
  if (page === "cad") renderCad();
}

$("#nav").addEventListener("click", (e) => {
  const b = e.target.closest(".nav-item");
  if (b) show(b.dataset.page);
});
document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => show(b.dataset.goto)));

// ---- theme ----
function setTheme(t, save = true) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("nexvara-theme", t); } catch (_) { /* storage unavailable */ }
  if (save && api()) api().save_settings({ theme: t });
}
try { const t = localStorage.getItem("nexvara-theme"); if (t) setTheme(t); } catch (_) { /* ignore */ }
document.querySelectorAll("[data-theme-set]").forEach((b) => b.addEventListener("click", () => setTheme(b.dataset.themeSet)));

// ---- chat ----
function addMsg(text, me) {
  const m = el("div", me ? "msg me" : "msg", text);
  $("#chat-log").appendChild(m);
  m.scrollIntoView({ block: "end" });
}
$("#chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("#chat-text").value.trim();
  if (!text || !api()) return;
  $("#chat-text").value = "";
  addMsg(text, true);
  handleReply(await api().chat(text));
  showContext(await api().get_context_file());
});

function handleReply(r) {
  if (r.reply) addMsg(r.reply, false);
  if (r.confirm) addConfirm(r.confirm);
  if (r.task) track(r.task, true);
  if (r.open_bi) biOpenSource(r.open_bi);
  if (r.theme) setTheme(r.theme, false);
  if (r.bi_ui) biFromChat(r.bi_ui);
  if (r.dxf) addCadOpen(r.dxf);
  if (window.mediaOnReply) window.mediaOnReply(r);  // 🖼️ a made picture, 🔊 speaking
}

// A paid AI request waits for the user's answer; nothing is sent before "Ha".
function addConfirm(token) {
  const box = el("div", "row confirm-row");
  const yes = el("button", "btn primary", "Ha, davom et");
  const no = el("button", "btn", "Yo‘q");
  const answer = async (ok) => {
    yes.disabled = no.disabled = true;
    handleReply(await api().confirm_ai(token, ok));
    refreshAiStatus();
  };
  yes.addEventListener("click", () => answer(true));
  no.addEventListener("click", () => answer(false));
  box.append(yes, no);
  $("#chat-log").appendChild(box);
  box.scrollIntoView({ block: "end" });
}

function showContext(path) {
  $("#chat-context").hidden = !path;
  $("#chat-file").textContent = path || "";
}

$("#chat-attach").addEventListener("click", async () => {
  if (!api()) return;
  const r = await api().pick_file();
  if (r.path) {
    showContext(r.path);
    addMsg(`Fayl tanlandi: ${r.path}\nEndi buyruq yozing, masalan: «shu faylni formatla va saqla».`, false);
  }
});

function summary(t) {
  if (t.status === "succeeded") {
    const r = t.result || {};
    const lines = [`Tayyor ✓ ${t.title}`];
    (r.report || []).forEach((x) => lines.push(`• ${x}`));
    if (r.path) lines.push(`Natija: ${r.path}`);
    if (r.pdf) lines.push(`PDF: ${r.pdf}`);
    if (r.excerpt) lines.push(`Asl sahifalar: ${r.excerpt}`);
    const checks = r.checks || [];
    if (checks.length) lines.push(`Tekshiruv: ${checks.filter((c) => c.ok).length}/${checks.length}`);
    if (r.note) lines.push(r.note);
    return lines.join("\n");
  }
  if (t.status === "cancelled") return `Bekor qilindi: ${t.title}`;
  return `Bajarilmadi: ${t.title}\n${t.error}`;
}

// ---- tasks ----
function renderTask(t) {
  $("#task-empty").hidden = true;
  $("#task-box").hidden = false;
  $("#task-title").textContent = t.title;
  const badge = $("#task-status");
  badge.textContent = STATUS_LABEL[t.status] || t.status;
  badge.className = `badge ${t.status}`;

  const ol = $("#task-steps");
  ol.replaceChildren(...t.steps.map((s) => {
    const li = el("li", s.status);
    li.appendChild(el("span", "dot"));
    const body = el("div");
    body.appendChild(el("div", "", s.name));
    if (s.detail) body.appendChild(el("div", "detail", s.detail));
    li.appendChild(body);
    return li;
  }));

  $("#task-error").hidden = !t.error;
  $("#task-error").textContent = t.error;

  const res = $("#task-result");
  res.replaceChildren();
  if (t.result && t.result.checks) {
    t.result.checks.forEach((c) => res.appendChild(el("div", `check ${c.ok ? "ok" : "bad"}`, c.name)));
  }
  if (t.result && t.result.path) {
    const row = el("div", "row wrap");
    const b = el("button", "btn", "Faylni ko'rsatish");
    b.addEventListener("click", () => api().reveal_file(t.result.path));
    row.appendChild(b);
    if (t.result.sheet) {
      const sh = el("button", "btn", "Javob varaqasi (PDF)");
      sh.addEventListener("click", () => api().reveal_file(t.result.sheet));
      row.appendChild(sh);
    }
    if (t.result.excerpt) {
      const ex = el("button", "btn", "Asl sahifalar (PDF)");
      ex.addEventListener("click", () => api().reveal_file(t.result.excerpt));
      row.appendChild(ex);
    }
    if (t.result.book_path) {
      const bk = el("button", "btn", `Kitobda ochish (${t.result.start_page}-bet)`);
      bk.addEventListener("click", () => api().open_book_page(t.result.book_path, t.result.start_page));
      row.appendChild(bk);
    }
    res.appendChild(row);
  }
  res.hidden = !res.childElementCount;

  const running = t.status === "running" || t.status === "pending" || t.status === "paused";
  $("#task-cancel").disabled = !running || t.cancel_requested;
  // Pause stops at the next step (never inside an Office call); paused time is not a timeout.
  const pause = $("#task-pause");
  pause.disabled = !running || t.cancel_requested;
  pause.textContent = t.pause_requested ? i18n("task.resume") : i18n("task.pause");
  pause.dataset.paused = t.pause_requested ? "1" : "";
  document.querySelectorAll(".run-task").forEach((b) => { b.disabled = running; });
}

async function poll() {
  if (!currentTaskId) return;
  const t = await api().get_task(currentTaskId);
  if (!t) return;
  renderTask(t);
  if (["succeeded", "failed", "cancelled"].includes(t.status)) {
    clearInterval(pollTimer);
    pollTimer = null;
    refreshCount();
    if (chatTasks.has(t.id)) { chatTasks.delete(t.id); addMsg(summary(t), false); }
    if (t.status === "succeeded" && t.result && t.result.dxf) addCadOpen(t.result.dxf);
    if ($("#page-library").classList.contains("active")) renderLibrary();
  }
}

const chatTasks = new Set();

function track(t, fromChat) {
  if (fromChat) chatTasks.add(t.id);
  document.body.classList.add("show-panel");  // narrow windows: reveal the task panel
  currentTaskId = t.id;
  renderTask(t);
  refreshCount();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(poll, 300);
}

document.querySelectorAll(".run-task").forEach((btn) => btn.addEventListener("click", async () => {
  if (!api()) return;
  if (!btn.dataset.api) return;
  track(await api()[btn.dataset.api]());
}));

$("#task-pause").addEventListener("click", async () => {
  if (!currentTaskId) return;
  if ($("#task-pause").dataset.paused) await api().resume_task(currentTaskId);
  else await api().pause_task(currentTaskId);
  poll();
});

// The phone is looking at this screen: say so (it is turned off in settings.json if unwanted).
function showPhoneBadge(text) {
  let b = document.getElementById("phone-badge");
  if (!b) {
    b = el("div", "phone-badge", "");
    b.id = "phone-badge";
    b.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:50;padding:8px 14px;border-radius:12px;" +
      "background:#6366F1;color:#fff;font-weight:600;box-shadow:0 6px 20px rgba(0,0,0,.25)";
    document.body.appendChild(b);
  }
  b.textContent = text || i18n("phone.screen");
  b.hidden = false;
  clearTimeout(showPhoneBadge.t);
  showPhoneBadge.t = setTimeout(() => { b.hidden = true; }, 35000);
}

// Commands sent from the phone show up here too: the message, its task, the dashboard.
async function phoneEvents() {
  if (!api() || !api().ui_events) return;
  let events = [];
  try { events = await api().ui_events(); } catch (_) { return; }
  for (const ev of events) {
    if (ev.kind === "phone_chat") {
      addMsg(i18n("phone.prefix") + ev.text, true);
      handleReply(ev.reply || {});
    } else if (ev.kind === "nexvara_reply" && ev.reply) {
      handleReply(ev.reply);  // e.g. the AI fixed a failed command and tried again
    } else if (ev.kind === "phone_file") {
      addMsg(i18n("phone.file") + ev.name, false);
      showContext(ev.path);
    } else if (ev.kind === "task" && ev.task) {
      track(ev.task, false);
    } else if (ev.kind === "phone_screen") {
      showPhoneBadge();
    } else if (ev.kind === "phone_control") {
      showPhoneBadge(i18n("phone.control"));
    } else if (ev.kind === "cad_open" && ev.path) {
      if (cadConfirmDirty()) { show("cad"); cadLoad(await api().cad_open(ev.path)); }
    } else if (ev.kind === "bi_open" && ev.file) {
      biFromChat({ open: ev.file, state: ev.state && Object.keys(ev.state).length ? ev.state : null });
    }
  }
}

$("#task-cancel").addEventListener("click", async () => {
  if (currentTaskId) await api().cancel_task(currentTaskId);
  poll();
});

async function renderHistory() {
  const list = $("#history-list");
  if (!api()) return;
  const tasks = await api().list_tasks();
  if (!tasks.length) {
    list.replaceChildren(el("p", "muted", "Hali vazifa bajarilmagan."));
    return;
  }
  list.replaceChildren(...tasks.map((t) => {
    const c = el("div", "card");
    const left = el("div");
    left.appendChild(el("div", "", t.title));
    left.appendChild(el("div", "muted", new Date(t.created_at * 1000).toLocaleString()));
    c.appendChild(left);
    c.appendChild(el("span", `badge ${t.status}`, STATUS_LABEL[t.status] || t.status));
    return c;
  }));
}

async function refreshCount() {
  const tasks = await api().list_tasks();
  $("#task-count").textContent = tasks.length;
}

// ---- textbook library ----
let catalog = {};

function option(value, label) {
  const o = el("option", "", label);
  o.value = value;
  return o;
}

function fillSubjects() {
  const grade = $("#t-grade").value;
  const subjects = grade ? (catalog[grade] || []) : [...new Set(Object.values(catalog).flat())].sort();
  $("#t-subject").replaceChildren(option("", "— fan —"), ...subjects.map((s) => option(s, s)));
}

function srcError(msg) {
  $("#src-error").textContent = msg || "";
  $("#src-error").hidden = !msg;
}

async function renderSources() {
  const st = await api().sources_status();
  $("#src-edu").textContent = st.eduportal ? `${st.eduportal} ta fayl yuklangan` : "hali yuklanmagan";
  const tg = st.telegram;
  $("#tg-setup").hidden = tg.configured;
  $("#tg-login").hidden = !tg.configured || tg.authorized;
  $("#src-tg-btn").hidden = !tg.authorized;
  $("#src-tg").textContent = !tg.configured ? "sozlanmagan (pastdagi 1-qadam)"
    : !tg.authorized ? "Telegram'ga kirish kerak (2-qadam)"
    : `ulangan · ${st.rtm} ta yangi darslik yuklangan`;
}

$("#src-edu-btn").addEventListener("click", async () => { if (api()) track(await api().download_eduportal()); });
$("#src-tg-btn").addEventListener("click", async () => { if (api()) track(await api().tg_download()); });
$("#tg-save").addEventListener("click", async () => {
  const r = await api().tg_save_api($("#tg-id").value, $("#tg-hash").value);
  srcError(r.ok ? "" : r.error);
  renderSources();
});
$("#tg-send").addEventListener("click", async () => {
  const r = await api().tg_send_code($("#tg-phone").value);
  srcError(r.ok ? "" : r.error);
  if (r.ok) $("#src-tg").textContent = "Kod yuborildi — Telegram ilovangizni tekshiring";
});
$("#tg-signin").addEventListener("click", async () => {
  const r = await api().tg_sign_in($("#tg-code").value, $("#tg-pass").value);
  srcError(r.ok ? "" : r.error);
  renderSources();
});

async function renderLibrary() {
  if (!api()) return;
  renderSources();
  const info = await api().library_info();
  $("#lib-folder").textContent = info.folder;
  catalog = info.catalog;
  const grades = Object.keys(catalog).map(Number).sort((a, b) => a - b);
  const keepGrade = $("#t-grade").value;
  $("#t-grade").replaceChildren(option("", "— sinf —"), ...grades.map((g) => option(String(g), `${g}-sinf`)));
  if (grades.map(String).includes(keepGrade)) $("#t-grade").value = keepGrade;
  fillSubjects();

  $("#lib-empty").hidden = info.books.length > 0;
  $("#test-form").hidden = info.books.length === 0;
  $("#lib-count").textContent = `${info.books.length} ta darslik`;
  $("#lib-books").replaceChildren(...info.books.map((b) => {
    const tr = el("tr");
    [b.grade ? `${b.grade}` : "?", b.subject || "aniqlanmadi", b.year || "", b.pages, b.file]
      .forEach((v) => tr.appendChild(el("td", "", String(v))));
    return tr;
  }));
  $("#lib-problems").replaceChildren(...info.problems.map((p) => el("li", "", `${p.file}: ${p.note}`)));
  $("#lib-problems-box").hidden = info.problems.length === 0;
}

$("#t-grade").addEventListener("change", fillSubjects);
$("#lib-open").addEventListener("click", () => api() && api().open_library_folder());
$("#lib-index").addEventListener("click", async () => { if (api()) track(await api().index_library()); });
$("#t-topic-show").addEventListener("click", async () => {
  if (!api()) return;
  const r = await api().show_topic({
    grade: $("#t-grade").value, subject: $("#t-subject").value, topic: $("#t-topic").value,
  });
  if (!r.id) { $("#t-error").textContent = r.error; $("#t-error").hidden = false; return; }
  $("#t-error").hidden = true;
  track(r);
});

$("#test-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!api()) return;
  const r = await api().make_test({
    grade: $("#t-grade").value, subject: $("#t-subject").value, topic: $("#t-topic").value,
    count: $("#t-count").value, variants: $("#t-variants").value, ai: $("#t-ai").checked,
  });
  if (r.confirm) {
    const ok = confirm(r.confirm.text);
    const r2 = await api().confirm_ai(r.confirm.token, ok);
    if (r2.task) { $("#t-error").hidden = true; track(r2.task); }
    else if (ok) { $("#t-error").textContent = r2.reply; $("#t-error").hidden = false; }
    return;
  }
  if (!r.id) { $("#t-error").textContent = r.error; $("#t-error").hidden = false; return; }
  $("#t-error").hidden = true;
  track(r);
});

$("#panel-close").addEventListener("click", () => document.body.classList.remove("show-panel"));

// ---- Bosh sahifa: AI balans va xarajatlar ----
const usd = (v) => `$${Number(v || 0).toFixed(2)}`;
const usd4 = (v) => `$${Number(v || 0).toFixed(4)}`;

function balanceText(p) {
  if (!p.balance_api) return i18n("ai.no_balance_api");
  const b = p.balance;
  if (!b) return p.has_key ? "«Balansni yangilash»ni bosing" : "Kalit kiritilmagan";
  if (b.error) return `Xatolik yuz berdi: ${b.error}`;
  const parts = (b.balances || []).map((x) => `${x.total.toFixed(2)} ${x.currency}` +
    (x.granted ? ` (berilgan: ${x.granted.toFixed(2)})` : ""));
  return (parts.join(" · ") || "—") + (b.available ? "" : " · API uchun yetarli emas");
}

function limitBar(spent, limit) {
  const bar = el("div", "ai-bar");
  const share = limit > 0 ? Math.min(1, spent / limit) : 0;
  if (share >= 1) bar.classList.add("over"); else if (share >= 0.8) bar.classList.add("warn");
  const fill = document.createElement("i");
  fill.style.width = `${Math.round(share * 100)}%`;
  bar.appendChild(fill);
  return bar;
}

function aiRow(label, value) {
  const r = el("div", "ai-row");
  r.append(el("span", "", label), el("span", "", value));
  return r;
}

function drawSpendChart(series) {
  const box = $("#ai-money-chart");
  const W = 600, H = 140, pad = 18;
  const max = Math.max(0.01, ...series.map((d) => d.total));
  const bw = (W - pad * 2) / series.length;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="So‘nggi 30 kunlik taxminiy sarf">`;
  s += `<line class="axis" x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}"/>`;
  series.forEach((d, i) => {
    const h = (d.total / max) * (H - pad * 2);
    const x = pad + i * bw + 1;
    s += `<rect class="bar" x="${x.toFixed(1)}" y="${(H - pad - h).toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${h.toFixed(1)}" rx="2"><title>${esc(d.day)}: ${esc(usd4(d.total))}</title></rect>`;
  });
  s += `<text x="${pad}" y="12">${esc(usd(max))}</text><text x="${W - pad}" y="${H - 4}" text-anchor="end">${esc(series.at(-1)?.day || "")}</text></svg>`;
  box.innerHTML = s; // only numbers and dates we computed ourselves, escaped
}

async function renderAiMoney() {
  if (!api()) return;
  const d = await api().ai_dashboard();
  const warn = $("#ai-money-warn");
  warn.hidden = !d.warnings.length;
  warn.className = d.blocked ? "ai-warn over" : "ai-warn";
  warn.textContent = d.warnings.join(" ");
  const totals = $("#ai-money-totals");
  totals.textContent = "";
  [["Bugun (taxminiy)", usd4(d.spent_today)], ["Shu oy (taxminiy)", usd4(d.spent_month)],
    [i18n("ai.daily_limit"), usd(d.daily_budget_usd)], [i18n("ai.monthly_limit"), usd(d.monthly_budget_usd)],
    [i18n("ai.task_limit"), d.task_limit_usd == null ? "—" : usd(d.task_limit_usd)]].forEach(([k, v]) => {
    const c = el("div", "ai-total"); c.append(el("span", "muted small", k), el("b", "", v)); totals.appendChild(c);
  });
  const cards = $("#ai-money-cards");
  cards.textContent = "";
  Object.entries(d.providers).forEach(([name, p]) => {
    const c = el("div", "ai-card");
    const h = el("h3", "", p.label);
    h.appendChild(el("span", p.has_key ? "badge succeeded" : "badge", p.has_key ? i18n("ai.connected") : i18n("ai.not_connected")));
    c.append(h,
      aiRow("Bugun sarflangan", usd4(p.spent_today)), limitBar(p.spent_today, p.daily_limit),
      aiRow("Shu oy sarflangan", usd4(p.spent_month)), limitBar(p.spent_month, p.monthly_limit),
      aiRow(i18n("ai.daily_limit"), usd(p.daily_limit)), aiRow(i18n("ai.monthly_limit"), usd(p.monthly_limit)),
      aiRow(`${i18n("ai.left")} (oy)`, usd(p.left_month)));
    // Real money on the provider's account — not the same as "left of your own limit".
    c.appendChild(el("div", "ai-balance", p.balance_api
      ? `${i18n("ai.real_balance")}: ${balanceText(p)}`
      : `${i18n("ai.no_balance_api")} — «${i18n("ai.pay")}» sahifasida ko‘ring.`));
    const row = el("div", "row wrap");
    const pay = el("button", "btn small-btn", i18n("ai.pay"));
    pay.type = "button";
    pay.addEventListener("click", () => api().open_url(p.billing_url));
    row.appendChild(pay);
    if (p.balance_api && p.has_key) {
      const rb = el("button", "btn small-btn", i18n("ai.refresh_balance"));
      rb.type = "button";
      rb.addEventListener("click", async () => { rb.disabled = true; await api().ai_balance(name); renderAiMoney(); });
      row.appendChild(rb);
    }
    c.appendChild(row);
    cards.appendChild(c);
  });
  const split = $("#ai-money-split");
  split.textContent = "";
  d.split.forEach((x) => {
    const r = el("div", "ai-split-row");
    r.append(el("span", "", x.label), limitBar(x.share, 1), el("span", "", usd4(x.spent_month)));
    split.appendChild(r);
  });
  drawSpendChart(d.series);
  const tb = $("#ai-money-history");
  tb.textContent = "";
  if (!d.history.length) {
    const tr = el("tr"); tr.appendChild(el("td", "muted", "Hali pullik AI so‘rovi bo‘lmagan.")); tb.appendChild(tr);
    return;
  }
  const head = el("tr");
  ["Vaqt", i18n("ai.provider"), "Model", "Ish", "Token", "Narx (taxminiy)"].forEach((x) => head.appendChild(el("th", "", x)));
  tb.appendChild(head);
  d.history.forEach((u) => {
    const tr = el("tr");
    [new Date(u.ts * 1000).toLocaleString(), (d.providers[u.provider] || {}).label || u.provider, u.model,
      u.purpose, `${u.input_tokens}+${u.output_tokens}`, usd4(u.cost)].forEach((v) => tr.appendChild(el("td", "", v)));
    tb.appendChild(tr);
  });
}
$("#ai-money-refresh").addEventListener("click", () => renderAiMoney());

// ---- settings ----
let settings = null;

async function renderSettings() {
  if (!api()) return;
  settings = await api().get_settings();
  $("#s-count").value = settings.test_count;
  $("#s-variants").value = settings.test_variants;
  $("#s-keep-open").checked = settings.keep_office_open;
  const info = await api().get_info();
  $("#s-data").textContent = info.data_dir || "";
  renderAi();
  renderAccount();
  renderUpdate();
  renderSync();
}

// ---- sync between devices ----
async function renderSync(status) {
  if (!api()) return;
  const st = status || await api().sync_status();
  if (document.activeElement !== $("#sync-folder")) $("#sync-folder").value = st.folder || "";
  $("#sync-drive").checked = !!st.google_drive;
  $("#sync-chat").checked = !!st.chat;
  $("#sync-pass").placeholder = st.has_passphrase ? "saqlangan ✓ (almashtirish uchun yozing)" : "parol kiriting";
  const last = st.last ? new Date(st.last * 1000).toLocaleString() : "hali yo‘q";
  if (!$("#sync-msg").dataset.keep) $("#sync-msg").textContent = `Oxirgi sinxron: ${last}`;
}

$("#sync-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = $("#sync-error");
  const pw = $("#sync-pass").value;
  if (pw) {
    const r = await api().sync_set_passphrase(pw);
    $("#sync-pass").value = "";
    if (!r.ok) { err.hidden = false; err.textContent = r.error; return; }
  }
  const r = await api().save_settings({ sync: { folder: $("#sync-folder").value.trim(), google_drive: $("#sync-drive").checked,
                                           chat: $("#sync-chat").checked } });
  err.hidden = r.ok; err.textContent = r.ok ? "" : r.error;
  renderSync();
});
$("#sync-now").addEventListener("click", async () => {
  $("#sync-msg").textContent = "Sinxronlanmoqda…";
  const r = await api().sync_now();
  $("#sync-error").hidden = r.ok; $("#sync-error").textContent = r.ok ? "" : r.error;
  $("#sync-msg").dataset.keep = r.ok ? "1" : "";
  $("#sync-msg").textContent = r.ok ? r.summary : "";
  if (r.ok) renderSync(r);
});

// ---- version and updates ----
async function renderUpdate(status) {
  if (!api()) return;
  const st = status || await api().update_status();
  $("#upd-info").textContent = `O‘rnatilgan versiya: ${st.current}` +
    (st.kept.length ? ` · orqaga qaytarish uchun saqlangan: ${st.kept.join(", ")}` : "");
  if (document.activeElement !== $("#upd-channel")) $("#upd-channel").value = st.channel || "";
  const msg = $("#upd-msg"), err = $("#upd-error");
  err.hidden = !st.error; err.textContent = st.error || "";
  const ls = st.last_start || {};
  if (ls.state === "updated") msg.textContent = `Yangilandi: ${ls.from} → ${ls.to} ✓`;
  else if (ls.state === "failed") {
    msg.textContent = `${ls.to} versiyaga yangilash tugamadi, hozir ${ls.running} ishlayapti.`;
  } else msg.textContent = "";
  const c = st.check;
  if (c) msg.textContent = c.available ? `Yangi versiya bor: ${c.version}. ${c.notes || ""}` : "Eng so‘nggi versiya o‘rnatilgan ✓";
  $("#upd-install").hidden = !(c && c.available);
}

$("#upd-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api().save_settings({ update: { channel: $("#upd-channel").value.trim() } });
  $("#upd-error").hidden = r.ok; $("#upd-error").textContent = r.ok ? "" : r.error;
  if (r.ok) renderUpdate();
});
$("#upd-check").addEventListener("click", async () => {
  $("#upd-msg").textContent = "Tekshirilmoqda…";
  renderUpdate(await api().update_check());
});
$("#upd-install").addEventListener("click", async () => {
  if (!confirm("Yangilanish o‘rnatilsinmi? NEXVARA yopiladi va o‘zi qayta ochiladi. Ma’lumotlaringiz saqlanadi.")) return;
  $("#upd-msg").textContent = "Yuklanmoqda va tekshirilmoqda…";
  const r = await api().update_install();
  if (r.ok) $("#upd-msg").textContent = `${r.installing} o‘rnatilmoqda, NEXVARA hozir yopiladi…`;
  else renderUpdate(r);
});

// Start-up notice: a signed newer version is on the channel (nothing is downloaded yet).
async function checkUpdateBanner() {
  let r;
  try { r = await api().update_auto(); } catch (e) { return; }
  const ls = r.last_start || {};
  const box = $("#update-banner"), text = $("#update-banner-text");
  if (ls.state === "updated") {
    text.textContent = `NEXVARA yangilandi: ${ls.from} → ${ls.to} ✓ Ma’lumotlaringiz joyida.`;
    $("#update-banner-go").hidden = true; box.hidden = false;
  } else if (ls.state === "failed") {
    text.textContent = `${ls.to} versiyaga yangilash tugamadi — ${ls.running} ishlayapti. ` +
      "Sozlamalar → Yangilanish bo‘limida qayta urinish yoki orqaga qaytarish mumkin.";
    $("#update-banner-go").hidden = true; box.hidden = false;
  } else if (r.available) {
    text.textContent = `Yangi versiya bor: ${r.version}. ${r.notes || ""}`;
    $("#update-banner-go").hidden = false; box.hidden = false;
  }
}
$("#update-banner-later").addEventListener("click", () => { $("#update-banner").hidden = true; });
$("#update-banner-go").addEventListener("click", async () => {
  if (!confirm("Yangilanish o‘rnatilsinmi? NEXVARA yopiladi va o‘zi qayta ochiladi. Ma’lumotlaringiz saqlanadi.")) return;
  $("#update-banner-go").disabled = true;
  $("#update-banner-text").textContent = "Yuklanmoqda va imzosi tekshirilmoqda…";
  const r = await api().update_install();
  $("#update-banner-text").textContent = r.ok ? `${r.installing} o‘rnatilmoqda, NEXVARA hozir yopiladi…`
    : `Xatolik yuz berdi: ${r.error}`;
  $("#update-banner-go").disabled = r.ok;
});

// ---- Google account ----
let accountTimer = null;

async function renderAccount(status) {
  if (!api()) return;
  const st = status || await api().account_status();
  const info = $("#account-info"), err = $("#account-error");
  const login = $("#account-login"), logout = $("#account-logout");
  err.hidden = true;
  const ask = $("#account-owner-ask");
  ask.hidden = !st.pending_owner;
  if (st.pending_owner) {
    $("#account-owner-text").textContent = `Kirildi: ${st.pending_owner.name || ""} ${st.pending_owner.email}. ` +
      "NEXVARA faqat shu hisob bilan ishlasinmi? (Boshqa hisoblar rad etiladi.)";
  }
  if (st.signed_in) {
    const ses = st.session === "offline" ? " · internet yo‘q, sessiya keyin tekshiriladi" : "";
    info.textContent = `Kirilgan: ${st.profile.name || ""} ${st.profile.email} · egasi ✓${ses}`;
  } else if (st.pending_owner) {
    info.textContent = "Bu hisob sizniki ekanini tasdiqlang:";
  } else if (!st.configured) {
    info.textContent = `Hozircha mavjud emas (BLOCKED): ${st.blocked}`;
  } else if (st.login.state === "waiting") {
    info.textContent = "Brauzerda Google hisobingizni tanlang…";
  } else {
    info.textContent = `Sozlangan (${st.client_id || ""}), kirilmagan`;
  }
  if (st.login.state === "error") { err.hidden = false; err.textContent = st.login.error; }
  login.hidden = st.signed_in;
  login.disabled = !st.configured || st.login.state === "waiting";
  logout.hidden = !st.signed_in;
  login.hidden = st.signed_in || !!st.pending_owner;
  $("#account-forget-owner").hidden = st.signed_in || !st.owner_set;
  clearTimeout(accountTimer);
  if (st.login.state === "waiting") accountTimer = setTimeout(() => renderAccount(), 1500);
}

$("#account-owner-yes").addEventListener("click", async () => renderAccount(await api().account_confirm_owner(true)));
$("#account-owner-no").addEventListener("click", async () => renderAccount(await api().account_confirm_owner(false)));
$("#account-forget-owner").addEventListener("click", async () => {
  if (!confirm("NEXVARA egasi bo‘lgan Google hisobi unutilsinmi? Keyingi kirgan hisobni yana tasdiqlaysiz.")) return;
  renderAccount(await api().account_forget_owner());
});
$("#account-import").addEventListener("click", async () => {
  const r = await api().account_import_client();
  renderAccount(r);
  if (!r.ok && r.error !== "Fayl tanlanmadi") { $("#account-error").hidden = false; $("#account-error").textContent = r.error; }
});
$("#account-login").addEventListener("click", async () => {
  const r = await api().account_login();
  if (!r.ok) { $("#account-error").hidden = false; $("#account-error").textContent = r.error; return; }
  renderAccount(r);
});
$("#account-logout").addEventListener("click", async () => {
  if (!confirm("Google hisobidan chiqilsinmi?")) return;
  renderAccount(await api().account_logout());
});

// ---- AI keys, budget, spending ----
const money = (v) => `$${Number(v || 0).toFixed(3)}`;

async function renderAi(status) {
  if (!api()) return;
  const st = status || await api().ai_status();
  const box = $("#ai-providers");
  box.textContent = "";
  Object.entries(st.providers).forEach(([name, p]) => {
    const row = el("div", "ai-prov");
    const head = el("div", "ai-prov-head");
    head.append(el("strong", "", p.label),
      el("span", p.has_key ? "badge succeeded" : "badge", p.has_key ? `${i18n("ai.connected")} · ${p.key_masked}` : i18n("ai.not_connected")));
    const checked = p.checked ? ` · tekshirilgan: ${new Date(p.checked.at * 1000).toLocaleDateString()}` : " · hali tekshirilmagan";
    const models = el("div", "muted small",
      Object.entries(p.models).map(([tier, m]) => `${st.tier_labels[tier]}: ${m || "bu hisobda mavjud emas"}`).join(" · ") + checked);
    const notes = el("div", "muted small", `${p.free_tier} ${p.subscription_note}`);
    const form = el("div", "row wrap");
    const input = el("input", "ai-key");
    input.type = "password"; input.placeholder = p.has_key ? "Yangi kalit (almashtirish uchun)" : p.key_hint;
    input.autocomplete = "off";
    const save = el("button", "btn primary", i18n("ai.check_save"));
    const paste = el("button", "btn primary", i18n("ai.from_clipboard"));
    paste.type = "button";
    paste.title = "Saytda nusxalangan kalit ekranga chiqmasdan saqlanadi, bufer tozalanadi";
    paste.addEventListener("click", async () => {
      paste.disabled = true; msg.textContent = "Tekshirilmoqda (bepul so‘rov)…";
      const r = await api().ai_save_key_from_clipboard(name);
      paste.disabled = false;
      if (!r.ok) { msg.textContent = `Xatolik yuz berdi: ${r.error}`; return; }
      msg.textContent = `Saqlandi ✓ Bufer tozalandi. Modellar: ${Object.values(r.models).join(", ")}` +
        (r.missing.length ? ` (bu hisobda mavjud bo‘lmagan darajalar: ${r.missing.join(", ")})` : "");
      renderAi(r.status); refreshAiStatus();
    });
    const get = el("button", "btn", `${i18n("ai.get_key")} ↗`);
    const pay = el("button", "btn", `${i18n("ai.pay")} ↗`);
    const usage = el("button", "btn", `${i18n("ai.usage_site")} ↗`);
    const msg = el("div", "muted small", "");
    save.type = get.type = pay.type = usage.type = "button";
    pay.addEventListener("click", () => api().open_url(p.billing_url));
    usage.addEventListener("click", () => api().open_url(p.usage_url));
    save.addEventListener("click", async () => {
      if (!input.value.trim()) return;
      save.disabled = true; msg.textContent = "Tekshirilmoqda (bepul so‘rov)…";
      const r = await api().ai_save_key(name, input.value);
      input.value = ""; save.disabled = false;
      if (!r.ok) { msg.textContent = `Xatolik yuz berdi: ${r.error}`; return; }
      msg.textContent = `Saqlandi ✓ Modellar: ${Object.values(r.models).join(", ")}` +
        (r.missing.length ? ` (bu hisobda mavjud bo‘lmagan darajalar: ${r.missing.join(", ")})` : "");
      renderAi(r.status); refreshAiStatus();
    });
    get.addEventListener("click", () => api().open_url(p.key_url));
    form.append(get, paste, input, save, pay, usage);
    if (p.has_key) {
      const del = el("button", "btn", "O‘chirish");
      del.type = "button";
      del.addEventListener("click", async () => {
        if (!confirm(`${p.label} kaliti o‘chirilsinmi?`)) return;
        renderAi(await api().ai_delete_key(name)); refreshAiStatus();
      });
      form.append(del);
    }
    const lim = el("div", "row wrap");
    const ld = el("input"); ld.type = "number"; ld.min = "0"; ld.step = "0.1";
    const lm = el("input"); lm.type = "number"; lm.min = "0"; lm.step = "0.5";
    ld.placeholder = `umumiy (${st.daily_budget_usd})`; lm.placeholder = `umumiy (${st.monthly_budget_usd})`;
    ld.value = p.own_limits.daily_usd ?? ""; lm.value = p.own_limits.monthly_usd ?? "";
    ld.title = `${p.label}: ${i18n("ai.daily_limit")}, $`; lm.title = `${p.label}: ${i18n("ai.monthly_limit")}, $`;
    const lt = el("input"); lt.type = "number"; lt.min = "0"; lt.step = "0.01";
    lt.placeholder = `umumiy (${st.task_limit_usd ?? "—"})`; lt.value = p.own_limits.task_usd ?? "";
    lt.title = `${p.label}: ${i18n("ai.task_limit")}, $`;
    const lsave = el("button", "btn small-btn", `${i18n("btn.save")} (limitlar)`); lsave.type = "button";
    lsave.addEventListener("click", async () => {
      const r = await api().ai_save_limits(name, ld.value, lm.value, lt.value);
      msg.textContent = r.ok ? i18n("msg.saved") : `Xatolik yuz berdi: ${r.error}`;
      if (r.ok) renderAi(r.status);
    });
    lim.append(el("span", "muted small", `${i18n("ai.daily_limit")}, $`), ld, el("span", "muted small", `${i18n("ai.monthly_limit")}, $`), lm,
      el("span", "muted small", `${i18n("ai.task_limit")}, $`), lt, lsave);
    const limNote = el("div", "muted small", "Bu NEXVARA’ning ichki limitlari — provayderdagi haqiqiy xarajat chegarasi emas. " +
      "Haqiqiy chegarani provayder saytida («To‘lov / Balans») ham qo‘ying.");
    row.append(head, models, notes, form, lim, limNote, msg);
    box.appendChild(row);
  });
  const sel = $("#ai-provider");
  sel.textContent = "";
  Object.entries(st.providers).filter(([, p]) => p.has_key).forEach(([name, p]) => {
    const o = el("option", "", p.label); o.value = name; sel.appendChild(o);
  });
  sel.value = st.provider;
  $("#ai-enabled").checked = st.enabled;
  $("#ai-daily").value = st.daily_budget_usd;
  $("#ai-monthly").value = st.monthly_budget_usd;
  $("#ai-confirm").value = st.confirm_over_usd;
  $("#ai-task").value = st.task_limit_usd ?? "";
  $("#ai-fallback").checked = st.fallback;
  $("#ai-free").checked = st.free_mode;
  $("#ai-free-confirmed").checked = st.free_tier_confirmed;
  $("#ai-catalog-status").textContent = Object.entries(st.catalog || {}).filter(([, c]) => c.checked_at)
    .map(([p, c]) => `${st.providers[p].label}: ${new Date(c.checked_at * 1000).toLocaleString()}${c.stale ? " (eskirgan)" : ""}${c.error ? " (internet/xizmat xatosi)" : ""}`)
    .join(" · ") || "Katalog hali tekshirilmagan";
  const gem = st.providers.gemini;
  $("#ai-free-note").textContent = !gem.has_key
    ? "Gemini kalitini kiriting va AI Studio hisobingizdagi tarifni tekshiring. Bepul kvota hisobga bog‘liq."
    : (st.free_active
      ? `Bepul rejim ishlayapti: bugun ${st.free_requests_today} ta bepul so‘rov. Google bepul darajada ` +
        "kunlik so‘rovlar sonini cheklaydi — tugasa, keyinroq qayta urinasiz (pullik provayderga o‘tilmaydi). " +
        "Eslatma: bepul darajada Google so‘rovlarni o‘z xizmatlarini yaxshilash uchun ishlatishi mumkin; " +
        "NEXVARA ism, telefon, pasport kabi shaxsiy ma’lumotlarni yuborishdan oldin yashiradi. " +
        "AI Studio’da to‘lov (Billing) yoqilmagan bo‘lsin — aks holda Google haq oladi."
      : "Free Tier tasdiqlanmagan yoki o‘chiq. Pullik so‘rovlar oldidan tasdiq so‘raladi.");
  $("#ai-send-text").checked = st.send_textbook_text;
  $("#ai-spent").textContent =
    `${i18n("ai.estimated")}: bugun ${money(st.spent_today)} / ${money(st.daily_budget_usd)}, shu oy ${money(st.spent_month)} / ${money(st.monthly_budget_usd)}. Narxlar taxminiy — provayder hisobidagi summa asosiy.` +
    (st.warnings.length ? ` ${st.warnings.join(" ")}` : "");
  const usage = await api().ai_usage();
  const t = $("#ai-usage");
  t.textContent = "";
  if (usage.length) {
    const head = el("tr");
    ["Vaqt", "Ish", "Model", "Token", "Narx (taxminiy)"].forEach((h) => head.appendChild(el("th", "", h)));
    t.appendChild(head);
    usage.forEach((u) => {
      const tr = el("tr");
      [new Date(u.ts * 1000).toLocaleString(), u.purpose, u.model,
        `${u.input_tokens}+${u.output_tokens}`, money(u.cost)].forEach((v) => tr.appendChild(el("td", "", v)));
      t.appendChild(tr);
    });
  }
}

$("#ai-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api().save_settings({ ai: {
    enabled: $("#ai-enabled").checked, provider: $("#ai-provider").value || "",
    daily_budget_usd: Number($("#ai-daily").value), monthly_budget_usd: Number($("#ai-monthly").value),
    confirm_over_usd: Number($("#ai-confirm").value), send_textbook_text: $("#ai-send-text").checked,
    task_limit_usd: $("#ai-task").value === "" ? null : Number($("#ai-task").value),
    fallback: $("#ai-fallback").checked, free_mode: $("#ai-free").checked,
    free_tier_confirmed: $("#ai-free-confirmed").checked,
  } });
  $("#ai-error").hidden = r.ok; $("#ai-error").textContent = r.ok ? "" : r.error;
  $("#ai-saved").textContent = r.ok ? "Saqlandi ✓" : "";
  if (r.ok) { renderAi(); refreshAiStatus(); }
});

$("#ai-refresh-catalog").addEventListener("click", async () => {
  const button = $("#ai-refresh-catalog"); button.disabled = true;
  $("#ai-catalog-status").textContent = "Rasmiy kataloglar tekshirilmoqda…";
  try {
    const r = await api().ai_refresh_catalog();
    await renderAi();
    $("#ai-catalog-status").textContent += " · " + Object.entries(r.result)
      .map(([p, v]) => `${p}: ${v.ok ? "yangilandi" : "oldingi katalog saqlandi"}`).join(" · ");
    if (window.mediaLoad) window.mediaLoad();
  } catch (e) { $("#ai-catalog-status").textContent = String(e); }
  finally { button.disabled = false; }
});

async function refreshAiStatus() {
  const st = await api().ai_status();
  const p = st.providers[st.provider];
  $("#ai-status").textContent = st.ready && p ? p.label : (p ? "O‘chirilgan" : "Ulanmagan");
}

$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api().save_settings({
    test_count: Number($("#s-count").value), test_variants: Number($("#s-variants").value),
    keep_office_open: $("#s-keep-open").checked,
  });
  $("#s-error").hidden = r.ok; $("#s-error").textContent = r.ok ? "" : r.error;
  $("#s-saved").textContent = r.ok ? "Saqlandi ✓" : "";
  if (r.ok) { settings = r.settings; applySettings(); }
});
$("#s-open-data").addEventListener("click", () => api() && api().open_data_folder());
$("#s-shortcut").addEventListener("click", async () => {
  const r = await api().create_shortcut();
  $("#s-msg").textContent = r.ok ? `Yorliq yaratildi: ${r.path}` : `Xato: ${r.error}`;
});
$("#s-clear-history").addEventListener("click", async () => {
  if (!confirm("Barcha vazifalar tarixi o‘chirilsinmi? Yaratilgan fayllar o‘chmaydi.")) return;
  await api().clear_history();
  $("#s-msg").textContent = "Tarix tozalandi";
});

function applySettings() {
  if (!settings) return;
  if ($("#t-count") && !$("#t-count").dataset.touched) $("#t-count").value = settings.test_count;
  if ($("#t-variants") && !$("#t-variants").dataset.touched) $("#t-variants").value = settings.test_variants;
}
["t-count", "t-variants"].forEach((id) => $("#" + id).addEventListener("input", (e) => { e.target.dataset.touched = "1"; }));

// ---- memory ----
const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString() : "");

async function renderMemory() {
  if (!api()) return;
  const facts = await api().memory_facts();
  const list = $("#mem-facts");
  list.textContent = "";
  if (!facts.length) list.appendChild(el("li", "muted", "Hozircha bo‘sh"));
  facts.forEach((f) => {
    const li = el("li", "item-row");
    li.append(el("span", "grow", f.text));
    const edit = el("button", "btn small-btn", "Tahrirlash");
    const del = el("button", "btn small-btn", "O‘chirish");
    edit.addEventListener("click", async () => {
      const t = prompt("Yangi matn:", f.text);
      if (t === null) return;
      const r = await api().memory_update_fact(f.id, t);
      if (!r.ok) alert(r.error);
      renderMemory();
    });
    del.addEventListener("click", async () => {
      if (!confirm(`O‘chirilsinmi?\n${f.text}`)) return;
      await api().memory_delete_fact(f.id);
      renderMemory();
    });
    li.append(edit, del);
    list.appendChild(li);
  });
  const chat = await api().memory_chat(300);
  const box = $("#mem-chat");
  box.textContent = "";
  if (!chat.length) box.appendChild(el("div", "muted", "Suhbatlar yo‘q"));
  chat.forEach((c) => {
    const row = el("div", c.role === "user" ? "mem-line me" : "mem-line");
    row.append(el("span", "muted small", when(c.ts) + " "), el("span", "", c.text));
    box.appendChild(row);
  });
  box.scrollTop = box.scrollHeight;
  const files = await api().recent_files();
  const t = $("#mem-files");
  t.textContent = "";
  if (!files.length) { t.appendChild(el("tr")).appendChild(el("td", "muted", "Hozircha fayl yo‘q")); }
  files.forEach((f) => {
    const tr = el("tr", "clickable");
    [f.name, f.task, when(f.ts)].forEach((v) => tr.appendChild(el("td", "", v)));
    tr.title = f.path;
    tr.addEventListener("click", () => api().reveal_file(f.path));
    t.appendChild(tr);
  });
}

$("#mem-fact-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api().memory_add_fact($("#mem-fact").value);
  if (!r.ok) { alert(r.error); return; }
  $("#mem-fact").value = "";
  renderMemory();
});
$("#mem-search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const found = await api().memory_search($("#mem-search").value);
  const ul = $("#mem-search-results");
  ul.textContent = "";
  const KIND = { fact: "Eslab qolingan", chat: "Suhbat", rule: "Qoida", task: "Vazifa" };
  if (!found.length) ul.appendChild(el("li", "muted", "Hech narsa topilmadi"));
  found.forEach((x) => {
    const li = el("li", "item-row");
    li.append(el("span", "badge", KIND[x.kind] || x.kind), el("span", "grow", x.text),
      el("span", "muted small", when(x.ts)));
    ul.appendChild(li);
  });
});
$("#mem-clear-chat").addEventListener("click", async () => {
  if (!confirm("Barcha suhbatlar tarixi o‘chirilsinmi? Eslab qolinganlar va qoidalar qoladi.")) return;
  await api().memory_clear_chat();
  renderMemory();
});
$("#mem-export").addEventListener("click", async () => {
  const r = await api().memory_export();
  $("#mem-backup-msg").textContent = r.ok ? `Saqlandi: ${r.path}` : `Xato: ${r.error}`;
});
$("#mem-import").addEventListener("click", async () => {
  const r = await api().memory_import("");
  if (!r.ok && !r.error) return;
  $("#mem-backup-msg").textContent = r.ok
    ? `Tiklandi: ${r.facts} ta eslatma, ${r.rules} ta qoida (borlari takrorlanmadi)` : `Xato: ${r.error}`;
  renderMemory();
});

// ---- Teach NEXVARA ----
async function teachCheck() {
  const r = await api().teach_preview($("#teach-app").value, $("#teach-text").value);
  $("#teach-preview").textContent = r.actions && r.actions.length ? `Har safar: ${r.actions.join("; ")}` : "";
  $("#teach-error").hidden = !r.error; $("#teach-error").textContent = r.error || "";
  return r;
}
$("#teach-check").addEventListener("click", teachCheck);
$("#teach-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api().teach_add($("#teach-app").value, $("#teach-text").value);
  if (!r.ok) { $("#teach-error").hidden = false; $("#teach-error").textContent = r.error; return; }
  $("#teach-text").value = ""; $("#teach-preview").textContent = "Saqlandi ✓"; $("#teach-error").hidden = true;
  drawRules(r.rules);
});

async function renderTeach() { if (api()) drawRules(await api().teach_rules()); }

function drawRules(rules) {
  const box = $("#teach-rules");
  box.textContent = "";
  if (!rules.length) box.appendChild(el("div", "muted", "Hali qoida yo‘q"));
  rules.forEach((r) => {
    const row = el("div", "ai-prov");
    const head = el("div", "ai-prov-head");
    const tog = el("label", "check-inline");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = r.enabled;
    cb.addEventListener("change", async () => drawRules((await api().teach_update(r.id, null, cb.checked)).rules));
    tog.append(cb, document.createTextNode(" yoqilgan"));
    head.append(el("span", "", ""), tog);
    head.firstChild.append(el("span", "badge", r.app_label), document.createTextNode(` ${r.text}`));
    const acts = el("div", r.problem ? "error" : "muted small",
      r.problem || `Har safar: ${r.actions.join("; ")} · versiya ${r.version}`);
    const btns = el("div", "row wrap");
    const edit = el("button", "btn small-btn", "Tahrirlash");
    const vers = el("button", "btn small-btn", "Versiyalar");
    const del = el("button", "btn small-btn", "O‘chirish");
    edit.addEventListener("click", async () => {
      const t = prompt("Qoidaning yangi matni:", r.text);
      if (t === null) return;
      const res = await api().teach_update(r.id, t, null);
      if (!res.ok) { alert(res.error); return; }
      drawRules(res.rules);
    });
    vers.addEventListener("click", async () => {
      const v = await api().teach_versions(r.id);
      alert(v.map((x) => `v${x.version} (${when(x.ts)}): ${x.text}`).join("\n"));
    });
    del.addEventListener("click", async () => {
      if (!confirm(`Qoida o‘chirilsinmi?\n${r.text}`)) return;
      drawRules(await api().teach_delete(r.id));
    });
    btns.append(edit, vers, del);
    row.append(head, acts, btns);
    box.appendChild(row);
  });
}

// ---- files ----
let fileRows = [];
const selected = new Set();
const fmtSize = (n) => n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;

async function renderFiles() { if (api()) drawFileLog(); }

$("#f-form").addEventListener("submit", async (e) => { e.preventDefault(); await filesSearch(); });
async function filesSearch() {
  $("#f-count").textContent = "(qidirilmoqda…)";
  const r = await api().files_search($("#f-query").value, $("#f-folder").value, $("#f-ext").value);
  $("#f-error").hidden = r.ok; $("#f-error").textContent = r.ok ? "" : r.error;
  fileRows = r.ok ? r.files : [];
  selected.clear();
  drawFiles();
}
$("#f-pick").addEventListener("click", async () => {
  const f = await api().files_pick_folder();
  if (f) { $("#f-folder").value = f; filesSearch(); }
});
$("#f-clear-folder").addEventListener("click", () => { $("#f-folder").value = ""; });

function drawFiles() {
  const t = $("#f-table");
  t.textContent = "";
  $("#f-count").textContent = fileRows.length ? `(${fileRows.length} ta, tanlangan: ${selected.size})` : "";
  if (!fileRows.length) return;
  const head = el("tr");
  const all = el("input"); all.type = "checkbox";
  all.checked = selected.size === fileRows.length;
  all.addEventListener("change", () => {
    fileRows.forEach((f) => (all.checked ? selected.add(f.path) : selected.delete(f.path)));
    drawFiles();
  });
  const th0 = el("th"); th0.appendChild(all); head.appendChild(th0);
  ["Nomi", "Papka", "Hajmi", "O‘zgargan"].forEach((h) => head.appendChild(el("th", "", h)));
  t.appendChild(head);
  fileRows.forEach((f) => {
    const tr = el("tr", "clickable");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = selected.has(f.path);
    cb.addEventListener("click", (e) => e.stopPropagation());
    cb.addEventListener("change", () => { cb.checked ? selected.add(f.path) : selected.delete(f.path); drawFiles(); });
    const td0 = el("td"); td0.appendChild(cb); tr.appendChild(td0);
    [f.name, f.folder, fmtSize(f.size), new Date(f.modified * 1000).toLocaleString()].forEach((v) => tr.appendChild(el("td", "", v)));
    tr.addEventListener("click", () => showFileInfo(f.path));
    tr.addEventListener("dblclick", () => api().open_file(f.path));
    t.appendChild(tr);
  });
}

async function showFileInfo(path) {
  const r = await api().files_info(path);
  const box = $("#f-info");
  box.hidden = false; box.textContent = "";
  if (!r.ok) { box.textContent = r.error; return; }
  const i = r.result;
  box.append(el("strong", "", i.name), el("div", "mono", [
    `Joyi: ${i.folder}`, `Hajmi: ${fmtSize(i.size)} (${i.size} bayt)`,
    `Yaratilgan: ${new Date(i.created * 1000).toLocaleString()}`,
    `O‘zgargan: ${new Date(i.modified * 1000).toLocaleString()}`,
    `SHA-256: ${i.sha256}`, i.zip_entries !== undefined ? `Arxivda: ${i.zip_entries} ta element` : "",
  ].filter(Boolean).join("\n")));
}

function chosen(min = 1) {
  const list = [...selected];
  if (list.length < min) { $("#f-msg").textContent = "Avval jadvaldan fayl(lar)ni belgilang ☑"; return null; }
  return list;
}
const fileResult = (r, okText) => {
  $("#f-msg").textContent = r.ok ? okText(r.result) : `Xato: ${r.error}`;
  drawFileLog();
  return r.ok;
};

$("#f-actions").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-fa]");
  if (!b || !api()) return;
  const act = b.dataset.fa;
  const list = chosen();
  if (!list) return;
  if (act === "open") list.slice(0, 5).forEach((p) => api().open_file(p));
  if (act === "reveal") api().reveal_file(list[0]);
  if (act === "copy" || act === "move") {
    const folder = await api().files_pick_folder();
    if (!folder) return;
    if (act === "move" && !confirm(`${list.length} ta fayl ko‘chirilsinmi?\n→ ${folder}`)) return;
    const r = await (act === "copy" ? api().files_copy(list, folder) : api().files_move(list, folder));
    if (fileResult(r, (x) => `${x.length} ta fayl ${act === "copy" ? "nusxalandi" : "ko‘chirildi"} → ${folder}`)) filesSearch();
  }
  if (act === "rename") {
    if (list.length === 1) {
      const name = prompt("Yangi nom (kengaytmasiz ham bo‘ladi):", list[0].split("\\").pop());
      if (!name) return;
      if (fileResult(await api().files_rename(list[0], name), (x) => `Yangi nom: ${x}`)) filesSearch();
    } else {
      const pattern = prompt(`${list.length} ta fayl uchun nom namunasi ({n} — tartib raqami):`, "Hujjat_{n}");
      if (!pattern) return;
      if (fileResult(await api().files_rename_batch(list, pattern), (x) => `${x.length} ta fayl qayta nomlandi`)) filesSearch();
    }
  }
  if (act === "zip") fileResult(await api().files_zip(list), (x) => `Arxiv: ${x}`);
  if (act === "unzip") {
    const zips = list.filter((p) => p.toLowerCase().endsWith(".zip"));
    if (!zips.length) { $("#f-msg").textContent = "ZIP fayl tanlang"; return; }
    fileResult(await api().files_unzip(zips[0]), (x) => `Chiqarildi: ${x}`);
  }
  if (act === "pdf") {
    const snap = await api().files_to_pdf(list);
    if (snap.id) { track(snap); $("#f-msg").textContent = "PDF'ga aylantirilmoqda — jarayon o‘ng panelda"; }
    else $("#f-msg").textContent = snap.error;
  }
  if (act === "backup") fileResult(await api().files_backup(list), (x) => `${x.length} ta zaxira nusxa olindi (D:\\NEXVARA\\Zaxira\\Fayllar)`);
  if (act === "versions") {
    const vers = await api().files_versions(list[0]);
    if (!vers.length) { $("#f-msg").textContent = "Bu faylning zaxira nusxasi yo‘q. Avval «Zaxira nusxa»ni bosing."; return; }
    const pick = prompt(vers.map((v, i) => `${i + 1}) ${new Date(v.modified * 1000).toLocaleString()} — ${fmtSize(v.size)}`).join("\n") +
      "\n\nQaysi versiyani tiklay? Raqamini yozing (hozirgi fayl ham zaxiraga olinadi):");
    const v = vers[Number(pick) - 1];
    if (!v) return;
    fileResult(await api().files_restore(v.path, list[0]), () => "Tiklandi ✓ (oldingi holati ham zaxirada)");
  }
  if (act === "recycle") {
    if (!confirm(`${list.length} ta fayl Savatga (Recycle Bin) o‘chirilsinmi?\nKerak bo‘lsa Savatdan qaytarish mumkin.`)) return;
    if (fileResult(await api().files_recycle(list), (n) => `${n} ta fayl Savatga o‘tkazildi`)) filesSearch();
  }
});

let tidyFolder = "";
$("#f-tidy-pick").addEventListener("click", async () => {
  tidyFolder = await api().files_pick_folder();
  if (!tidyFolder) return;
  $("#f-tidy-folder").textContent = tidyFolder;
  const r = await api().files_tidy_plan(tidyFolder);
  const t = $("#f-tidy-plan");
  t.textContent = "";
  $("#f-tidy-run").disabled = !(r.ok && r.result.length);
  if (!r.ok) { t.appendChild(el("tr")).appendChild(el("td", "error", r.error)); return; }
  if (!r.result.length) { t.appendChild(el("tr")).appendChild(el("td", "muted", "Tartiblanadigan fayl yo‘q")); return; }
  r.result.forEach((x) => { const tr = el("tr"); tr.append(el("td", "", x.name), el("td", "", `→ ${x.to}`)); t.appendChild(tr); });
});
$("#f-tidy-run").addEventListener("click", async () => {
  if (!confirm(`«${tidyFolder}» papkasidagi fayllar ichki papkalarga ajratilsinmi?`)) return;
  const r = await api().files_tidy(tidyFolder);
  $("#f-tidy-plan").textContent = "";
  $("#f-tidy-run").disabled = true;
  $("#f-tidy-folder").textContent = r.ok ? `Tayyor: ${Object.entries(r.result).map(([k, v]) => `${k}: ${v}`).join(", ")}` : `Xato: ${r.error}`;
  drawFileLog();
});

const OPS = { copy: "Nusxa", move: "Ko‘chirish", rename: "Nomlash", zip: "ZIP", unzip: "ZIP ochish",
  backup: "Zaxira", restore: "Tiklash", recycle: "Savatga", pdf: "PDF" };
async function drawFileLog() {
  const rows = await api().files_log();
  const t = $("#f-log");
  t.textContent = "";
  if (!rows.length) { t.appendChild(el("tr")).appendChild(el("td", "muted", "Hali amal bajarilmagan")); return; }
  rows.slice(0, 40).forEach((x) => {
    const tr = el("tr");
    const what = x.dst || (x.files ? x.files.join(", ") : x.src || "");
    tr.append(el("td", "", new Date(x.ts * 1000).toLocaleString()), el("td", "", OPS[x.action] || x.action), el("td", "", what));
    t.appendChild(tr);
  });
}

// ---- workflows ----
let wfEditing = { id: 0, steps: [] };
let wfTimer = null;
const TRIG = (w) => w.trigger.type === "folder" ? `papka: ${w.trigger.folder} (${w.trigger.ext || "barcha fayllar"})`
  : w.trigger.type === "daily" ? `har kuni ${w.trigger.time}` : "qo‘lda";
const RUN_STATUS = STATUS_LABEL;

async function renderWorkflows() {
  if (!api()) return;
  const tpl = $("#wf-template");
  if (tpl.options.length === 1) {
    (await api().wf_templates()).forEach((t, i) => { const o = el("option", "", t.name); o.value = i; tpl.appendChild(o); });
  }
  drawWorkflows(await api().wf_list());
  drawRuns();
  wfPoll();
  if (!wfEditing.steps.length) wfReset();
}

function wfPoll() {
  clearInterval(wfTimer);
  wfTimer = setInterval(async () => {
    if (!$("#page-workflows").classList.contains("active")) { clearInterval(wfTimer); return; }
    drawActive(await api().wf_active());
  }, 1200);
}

function drawActive(list) {
  $("#wf-active-card").hidden = !list.length;
  const box = $("#wf-active");
  box.textContent = "";
  list.forEach((a) => {
    const row = el("div", "item-row");
    row.append(el("span", "grow", `${a.name}${a.paused ? " — pauzada" : ""}${a.waiting_approval ? ` — tasdiq: ${a.waiting_approval}` : ""}`));
    if (a.waiting_approval) {
      const ok = el("button", "btn primary small-btn", "Tasdiqlash");
      ok.addEventListener("click", async () => { await api().wf_approve(a.run_id); });
      row.appendChild(ok);
    }
    const pause = el("button", "btn small-btn", a.paused ? "Davom ettirish" : "Pauza");
    pause.addEventListener("click", async () => { a.paused ? await api().wf_resume(a.run_id) : await api().wf_pause(a.run_id); });
    const stop = el("button", "btn small-btn danger", "To‘xtatish");
    stop.addEventListener("click", async () => { if (confirm("Ish jarayoni to‘xtatilsinmi?")) await api().cancel_task(a.task_id); });
    row.append(pause, stop);
    box.appendChild(row);
  });
}

function drawWorkflows(list) {
  const box = $("#wf-list");
  box.textContent = "";
  if (!list.length) box.appendChild(el("div", "muted", "Hali ish jarayoni yo‘q — pastda yarating yoki shablondan boshlang."));
  list.forEach((w) => {
    const row = el("div", "ai-prov");
    const head = el("div", "ai-prov-head");
    head.append(el("strong", "", w.name), el("span", "badge", TRIG(w)));
    const last = w.last_run ? `Oxirgi: ${RUN_STATUS[w.last_run.status] || w.last_run.status}, ${when(w.last_run.started)}` : "Hali bajarilmagan";
    const info = el("div", "muted small", `${w.steps.length} ta qadam · ${last}${w.enabled ? "" : " · o‘chirilgan"}`);
    const btns = el("div", "row wrap");
    const run = el("button", "btn primary small-btn", "Ishga tushirish");
    run.addEventListener("click", async () => {
      let file = "";
      if (w.trigger.type === "folder") { file = await api().wf_pick_file(); if (!file) return; }
      const r = await api().wf_run(w.id, file);
      if (!r.ok) { alert(r.error); return; }
      track(r.task);
      setTimeout(async () => drawActive(await api().wf_active()), 300);
    });
    const edit = el("button", "btn small-btn", "Tahrirlash");
    edit.addEventListener("click", () => wfLoad(w));
    const tog = el("button", "btn small-btn", w.enabled ? "O‘chirib qo‘yish" : "Yoqish");
    tog.addEventListener("click", async () => {
      const r = await api().wf_save({ ...w, enabled: !w.enabled });
      if (!r.ok) { alert(r.error); return; }
      drawWorkflows(r.workflows);
    });
    const hist = el("button", "btn small-btn", "Tarix");
    hist.addEventListener("click", () => drawRuns(w.id));
    const del = el("button", "btn small-btn danger", "O‘chirish");
    del.addEventListener("click", async () => {
      if (!confirm(`«${w.name}» o‘chirilsinmi?`)) return;
      drawWorkflows(await api().wf_delete(w.id));
    });
    btns.append(run, edit, tog, hist, del);
    row.append(head, info, btns);
    box.appendChild(row);
  });
}

async function drawRuns(wfId = 0) {
  const runs = await api().wf_runs(wfId);
  const t = $("#wf-runs");
  t.textContent = "";
  if (!runs.length) { t.appendChild(el("tr")).appendChild(el("td", "muted", "Hali bajarilmagan")); return; }
  const names = Object.fromEntries((await api().wf_list()).map((w) => [w.id, w.name]));
  runs.forEach((r) => {
    const tr = el("tr");
    const steps = r.log.map((x) => `${x.ok ? "✓" : "✗"} ${x.step}: ${x.text}`).join("\n");
    tr.append(el("td", "", when(r.started)), el("td", "", names[r.wf_id] || `#${r.wf_id}`),
      el("td", "", r.trigger), el("td", "", RUN_STATUS[r.status] || r.status), el("td", "mono", steps));
    t.appendChild(tr);
  });
}

function wfReset() {
  wfEditing = { id: 0, steps: [{ kind: "command", text: "" }], enabled: true };
  $("#wf-form-title").textContent = "Yangi ish jarayoni";
  $("#wf-name").value = ""; $("#wf-trigger").value = "manual"; $("#wf-folder").value = "";
  $("#wf-ext").value = ""; $("#wf-time").value = "08:00"; $("#wf-retries").value = 1; $("#wf-onerror").value = "stop";
  $("#wf-error").hidden = true; $("#wf-saved").textContent = "";
  drawSteps(); wfTrigger();
}

function wfLoad(w) {
  wfEditing = JSON.parse(JSON.stringify(w));
  $("#wf-form-title").textContent = w.id ? `Tahrirlash: ${w.name}` : "Yangi ish jarayoni (shablondan)";
  $("#wf-name").value = w.name;
  $("#wf-trigger").value = w.trigger.type || "manual";
  $("#wf-folder").value = w.trigger.folder || "";
  $("#wf-ext").value = w.trigger.ext || "";
  $("#wf-time").value = w.trigger.time || "08:00";
  $("#wf-retries").value = w.retries ?? 1;
  $("#wf-onerror").value = w.on_error || "stop";
  drawSteps(); wfTrigger();
  $("#wf-form").scrollIntoView({ block: "start" });
}

function drawSteps() {
  const box = $("#wf-steps");
  box.textContent = "";
  wfEditing.steps.forEach((s, i) => {
    const row = el("div", "item-row");
    const LABEL = { command: "Buyruq", approve: "Tasdiq", wait: "Kutish" };
    row.appendChild(el("span", "badge", `${i + 1}. ${LABEL[s.kind]}`));
    const inp = el("input", "grow-input");
    if (s.kind === "wait") { inp.type = "number"; inp.min = 1; inp.max = 3600; inp.value = s.seconds || 10; inp.placeholder = "soniya"; }
    else { inp.type = "text"; inp.value = s.text || ""; inp.placeholder = s.kind === "approve" ? "Savol (masalan: Davom etaymi?)" : "masalan: {fayl} ni och, jadvalni formatla, PDF qilib saqla"; }
    inp.addEventListener("input", () => { if (s.kind === "wait") s.seconds = Number(inp.value); else s.text = inp.value; });
    row.appendChild(inp);
    const up = el("button", "btn small-btn", "↑"); up.type = "button";
    up.addEventListener("click", () => { if (i) { [wfEditing.steps[i - 1], wfEditing.steps[i]] = [wfEditing.steps[i], wfEditing.steps[i - 1]]; drawSteps(); } });
    const rm = el("button", "btn small-btn", "✕"); rm.type = "button";
    rm.addEventListener("click", () => { wfEditing.steps.splice(i, 1); drawSteps(); });
    row.append(up, rm);
    box.appendChild(row);
  });
}

function wfTrigger() {
  const t = $("#wf-trigger").value;
  document.querySelectorAll("[data-trig]").forEach((x) => { x.hidden = x.dataset.trig !== t; });
}
$("#wf-trigger").addEventListener("change", wfTrigger);
document.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => {
  wfEditing.steps.push(b.dataset.add === "wait" ? { kind: "wait", seconds: 10 } : { kind: b.dataset.add, text: "" });
  drawSteps();
}));
$("#wf-folder-pick").addEventListener("click", async () => { const f = await api().files_pick_folder(); if (f) $("#wf-folder").value = f; });
$("#wf-new").addEventListener("click", wfReset);
$("#wf-template").addEventListener("change", async () => {
  const i = $("#wf-template").value;
  if (i === "") return;
  const t = (await api().wf_templates())[Number(i)];
  wfLoad({ ...t, id: 0, retries: 1, on_error: "stop", enabled: true });
  $("#wf-template").value = "";
});
$("#wf-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const t = $("#wf-trigger").value;
  const trigger = { type: t };
  if (t === "folder") { trigger.folder = $("#wf-folder").value; trigger.ext = $("#wf-ext").value; }
  if (t === "daily") trigger.time = $("#wf-time").value;
  const r = await api().wf_save({
    ...wfEditing, name: $("#wf-name").value, trigger,
    retries: Number($("#wf-retries").value), on_error: $("#wf-onerror").value,
  });
  $("#wf-error").hidden = r.ok; $("#wf-error").textContent = r.ok ? "" : r.error;
  if (!r.ok) return;
  wfEditing.id = r.id;
  $("#wf-saved").textContent = "Saqlandi ✓";
  $("#wf-form-title").textContent = `Tahrirlash: ${$("#wf-name").value}`;
  drawWorkflows(r.workflows);
});

// ---- devices ----
let devTimer = null;
async function renderDevices() {
  renderDeviceOptions();
  if (!api()) return;
  renderTailscale();
  drawDevices(await api().devices_status());
  clearInterval(devTimer);
  devTimer = setInterval(async () => {
    if (!$("#page-devices").classList.contains("active")) { clearInterval(devTimer); return; }
    drawDevices(await api().devices_status());
  }, 2000);
}

function drawDevices(st) {
  $("#dev-pc").textContent = st.pc;
  $("#dev-os").textContent = st.os;
  $("#dev-toggle").disabled = !st.available;
  $("#dev-toggle").textContent = st.running ? "O‘chirish" : "Yoqish";
  $("#dev-toggle").className = st.running ? "btn" : "btn primary";
  $("#dev-state").textContent = st.running ? `Yoqilgan: ${st.url}` : "O‘chiq";
  $("#dev-pair").hidden = !st.running;
  if (st.running) {
    $("#dev-url").textContent = st.url;
    $("#dev-fp").textContent = st.fingerprint ? `Sertifikat: ${st.fingerprint.slice(0, 16)}…${st.fingerprint.slice(-8)}` : "";
    if (st.code) {
      $("#dev-qr").innerHTML = st.qr_svg; // made by NEXVARA itself (segno), not user input
      $("#dev-code").textContent = st.code;
      $("#dev-left").textContent = `${Math.floor(st.code_left / 60)}:${String(st.code_left % 60).padStart(2, "0")} qoldi`;
    } else {
      $("#dev-qr").textContent = "";
      $("#dev-code").textContent = "——————";
      $("#dev-left").textContent = st.locked ? "Ko‘p noto‘g‘ri urinish — yangi kod oling" : "Kod ishlatildi yoki eskirdi — yangi kod oling";
    }
  }
  const box = $("#dev-list");
  box.textContent = "";
  if (!st.devices.length) box.appendChild(el("div", "muted", "Hali qurilma bog‘lanmagan"));
  st.devices.forEach((d) => {
    const row = el("div", "item-row");
    row.append(el("span", "grow", `📱 ${d.name}`),
      el("span", "muted small", d.last_seen ? `oxirgi: ${when(d.last_seen)} (${d.last_ip})` : "hali ulanmagan"));
    const rm = el("button", "btn small-btn danger", "Uzish");
    rm.addEventListener("click", async () => {
      if (!confirm(`«${d.name}» uzilsinmi? U qayta bog‘lanishi uchun yangi kod kerak bo‘ladi.`)) return;
      drawDevices(await api().devices_revoke(d.id));
    });
    row.appendChild(rm);
    box.appendChild(row);
  });
}

// Tailscale found but the firewall rule missing: offer one button (firewall.py).
async function renderTailscale() {
  if (!api().devices_tailscale) return;
  const t = await api().devices_tailscale();
  $("#dev-ts").hidden = !t.needed;
}
$("#dev-ts-allow").addEventListener("click", async () => {
  $("#dev-ts-allow").disabled = true;
  const r = await api().devices_allow_tailscale();
  $("#dev-ts-allow").disabled = false;
  $("#dev-ts").hidden = !r.needed;
  $("#dev-error").hidden = r.ok; $("#dev-error").textContent = r.ok ? "" : r.error;
});

// What a paired phone may do: see the screen, control mouse/keyboard, NEXVARA at sign-in.
async function renderDeviceOptions() {
  if (!api() || !api().devices_options) return;
  const o = await api().devices_options();
  for (const k of ["screen_view", "control", "autostart"]) {
    const box = $("#opt-" + k);
    if (box) box.checked = !!o[k];
  }
}
for (const k of ["screen_view", "control", "autostart"]) {
  const box = document.getElementById("opt-" + k);
  if (box) box.addEventListener("change", async () => {
    if (k === "control" && box.checked && !confirm("Telefon bu kompyuterning sichqonchasi va klaviaturasini boshqara oladi. Yoqilsinmi?")) {
      box.checked = false;
      return;
    }
    await api().devices_set_option(k, box.checked);
    renderDeviceOptions();
  });
}

$("#dev-toggle").addEventListener("click", async () => {
  const st = await api().devices_status();
  const r = st.running ? await api().devices_stop() : await api().devices_start();
  $("#dev-error").hidden = r.ok !== false; $("#dev-error").textContent = r.error || "";
  drawDevices(r.ok === false ? st : r);
});
$("#dev-newcode").addEventListener("click", async () => drawDevices(await api().devices_new_code()));

// ---- boot ----
window.addEventListener("pywebviewready", async () => {
  const info = await api().get_info();
  $("#version").textContent = `NEXVARA v${info.version}`;
  $("#sys-info").textContent = [
    `Versiya: ${info.version}`, `Operatsion tizim: ${info.os}`, `Python: ${info.python}`,
    `AI ulangan: ${info.ai_connected ? "ha" : "yo‘q"}`, `Ma’lumotlar papkasi: ${info.data_dir}`,
  ].join("\n");
  refreshAiStatus();
  renderAiMoney();
  checkUpdateBanner();
  // The conversation continues where it stopped last time.
  (await api().memory_chat(30)).forEach((c) => addMsg(c.text, c.role === "user"));
  settings = await api().get_settings();
  setTheme(settings.theme, false);
  applySettings();
  refreshCount();
  setInterval(phoneEvents, 1500);
});
