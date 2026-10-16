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
