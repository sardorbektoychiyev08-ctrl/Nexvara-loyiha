"""What the AI does inside NEXVARA. Office work itself stays in the tested offline executors:
the AI only turns free-form text into a command they understand, answers questions from
the textbooks, and writes test questions from a topic's text."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Any

from nexvara.ai.providers import AiError
from nexvara.ai.router import AiRouter, Estimate

# ---------------- understanding a request ----------------

CLASSIFY_SYSTEM = """Sen NEXVARA ilovasining buyruq tushunuvchisisan. Foydalanuvchi o‘zbekcha \
(ba’zan ruscha yoki xato bilan) yozadi. Uning so‘rovini quyidagi turlardan biriga ajrat va \
ilova tushunadigan oddiy o‘zbekcha (lotin) buyruqqa qayta yoz.

Turlar va ilova tushunadigan buyruq namunalari:
- "test": darslik bo‘yicha test. Namuna: "7-sinf fizika Nyuton qonunlari 20 ta test 2 variant"
- "topic": darslik mavzusini chiqarib berish. \
Namuna: "7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber"
- "presentation": darslik mavzusidan taqdimot. \
Namuna: "8-sinf tarix Amir Temur mavzusida taqdimot tayyorla"
- "command": mavjud Office faylida ish. Ilova shu so‘zlarni tushunadi:
  Excel: "Hisobot.xlsx ni och, B ustun bo‘yicha kamayish tartibida saralab, filtr qo‘y, \
dublikatlarni o‘chir, bo‘sh joylarni tozala, C ustunni pul formatiga o‘tkaz, jami qo‘sh, \
diagramma qo‘sh, PDF qilib saqla"
  Word: "Xat.docx ni och, «eski» so‘zini «yangi» ga almashtir, sarlavha qo‘sh, PDF qilib saqla"
  PowerPoint: "Taqdimot.pptx ni PDF qilib saqla"
  Fayl nomini foydalanuvchi aytganicha saqla. Fayl aytilmagan bo‘lsa "shu fayl" deb yoz.
- "question": bilim savoli (darslik mavzusi, fan, ta’rif, sana va h.k.).
- "chat": salomlashish, ilova haqida savol yoki boshqa suhbat.

