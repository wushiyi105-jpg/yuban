"""模型层：逐句批改，每条错误必须点名原文里的片段。

这里最重要的一条规矩是核验：模型说「last weekend」有错，那「last weekend」
必须真出现在原文里。不在就丢掉——宁可少报一条，也不让人对着不存在的字去改。
"""

from __future__ import annotations

import json
import re

from . import llm

SYSTEM = """你是一位英语写作教练，批改非母语者的英文段落。

规则：
1. 逐句检查。只报真正的问题：语法、搭配、时态、单复数、冠词、标点、明显不地道的表达。
2. 每条问题必须给出「span」——从原句里逐字抄下来的片段，不能改写、不能补字。抄不到就别报。
3. 不许把正确的句子判成错误。不确定就放过。
4. 给出整段的自然版改写（rewrite），保留原意和原有信息，不许加原文没有的内容。
5. level 用 CEFR：A1 A2 B1 B2 C1 C2。
6. 只输出 JSON，不要任何解释文字。

JSON 结构：
{
  "sentences": [
    {
      "original": "原句，逐字抄",
      "issues": [
        {"span": "原文里的片段", "type": "时态", "fixed": "改成什么", "why": "一句话原因"}
      ],
      "rewrite": "这一句的自然写法"
    }
  ],
  "rewrite": "整段改写",
  "level": "B1",
  "comment": "两三句话，指出最该先改的一个毛病"
}

type 只能用这几个：时态、单复数、冠词、介词、搭配、标点、拼写、语序、用词、其他。"""


def _as_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for k in ("value", "text", "span", "fixed"):
            if isinstance(value.get(k), str):
                return value[k].strip()
    if isinstance(value, list) and value:
        return _as_text(value[0])
    return ""


def _flat(chars: str) -> str:
    """去掉标点、空白并小写，用于比对。

    一开始我只去了空白，结果模型抄句子时顺手把句末句号省了，五句话全被判
    「原文里找不到」——警告比问题还多。加上标点归一之后才干净。
    """
    return re.sub(r"[\s\.,!?;:，。！？；：、'\"“”‘’…]+", "", (chars or "")).lower()


def locate(span: str, original: str) -> bool:
    """模型给的 span 是否真的在原文里（忽略大小写与空白差异）。"""
    s = _flat(span)
    return bool(s) and s in _flat(original)


def verify(sentences_in: list[dict], sent_orig: list[str]) -> tuple[list[dict], list[str]]:
    """核验模型输出：句子要能对上原文，span 要在句子里，问题类型要在白名单。

    返回 (清洗后的句子列表, 问题清单)。
    """
    notes: list[str] = []
    out: list[dict] = []
    types_ok = {"时态", "单复数", "冠词", "介词", "搭配", "标点", "拼写", "语序", "用词", "其他"}

    for item in sentences_in:
        if not isinstance(item, dict):
            continue
        original = _as_text(item.get("original"))
        # 原文句子：优先用模型抄的（要能在全文里对上），对不上就按顺序取
        if original and not locate(original, "\n".join(sent_orig)):
            notes.append(f"模型引用的句子在原文里找不到，按顺序对齐：{original[:30]}")
            original = ""
        if not original:
            idx = len(out)
            original = sent_orig[idx] if idx < len(sent_orig) else ""

        kept: list[dict] = []
        for iss in item.get("issues") or []:
            if not isinstance(iss, dict):
                continue
            span = _as_text(iss.get("span"))
            kind = _as_text(iss.get("type")) or "其他"
            if kind not in types_ok:
                kind = "其他"
            if not locate(span, original):
                notes.append(f"丢掉一条查不到出处的指正：{span or '(空)'}")
                continue
            kept.append({
                "span": span,
                "type": kind,
                "fixed": _as_text(iss.get("fixed")),
                "why": _as_text(iss.get("why")),
            })

        out.append({
            "original": original,
            "issues": kept,
            "rewrite": _as_text(item.get("rewrite")),
        })

    return out, notes


def build_prompt(text: str, local: list[dict], level_hint: str = "") -> str:
    local_lines = "\n".join(
        f"- {it['type']}：{it['span']} → {it['why']}" for it in local[:12]
    ) or "（本地规则没查出问题）"
    return f"""请批改下面这段英文。

原文：
---
{text.strip()}
---

本地规则已经查出的问题（这些不用你重复报，除非你的判断不同）：
{local_lines}

{f"作者自评水平：{level_hint}" if level_hint else ""}

按要求逐句检查，只输出 JSON。"""


def parse(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def review(text: str, local: list[dict], level_hint: str = "") -> dict:
    """跑模型，核验，合并本地结果。返回 {sentences, rewrite, level, comment, notes, error}。"""
    from . import checks

    sent_orig = checks.sentences(text)
    result = {"sentences": [], "rewrite": "", "level": "", "comment": "", "notes": [], "error": ""}
    try:
        raw = llm.chat(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": build_prompt(text, local, level_hint)}],
            max_tokens=1800,
        )
    except llm.LLMError as e:
        result["error"] = f"模型没回：{e}"
        return result

    data = parse(raw)
    if not data:
        result["error"] = "模型输出不是 JSON，原文：" + (raw or "")[:80]
        return result

    sentences_out, notes = verify(data.get("sentences") or [], sent_orig)
    result["sentences"] = sentences_out
    result["rewrite"] = _as_text(data.get("rewrite"))
    result["level"] = (_as_text(data.get("level")) or "").upper()[:2]
    result["comment"] = _as_text(data.get("comment"))
    result["notes"] = notes
    return result


def total_issues(reviewed: dict) -> int:
    return sum(len(s["issues"]) for s in reviewed.get("sentences") or [])


def render(reviewed: dict) -> str:
    if reviewed.get("error"):
        return reviewed["error"]

    lines: list[str] = []
    if reviewed.get("level"):
        lines.append(f"水平判断：{reviewed['level']}")
    if reviewed.get("comment"):
        lines.append(reviewed["comment"])

    n = total_issues(reviewed)
    lines.append(f"\n=== 逐句（{len(reviewed.get('sentences') or [])} 句，{n} 处问题） ===")
    for s in reviewed.get("sentences") or []:
        lines.append(f"\n· {s['original']}")
        for iss in s["issues"]:
            fixed = f" → {iss['fixed']}" if iss["fixed"] else ""
            lines.append(f"    [{iss['type']}] {iss['span']}{fixed}")
            if iss["why"]:
                lines.append(f"      {iss['why']}")
        if s["rewrite"]:
            lines.append(f"    改：{s['rewrite']}")

    if reviewed.get("rewrite"):
        lines.append("\n=== 整段改写 ===")
        lines.append(reviewed["rewrite"])

    for note in reviewed.get("notes") or []:
        lines.append(f"! {note}")

    return "\n".join(lines)
