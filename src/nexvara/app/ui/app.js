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
  if (page === "settings") renderSettings();
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
}

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
      el("span", p.has_key ? "badge succeeded" : "badge", p.has_key ? `Kalit bor ${p.key_masked}` : "Kalit yo‘q"));
    const models = el("div", "muted small",
      Object.entries(p.models).map(([t, m]) => `${st.tier_labels[t]}: ${m}`).join(" · "));
    const form = el("div", "row wrap");
    const input = el("input", "ai-key");
    input.type = "password"; input.placeholder = p.has_key ? "Yangi kalit (almashtirish uchun)" : p.key_hint;
    input.autocomplete = "off";
    const save = el("button", "btn primary", "Tekshirish va saqlash");
    const get = el("button", "btn", "Kalit olish ↗");
    const msg = el("div", "muted small", "");
    save.type = get.type = "button";
    save.addEventListener("click", async () => {
      if (!input.value.trim()) return;
      save.disabled = true; msg.textContent = "Tekshirilmoqda (bepul so‘rov)…";
      const r = await api().ai_save_key(name, input.value);
      input.value = ""; save.disabled = false;
      if (!r.ok) { msg.textContent = `Xato: ${r.error}`; return; }
      msg.textContent = `Saqlandi ✓ Modellar: ${Object.values(r.models).join(", ")}` +
        (r.missing.length ? ` (hisobda topilmadi: ${r.missing.join(", ")})` : "");
      renderAi(r.status); refreshAiStatus();
    });
    get.addEventListener("click", () => api().open_url(p.key_url));
    form.append(input, save, get);
    if (p.has_key) {
      const del = el("button", "btn", "O‘chirish");
      del.type = "button";
      del.addEventListener("click", async () => {
        if (!confirm(`${p.label} kaliti o‘chirilsinmi?`)) return;
        renderAi(await api().ai_delete_key(name)); refreshAiStatus();
      });
      form.append(del);
    }
    row.append(head, models, form, msg);
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
  $("#ai-send-text").checked = st.send_textbook_text;
  $("#ai-spent").textContent =
    `Sarflandi: bugun ${money(st.spent_today)} / ${money(st.daily_budget_usd)}, shu oy ${money(st.spent_month)} / ${money(st.monthly_budget_usd)}. Narxlar taxminiy (provayder hisobidagi summa asosiy).`;
  const usage = await api().ai_usage();
  const t = $("#ai-usage");
  t.textContent = "";
  if (usage.length) {
    const head = el("tr");
    ["Vaqt", "Ish", "Model", "Token", "Narx"].forEach((h) => head.appendChild(el("th", "", h)));
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
  } });
  $("#ai-error").hidden = r.ok; $("#ai-error").textContent = r.ok ? "" : r.error;
  $("#ai-saved").textContent = r.ok ? "Saqlandi ✓" : "";
  if (r.ok) { renderAi(); refreshAiStatus(); }
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

// ---- boot ----
window.addEventListener("pywebviewready", async () => {
  const info = await api().get_info();
  $("#version").textContent = `NEXVARA v${info.version}`;
  $("#sys-info").textContent = JSON.stringify(info, null, 2);
  refreshAiStatus();
  settings = await api().get_settings();
  setTheme(settings.theme, false);
  applySettings();
  refreshCount();
});
