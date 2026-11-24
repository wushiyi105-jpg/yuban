import unittest

from yuban import checks


class StatsTest(unittest.TestCase):
    def test_words_and_sentences(self):
        s = checks.stats("I like it. You too! Do you?")
        self.assertEqual(s["words"], 7)
        self.assertEqual(s["sentences"], 3)

    def test_empty(self):
        s = checks.stats("")
        self.assertEqual(s["words"], 0)
        self.assertEqual(s["avg_sentence"], 0.0)

    def test_avg_and_longest(self):
        s = checks.stats("One two three. Four five.")
        self.assertEqual(s["avg_sentence"], 2.5)
        self.assertEqual(s["longest_sentence"], 3)

    def test_long_word_ratio(self):
        s = checks.stats("international cooperation is good")
        self.assertGreater(s["long_word_ratio"], 0.4)

    def test_unique_ratio_repeats(self):
        s = checks.stats("the the the the")
        self.assertLess(s["unique_ratio"], 0.3)


class SentencesTest(unittest.TestCase):
    def test_split_keeps_order(self):
        self.assertEqual(checks.sentences("A b. C d!\nE f?"), ["A b", "C d", "E f"])

    def test_blank_lines_dropped(self):
        self.assertEqual(checks.sentences("one.\n\n\ntwo."), ["one", "two"])


class ArticleTest(unittest.TestCase):
    def test_a_before_vowel(self):
        out = checks.issues("I ate a apple.")
        self.assertTrue(any(i["type"] == "冠词" for i in out))

    def test_an_before_consonant(self):
        out = checks.issues("He is an teacher.")
        self.assertTrue(any(i["type"] == "冠词" for i in out))

    def test_correct_article_silent(self):
        self.assertEqual(checks.issues("I ate an apple."), [])

    def test_university_is_a(self):
        # 拼写以 u 开头但读音是辅音
        self.assertFalse(any(i["type"] == "冠词" for i in checks.issues("a university")))

    def test_hour_is_an(self):
        self.assertFalse(any(i["type"] == "冠词" for i in checks.issues("an hour ago")))


class ChinglishTest(unittest.TestCase):
    def test_very_like(self):
        out = checks.issues("I very like music.")
        self.assertTrue(any("very like" in i["span"].lower() for i in out))

    def test_case_insensitive_span_keeps_original(self):
        out = checks.issues("Very Like music.")
        span = [i["span"] for i in out if i["type"] == "中式表达"][0]
        self.assertEqual(span, "Very Like")

    def test_how_to_say(self):
        self.assertTrue(any(i["type"] == "中式表达" for i in checks.issues("How to say, I agree")))

    def test_clean_sentence_no_false_positive(self):
        self.assertEqual(checks.issues("I really like music."), [])


class SpellingTest(unittest.TestCase):
    def test_recieve(self):
        out = checks.issues("I will recieve it.")
        self.assertTrue(any(i["type"] == "拼写" and i["span"] == "recieve" for i in out))

    def test_receive_ok(self):
        self.assertEqual(checks.issues("I will receive it."), [])


class PunctuationTest(unittest.TestCase):
    def test_chinese_char(self):
        self.assertTrue(any(i["type"] == "标点" for i in checks.issues("I like it 很 much")))

    def test_double_space(self):
        self.assertTrue(any(i["type"] == "标点" for i in checks.issues("I  like it")))

    def test_no_final_punct(self):
        self.assertTrue(any("最后一句" in i["why"] for i in checks.issues("I like it")))

    def test_final_punct_ok(self):
        self.assertEqual(checks.issues("I like it."), [])

    def test_repeated_exclamation(self):
        self.assertTrue(any(i["type"] == "标点" for i in checks.issues("Wow!! So good.")))


class RepeatTest(unittest.TestCase):
    def test_word_repeated_four_times(self):
        out = checks.issues("Museum museum museum museum is big.")
        self.assertTrue(any(i["type"] == "重复" for i in out))

    def test_common_word_not_flagged(self):
        out = checks.issues("the the the the is big.")
        self.assertFalse(any(i["type"] == "重复" for i in out))


class GroupTest(unittest.TestCase):
    def test_group_by_type(self):
        out = checks.group(checks.issues("I very like a apple."))
        self.assertIn("中式表达", out)
        self.assertIn("冠词", out)


class SummaryTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(checks.summary(""), "还没写东西")

    def test_long_sentence_hint(self):
        text = " ".join(["word"] * 30) + "."
        self.assertIn("偏长", checks.summary(text))

    def test_short_sentence_hint(self):
        self.assertIn("偏短", checks.summary("Go. Run. Sit. Eat."))


if __name__ == "__main__":
    unittest.main()


