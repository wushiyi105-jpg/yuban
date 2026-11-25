"""命令行入口。"""

from __future__ import annotations

import argparse
import os
from datetime import datetime

from . import checks, review, store

_OPENED: list = []


def _open(args):
    conn = store.connect(args.db)
    _OPENED.append(conn)
    return conn


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def cmd_check(args) -> int:
    text = _read(args.file) if os.path.isfile(args.file) else args.file
    local = checks.issues(text)
    print(checks.summary(text))
    if not local:
        print("\n本地规则没查出问题。")
    else:
        print(f"\n本地规则查出 {len(local)} 处：")
        for it in local:
            print(f"  [{it['type']}] {it['span']} —— {it['why']}")
    return 0


def cmd_write(args) -> int:
    conn = _open(args)
    text = _read(args.file) if os.path.isfile(args.file) else args.file
    if not text.strip():
        print("✗ 没内容")
        return 1

    local = checks.issues(text)
    print(checks.summary(text))
    if local:
        print(f"\n规则先查出 {len(local)} 处：")
        for it in local:
            print(f"  [{it['type']}] {it['span']} —— {it['why']}")

    if args.no_model:
        store.save_piece(conn, text, title=args.title or "", local=local, created=_now())
        print("\n（跳过了模型批改，只记录了规则结果）")
        return 0

    print("\n等模型看一遍……")
    result = review.review(text, local, args.level or "")
    if result["error"]:
        print(f"✗ {result['error']}")
        store.save_piece(conn, text, title=args.title or "", local=local, created=_now())
        print("（本地结果已存，模型部分留空）")
        return 0

    print("\n" + review.render(result))
    pid = store.save_piece(
        conn, text, title=args.title or "", level=result["level"],
        comment=result["comment"], rewrite=result["rewrite"],
        sentences=result["sentences"], local=local, created=_now())
    print(f"\n· 已存为第 {pid} 篇")

    top = store.top_types(conn, 3)
    if top and top[0]["n"] >= 3:
        bits = "、".join("{} {} 次".format(t["type"], t["n"]) for t in top)
        print(f"· 累计最常被指出的：{bits}")
    return 0


def cmd_list(args) -> int:
    conn = _open(args)
    rows = store.list_pieces(conn)
    if not rows:
        print("还没有练习记录。用 `write` 录第一篇。")
        return 0
    print(f"{'ID':>3}  {'词数':>5}  {'本地':>4} {'模型':>4}  水平   标题")
    for r in rows:
        print(f"{r['id']:>3}  {r['chars']:>5}  {r['local_count']:>4} {r['model_count']:>4}"
              f"  {r['level'] or '-':<5} {r['title'][:40]}")
    return 0


def cmd_show(args) -> int:
    conn = _open(args)
    piece = store.get_piece(conn, args.id)
    if not piece:
        print(f"✗ 没有第 {args.id} 篇")
        return 1
    print(f"=== [{piece['id']}] {piece['title']} · {piece['created']} ===")
    print(piece["text"].strip())
    print(f"\n水平：{piece['level'] or '-'}")
    if piece["comment"]:
        print(piece["comment"])
    if piece["issues"]:
        print(f"\n问题 {len(piece['issues'])} 处：")
        for it in piece["issues"]:
            src = "规则" if it["source"] == "local" else "模型"
            print(f"  [{src}/{it['type']}] {it['span']} —— {it['why']}")
    if piece["rewrite"]:
        print("\n改写：")
        print(piece["rewrite"])
    return 0


def cmd_rm(args) -> int:
    conn = _open(args)
    print("· 删掉了" if store.delete_piece(conn, args.id) else "✗ 没有这篇")
    return 0


def cmd_stats(args) -> int:
    conn = _open(args)
    s = store.stats(conn)
    if not s["pieces"]:
        print("还没有记录。")
        return 0
    print(f"练习 {s['pieces']} 篇 · 被指出 {s['issues']} 处 · 涉及 {s['types']} 类问题")
    print(f"同一处反复犯的有 {s['distinct_spans']} 个")
    if s["top"]:
        print("\n最常被指出：")
        for t in s["top"]:
            print(f"  {t['type']} {t['n']} 次")
    if s["recent"]:
        print("\n最近 30 天：")
        for t in s["recent"]:
            print(f"  {t['type']} {t['n']} 次")
    return 0


def cmd_serve(args) -> int:
    from . import web
    conn = store.connect(args.db)
    srv = web.make_server(conn, port=args.port, db=args.db)
    host, port = srv.server_address
    print(f"语伴已起在 http://127.0.0.1:{port}")
    print("Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n停了")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yuban", description="英语写作陪练：规则查硬错，模型看语感")
    p.add_argument("--db", default="data/yuban.db")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="只跑本地规则，不调模型")
    c.add_argument("file", help="文件路径，或直接给一段文字")
    c.set_defaults(func=cmd_check)

    w = sub.add_parser("write", help="录一篇，规则检查 + 模型批改")
    w.add_argument("file")
    w.add_argument("--title", default="")
    w.add_argument("--level", default="", help="自评水平，如 B1")
    w.add_argument("--no-model", action="store_true", help="只跑规则")
    w.set_defaults(func=cmd_write)

    sub.add_parser("list", help="所有练习").set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="看某一篇")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_show)

    r = sub.add_parser("rm", help="删一篇")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rm)

    sub.add_parser("stats", help="常犯错误统计").set_defaults(func=cmd_stats)

    v = sub.add_parser("serve", help="起网页")
    v.add_argument("--port", type=int, default=8775)
    v.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    finally:
        while _OPENED:
            try:
                _OPENED.pop().close()
            except Exception:  # noqa: BLE001
                pass
