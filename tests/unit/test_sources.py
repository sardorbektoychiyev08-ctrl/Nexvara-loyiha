"""Textbook sources without network: page parsing, file filtering, a fake Telegram client."""

from types import SimpleNamespace

import pytest

from nexvara.sources import eduportal
from nexvara.sources.telegram_rtm import TelegramRtm, grade_of, is_uzbek_textbook, safe_name

# ---------- eduportal ----------


def test_eduportal_page_parsing_takes_grade_from_path():
    html = (
        '<a href="../../Umumiyfiles/darsliklar/1/alifbe_1_uzb.pdf">a</a>'
        '<a href="../../Umumiyfiles/darsliklar/1/alifbe_1_rus.pdf">b</a>'
        '<a href="../../Umumiyfiles/darsliklar/10/adabiyot_2qism_10_uzb.pdf">c</a>'
    )
    books = eduportal.parse_page(html)
    assert [(b.grade, b.name) for b in books] == [
        (1, "alifbe_1_uzb.pdf"),
        (10, "adabiyot_2qism_10_uzb.pdf"),
    ]
    assert books[0].url == "http://eduportal.uz/Umumiyfiles/darsliklar/1/alifbe_1_uzb.pdf"


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        out, self.body = (self.body, b"") if n < 0 else (self.body[:n], self.body[n:])
        return out


class FakeOpener:
    def __init__(self, bodies):
        self.bodies = bodies
        self.calls = []

    def open(self, url, timeout=0):
        self.calls.append(url)
        body = self.bodies[url]
        if isinstance(body, Exception):
            raise body
        return FakeResponse(body)


def test_eduportal_download_is_resumable_and_checks_pdf(tmp_path):
    good = eduportal.RemoteBook(7, "fizika_7_uzb.pdf", "uzb")
    html = eduportal.RemoteBook(7, "kimyo_7_uzb.pdf", "uzb")
    opener = FakeOpener({good.url: b"%PDF-1.4 data", html.url: b"<html>error</html>"})
    rep = eduportal.download_all(tmp_path, [good, html], opener=opener, retries=1)
    assert rep.downloaded == ["fizika_7_uzb.pdf"] and len(rep.failed) == 1
    assert (tmp_path / "eduportal" / "7-sinf" / "fizika_7_uzb.pdf").read_bytes().startswith(b"%PDF")
    assert not list(tmp_path.rglob("*.part"))
    rep2 = eduportal.download_all(tmp_path, [good], opener=opener)
    assert rep2.skipped == ["fizika_7_uzb.pdf"] and opener.calls.count(good.url) == 1


# ---------- Telegram filter ----------

UZB_SCHOOLS = "Ta’lim o‘zbek tilida olib boriladigan maktablar uchun"


@pytest.mark.parametrize(
    ("name", "caption", "ok"),
    [
        ("Algebra_7-sinf_2-CH_uzb.pdf", "", True),
        ("Geometriya 10-sinf_2-CH_uzb.pdf", "", True),
        ("Algebra_7-sinf_2-CH_qardosh.zip", "", False),
        ("Rus_tili_6-sinf_2-CH.pdf", "", False),
        ("Literatura_7-sinf_2-CH.pdf", "", False),
        ("10 DHA-Dastur.doc", "", False),
        ("Huquq 10-sinf. 01. 09. 23.pdf", UZB_SCHOOLS, True),
        ("Huquq.pdf", UZB_SCHOOLS, False),  # no grade
    ],
)  # fmt: skip
def test_uzbek_textbook_filter(name, caption, ok):
    assert is_uzbek_textbook(name, caption) is ok


def test_grade_and_safe_name():
    assert grade_of("Algebra_7-sinf_2-CH_uzb.pdf") == 7
    assert grade_of("x.pdf", "10-sinf uchun") == 10
    assert safe_name("a:b/c?.pdf") == "a_b_c_.pdf"


# ---------- Telegram flow with a fake client ----------


class FakeClient:
    def __init__(self, session, api_id, api_hash):
        self.connected = False
        self.authorized = False
        self.messages = []

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return self.authorized

    async def send_code_request(self, phone):
        return SimpleNamespace(phone_code_hash="hash-1")

    async def sign_in(self, phone=None, code=None, phone_code_hash=None, password=None):
        assert phone_code_hash == "hash-1" and code == "12345"
        self.authorized = True

    async def iter_messages(self, channel, filter=None):
        for m in self.messages:
            yield m


def message(name, body, caption=""):
    async def download_media(file):
        with open(file, "wb") as f:
            f.write(body)

    return SimpleNamespace(
        file=SimpleNamespace(name=name, size=len(body)),
        message=caption,
        download_media=download_media,
    )


def test_telegram_login_and_download(tmp_path):
    clients = []

    def factory(*args):
        clients.append(FakeClient(*args))
        return clients[-1]

    tg = TelegramRtm(tmp_path, client_factory=factory)
    assert tg.status() == {"configured": False, "authorized": False}
    with pytest.raises(ValueError):
        tg.save_api("123", "not-a-hash")
    tg.save_api("123", "0123456789abcdef0123456789abcdef")
    assert tg.status() == {"configured": True, "authorized": False}
    with pytest.raises(ValueError):
        tg.send_code("abc")
    tg.send_code("+998 90 123 45 67")
    tg.sign_in("12345")
    assert tg.status()["authorized"] is True

    clients[0].messages = [
        message("Algebra_7-sinf_2-CH_uzb.pdf", b"%PDF-1.7 algebra"),
        message("Rus_tili_7-sinf_2-CH.pdf", b"%PDF-1.7 rus"),
        message("Fizika_8-sinf_1-CH_uzb.pdf", b"<html>not a pdf</html>"),
    ]
    rep = tg.download(tmp_path / "Darsliklar")
    assert rep.downloaded == ["Algebra_7-sinf_2-CH_uzb.pdf"]
    assert rep.ignored == 1 and len(rep.failed) == 1
    assert (tmp_path / "Darsliklar" / "rtm" / "7-sinf" / "Algebra_7-sinf_2-CH_uzb.pdf").is_file()
    rep2 = tg.download(tmp_path / "Darsliklar")
    assert rep2.skipped == ["Algebra_7-sinf_2-CH_uzb.pdf"] and not rep2.downloaded
