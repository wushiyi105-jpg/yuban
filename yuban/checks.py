"""本地能算的那部分：词数、句长、重复、a/an、常见错拼、中式表达、标点。

这些不需要模型。模型会漏，也会编；本地规则不会编，但只认它见过的东西。
两层叠在一起才够用：规则抓「必须有答案的」，模型抓「读懂才知道的」。
"""

from __future__ import annotations

import re

WORD = re.compile(r"[A-Za-z']+")
SENT_END = re.compile(r"[.!?]+")
CJK = re.compile(r"[\u4e00-\u9fff]")

# 中国人写英语最常犯的固定搭配错误。都是整句级的死错，认字面就够。
CHINGLISH = [
    ("very like", "like 本身就是动词，不加 very，用 really like"),
    ("very want", "want 是动词，用 really want"),
    ("how to say", "用 how do you say / how should I put it"),
    ("open the light", "开灯是 turn on the light"),
    ("close the light", "关灯是 turn off the light"),
    ("eat medicine", "吃药是 take medicine"),
    ("play computer", "玩电脑是 use the computer / play on the computer"),
    ("have a good rest", "可以，但更自然的是 get some rest"),
    ("according to my opinion", "according to 后面接来源，观点用 in my opinion"),
    ("in my personal opinion", "in my opinion 已经是我个人的意思"),
    ("learn knowledge", "搭配是 gain / acquire knowledge"),
    ("make a progress", "progress 不可数，说 make progress"),
    ("discuss about", "discuss 后面不加 about"),
    ("enter into", "enter 后面不加 into"),
    ("contact with", "作动词时是 contact sb，不加 with"),
    ("look forward to see", "to 后面接动名词：look forward to seeing"),
    ("one of my friend", "one of 后面接复数：one of my friends"),
    ("a lot of informations", "information 不可数"),
    ("more better", "better 已经是比较级"),
    ("most cheapest", "cheapest 已经是最高级"),
    ("repeat again", "repeat 已含 again 的意思"),
    ("return back", "return 已含 back 的意思"),
]

# 高频拼写错误（词表只放真常见的，宁缺勿滥：误报一次就没人信这套检查了）
SPELLING = {
    "recieve": "receive",
    "seperate": "separate",
    "occured": "occurred",
    "occuring": "occurring",
    "definately": "definitely",
    "enviroment": "environment",
    "goverment": "government",
    "neccessary": "necessary",
    "begining": "beginning",
    "sucess": "success",
    "succesful": "successful",
    "thier": "their",
    "teh": "the",
    "alot": "a lot",
    "becuase": "because",
    "reccomend": "recommend",
    "accomodation": "accommodation",
    "unforgetable": "unforgettable",
    "responsable": "responsible",
    "comparision": "comparison",
}

VOWELS = "aeiou"
EXCEPTIONS = ("university", "uniform", "united", "unique", "useful", "usual", "user",
              "european", "one", "once", "hour", "honest", "honor")

COMMON_WORDS = {"the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "in",
                "it", "i", "you", "we", "they", "he", "she", "that", "this", "for", "on",
                "with", "my", "me", "be", "do", "not", "have", "has", "had", "will"}


def words(text: str) -> list[str]:
    return WORD.findall(text or "")


def sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?\n]+", text or "")
    return [p.strip() for p in parts if p.strip()]


def stats(text: str) -> dict:
    ws = words(text)
    ss = sentences(text)
    long_words = [w for w in ws if len(w) >= 8]
    uniq = {w.lower() for w in ws}
    return {
        "words": len(ws),
        "sentences": len(ss),
        "avg_sentence": round(len(ws) / len(ss), 1) if ss else 0.0,
        "long_word_ratio": round(len(long_words) / len(ws), 3) if ws else 0.0,
        "unique_ratio": round(len(uniq) / len(ws), 3) if ws else 0.0,
        "longest_sentence": max((len(words(s)) for s in ss), default=0),
    }


def _span(text: str, needle: str) -> str:
    """把命中的原词原样取出来（保留大小写），用于标出问题位置。"""
    m = re.search(re.escape(needle), text or "", re.IGNORECASE)
    return m.group(0) if m else needle


def issues(text: str) -> list[dict]:
    """本地能确定的毛病。每条带 span（原文片段），方便高亮。"""
    out: list[dict] = []
    low = (text or "").lower()

    for bad, why in CHINGLISH:
        if bad in low:
            out.append({"type": "中式表达", "span": _span(text, bad), "why": why})

    for w in words(text):
        if w.lower() in SPELLING:
            out.append({"type": "拼写", "span": w, "why": f"应为 {SPELLING[w.lower()]}"})

    # a / an：后面紧跟的词以元音音素开头就用 an（有几类例外，见 EXCEPTIONS）
    for m in re.finditer(r"\b(a|an)\s+([A-Za-z][A-Za-z']*)", text or ""):
        art, word = m.group(1), m.group(2)
        low_word = word.lower()
        vowel_sound = low_word[0] in VOWELS and low_word not in EXCEPTIONS
        if low_word in EXCEPTIONS:
            vowel_sound = low_word in ("hour", "honest", "honor")
        if art.lower() == "a" and vowel_sound:
            out.append({"type": "冠词", "span": m.group(0), "why": f"{word} 以元音音素开头，用 an"})
        elif art.lower() == "an" and not vowel_sound:
            out.append({"type": "冠词", "span": m.group(0), "why": f"{word} 以辅音音素开头，用 a"})

    # 标点
    if CJK.search(text or ""):
        out.append({"type": "标点", "span": CJK.search(text).group(0), "why": "正文里混进了中文字符"})
    if re.search(r"\s{2,}", text or ""):
        out.append({"type": "标点", "span": "  ", "why": "出现了连续空格"})
    if re.search(r"[!?]{2,}", text or ""):
        out.append({"type": "标点", "span": re.search(r"[!?]{2,}", text).group(0),
                    "why": "连续感叹号或问号，正式写作里少用"})
    stripped = (text or "").strip()
    if stripped and stripped[-1] not in ".!?\"'":
        out.append({"type": "标点", "span": stripped[-1], "why": "最后一句没有句末标点"})

    # 重复词：同一个实词出现 4 次以上
    counts: dict[str, int] = {}
    for w in words(text):
        lw = w.lower()
        if lw in COMMON_WORDS or len(lw) < 3:
            continue
        counts[lw] = counts.get(lw, 0) + 1
    for lw, n in counts.items():
        if n >= 4:
            out.append({"type": "重复", "span": lw,
                        "why": f"「{lw}」出现 {n} 次，换几个说法"})

    return out


def group(issues_list: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for it in issues_list:
        out.setdefault(it["type"], []).append(it)
    return out


def summary(text: str) -> str:
    s = stats(text)
    if not s["words"]:
        return "还没写东西"
    bits = [f"{s['words']} 词", f"{s['sentences']} 句", f"平均每句 {s['avg_sentence']} 词"]
    if s["avg_sentence"] > 26:
        bits.append("句子偏长，读起来会累")
    elif s["avg_sentence"] < 8:
        bits.append("句子偏短，可以合几句练练复句")
    if s["unique_ratio"] < 0.45:
        bits.append("用词重复率高")
    return " · ".join(bits)
