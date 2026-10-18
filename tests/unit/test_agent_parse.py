import pytest

from nexvara.agent import files
from nexvara.agent.parse import find_file, parse_command, split_clauses


def kinds(plan):
    return [a.kind for a in plan.actions]


def test_full_excel_command_from_spec():
    plan = parse_command(
        "Hisobot.xlsx ni och, ma’lumotlarni tozala, dublikatlarni o‘chir, Summa bo‘yicha "
        "kamayish tartibida sarala, jadvalni formatla, jami qo‘sh, diagramma qo‘sh va saqla"
    )
    assert (plan.app, plan.file) == ("excel", "Hisobot.xlsx")
    assert kinds(plan) == ["open", "clean", "dedupe", "sort", "format", "total", "chart", "save"]
    sort = plan.actions[3]
    assert sort.args == {"column": "summa", "descending": True}
    assert plan.unknown == []


@pytest.mark.parametrize(
    ("text", "args"),
    [
        ("savdo.xlsx faylida Hudud ustunida Toshkentni filtrla",
         {"column": None, "words": "hudud toshkentni", "value": None, "criteria": None}),
        ("shu faylda Daromad 500000 dan katta qatorlarni filtrla",
         {"column": None, "words": "daromad", "value": None, "criteria": ">500000"}),
        ("Summa < 1000 bo‘yicha filtrla",
         {"column": None, "words": "summa", "value": None, "criteria": "<1000"}),
        ("Buxoro bo‘yicha filtrla",
         {"column": None, "words": "buxoro", "value": None, "criteria": None}),
    ],
)  # fmt: skip
def test_filter_clauses(text, args):
    plan = parse_command(text, context_file="D:/x/savdo.xlsx")
    assert kinds(plan) == ["filter"] and plan.actions[0].args == args


def test_short_filler_words_do_not_eat_real_words():
    # "da", "bu", "ga" are fillers, but "Daromad", "Buxoro", "Gaz" must survive.
    plan = parse_command("Daromad bo‘yicha sarala", context_file="D:/x/a.xlsx")
    assert plan.actions[0].args["column"] == "daromad"
    plan = parse_command("Gaz bo‘yicha filtrla", context_file="D:/x/a.xlsx")
    assert plan.actions[0].args["words"] == "gaz"


def test_sort_by_letter_and_direction():
    plan = parse_command("B ustun bo‘yicha o‘sish tartibida sarala", context_file="D:/x/a.xlsx")
    assert plan.actions[0].args == {"column": "B", "descending": False}


def test_chart_and_pivot():
    plan = parse_command("Hudud bo‘yicha doira diagramma, keyin Hudud bo‘yicha Summa uchun "
                         "pivot jadval yasa", context_file="D:/x/a.xlsx")  # fmt: skip
    assert kinds(plan) == ["chart", "pivot"]
    assert plan.actions[0].args["kind"] == "pie"
    assert plan.actions[1].args["words"] == "hudud summa"


def test_word_command():
    plan = parse_command(
        'ariza.docx da "Aliyev Vali" ni "Karimov Olim" ga almashtir, shriftni Times New Roman 14 '
        "qil, qator oralig‘ini 1,5 qil, xatboshi 1,25 sm, sahifa raqamlarini qo‘y, mundarija "
        "qo‘sh va PDF ga saqla"
    )
    assert plan.app == "word" and plan.file == "ariza.docx"
    assert kinds(plan) == ["replace", "font", "spacing", "indent", "page_numbers", "toc", "pdf"]
    assert plan.actions[0].args == {"find": "Aliyev Vali", "replace": "Karimov Olim"}
    assert plan.actions[1].args == {"name": "Times New Roman", "size": 14.0}
    assert plan.actions[2].args == {"value": 1.5}
    assert plan.actions[3].args == {"cm": 1.25}


def test_overwrite_only_when_asked():
    assert not parse_command("a.xlsx ni formatla va saqla").actions[-1].args["overwrite"]
    assert parse_command("a.xlsx ni formatla va ustiga saqla").actions[-1].args["overwrite"]


def test_context_file_and_plain_chat():
    plan = parse_command("shu faylni formatla", context_file="D:/x/hisobot.xlsx")
    assert (plan.app, plan.file) == ("excel", "D:/x/hisobot.xlsx")
    assert parse_command("salom, qalaysan?") is None
    assert parse_command("rahmat") is None


def test_new_excel_table_from_column_names():
    plan = parse_command(
        "Excel’da 5 ustunli o‘quvchilar jadvali tuz: F.I.Sh, Sinf, Sana, Baho, Izoh"
    )
    assert (plan.app, plan.file, kinds(plan)) == ("excel", None, ["create_table"])
    assert plan.actions[0].args == {
        "count": 5,
        "title": "o‘quvchilar",
        "headers": ["F.I.Sh", "Sinf", "Sana", "Baho", "Izoh"],
    }


