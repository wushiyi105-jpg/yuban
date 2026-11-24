import json
import unittest
from unittest.mock import patch

from yuban import llm, review


class LocateTest(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(review.locate("many photo", "We take many photo and eat"))

    def test_ignores_case_and_space(self):
        self.assertTrue(review.locate("Many  Photo", "we take many photo"))

    def test_ignores_punctuation(self):
        # 模型抄句子常把句号省掉，这不算「查不到出处」
        self.assertTrue(review.locate("Last weekend I like it", "Last weekend I like it."))

    def test_missing(self):
        self.assertFalse(review.locate("very like", "I really like it"))

    def test_empty_span(self):
        self.assertFalse(review.locate("", "anything"))


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.sents = ["I very like go there", "We take many photo"]

    def test_keeps_valid_issue(self):
        out, notes = review.verify(
            [{"original": "I very like go there",
              "issues": [{"span": "very like", "type": "搭配", "fixed": "really like", "why": "x"}]}],
            self.sents)
        self.assertEqual(len(out[0]["issues"]), 1)
        self.assertEqual(out[0]["issues"][0]["type"], "搭配")
        self.assertEqual(notes, [])

    def test_drops_span_not_in_text(self):
        out, notes = review.verify(
            [{"original": "I very like go there",
              "issues": [{"span": "very much like", "type": "搭配", "fixed": "", "why": ""}]}],
            self.sents)
        self.assertEqual(out[0]["issues"], [])
        self.assertIn("查不到出处", notes[0])

    def test_unknown_type_becomes_other(self):
        out, _ = review.verify(
            [{"original": "We take many photo",
              "issues": [{"span": "many photo", "type": "神秘类型", "fixed": "many photos", "why": ""}]}],
            self.sents)
        self.assertEqual(out[0]["issues"][0]["type"], "其他")

    def test_original_not_in_text_falls_back_by_order(self):
        out, notes = review.verify(
            [{"original": "完全不存在的句子", "issues": []},
             {"original": "We take many photo", "issues": []}],
            self.sents)
        self.assertEqual(out[0]["original"], "I very like go there")
        self.assertTrue(any("找不到" in n for n in notes))

    def test_empty_list(self):
        out, notes = review.verify([], self.sents)
        self.assertEqual(out, [])
        self.assertEqual(notes, [])

    def test_non_dict_items_skipped(self):
        out, _ = review.verify(["junk", None], self.sents)
        self.assertEqual(out, [])

    def test_flatten_value_wrapper(self):
        out, _ = review.verify(
            [{"original": {"value": "We take many photo"},
              "issues": [{"span": {"value": "many photo"}, "type": "单复数"}]}],
            self.sents)
        self.assertEqual(out[0]["original"], "We take many photo")
        self.assertEqual(out[0]["issues"][0]["span"], "many photo")


class ParseTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(review.parse('{"a":1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(review.parse('```json\n{"a":1}\n```'), {"a": 1})

    def test_with_preamble(self):
        self.assertEqual(review.parse('好的，结果如下：\n{"a":1}'), {"a": 1})

    def test_garbage(self):
        self.assertEqual(review.parse("模型挂了"), {})

    def test_empty(self):
        self.assertEqual(review.parse(""), {})

    def test_array_is_not_dict(self):
        self.assertEqual(review.parse("[1,2]"), {})


class ReviewTest(unittest.TestCase):
    def test_model_error(self):
        with patch.object(llm, "chat", side_effect=llm.LLMError("429")):
            r = review.review("I like it.", [])
        self.assertIn("429", r["error"])

    def test_not_json(self):
        with patch.object(llm, "chat", return_value="我不会 JSON"):
            r = review.review("I like it.", [])
        self.assertIn("不是 JSON", r["error"])

    def test_happy_path(self):
        payload = json.dumps({
            "sentences": [{"original": "I very like it.", "issues": [],
                           "rewrite": "I really like it."}],
            "rewrite": "I really like it.",
            "level": "a2",
            "comment": "先改搭配",
        }, ensure_ascii=False)
        with patch.object(llm, "chat", return_value=payload):
            r = review.review("I very like it.", [])
        self.assertEqual(r["level"], "A2")
        self.assertEqual(r["rewrite"], "I really like it.")
        self.assertEqual(r["comment"], "先改搭配")
        self.assertEqual(r["error"], "")

    def test_prompt_includes_local_issues(self):
        captured = {}

        def fake(msgs, max_tokens=1000):
            captured["prompt"] = msgs[-1]["content"]
            return "{}"

        with patch.object(llm, "chat", side_effect=fake):
            review.review("I very like it.", [{"type": "中式表达", "span": "very like", "why": "别这么写"}])
        self.assertIn("very like", captured["prompt"])
        self.assertIn("别这么写", captured["prompt"])

    def test_prompt_marks_no_local_issues(self):
        captured = {}

        def fake(msgs, max_tokens=1000):
            captured["prompt"] = msgs[-1]["content"]
            return "{}"

        with patch.object(llm, "chat", side_effect=fake):
            review.review("I like it.", [])
        self.assertIn("没查出问题", captured["prompt"])


class TotalTest(unittest.TestCase):
    def test_count(self):
        self.assertEqual(review.total_issues(
            {"sentences": [{"issues": [1, 2]}, {"issues": [3]}]}), 3)

    def test_empty(self):
        self.assertEqual(review.total_issues({}), 0)


class RenderTest(unittest.TestCase):
    def test_error_passthrough(self):
        self.assertEqual(review.render({"error": "模型没回"}), "模型没回")

    def test_body(self):
        text = review.render({
            "level": "B1", "comment": "时态最要紧",
            "sentences": [{"original": "We take photo", "rewrite": "We took photos",
                           "issues": [{"type": "时态", "span": "take", "fixed": "took", "why": "过去时"}]}],
            "rewrite": "We took photos", "notes": ["一处兜底"],
        })
        for piece in ("B1", "时态最要紧", "We take photo", "took", "过去时", "We took photos", "一处兜底"):
            self.assertIn(piece, text)

    def test_points_to_section(self):
        text = review.render({"sentences": [], "rewrite": "", "notes": []})
        self.assertIn("0 处问题", text)


if __name__ == "__main__":
    unittest.main()
