"""空批次三处旁路的回归测试：表单必填、直打入口拒收、落库前不再自动起名。"""

import re

import pytest

import app as app_module
from app import app as flask_app
from blank_lot import (
    AUTO_PREFIX,
    accept_lot,
    allow_direct_api_blank,
    form_required_lot,
    is_autogen,
    normalize_lot,
)

BLANKS = ["", "   ", " \t\n "]


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        stmt = " ".join(sql.split()).upper()
        if stmt.startswith("SELECT * FROM CUPPINGS"):
            self._result = sorted(self.conn.rows, key=lambda r: r["id"], reverse=True)
        elif stmt.startswith("INSERT INTO CUPPINGS"):
            lot, aroma, taste, liquor, score, verdict, note, created_by = params
            row = {
                "id": len(self.conn.rows) + 1,
                "lot": lot,
                "aroma": aroma,
                "taste": taste,
                "liquor": liquor,
                "score": score,
                "verdict": verdict,
                "note": note,
                "created_by": created_by,
            }
            self.conn.rows.append(row)
            self._result = row
        else:
            raise AssertionError(f"未预期的 SQL: {sql}")

    def fetchall(self):
        return list(self._result)

    def fetchone(self):
        return self._result


class FakeConn:
    def __init__(self):
        self.rows = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, cursor_factory=None):
        return FakeCursor(self)

    def commit(self):
        self.committed = True


@pytest.fixture
def store(monkeypatch):
    conn = FakeConn()
    monkeypatch.setattr(app_module, "db", lambda: conn)
    return conn


@pytest.fixture
def client():
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


@pytest.fixture
def taster(client):
    login(client, "taster", "tea123456")
    return client


def submit(client, lot=None, aroma="7", taste="7", liquor="7", hx=False):
    form = {"aroma": aroma, "taste": taste, "liquor": liquor}
    if lot is not None:
        form["lot"] = lot
    headers = {"HX-Request": "true"} if hx else {}
    return client.post("/cuppings", data=form, headers=headers)


# ---- 守卫策略本身 ----

def test_accept_lot_rejects_blank():
    assert accept_lot(None) is False
    for blank in BLANKS:
        assert accept_lot(blank) is False


def test_accept_lot_allows_real_name():
    assert accept_lot("春茶-A") is True
    assert accept_lot("  春茶-A  ") is True


def test_normalize_never_autogens():
    for raw in [None, *BLANKS]:
        assert normalize_lot(raw) == ""
        assert not is_autogen(normalize_lot(raw))
    assert normalize_lot("  春茶-A  ") == "春茶-A"


def test_bypass_flags_closed():
    assert form_required_lot() is True
    assert allow_direct_api_blank() is False


# ---- 直打服务入口（绕过页面）----

@pytest.mark.parametrize("lot", BLANKS)
def test_direct_api_rejects_blank_lot(taster, store, lot):
    res = submit(taster, lot=lot)
    assert res.status_code == 400
    assert store.rows == []


def test_direct_api_rejects_missing_lot(taster, store):
    res = submit(taster)
    assert res.status_code == 400
    assert store.rows == []


@pytest.mark.parametrize("lot", BLANKS)
def test_htmx_submit_rejects_blank_lot(taster, store, lot):
    res = submit(taster, lot=lot, hx=True)
    assert res.status_code == 400
    assert store.rows == []


# ---- 合法名仍写入 ----

def test_valid_lot_written(taster, store):
    res = submit(taster, lot="秋茶-7")
    assert res.status_code == 302
    assert len(store.rows) == 1
    row = store.rows[0]
    assert row["lot"] == "秋茶-7"
    assert row["score"] == pytest.approx(7.0)
    assert row["verdict"] == "通过"


def test_valid_lot_trimmed_not_renamed(taster, store):
    res = submit(taster, lot="  秋茶-8  ", hx=True)
    assert res.status_code == 200
    assert store.rows[0]["lot"] == "秋茶-8"


# ---- 库中无系统生成名 ----

def test_no_autogen_names_in_store(taster, store):
    for lot in ["", "   ", "秋茶-7"]:
        submit(taster, lot=lot)
    assert len(store.rows) == 1
    for row in store.rows:
        assert row["lot"].strip() != ""
        assert not row["lot"].startswith(AUTO_PREFIX)
        assert not is_autogen(row["lot"])


# ---- 只读不能写 ----

def test_reader_cannot_write(client, store):
    login(client, "observer", "look123456")
    res = submit(client, lot="秋茶-7")
    assert res.status_code == 403
    assert store.rows == []


def test_anonymous_cannot_write(client, store):
    res = submit(client, lot="秋茶-7")
    assert res.status_code == 302
    assert store.rows == []


# ---- 页面表单同样收紧 ----

def test_form_marks_lot_required(taster, store):
    html = taster.get("/").get_data(as_text=True)
    tag = re.search(r"<input\b[^>]*\bname=\"lot\"[^>]*>", html)
    assert tag is not None
    assert "required" in tag.group(0)
