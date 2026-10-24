"""Excel dashboard from the user's own table (no Office needed for the table logic)."""

from __future__ import annotations

import pytest

from nexvara.core.task import UserError
from nexvara.skills.excel.userdash import expected, split_table


def test_table_is_split_into_category_and_numbers_and_total_row_dropped():
    values = [
        ["Mahsulot", "Soni", "Narxi", "Jami"],
        ["Daftar", 10, 5000, 50000],
        ["Ruchka", 20, 3000, 60000],
        ["Daftar", 5, 5000, 25000],
        ["Jami", 35, None, 135000],
    ]
    headers, body, cat, nums = split_table(values)
    assert headers[cat] == "Mahsulot" and [headers[c] for c in nums] == ["Soni", "Narxi", "Jami"]
    assert len(body) == 3  # the «Jami» row is not data
    exp = expected(body, cat, nums)
    assert exp["totals"][3] == 135000 and exp["groups"]["Daftar"][3] == 75000


def test_table_without_numbers_is_refused():
    with pytest.raises(UserError):
        split_table([["Ism", "Sinf"], ["Ali", "7-A"], ["Vali", "7-B"]])
