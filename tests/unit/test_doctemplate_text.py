"""Official Uzbek application structure and robust ready-document data."""

from __future__ import annotations

import pytest

from nexvara import doctemplates
from nexvara.core.task import UserError


def sample(tid: str) -> dict[str, str]:
    template = doctemplates.TEMPLATES[tid]
    return {key: example for key, _label, example in template["fields"]}


@pytest.mark.parametrize("tid", list(doctemplates.TEMPLATES))
def test_every_template_renders_its_catalog_example(tid):
    blocks = doctemplates.render(tid, sample(tid))
    assert blocks and all(text.strip() for _kind, text in blocks)
    assert blocks[-1][0] == "sign"
    assert "None" not in "\n".join(text for _kind, text in blocks)


@pytest.mark.parametrize("tid", ["ariza_umumiy", "ariza_tatil", "ariza_ishga"])
def test_application_has_address_title_request_and_named_signature(tid):
    fields = sample(tid)
    blocks = doctemplates.render(tid, fields)
    assert [kind for kind, _ in blocks] == ["right", "right", "title", "body", "sign"]
    assert blocks[0][1] == fields["kimga"] and blocks[1][1] == fields["kimdan"]
    assert blocks[2] == ("title", "ARIZA")
    assert blocks[3][1].endswith(".") and "so‘rayman" in blocks[3][1]
    assert blocks[4][1].endswith(fields["arizachi"])
    assert "\t" in blocks[4][1]  # date left, signature and name right


def test_leave_and_job_dates_are_grammatical_and_checked():
    leave = sample("ariza_tatil")
    body = doctemplates.render("ariza_tatil", leave)[3][1]
    assert "2026-yil 20-oktabrdan boshlab 3 kalendar kun" in body
    assert "ish haqi saqlanmaydigan ta’til" in body
    assert "20.10.2026 dan" not in body
    job = sample("ariza_ishga")
    job["lavozim"] = "fizika fani o‘qituvchisi lavozimiga"
    body = doctemplates.render("ariza_ishga", job)[3][1]
    assert "2026-yil 1-noyabrdan" in body
    assert body.count("lavozimiga") == 1
    for value in ("31.02.2026", "2026-10-20", "bugun"):
        with pytest.raises(UserError, match="Sanani"):
            doctemplates.render("ariza_tatil", {**leave, "boshlanish": value})
    for value in ("0", "-2", "uch", "366"):
        with pytest.raises(UserError, match="Ta’til kunlari"):
            doctemplates.render("ariza_tatil", {**leave, "kunlar": value})


def test_missing_and_blank_fields_fail_without_inventing_data():
    fields = sample("ariza_umumiy")
    for key in fields:
        with pytest.raises(UserError, match="To‘ldiring"):
            doctemplates.render("ariza_umumiy", {**fields, key: None})
    with pytest.raises(UserError, match="maydonlari"):
        doctemplates.render("ariza_umumiy", None)


def test_general_application_keeps_user_request_and_safe_single_line_address():
    fields = sample("ariza_umumiy")
    fields["kimga"] = "Maktab\n direktori A. Karimovga"
    fields["murojaat"] = "Menga ma’lumotnoma berishingizni so‘rayman"
    blocks = doctemplates.render("ariza_umumiy", fields)
    assert blocks[0][1] == "Maktab direktori A. Karimovga"
    assert blocks[3][1] == "Menga ma’lumotnoma berishingizni so‘rayman."