Faqat JSON qaytar, boshqa hech narsa yozma:
{"kind": "...", "command": "qayta yozilgan buyruq yoki bo‘sh", "grade": sinf yoki null, \
"subject": "fan nomi yoki bo‘sh"}"""


@dataclass
class Intent:
    kind: str
    command: str = ""
    grade: int | None = None
    subject: str = ""


def _json_from(text: str) -> Any:
    """The first JSON object/array in a reply (models sometimes wrap it in ``` fences)."""
    text = text.strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except ValueError:
                continue
    raise AiError("AI javobini tushunib bo‘lmadi (JSON emas).")


def classify(router: AiRouter, text: str, approved: bool = False) -> Intent:
    r = router.complete(
        "classify",
        CLASSIFY_SYSTEM,
        [{"role": "user", "content": text}],
        max_tokens=2000,
        expected_out=300,
        approved=approved,
        effort="low",
    )
    data = _json_from(r.text)
    if not isinstance(data, dict):
        raise AiError("AI javobini tushunib bo‘lmadi.")
    kind = str(data.get("kind") or "chat")
    if kind not in ("test", "topic", "presentation", "command", "question", "chat"):
        kind = "chat"
    grade = data.get("grade")
    try:
        grade = int(grade) if grade not in (None, "") else None
    except (TypeError, ValueError):
        grade = None
    return Intent(
        kind, str(data.get("command") or "").strip(), grade, str(data.get("subject") or "")
    )


# ---------------- questions answered from the textbooks ----------------

QA_SYSTEM = """Sen NEXVARA — o‘qituvchi va o‘quvchilar uchun yordamchisan. Javobni o‘zbek \
tilida (lotin yozuvida), aniq va qisqa yoz. Agar quyida darslik parchalari berilgan bo‘lsa, \
avvalo ularga tayan va qaysi darslik va betdan olganingni [kitob, bet] ko‘rinishida ko‘rsat. \
Parchalarda javob bo‘lmasa, o‘z bilimingdan javob ber va buni ochiq ayt. To‘qib chiqarma."""

MAX_PASSAGES = 4
PASSAGE_CHARS = 2500


@dataclass
class Answer:
    text: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    cost: float = 0.0


def find_passages(text: str, grade: int | None = None, subject: str | None = None):
    from nexvara.knowledge.catalog import detect_grade, detect_subject
    from nexvara.knowledge.service import open_library

    grade = grade or detect_grade(text)
    subject = subject or detect_subject(text)
    lib = open_library()
    try:
        hits = lib.search(text, grade, subject, limit=MAX_PASSAGES)
        if not hits and (grade or subject):
            hits = lib.search(text, None, None, limit=MAX_PASSAGES)
        return hits
    finally:
        lib.close()


def _qa_messages(text: str, hits, send_text: bool) -> list[dict[str, str]]:
    if not hits or not send_text:
        return [{"role": "user", "content": text}]
    parts = [f"[{h.book.label()}, {h.page_no}-bet]\n{h.text[:PASSAGE_CHARS]}" for h in hits]
    return [
        {
            "role": "user",
            "content": "Darslik parchalari:\n\n" + "\n\n---\n\n".join(parts) + f"\n\nSavol: {text}",
        }
    ]


def answer_question(
    router: AiRouter, text: str, approved: bool = False, grade=None, subject=None
) -> Answer:
    send = bool(router.config().get("send_textbook_text", True))
    hits = find_passages(text, grade, subject) if send else []
    r = router.complete(
        "qa", QA_SYSTEM, _qa_messages(text, hits, send), max_tokens=6000, expected_out=900,
        approved=approved,
    )  # fmt: skip
    sources = [{"book": h.book.label(), "page": h.page_no, "path": h.book.path} for h in hits]
    return Answer(r.text.strip(), sources, r.cost)


def chat_reply(router: AiRouter, text: str, approved: bool = False) -> Answer:
    system = (
        "Sen NEXVARA — Windows uchun shaxsiy AI yordamchisan: Excel, Word, PowerPoint "
        "fayllari bilan ishlaysan, maktab darsliklaridan mavzu chiqarasan, test va taqdimot "
        "tuzasan. O‘zbek tilida (lotin) qisqa va do‘stona javob ber."
    )
    r = router.complete(
        "classify", system, [{"role": "user", "content": text}], max_tokens=2000,
        expected_out=300, approved=approved, effort="low",
    )  # fmt: skip
    return Answer(r.text.strip(), [], r.cost)


# ---------------- tests written by the AI ----------------

TEST_SYSTEM = """Sen tajribali o‘qituvchisan. Berilgan darslik matni asosida o‘zbek tilida \
(lotin yozuvida) sifatli test savollari tuz.
Talablar:
- har bir savolda 4 ta javob varianti, faqat bittasi to‘g‘ri;
- noto‘g‘ri variantlar ishonarli bo‘lsin (shu mavzudagi tushunchalar), lekin aniq noto‘g‘ri;
- savollar turli bo‘lsin: ta’rif, sabab-oqibat, sana/son, misol, taqqoslash, qo‘llash;
- faqat matndagi ma’lumotga tayan, matnda yo‘q narsani so‘rama;
- to‘g‘ri javob o‘rni (0–3) savoldan savolga turlicha bo‘lsin;
- "page" — savol olingan bet raqami (matndagi [N-bet] belgisidan).
Faqat JSON massiv qaytar:
[{"q": "savol matni", "options": ["A", "B", "C", "D"], "answer": 0, "page": 12}]"""

MAX_MATERIAL_CHARS = 24000
OUT_TOKENS_PER_QUESTION = 140


def _material(pages: list[tuple[int, str]]) -> str:
    out, total = [], 0
    for p, t in pages:
        chunk = f"[{p}-bet]\n{t.strip()}"
        if total + len(chunk) > MAX_MATERIAL_CHARS:
            chunk = chunk[: max(0, MAX_MATERIAL_CHARS - total)]
        if chunk:
            out.append(chunk)
            total += len(chunk)
        if total >= MAX_MATERIAL_CHARS:
            break
    return "\n\n".join(out)


def _test_request(req, material: str) -> tuple[list[dict[str, str]], int, int]:
    wanted = min(req.count * req.variants, 120)
    msg = f"Darslik matni:\n\n{material}\n\nShu matn bo‘yicha {wanted} ta turli test savoli tuz."
    max_tokens = min(32000, 2000 + wanted * OUT_TOKENS_PER_QUESTION * 2)
    return [{"role": "user", "content": msg}], wanted, max_tokens


def estimate_test(router: AiRouter, req) -> Estimate:
    from nexvara.knowledge.service import topic_material

    _book, pages, _topic = topic_material(req)
    messages, wanted, _max = _test_request(req, _material(pages))
    return router.estimate("balanced", TEST_SYSTEM, messages, wanted * OUT_TOKENS_PER_QUESTION)


def parse_questions(data: Any) -> list:
    from nexvara.knowledge.quiz import Question

    out = []
    if isinstance(data, dict):
        data = data.get("questions") or []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or item.get("question") or "").strip()
        opts = [str(o).strip() for o in (item.get("options") or [])]
        try:
            ans = int(item.get("answer"))
        except (TypeError, ValueError):
            continue
        if not q or len(opts) != 4 or not all(opts) or not 0 <= ans < 4:
            continue
        if len({o.casefold() for o in opts}) < 4:
            continue
        opts = [re.sub(r"^[A-Da-d][).]\s*", "", o) for o in opts]
        page = item.get("page")
        source = f"{page}-bet" if isinstance(page, int) or str(page).isdigit() else ""
        out.append(Question("mcq", q, "ABCD"[ans], opts, source=source))
    return out


def _shuffled(q, rng: random.Random):
    from nexvara.knowledge.quiz import Question

    correct = q.options["ABCD".index(q.answer)]
    opts = q.options[:]
    rng.shuffle(opts)
    return Question("mcq", q.text, "ABCD"[opts.index(correct)], opts, source=q.source)


def make_ai_quizzes(router: AiRouter, req, approved: bool = False):
    """(book, topic, quizzes) like service.make_quizzes, but the questions come from the AI.
    Picture questions found offline (book figures) are kept: the AI cannot see the images."""
    from nexvara.knowledge.quiz import QuizResult
    from nexvara.knowledge.service import make_quizzes, topic_material

    book, pages, topic = topic_material(req)
    messages, wanted, max_tokens = _test_request(req, _material(pages))
    r = router.complete(
        "test", TEST_SYSTEM, messages, max_tokens=max_tokens,
        expected_out=wanted * OUT_TOKENS_PER_QUESTION, approved=approved,
    )  # fmt: skip
    pool = parse_questions(_json_from(r.text))
    if not pool:
        raise AiError("AI yaroqli savol qaytarmadi; qayta urinib ko‘ring yoki AI’siz tuzing.")
    try:
        _b, _t, offline = make_quizzes(req)
    except (LookupError, ValueError):
        offline = []
    quizzes = []
    for v in range(req.variants):
        rng = random.Random(2000 + v)
        pics = [q for q in (offline[v].questions if v < len(offline) else []) if q.image]
        pics = pics[: max(0, req.count // 4)]
        start = (v * req.count) % len(pool)
        chosen = [
            pool[(start + i) % len(pool)] for i in range(min(req.count - len(pics), len(pool)))
        ]
        if req.variants > 1:
            rng.shuffle(chosen)
        qs = [_shuffled(q, rng) if v else q for q in chosen] + pics
        note = ""
        if len(qs) < req.count:
            note = f"AI {len(pool)} ta savol berdi, {req.count} ta so‘ralgan edi."
        quizzes.append(QuizResult(qs, req.count, note))
    return book, topic, quizzes, r.cost
