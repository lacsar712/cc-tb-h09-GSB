"""测试基座：默认用内存 SQLite 替身跑真实 Flask 路由与落库路径；
设置 TEST_DATABASE_URL 时改打真实 PostgreSQL（如 docker compose 起的库）。"""

import os
import sqlite3
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS cuppings (
    id serial PRIMARY KEY,
    lot text NOT NULL,
    aroma double precision NOT NULL,
    taste double precision NOT NULL,
    liquor double precision NOT NULL,
    score double precision NOT NULL,
    verdict text NOT NULL,
    note text NOT NULL,
    created_by text NOT NULL
)
"""

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS cuppings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot TEXT NOT NULL,
    aroma REAL NOT NULL,
    taste REAL NOT NULL,
    liquor REAL NOT NULL,
    score REAL NOT NULL,
    verdict TEXT NOT NULL,
    note TEXT NOT NULL,
    created_by TEXT NOT NULL
)
"""


class _SqliteCursor:
    """把 psycopg2 的 %s 占位翻译成 sqlite 的 ?，其余透传。"""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        self._raw.execute(sql.replace("%s", "?"), tuple(params))
        return self

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._raw.close()
        return False


class _SqliteConn:
    """模拟 psycopg2 连接的上下文管理语义（提交/回滚，不关闭共享连接）。"""

    def __init__(self, shared):
        self._shared = shared

    def cursor(self, cursor_factory=None):
        return _SqliteCursor(self._shared.cursor())

    def commit(self):
        self._shared.commit()

    def close(self):  # 共享连接由夹具统一管理
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._shared.commit()
        else:
            self._shared.rollback()
        return False


class Harness:
    def __init__(self, client, connect):
        self.client = client
        self._connect = connect

    def login(self, username, password):
        return self.client.post(
            "/login", data={"username": username, "password": password}
        )

    def rows(self):
        from psycopg2.extras import RealDictCursor

        conn = self._connect()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM cuppings ORDER BY id")
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def lots(self):
        return [row["lot"] for row in self.rows()]


@pytest.fixture()
def harness(monkeypatch):
    pg_url = os.environ.get("TEST_DATABASE_URL")
    if pg_url:
        os.environ["DATABASE_URL"] = pg_url
    else:
        os.environ.pop("DATABASE_URL", None)

    import app as app_module

    if pg_url:
        import psycopg2

        admin = psycopg2.connect(pg_url)
        with admin.cursor() as cur:
            cur.execute(PG_SCHEMA)
            cur.execute("DELETE FROM cuppings")
        admin.commit()
        admin.close()
        connect = lambda: psycopg2.connect(pg_url)  # noqa: E731
    else:
        shared = sqlite3.connect(":memory:", check_same_thread=False)
        shared.row_factory = sqlite3.Row
        shared.execute(SQLITE_SCHEMA)
        shared.commit()
        monkeypatch.setattr(app_module, "db", lambda: _SqliteConn(shared))
        connect = lambda: _SqliteConn(shared)  # noqa: E731

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield Harness(client, connect)
