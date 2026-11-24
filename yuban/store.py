"""练习记录的存储：每篇一段正文 + 批改结果 + 每条问题都单独入表。

问题单独入表是为了统计——单个「这篇错了 7 处」没用，
「你三个月里被指出 11 次时态问题」才有用。
"""

from __future__ import annotations

import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS pieces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    rewrite TEXT NOT NULL DEFAULT '',
    sentences TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    local_count INTEGER NOT NULL DEFAULT 0,
    model_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    piece_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    span TEXT NOT NULL DEFAULT '',
    why TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'model',
    created TEXT NOT NULL,
    FOREIGN KEY (piece_id) REFERENCES pieces(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_issues_piece ON issues(piece_id);
"""


def connect(path: str = "data/yuban.db") -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # 网页是多线程的：每个请求一个线程，共用一个连接，所以必须关掉线程检查并自己加锁。
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def save_piece(conn, text, title="", level="", comment="", rewrite="",
               sentences=None, local=None, model=None, created="") -> int:
    sentences = sentences or []
    local = local or []
    model = model or []
    cur = conn.execute(
        "INSERT INTO pieces (title, text, level, comment, rewrite, sentences, created, local_count, model_count)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (title or text.strip()[:24], text, level, comment, rewrite,
         json.dumps(sentences, ensure_ascii=False), created, len(local),
         sum(len(s.get("issues") or []) for s in sentences)),
    )
    pid = cur.lastrowid
    for it in local:
        conn.execute("INSERT INTO issues (piece_id, type, span, why, source, created) VALUES (?,?,?,?,?,?)",
                     (pid, it.get("type", "其他"), it.get("span", ""), it.get("why", ""), "local", created))
    for s in sentences:
        for iss in s.get("issues") or []:
            conn.execute("INSERT INTO issues (piece_id, type, span, why, source, created) VALUES (?,?,?,?,?,?)",
                         (pid, iss.get("type", "其他"), iss.get("span", ""), iss.get("why", ""), "model", created))
    conn.commit()
    return pid


def get_piece(conn, pid: int) -> dict | None:
    row = conn.execute("SELECT * FROM pieces WHERE id=?", (pid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["sentences"] = json.loads(d.get("sentences") or "[]")
    except json.JSONDecodeError:
        d["sentences"] = []
    d["issues"] = [dict(r) for r in conn.execute(
        "SELECT type, span, why, source FROM issues WHERE piece_id=? ORDER BY id", (pid,))]
    return d


def list_pieces(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, title, level, created, local_count, model_count,"
        " length(text) AS chars FROM pieces ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def delete_piece(conn, pid: int) -> bool:
    cur = conn.execute("DELETE FROM pieces WHERE id=?", (pid,))
    conn.commit()
    return cur.rowcount > 0


def by_type(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT type, source, COUNT(*) AS n FROM issues GROUP BY type, source ORDER BY n DESC").fetchall()
    return [dict(r) for r in rows]


def top_types(conn, n: int = 3) -> list[dict]:
    """跨所有练习，被指出最多的错误类型。本地与模型合并计数。"""
    rows = conn.execute(
        "SELECT type, COUNT(*) AS n FROM issues GROUP BY type ORDER BY n DESC, type LIMIT ?",
        (n,)).fetchall()
    return [dict(r) for r in rows]


def stats(conn) -> dict:
    pieces = conn.execute("SELECT COUNT(*) AS n FROM pieces").fetchone()["n"]
    issues = conn.execute("SELECT COUNT(*) AS n FROM issues").fetchone()["n"]
    spans = conn.execute("SELECT COUNT(DISTINCT span) AS n FROM issues WHERE span <> ''").fetchone()["n"]
    recent = conn.execute(
        "SELECT type, COUNT(*) AS n FROM issues WHERE created >= date('now', '-30 day')"
        " GROUP BY type ORDER BY n DESC LIMIT 3").fetchall()
    return {
        "pieces": pieces,
        "issues": issues,
        "distinct_spans": spans,
        "types": len(conn.execute("SELECT DISTINCT type FROM issues").fetchall()),
        "top": top_types(conn, 3),
        "recent": [dict(r) for r in recent],
    }
