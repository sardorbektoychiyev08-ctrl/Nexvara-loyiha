"use strict";

const $ = (sel) => document.querySelector(sel);
const STATUS_LABEL = {
  pending: "Kutilmoqda", running: "Bajarilmoqda", succeeded: "Bajarildi",
  failed: "Xato", cancelled: "Bekor qilindi",
};
const PAGES = new Set(["home", "chat", "office", "history", "settings"]);

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
});

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
    const b = el("button", "btn", "Faylni ko'rsatish");
    b.addEventListener("click", () => api().reveal_file(t.result.path));
    const row = el("div", "row");
    row.appendChild(b);
    res.appendChild(row);
  }
  res.hidden = !res.childElementCount;

  const running = t.status === "running" || t.status === "pending";
  $("#task-cancel").disabled = !running || t.cancel_requested;
  $("#run-excel").disabled = running;
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
  }
}

$("#run-excel").addEventListener("click", async () => {
  if (!api()) return;
  const t = await api().run_excel_demo();
  currentTaskId = t.id;
  renderTask(t);
  refreshCount();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(poll, 300);
});

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

// ---- boot ----
window.addEventListener("pywebviewready", async () => {
  const info = await api().get_info();
  $("#version").textContent = `NEXVARA v${info.version}`;
  $("#sys-info").textContent = JSON.stringify(info, null, 2);
  $("#ai-status").textContent = info.ai_connected ? "Ulangan" : "Ulanmagan";
});
