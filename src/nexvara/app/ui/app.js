"use strict";

const $ = (sel) => document.querySelector(sel);
const STATUS_LABEL = {
  pending: "Kutilmoqda", running: "Bajarilmoqda", succeeded: "Bajarildi",
  failed: "Xato", cancelled: "Bekor qilindi",
};
const PAGES = new Set(["home", "chat", "office", "library", "history", "settings"]);

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
  if (page === "history") renderHistory();
  if (page === "library") renderLibrary();
}

$("#nav").addEventListener("click", (e) => {
  const b = e.target.closest(".nav-item");
  if (b) show(b.dataset.page);
});
document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => show(b.dataset.goto)));

// ---- theme ----
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("nexvara-theme", t); } catch (_) { /* storage unavailable */ }
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
  const r = await api().chat(text);
  if (r.reply) addMsg(r.reply, false);
  if (r.task) track(r.task, true);
  showContext(await api().get_context_file());
});

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

  const running = t.status === "running" || t.status === "pending";
  $("#task-cancel").disabled = !running || t.cancel_requested;
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
    if ($("#page-library").classList.contains("active")) renderLibrary();
  }
}

const chatTasks = new Set();

function track(t, fromChat) {
  if (fromChat) chatTasks.add(t.id);
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
    count: $("#t-count").value, variants: $("#t-variants").value,
  });
  if (!r.id) { $("#t-error").textContent = r.error; $("#t-error").hidden = false; return; }
  $("#t-error").hidden = true;
  track(r);
});

// ---- boot ----
window.addEventListener("pywebviewready", async () => {
  const info = await api().get_info();
  $("#version").textContent = `NEXVARA v${info.version}`;
  $("#sys-info").textContent = JSON.stringify(info, null, 2);
  $("#ai-status").textContent = info.ai_connected ? "Ulangan" : "Ulanmagan";
});
