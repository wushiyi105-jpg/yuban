import json
import os
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch

from yuban import llm, store, web

CV = os.path.join(os.path.dirname(__file__), "..", "samples", "第一篇.txt")

PAYLOAD = {
    "sentences": [{"original": "I very like it.", "issues": [], "rewrite": "I really like it."}],
    "rewrite": "I really like it.",
    "level": "B1",
    "comment": "先改搭配",
}


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store.connect(os.path.join(self.tmp, "t.db"))
        self.srv = web.make_server(self.conn, port=0)
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.t.join(timeout=3)
        self.conn.close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.read().decode("utf-8")

    def post(self, path, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_index(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("语伴", body)
        self.assertIn("/api/review", body)

    def test_list_empty(self):
        status, body = self.get("/api/list")
        d = json.loads(body)
        self.assertEqual(d["pieces"], [])

    def test_check(self):
        status, body = self.post("/api/check", {"text": "I very like a apple."})
        self.assertEqual(status, 200)
        d = json.loads(body)
        types = {i["type"] for i in d["issues"]}
        self.assertIn("中式表达", types)
        self.assertIn("冠词", types)
        self.assertIn("5 词", d["summary"])

    def test_check_empty(self):
        status, body = self.post("/api/check", {"text": "  "})
        self.assertEqual(status, 400)

    def test_check_bad_json(self):
        req = urllib.request.Request(self.base + "/api/check", data=b"not json",
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_review_saves(self):
        with patch.object(llm, "chat", return_value=json.dumps(PAYLOAD, ensure_ascii=False)):
            status, body = self.post("/api/review", {"text": "I very like it.", "level": "B1"})
        self.assertEqual(status, 200)
        d = json.loads(body)
        self.assertEqual(d["review"]["level"], "B1")
        self.assertIn("piece_id", d)
        self.assertEqual(len(store.list_pieces(self.conn)), 1)

    def test_review_model_down(self):
        with patch.object(llm, "chat", side_effect=llm.LLMError("429")):
            status, body = self.post("/api/review", {"text": "I very like it."})
        self.assertEqual(status, 502)
        d = json.loads(body)
        self.assertIn("429", d["review"]["error"])
        self.assertEqual(len(store.list_pieces(self.conn)), 0)

    def test_unknown_get(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/api/nope")
        self.assertEqual(cm.exception.code, 404)

    def test_unknown_post(self):
        status, _ = self.post("/api/nope", {})
        self.assertEqual(status, 404)

    def test_list_after_save(self):
        with patch.object(llm, "chat", return_value=json.dumps(PAYLOAD, ensure_ascii=False)):
            self.post("/api/review", {"text": "I very like it."})
        status, body = self.get("/api/list")
        self.assertEqual(len(json.loads(body)["pieces"]), 1)


if __name__ == "__main__":
    unittest.main()

