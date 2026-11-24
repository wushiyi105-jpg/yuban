import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from yuban import cli, llm, store

CV = os.path.join(os.path.dirname(__file__), "..", "samples", "第一篇.txt")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")

    def run_cli(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["--db", self.db] + argv)
        return code, buf.getvalue()

    def save(self, text, **kw):
        """测试里造数据用。连接必须关掉，不然 Windows 上会挂着文件句柄。"""
        conn = store.connect(self.db)
        try:
            return store.save_piece(conn, text, **kw)
        finally:
            conn.close()

    def pieces(self):
        conn = store.connect(self.db)
        try:
            return store.list_pieces(conn)
        finally:
            conn.close()

    def piece(self, pid):
        conn = store.connect(self.db)
        try:
            return store.get_piece(conn, pid)
        finally:
            conn.close()

    def test_check_file(self):
        code, out = self.run_cli(["check", CV])
        self.assertEqual(code, 0)
        self.assertIn("very like", out)
        self.assertIn("60 词", out)

    def test_check_inline_text(self):
        code, out = self.run_cli(["check", "I very like it."])
        self.assertIn("中式表达", out)

    def test_write_no_model(self):
        code, out = self.run_cli(["write", CV, "--no-model"])
        self.assertEqual(code, 0)
        self.assertIn("跳过了模型批改", out)
        self.assertEqual(len(self.pieces()), 1)

    def test_write_with_model(self):
        payload = json.dumps({"sentences": [], "rewrite": "fixed", "level": "B1",
                              "comment": "先改时态"}, ensure_ascii=False)
        with patch.object(llm, "chat", return_value=payload):
            code, out = self.run_cli(["write", CV, "--title", "周末"])
        self.assertEqual(code, 0)
        self.assertIn("已存为第 1 篇", out)
        self.assertEqual(self.piece(1)["level"], "B1")

    def test_write_model_down_still_saves_local(self):
        with patch.object(llm, "chat", side_effect=llm.LLMError("连不上")):
            code, out = self.run_cli(["write", CV])
        self.assertEqual(code, 0)
        self.assertIn("已存", out)
        self.assertEqual(len(self.pieces()), 1)

    def test_write_empty_text(self):
        code, out = self.run_cli(["write", "   "])
        self.assertEqual(code, 1)
        self.assertIn("没内容", out)

    def test_list_empty(self):
        code, out = self.run_cli(["list"])
        self.assertIn("还没有", out)

    def test_list_shows_titles(self):
        self.save("x", title="占位", created="x")
        code, out = self.run_cli(["list"])
        self.assertIn("占位", out)

    def test_show_existing(self):
        self.save("I very like it.", title="t",
                         local=[{"type": "中式表达", "span": "very like", "why": "别"}], created="x")
        code, out = self.run_cli(["show", "1"])
        self.assertEqual(code, 0)
        self.assertIn("规则/中式表达", out)

    def test_show_missing(self):
        code, out = self.run_cli(["show", "77"])
        self.assertEqual(code, 1)
        self.assertIn("没有第 77 篇", out)

    def test_rm(self):
        self.save("x", created="x")
        code, out = self.run_cli(["rm", "1"])
        self.assertIn("删掉了", out)

    def test_stats_empty(self):
        code, out = self.run_cli(["stats"])
        self.assertIn("还没有记录", out)

    def test_stats_after_write(self):
        self.run_cli(["write", CV, "--no-model"])
        code, out = self.run_cli(["stats"])
        self.assertIn("练习 1 篇", out)
        self.assertIn("最常被指出", out)

    def test_repeat_hint_after_three(self):
        payload = json.dumps({"sentences": [{"original": "I very like go there",
                                             "issues": [{"span": "very like", "type": "搭配",
                                                         "fixed": "really like", "why": "x"}]}],
                              "rewrite": "", "level": "B1", "comment": ""}, ensure_ascii=False)
        with patch.object(llm, "chat", return_value=payload):
            for _ in range(3):
                self.run_cli(["write", "I very like go there."])
        code, out = self.run_cli(["write", "I very like go there."])
        self.assertIn("累计最常被指出的", out)

    def test_parser_has_all_subcommands(self):
        p = cli.build_parser()
        names = p._subparsers._group_actions[0].choices
        for sub in ("check", "write", "list", "show", "rm", "stats", "serve"):
            self.assertIn(sub, names)


if __name__ == "__main__":
    unittest.main()

