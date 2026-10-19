"use strict";

// Chat tools: 🔊 read answers aloud · 🖼️ a photo from the PC · 📷 the webcam · ✨ make a picture ·
// 🎧 hands-free conversation (listen → answer → speak → listen) · 🧠 AUTO/MANUAL per direction.
// Everything here calls the PC side; AI keys never reach this page.
const media = { speak: false, live: false, audio: null, caps: null };

function mediaBtn(id, on) {
  const b = $(id); if (!b) return;
  b.classList.toggle("on", !!on); b.setAttribute("aria-pressed", on ? "true" : "false");
}

async function mediaLoad() {
  if (!api() || !api().ai_capabilities) return;
  try { media.caps = await api().ai_capabilities(); } catch (_) { return; }
  media.speak = !!media.caps.speak_replies;
  mediaBtn("#chat-speak", media.speak);
  const t = media.caps.capabilities.text;
  $("#chat-models").textContent = `🧠 ${t.mode === "manual" ? t.model : "AUTO"}`;
  mediaPreview();
  const panel = $("#ai-caps-settings");
  if (panel) renderCaps(panel);
}

async function mediaPreview() {
  if (!api() || !api().ai_preview) return;
  const text = $("#chat-text").value;
  const r = await api().ai_preview(text, "text");
  const rows = Object.entries(media.caps?.catalog || {}).filter(([, c]) => c.checked_at);
  const latest = rows.length ? Math.max(...rows.map(([, c]) => c.checked_at)) : 0;
  const stamp = latest ? new Date(latest * 1000).toLocaleString() : "tekshirilmagan";
  $("#chat-ai-meta").textContent = r.ok
    ? `${r.mode} · ${r.provider} · ${r.model} · ${r.free ? "FREE" : "PAID"} · taxmin ≈$${r.estimated_cost.toFixed(4)} · katalog: ${stamp}${r.catalog?.stale ? " (eskirgan)" : ""}`
    : `${r.mode} · ${r.error} · katalog: ${stamp}`;
}
let mediaPreviewTimer;
$("#chat-text").addEventListener("input", () => {
  clearTimeout(mediaPreviewTimer); mediaPreviewTimer = setTimeout(mediaPreview, 450);
});

// ---- 🔊 speaking ----
async function mediaSpeak(text) {
  if (!text) return;
  let r = await api().ai_speak(text, false, !!media.live);
  if (r.needs_approval && window.confirm(`${r.error}\nOvozli javob uchun pullik so‘rovni tasdiqlaysizmi?`))
    r = await api().ai_speak(text, true, !!media.live);
  if (!r.ok) { addMsg(`🔊 ${r.error}`, false); if (media.live) liveListen(); return; }
  if (media.audio) media.audio.pause();
  media.audio = new Audio(`data:${r.mime};base64,${r.audio}`);
  media.audio.onended = () => { if (media.live) liveListen(); };
  media.audio.play().catch(() => { if (media.live) liveListen(); });
}

// Called by handleReply for every answer.
window.mediaOnReply = (r) => {
  if (r.ai) {
    const a = r.ai;
    $("#chat-ai-meta").textContent = `${a.mode} · ${a.provider} · ${a.model} · ${a.free ? "FREE" : "PAID"} · taxmin ≈$${a.estimated_cost.toFixed(4)} · ` +
      (a.cost == null ? "haqiqiy sarf noma’lum" : `token bo‘yicha hisob ≈$${a.cost.toFixed(4)}`);
  }
  if (r.image_data) {
    const fig = el("figure", "msg ai-image");
    const img = el("img"); img.src = r.image_data; img.alt = "AI yaratgan rasm";
    fig.appendChild(img);
    $("#chat-log").appendChild(fig); fig.scrollIntoView({ block: "end" });
    showContext(r.image);
  }
  if ((media.speak || media.live) && r.reply && !r.confirm) mediaSpeak(r.reply);
  else if (media.live && r.confirm) addMsg("🎧 Tasdiq kerak — «Ha» yoki «Yo‘q» ni bosing, keyin suhbat davom etadi.", false);
};

