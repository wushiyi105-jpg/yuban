import os
import tempfile
import unittest

from yuban import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store.connect(os.path.join(self.tmp, "t.db"))

    def tearDown(self):
        self.conn.close()

    def test_save_and_get(self):
        pid = store.save_piece(self.conn, "I very like it.", title="第一篇",
                               local=[{"type": "中式表达", "span": "very like", "why": "别"}],
                               created="2026-11-25 10:00")
        piece = store.get_piece(self.conn, pid)
        self.assertEqual(piece["title"], "第一篇")
        self.assertEqual(piece["local_count"], 1)
        self.assertEqual(len(piece["issues"]), 1)
        self.assertEqual(piece["issues"][0]["source"], "local")

    def test_default_title_uses_text(self):
        pid = store.save_piece(self.conn, "Hello there, this is a paragraph.", created="x")
        self.assertIn("Hello", store.get_piece(self.conn, pid)["title"])

    def test_model_issues_counted_separately(self):
        pid = store.save_piece(
            self.conn, "text", sentences=[{"original": "text", "issues": [
                {"type": "时态", "span": "take", "why": "过去时"},
                {"type": "拼写", "span": "recieve", "why": "e 在 i 前"}]}],
            local=[{"type": "标点", "span": " ", "why": "双空格"}], created="x")
        piece = store.get_piece(self.conn, pid)
        self.assertEqual(piece["model_count"], 2)
        self.assertEqual(piece["local_count"], 1)
        self.assertEqual(len(piece["issues"]), 3)

    def test_get_missing(self):
        self.assertIsNone(store.get_piece(self.conn, 999))

    def test_list_newest_first(self):
        a = store.save_piece(self.conn, "one", title="a", created="x")
        b = store.save_piece(self.conn, "two", title="b", created="x")
        self.assertEqual([r["id"] for r in store.list_pieces(self.conn)][:2], [b, a])

    def test_delete_cascades(self):
        pid = store.save_piece(self.conn, "x", local=[{"type": "拼写", "span": "teh", "why": ""}],
                               created="x")
        self.assertTrue(store.delete_piece(self.conn, pid))
        n = self.conn.execute("SELECT COUNT(*) FROM issues WHERE piece_id=?", (pid,)).fetchone()[0]
        self.assertEqual(n, 0)

    def test_delete_missing(self):
        self.assertFalse(store.delete_piece(self.conn, 12345))

    def test_by_type(self):
        store.save_piece(self.conn, "x", local=[{"type": "拼写", "span": "teh", "why": ""}], created="x")
        store.save_piece(self.conn, "y", local=[{"type": "拼写", "span": "alot", "why": ""}], created="x")
        rows = store.by_type(self.conn)
        self.assertEqual(rows[0]["type"], "拼写")
        self.assertEqual(rows[0]["n"], 2)

    def test_top_types_merges_sources(self):
        store.save_piece(self.conn, "x", local=[{"type": "标点", "span": " ", "why": ""}], created="x")
        store.save_piece(self.conn, "y", sentences=[{"original": "y", "issues": [
            {"type": "标点", "span": ".", "why": ""}]}], created="x")
        self.assertEqual(store.top_types(self.conn, 1)[0]["type"], "标点")

    def test_top_types_limit(self):
        for t in ("拼写", "标点", "时态", "冠词"):
            store.save_piece(self.conn, t, local=[{"type": t, "span": "w", "why": ""}], created="x")
        self.assertEqual(len(store.top_types(self.conn, 2)), 2)

    def test_stats_empty(self):
        s = store.stats(self.conn)
        self.assertEqual(s["pieces"], 0)
        self.assertEqual(s["issues"], 0)

    def test_stats_counts(self):
        store.save_piece(self.conn, "x", local=[{"type": "拼写", "span": "teh", "why": ""}], created="x")
        store.save_piece(self.conn, "y", local=[{"type": "拼写", "span": "teh", "why": ""}], created="x")
        s = store.stats(self.conn)
        self.assertEqual(s["pieces"], 2)
        self.assertEqual(s["issues"], 2)
        self.assertEqual(s["distinct_spans"], 1)
        self.assertEqual(s["top"][0]["type"], "拼写")

    def test_sentences_roundtrip_bad_json(self):
        pid = store.save_piece(self.conn, "x", created="x")
        self.conn.execute("UPDATE pieces SET sentences='不是JSON' WHERE id=?", (pid,))
        self.conn.commit()
        self.assertEqual(store.get_piece(self.conn, pid)["sentences"], [])

    def test_reopen_keeps_data(self):
        path = os.path.join(self.tmp, "t.db")
        store.save_piece(self.conn, "abc", title="keep", created="x")
        c2 = store.connect(path)
        self.assertEqual(len(store.list_pieces(c2)), 1)
        c2.close()

    def test_dir_created(self):
        p = os.path.join(self.tmp, "deep", "nested", "t.db")
        c = store.connect(p)
        self.assertTrue(os.path.exists(p))
        c.close()


if __name__ == "__main__":
    unittest.main()
