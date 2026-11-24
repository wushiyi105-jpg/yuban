"""生成 assets/demo.gif：960×600 的终端风演示动图。

只用 Pillow（开发期依赖，不进 requirements）。跑法：
    python scripts/make_demo_gif.py

本地规则先查硬错，模型再补语感，两边都要指得出原文。
8 处指正全部对回原句。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 600
BG = "#0b0f14"
BAR = "#161b22"
LINE = "#21262d"
GREEN = "#7ee787"
TEXT = "#c9d1d9"
DIM = "#8b949e"
BLUE = "#79c0ff"
YELLOW = "#e3b341"
RED = "#ff7b72"

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

LINE_H = 25
MAX_W = W - 56

COLORS = {"cmd": GREEN, "out": TEXT, "dim": DIM, "cite": BLUE, "warn": YELLOW, "bad": RED}


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size)


_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def clip(text: str, size: int = 16) -> str:
    f = font(size)
    if _MEASURE.textlength(text, font=f) <= MAX_W:
        return text
    while text and _MEASURE.textlength(text + "…", font=f) > MAX_W:
        text = text[:-1]
    return text + "…"


def render(rows, cursor_row=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 36], fill=BAR)
    for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([16 + i * 22, 12, 28 + i * 22, 24], fill=color)
    d.text((92, 9), "yuban — 简历对账，改写只准改措辞，不许加事实", font=font(15), fill=DIM)
    d.line([0, 36, W, 36], fill=LINE)

    y = 54
    for idx, (style, text) in enumerate(rows):
        shown = clip(text)
        d.text((26, y), shown, font=font(16), fill=COLORS[style])
        if cursor_row == idx:
            w = _MEASURE.textlength(shown, font=font(16))
            d.rectangle([26 + w + 4, y + 2, 26 + w + 12, y + 19], fill=GREEN)
        y += LINE_H
        if y > H - 16:
            break
    return img


SCRIPT = [
    ("cmd", "> python -m yuban write samples/第一篇.txt"),
    ("out", "60 词 · 5 句 · 平均每句 12.0 词"),
    ("dim", "规则先查出 4 处："),
    ("warn", "  [中式表达] very like —— like 是动词，不加 very，用 really like"),
    ("warn", "  [冠词] a apple —— apple 以元音音素开头，用 an"),
    ("warn", "  [拼写] recieve —— 应为 receive"),
    ("warn", "  [中式表达] How to say —— 用 how do you say"),
    ("dim", "等模型看一遍……"),
    ("out", "水平判断：B1"),
    ("out", "最该先改的是时态：整段讲 Last weekend 的事，动词却用现在时"),
    ("dim", "· Last weekend I very like go to the museum with my friend"),
    ("dim", "    [时态] very like → really liked"),
    ("dim", "    [搭配] go to → going to"),
    ("dim", "· We take many photo and eat a apple in the garden"),
    ("dim", "    [时态] take → took"),
    ("out", "    [单复数] photo → photos"),
    ("dim", "    [时态] eat → ate"),
    ("out", "    改：We took many photos and ate an apple in the garden."),
    ("dim", "· I think it is a good place for study history"),
    ("warn", "    [搭配] for study → to study"),
    ("out", "    改：I think it is a good place to study history."),
    ("dim", "累计最常被指出的：时态 3 次、中式表达 2 次、搭配 2 次"),
]
TAIL = [
    ("out", "8 处指正，每一处都点出原文里的字。"),
    ("dim", "查不到出处的当场丢掉：模型曾把整句改写塞进 span，被程序拦下。"),
]

def build():
    frames, shown = [], []
    for style, text in SCRIPT:
        if style == "cmd":
            for i in range(6, len(text) + 1, 6):
                frames.append(render(shown + [("cmd", text[:i])], cursor_row=len(shown)))
        shown = shown + [(style, text)]
        frames.append(render(shown))
    for _ in range(12):
        frames.append(render(shown + TAIL))

    frames = [f.quantize(colors=20, method=Image.MEDIANCUT) for f in frames]
    os.makedirs("assets", exist_ok=True)
    out = os.path.join("assets", "demo.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
    print(f"ok -> {out}  {len(frames)} 帧  {os.path.getsize(out) / 1024:.1f} KB")


if __name__ == "__main__":
    build()

