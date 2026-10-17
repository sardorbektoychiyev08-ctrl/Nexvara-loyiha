// NEXVARA interfeysining markaziy tarjima lug‘ati.
// Asosiy til — o‘zbek (lotin). Boshqa til qo‘shish uchun I18N ga yangi kalit (masalan "ru")
// va bir xil kalitlar bilan lug‘at qo‘shiladi; sahifadagi [data-i18n] elementlar shu yerdan oladi.
// Brendlar (Windows, Excel, Word, PowerPoint, Google, OneDrive, OpenAI, Claude, Gemini, DeepSeek),
// API, JSON va fayl kengaytmalari tarjima qilinmaydi.
"use strict";

const I18N = {
  uz: {
    // menyu (12 bo‘lim)
    "nav.home": "Bosh sahifa",
    "nav.chat": "AI suhbat",
    "nav.office": "Office yordamchisi",
    "nav.library": "Darsliklar va testlar",
    "nav.files": "Fayllar",
    "nav.bi": "NEXVARA BI",
    "nav.workflows": "Ish jarayonlari",
    "nav.teach": "NEXVARA’ga o‘rgatish",
    "nav.memory": "Xotira",
    "nav.history": "Vazifalar va tarix",
    "nav.devices": "Qurilmalar",
    "nav.settings": "Sozlamalar",
    // vazifa va ish jarayoni holatlari
    "status.pending": "Kutilmoqda",
    "status.running": "Bajarilmoqda",
    "status.succeeded": "Bajarildi",
    "status.failed": "Xatolik yuz berdi",
    "status.cancelled": "Bekor qilindi",
    // umumiy tugmalar va so‘zlar
    "btn.save": "Saqlash",
    "btn.cancel": "Bekor qilish",
    "btn.retry": "Qayta urinish",
    "btn.close": "Yopish",
    "msg.loading": "Yuklanmoqda…",
    "msg.saved": "Saqlandi ✓",
    // AI va xarajatlar
    "ai.provider": "AI provayderi",
    "ai.daily_limit": "Kunlik limit",
    "ai.monthly_limit": "Oylik limit",
    "ai.task_limit": "Bitta topshiriq limiti",
    "ai.balance": "Balans",
    "ai.usage": "Sarf",
    "ai.billing": "To‘lov",
    "ai.pay": "To‘lov / Balans",
    "ai.usage_site": "Sarfni saytda ko‘rish",
    "ai.get_key": "API kalitini olish",
    "ai.check_save": "Kalitni tekshirish va saqlash",
    "ai.connected": "Ulangan",
    "ai.not_connected": "Ulanmagan",
    "ai.estimated": "Taxminiy sarf",
    "ai.left": "Limitdan qolgan",
    "ai.real_balance": "Provayderdagi haqiqiy balans",
    "ai.no_balance_api": "Haqiqiy balansni avtomatik olish imkoni yo‘q",
    "ai.refresh_balance": "Balansni yangilash",
  },
};

let LANG = "uz";

/** Kalit bo‘yicha matn; {nom} o‘rniga vars.nom qo‘yiladi. Topilmasa — kalitning o‘zi. */
function i18n(key, vars) {
  const dict = I18N[LANG] || I18N.uz;
  let s = dict[key] ?? I18N.uz[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

/** [data-i18n] → matn, [data-i18n-ph] → placeholder, [data-i18n-title] → title. */
function applyI18n(root) {
  const r = root || document;
  r.querySelectorAll("[data-i18n]").forEach((e) => { e.textContent = i18n(e.dataset.i18n); });
  r.querySelectorAll("[data-i18n-ph]").forEach((e) => { e.placeholder = i18n(e.dataset.i18nPh); });
  r.querySelectorAll("[data-i18n-title]").forEach((e) => { e.title = i18n(e.dataset.i18nTitle); });
  document.documentElement.lang = LANG;
}

document.addEventListener("DOMContentLoaded", () => applyI18n());
