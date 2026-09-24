"""空批次三条放行路径（表单校验、直打入口、落库前自动起名）全部掐断的回归测试。

覆盖：空串、纯空白、合法批次名；断言库中绝无系统生成名；只读角色不能写。
"""

import re

import pytest

from blank_lot import (
    AUTO_PREFIX,
    accept_lot,
    allow_direct_api_blank,
    form_required_lot,
    is_autogen,
    normalize_lot,
)

BLANKS = ["", " ", "   ", "\t", "\n", " \t \n ", "　　　"]  # 含全角空格
LEGAL_LOT = "秋茶-7"
SEVENS = {"aroma": "7", "taste": "7", "liquor": "7"}


# ---------- 守卫函数本身 ----------


@pytest.mark.parametrize("raw", BLANKS + [None])
def test_accept_lot_rejects_blank(raw):
    assert accept_lot(raw) is False


def test_accept_lot_accepts_legal_name():
    assert accept_lot(LEGAL_LOT) is True
    assert accept_lot(" 秋茶-7 ") is True


@pytest.mark.parametrize("raw", BLANKS + [None])
def test_normalize_lot_blank_raises_instead_of_autogen(raw):
    with pytest.raises(ValueError):
        normalize_lot(raw)


def test_normalize_lot_strips_but_never_autogens():
    assert normalize_lot(" 秋茶-7 ") == LEGAL_LOT
    assert not is_autogen(normalize_lot(LEGAL_LOT))


def test_guard_switches_closed():
    assert form_required_lot() is True
    assert allow_direct_api_blank() is False


# ---------- 直打服务入口（绕过页面） ----------


@pytest.mark.parametrize("lot", BLANKS)
def test_direct_post_blank_lot_rejected(harness, lot):
    harness.login("taster", "tea123456")
    res = harness.client.post("/cuppings", data={"lot": lot, **SEVENS})
    assert res.status_code == 400
    assert harness.rows() == []


def test_direct_post_missing_lot_rejected(harness):
    harness.login("taster", "tea123456")
    res = harness.client.post("/cuppings", data=SEVENS)
    assert res.status_code == 400
    assert harness.rows() == []


def test_legal_lot_with_sevens_is_written(harness):
    harness.login("taster", "tea123456")
    res = harness.client.post("/cuppings", data={"lot": LEGAL_LOT, **SEVENS})
    assert res.status_code in (200, 302)
    rows = harness.rows()
    assert len(rows) == 1
    assert rows[0]["lot"] == LEGAL_LOT
    assert rows[0]["score"] == 7.0
    assert rows[0]["verdict"] == "通过"


def test_legal_lot_written_via_page_submit(harness):
    harness.login("taster", "tea123456")
    res = harness.client.post(
        "/cuppings",
        data={"lot": LEGAL_LOT, **SEVENS},
        headers={"HX-Request": "true"},
    )
    assert res.status_code == 200
    assert LEGAL_LOT in res.get_data(as_text=True)
    assert harness.lots() == [LEGAL_LOT]


def test_no_autogen_names_in_db(harness):
    harness.login("taster", "tea123456")
    for lot in BLANKS:
        harness.client.post("/cuppings", data={"lot": lot, "aroma": "9", "taste": "9", "liquor": "9"})
    harness.client.post("/cuppings", data={"lot": LEGAL_LOT, **SEVENS})
    lots = harness.lots()
    assert lots == [LEGAL_LOT]
    assert all(not is_autogen(lot) for lot in lots)
    assert all(not str(lot).startswith(AUTO_PREFIX) for lot in lots)


# ---------- 只读不能写 ----------


def test_reader_cannot_write(harness):
    harness.login("observer", "look123456")
    res = harness.client.post("/cuppings", data={"lot": LEGAL_LOT, **SEVENS})
    assert res.status_code == 403
    assert harness.rows() == []


def test_anonymous_cannot_write(harness):
    res = harness.client.post("/cuppings", data={"lot": LEGAL_LOT, **SEVENS})
    assert res.status_code in (302, 401)
    assert harness.rows() == []


# ---------- 网页表单校验层 ----------


def test_form_marks_lot_required(harness):
    harness.login("taster", "tea123456")
    html = harness.client.get("/").get_data(as_text=True)
    assert re.search(r'<input[^>]*name="lot"[^>]*required', html)


def test_reader_has_no_submit_form(harness):
    harness.login("observer", "look123456")
    html = harness.client.get("/").get_data(as_text=True)
    assert "<form" not in html