$("#chat-speak").addEventListener("click", async () => {
  media.speak = !media.speak;
  mediaBtn("#chat-speak", media.speak);
  await api().ai_set_speak(media.speak);
  if (!media.speak && media.audio) media.audio.pause();
});

// ---- 🖼️ a photo from the PC ----
$("#chat-image").addEventListener("click", async () => {
  const r = await api().pick_image();
  if (!r.path) return;
  showContext(r.path);
  addMsg("🖼️ Rasm tanlandi. Endi savol yozing («bu rasmda nima bor?»), «matnini o‘qi», «Excel qil» yoki «shu rasmni … qilib o‘zgartir».", false);
});

// ---- 📷 webcam ----
$("#chat-camera").addEventListener("click", async () => {
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } }); }
  catch (e) { addMsg(`📷 Kamera ochilmadi: ${e.message || e}. Windows sozlamalarida kameraga ruxsat bering.`, false); return; }
  const box = el("div", "cam-modal"); box.setAttribute("role", "dialog"); box.setAttribute("aria-label", "Kamera");
  const video = el("video"); video.autoplay = true; video.playsInline = true; video.srcObject = stream;
  const bar = el("div", "row");
  const shot = el("button", "btn primary", "📸 Suratga olish"), cancel = el("button", "btn", "Bekor");
  const close = () => { stream.getTracks().forEach((t) => t.stop()); box.remove(); };
  cancel.addEventListener("click", close);
  shot.addEventListener("click", async () => {
    const c = document.createElement("canvas"); c.width = video.videoWidth || 1280; c.height = video.videoHeight || 720;
    c.getContext("2d").drawImage(video, 0, 0, c.width, c.height);
    const r = await api().save_camera_photo(c.toDataURL("image/jpeg", 0.9));
    close();
    if (!r.ok) { addMsg(`📷 ${r.error}`, false); return; }
    showContext(r.path);
    addMsg("📷 Surat olindi. Endi savol yozing yoki «matnini o‘qi» / «Excel qil» deng.", false);
  });
  bar.append(shot, cancel); box.append(video, bar); document.body.appendChild(box);
});

// ---- ✨ make / edit a picture ----
$("#chat-gen").addEventListener("click", async () => {
  let prompt = $("#chat-text").value.trim();
  if (!prompt) prompt = (window.prompt("✨ Qanday rasm kerak? (masalan: qishki maktab hovlisi, akvarel)") || "").trim();
  if (!prompt) return;
  const open = $("#chat-file").textContent || "";
  const edit = /\.(png|jpe?g|webp|bmp)$/i.test(open) && window.confirm("Ochiq rasmni shu bo‘yicha o‘zgartiraymi?\n(Bekor — yangi rasm yaratiladi)");
  $("#chat-text").value = edit ? `shu rasmni o‘zgartir: ${prompt}` : `rasm yarat: ${prompt}`;
  $("#chat-form").requestSubmit();
});

// ---- 🎧 hands-free conversation ----
function liveListen() { if (media.live && typeof voiceStart === "function") voiceStart({ live: true }); }
$("#chat-live").addEventListener("click", async () => {
  media.live = !media.live;
  mediaBtn("#chat-live", media.live);
  if (media.live) {
    addMsg("🎧 Jonli suhbat: gapiring — jim bo‘lsangiz o‘zi to‘xtaydi, javobni ovozda eshitasiz va yana tinglaydi. To‘xtatish: 🎧 ni yana bosing.", false);
    liveListen();
  } else {
    if (typeof voiceCancel === "function") voiceCancel();
    if (media.audio) media.audio.pause();
  }
});