def test_new_excel_table_chat_creates_a_named_task(tmp_path):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    runner = TaskRunner()
    api = Api(
        runner,
        output_dir=tmp_path,
        overrides={
            "command": lambda task: {"path": str(tmp_path / "new.xlsx")},
        },
    )
    reply = api.chat("Excel’da 3 ustunli sinf jadvali tuz: Ism, Baho, Sana")
    assert reply["task"]["title"].endswith(".xlsx")
    assert "Ism, Baho, Sana" in reply["reply"]
    assert runner.get(reply["task"]["id"]).wait(5)


def test_unknown_clauses_are_reported():
    plan = parse_command("a.xlsx ni formatla va kosmosga uchir")
    assert kinds(plan) == ["format"] and plan.unknown == ["kosmosga uchir"]


def test_split_and_find_file():
    assert split_clauses("1,5 qil, saqla va yop") == ["1,5 qil", "saqla", "yop"]
    assert find_file("«Yillik hisobot 2026.xlsx» ni och") == "Yillik hisobot 2026.xlsx"
    assert find_file(r"D:\Ish\savdo.xlsx ni och") == r"D:\Ish\savdo.xlsx"
    assert find_file("hech narsa") is None


# ---------- files ----------


def test_output_path_never_overwrites(tmp_path):
    src = tmp_path / "Hisobot.xlsx"
    src.write_bytes(b"x")
    out1 = files.output_path(src)
    assert out1.name == "Hisobot_NEXVARA.xlsx"
    out1.write_bytes(b"y")
    assert files.output_path(src).name == "Hisobot_NEXVARA-2.xlsx"
    # Re-working our own output does not stack suffixes.
    assert files.output_path(out1).name == "Hisobot_NEXVARA-2.xlsx"
    assert files.output_path(src, ".pdf").name == "Hisobot_NEXVARA.pdf"


def test_resolve_absolute_and_near(tmp_path, monkeypatch):
    f = tmp_path / "ish" / "Savdo.xlsx"
    f.parent.mkdir()
    f.write_bytes(b"x")
    assert files.resolve(str(f)) == f
    monkeypatch.setattr(files, "search_roots", lambda extra=None: list(extra or []))
    assert files.resolve("savdo.XLSX", near=tmp_path) == f
    with pytest.raises(LookupError):
        files.resolve("yoq.xlsx", near=tmp_path)
    with pytest.raises(LookupError):
        files.resolve(str(tmp_path / "yoq.xlsx"))


def test_backup(tmp_path):
    f = tmp_path / "a.docx"
    f.write_bytes(b"orig")
    b = files.backup(f)
    assert b.read_bytes() == b"orig" and b.name.startswith("a.bak-")


def test_words_inside_file_paths_do_not_change_intent(tmp_path):
    """Regression: a path like .../pytest-67/test_x/Savdo.xlsx was read as a test request."""
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import parse_test_request, parse_topic_request

    f = tmp_path / "Testlar mavzu" / "Savdo.xlsx"
    f.parent.mkdir()
    f.write_bytes(b"x")
    text = f"«{f}» ni och, formatla va saqla"
    assert parse_test_request(text) is None and parse_topic_request(text) is None
    runner = TaskRunner()
    api = Api(runner, overrides={"command": lambda task: {"path": ""}})
    reply = api.chat(text)
    assert reply["task"]["title"] == "Buyruq: Savdo.xlsx"
    assert runner.get(reply["task"]["id"]).wait(5)


X, W, P = "D:/x/savdo.xlsx", "D:/x/xat.docx", "D:/x/dars.pptx"


