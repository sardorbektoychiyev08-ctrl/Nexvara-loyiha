# Personal data and external AI

Code: [src/nexvara/ai/privacy.py](../src/nexvara/ai/privacy.py), applied in
[src/nexvara/ai/router.py](../src/nexvara/ai/router.py) `AiRouter.complete` — the single door
through which every AI request leaves the PC (all four providers, every purpose, and a
fallback provider too). Tests: [tests/unit/test_privacy.py](../tests/unit/test_privacy.py).

## What happens to a request

1. **Mask locally.** The user-originated parts (the message, chat history, remembered
   facts, Teach rules, file paths in the context) are scanned on this PC. Each personal item
   is replaced by a placeholder: `⟦ISM_1⟧`, `⟦TEL_1⟧`, `⟦JSHSHIR_1⟧`… The same value always
   gets the same placeholder within one request.
2. **Block if unsure.** If a personal-data keyword has a value next to it that matches no
   known format (e.g. "pasport: A 12-34"), or a long unknown number is left (8+ digits that
   are not an amount like "15 000 000"), the request is **not sent**: the user gets
   «So‘rov yuborilmadi …» and nothing is spent.
3. **Send** only the masked text. NEXVARA's own instructions and textbook passages are
   public text and are sent as they are (they need historical names such as "Amir Temur").
4. **Restore locally.** Placeholders in the AI's answer (also `[ISM_1]`, `«ISM_1»` variants)
   are replaced with the real values on this PC. The mapping lives in memory for that one
   request only; it is never written to disk, logs or the AI usage table.
5. The reply says how many items were kept on the PC:
   «🔒 N ta shaxsiy ma’lumot AI’ga yuborilmadi: kompyuterda yashirildi va javobda qayta tiklandi.»

## Detected

| Kind | Examples |
|---|---|
| ISM (name) | Uzbek/Russian surname and patronymic forms (Aliyev, Karimova, Anvarovna, … o‘g‘li/qizi), common first names (Vali, Nilufar…), words after "F.I.Sh.:", "ismi", "familiyasi", "o‘quvchi", "ota-onasi" |
| JSHSHIR / PINFL | 14 digits (spaces allowed) |
| PASPORT | AA1234567, ID card AD 1234567 |
| TEL | +998 90 123-45-67, 90 123 45 67 |
| EMAIL, KARTA | e-mail; 16-digit card numbers that pass the Luhn check |
| MANZIL | "… ko‘chasi 12-uy, kv. 45", mahalla, tumani, mavzesi, massivi |
| SANA | birth dates (05.03.2012) |
| STIR / INN | 9 digits after the keyword |

Not masked: public figures from textbooks and history (Alisher Navoiy, Amir Temur, Mirzo
Ulug‘bek, Isaak Nyuton…), place names (Toshkent, Samarqand…), product names, amounts.

## Limits of the method (honest list)

- Rule-based, not an AI model: an unusual name not in the lists and not next to a name field
  ("ismi", "F.I.Sh.") can pass unmasked. Keep student lists in files (file contents are
  never sent by the chat), not typed into chat.
- File contents are not sent to the AI by the chat/planner at all; only file names/paths,
  which are masked like any text.
- Textbook passages are sent only when "Savollarga javobda darslik parchalarini AI’ga
  yuborish" is on (Settings → AI).