// ---- 🧠 AUTO / MANUAL per direction ----
function renderCaps(root) {
  const st = media.caps; root.replaceChildren();
  if (!st) return;
  if (!st.connected.length) root.appendChild(el("p", "muted small", "Hali hech bir AI kaliti ulanmagan: Sozlamalar → AI."));
  Object.entries(st.capabilities).forEach(([cap, c]) => {
    const row = el("div", "cap-row");
    row.appendChild(el("div", "cap-label", c.label));
    const mode = el("select"); mode.setAttribute("aria-label", `${c.label}: rejim`);
    [["auto", "AUTO"], ["manual", "Qo‘lda"]].forEach(([v, t]) => { const o = el("option", "", t); o.value = v; mode.appendChild(o); });
    mode.value = c.mode;
    const prov = el("select"); prov.setAttribute("aria-label", `${c.label}: provayder`);
    const model = el("select"); model.setAttribute("aria-label", `${c.label}: model`);
    const fillModels = () => {
      model.replaceChildren();
      ((c.offers[prov.value] || {}).models || []).forEach((m) => { const o = el("option", "", m); o.value = m; model.appendChild(o); });
      if (c.model) model.value = c.model;
    };
    Object.entries(c.offers).forEach(([p, o]) => {
      const opt = el("option", "", `${o.label}${o.connected ? "" : " (kalit yo‘q)"}`); opt.value = p; opt.disabled = !o.connected; prov.appendChild(opt);
    });
    prov.value = c.provider || (st.connected.find((p) => c.offers[p]) || Object.keys(c.offers)[0] || "");
    fillModels();
    const info = el("div", "muted small cap-info");
    const showInfo = () => {
      const manual = mode.value === "manual";
      prov.hidden = model.hidden = !manual;
      info.textContent = manual ? "Faqat shu model ishlatiladi (almashtirilmaydi)."
        : c.auto_pick ? `AUTO hozir: ${c.offers[c.auto_pick.provider]?.label || c.auto_pick.provider} · ${c.auto_pick.model}${c.auto_pick.free ? " (bepul)" : ""}`
        : (cap === "text" || cap === "vision") ? "AUTO: vazifaga qarab arzon → kuchli model" : "AUTO: mos AI ulanmagan";
    };
    const save = async () => {
      const r = await api().ai_set_capability(cap, mode.value, prov.value, model.value);
      if (!r.ok) { info.textContent = r.error; info.classList.add("bad"); return; }
      info.classList.remove("bad"); media.caps = r; mediaLoad();
    };
    mode.addEventListener("change", () => { showInfo(); if (mode.value === "auto" || model.value) save(); });
    prov.addEventListener("change", () => { fillModels(); if (model.value) save(); });
    model.addEventListener("change", save);
    showInfo();
    row.append(mode, prov, model, info);
    root.appendChild(row);
  });
  const vrow = el("div", "cap-row");
  vrow.appendChild(el("div", "cap-label", "Ovoz (TTS)"));
  const vsel = el("select"); vsel.setAttribute("aria-label", "Ovoz");
  const o0 = el("option", "", "Standart"); o0.value = ""; vsel.appendChild(o0);
  Object.entries(st.voices).forEach(([p, names]) => names.forEach((n) => { const o = el("option", "", `${n} (${p})`); o.value = n; vsel.appendChild(o); }));
  vsel.addEventListener("change", () => api().ai_set_speak(media.speak, vsel.value));
  vrow.appendChild(vsel); root.appendChild(vrow);
}

$("#chat-models").addEventListener("click", async () => {
  const old = document.querySelector(".caps-pop"); if (old) { old.remove(); return; }
  await mediaLoad();
  const pop = el("div", "caps-pop card"); pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "AI modeli");
  const head = el("div", "row"); head.appendChild(el("b", "", "🧠 AI modeli: AUTO yoki qo‘lda"));
  const x = el("button", "btn small-btn", "Yopish"); x.addEventListener("click", () => pop.remove()); head.appendChild(x);
  const body = el("div"); renderCaps(body);
  const refresh = el("button", "btn", "Hozir yangilash");
  refresh.addEventListener("click", async () => {
    refresh.disabled = true;
    try { await api().ai_refresh_catalog(); await mediaLoad(); renderCaps(body); }
    finally { refresh.disabled = false; }
  });
  pop.append(head, refresh, body); $("#page-chat").appendChild(pop);
});
window.mediaLoad = mediaLoad;

window.addEventListener("pywebviewready", () => setTimeout(mediaLoad, 400));
setTimeout(mediaLoad, 1500);