@pytest.mark.parametrize(
    ("ctx", "text", "kind", "args"),
    [
        (X, "Summa 1000000 dan katta kataklarni qizil rang bilan belgila", "highlight",
         {"mode": "cells", "criteria": ">1000000", "color": "#FCA5A5", "words": "summa"}),
        (X, "Summa ustuniga rang shkalasi qo‘sh", "highlight", {"mode": "scale"}),
        (X, "Soni ustuniga ma’lumot chiziqlari qo‘sh", "highlight", {"mode": "bars"}),
        (X, "eng katta 3 ta Summani yashil bilan belgila", "highlight",
         {"mode": "top", "top": 3, "color": "#86EFAC"}),
        (X, "C ustunni pul formatiga o‘tkaz", "numfmt", {"kind": "money", "column": "C"}),
        (X, "Ulush ustunini foiz formatida qil", "numfmt", {"kind": "percent", "words": "ulush"}),
        (X, "Summa ustunini 2 xonali kasr qil", "numfmt", {"kind": "decimal", "decimals": 2}),
        (X, "o‘rtacha qatorini qo‘sh", "stats", {"funcs": ["average"]}),
        (X, "eng katta va eng kichik qiymat qatorlarini qo‘sh", "stats", {"funcs": ["max", "min"]}),
        (X, "Foyda = Summa - Soni * 1000 ustunini qo‘sh", "formula",
         {"name": "Foyda", "expr": "Summa - Soni * 1000"}),
        (X, "QQS ustunini qo‘sh: Summa ko‘paytir 0,12", "formula",
         {"name": "QQS", "expr": "Summa * 0,12"}),
        (X, "Mahsulot ustunini o‘chir", "delete_column", {"words": "mahsulot"}),
        (X, "varaq nomini «Hisobot 2026» qil", "rename_sheet", {"name": "Hisobot 2026"}),
        (X, "ustunlar kengligini moslashtir", "autofit", {}),
        (X, "albom qilib bir sahifaga sig‘dir", "print_setup", {"landscape": True, "fit": True}),
        (X, "shriftni Arial 12 qil", "font", {"name": "Arial", "size": 12.0}),
        (X, "summa bo‘yicha kamayish tartibida sartirovka qil", "sort",
         {"column": "summa", "descending": True}),
        (W, "matnni kenglik bo‘yicha tekisla", "align", {"how": "justify", "target": "body"}),
        (W, "sarlavhalarni markazga tekisla", "align", {"how": "center", "target": "headings"}),
        (W, "yuqori kolontitulga «5-maktab» yoz", "header", {"text": "5-maktab"}),
        (W, "pastki kolontitulga «Toshkent» yoz", "header", {"where": "footer"}),
        (W, "sahifani albom qil", "orientation", {"landscape": True}),
        (W, "chap chetini 3 sm, o‘ng chetini 1,5 sm qil", "margins", {"left": 3.0, "right": 1.5}),
        (W, "chetlarini 2 sm qil", "margins", {"top": 2.0, "left": 2.0}),
        (W, "ortiqcha bo‘sh joylarni tozala", "clean", {}),
        (W, "so‘zlarni sana", "count", {}),
        (W, "birinchi qatorni sarlavha qil", "title", {}),
        (W, "jadvallarni formatla", "tables", {}),
        (W, "hujjatni rasmiy formatla", "format", {}),
        (P, "barcha slaydlarga o‘tish effekti qo‘sh", "transition", {}),
        (P, "slayd raqamlarini qo‘sh", "slide_numbers", {}),
        (P, "slaydlarni tekshir", "check", {}),
    ],
)  # fmt: skip
def test_professional_commands(ctx, text, kind, args):
    plan = parse_command(text, context_file=ctx)
    assert plan is not None and kinds(plan) == [kind] and plan.unknown == [], plan
    for k, v in args.items():
        assert plan.actions[0].args[k] == v, (k, plan.actions[0].args)


def test_professional_commands_chain_in_one_message():
    plan = parse_command(
        "Savdo.xlsx ni och, Foyda = Summa - Soni ustunini qo‘sh, Summa ustunini pul formatiga "
        "o‘tkaz, Summa 1000000 dan katta kataklarni qizil bilan belgila, o‘rtacha qatorini qo‘sh, "
        "ustunlar kengligini moslashtir va saqla"
    )
    assert kinds(plan) == ["open", "formula", "numfmt", "highlight", "stats", "autofit", "save"]
    assert plan.unknown == []


def test_new_excel_table_without_count_and_with_ustunlari():
    plan = parse_command("Excel o‘quvchilar jadvali tuz, ustunlari: Ism, Sinf, Baho")
    assert kinds(plan) == ["create_table"], plan
    assert plan.actions[0].args["count"] == 3
    assert plan.actions[0].args["headers"] == ["Ism", "Sinf", "Baho"]
    assert plan.actions[0].args["title"] == "o‘quvchilar"
    plan = parse_command("Excel’da sinf jadvali tuz: Ism, Baho")
    assert plan.actions[0].args == {"count": 2, "headers": ["Ism", "Baho"], "title": "sinf"}
    assert kinds(parse_command("Excel’da 2 ustunli narxlar jadvali yarat — Mahsulot, Narx")) == [
        "create_table"
    ]


def test_sort_from_the_biggest_is_descending():
    """Live check 2026-10-19: «eng katta summadan boshlab tartibla» sorted ascending."""
    plan = parse_command("Savdo.xlsx ni eng katta summadan boshlab tartibla")
    sort = next(a for a in plan.actions if a.kind == "sort")
    assert sort.args["descending"] is True
    plan = parse_command("Savdo.xlsx ni summa bo‘yicha sarala")
    assert next(a for a in plan.actions if a.kind == "sort").args["descending"] is False


def test_live_phrases_official_letter_and_small_text():
    """Live check 2026-10-19: only the PDF was made, these parts were dropped."""
    w = parse_command(
        "ariza.docx ni direktorga topshiriladigan rasmiy ariza ko‘rinishiga keltir va PDF ham qil"
    )
    assert "format" in kinds(w) and "pdf" in kinds(w) and not w.unknown, w
    p = parse_command(
        "taqdimot.pptx dagi slaydlarni tekshir, mayda yozuvlarni kattalashtir va "
        "slayd raqamlarini qo‘y"
    )
    assert "fix" in kinds(p) and not p.unknown, p
