# 语伴 yuban

[![test](https://github.com/wushiyi105-jpg/yuban/workflows/test/badge.svg)](https://github.com/wushiyi105-jpg/yuban/actions)

一个英语写作陪练。你贴一段英文进去，它干两件事：规则把能算的硬错挑出来，模型把读懂了才看得出的毛病挑出来。

两条规矩贯穿全程：**每条指正都要点出原文里的片段**，点不出就丢掉；**本地能算的绝不交给模型**，省得模型一边漏一边编。

![演示](assets/demo.gif)

## 为什么非要分两层

我先让模型全权接管过一次。结果是它把 `a apple` 判成「冠词错误」却说 span 是 `apple`（原文根本没有单独的 apple），又对一句完全正确的 `The museum is very big` 也给了一条「用词不够地道」，理由是「big 可以让位于 spacious」。

这不是模型笨，是这件事本来就有两种答案：`a` 该改 `an`，这是查表就有答案的，不需要语感；「big 换成 spacious 是否更地道」才是语感，且因人而异。

于是拆开：

| 谁 | 管什么 | 为什么 |
| --- | --- | --- |
| 规则 | 拼写、a/an、中式搭配、重复词、标点 | 有唯一正确答案，且错一次就够丢人 |
| 模型 | 时态、单复数、语序、地道表达、整段改写 | 要读懂上下文才知道 |

规则那层是词表加正则，认不出词表外的东西，但它不会编。模型那层会编，所以每条都要过核。

## 真的跑了一遍

样例是 `samples/第一篇.txt`，一段故意写坏的中国学生英语：

```
Last weekend I very like go to the museum with my friend. We take many photo and eat a apple in the garden. The museum is very big and very beautiful. I think it is a good place for study history. How to say, I want to go there again next time, and I will recieve the ticket by email.
```

规则先查，四条：

```
[中式表达] very like —— like 本身就是动词，不加 very，用 really like
[中式表达] How to say —— 用 how do you say / how should I put it
[拼写] recieve —— 应为 receive
[冠词] a apple —— apple 以元音音素开头，用 an
```

模型再补，八条，逐句：

```
· Last weekend I very like go to the museum with my friend
    [时态] very like → really liked     Last weekend 要求过去时
    [搭配] go to → going to             like 后接动名词
    改：Last weekend I really liked going to the museum with my friend.

· We take many photo and eat a apple in the garden
    [时态] take → took
    [单复数] photo → photos             many 后接可数名词复数
    [时态] eat → ate                    与 take 并列，时态一致
    改：We took many photos and ate an apple in the garden.

· I think it is a good place for study history
    [搭配] for study → to study         表目的用不定式
    改：I think it is a good place to study history.

· How to say, I want to go there again next time, and I will recieve the ticket by email
    [用词] How to say → How should I put it
    [拼写] recieve → receive
```

八条里没有一条是错的。它甚至注意到 `take` 和 `eat` 必须同时改——单独改一个，句子还是不通。

## 核验：三个真实的坑

**一、模型抄句子会顺手改标点。** 第一版跑完，五句话全被判「原文里找不到」，警告比问题还多。原因是模型抄 `original` 时把句末句号省了，而我比对时只去了空白。改成连标点一起去掉才干净——`Last weekend I like it` 和 `Last weekend I like it.` 算同一句。

**二、span 可以整句塞进来。** 有次模型把 `span` 给成 `very like go to` 这种跨词片段，说是「整体搭配错」。这在原文里是真存在的，所以核验放行了——但它其实更适合做「改写」而不是「指出问题」。我把这归到类型判断，不归到核验，因为拦住它就要开始猜模型的意思了，那是另一种编。

**三、模型给的句子和原文句数对不上。** 它会把两句合成一段（`How to say, I want to...` 本来就是一句掰成两半），也可能只批改其中三句。所以我不用「第 n 句」定位，而是让它抄原句，找不到再按顺序兜底，并在结果里留一条 `!` 提示。宁可有提示，也不要错位——错位意味着「改：We took many photos」挂在 `The museum is very big` 下面，那比不批改更糟。

## 累积：单篇没用的东西

一篇「错了 7 处」不说明任何事。真正有用的是「你三个月里被指出 11 次时态问题」。

所以每条问题都单独进表（`issues` 表），带类型、原文片段、出处（规则/模型）。`stats` 按类型聚合，`write` 跑完顺带报一次累计——连续三篇都被指出同一个类型，才会触发那句提示。

这也是我给它配 `sqlite` 的唯一理由：不是为了存文章，是为了能按类型数。

## 快速开始

```bash
git clone https://github.com/wushiyi105-jpg/yuban.git && cd yuban
cp .env.example .env      # 填 LLM_API_KEY

python -m yuban check samples/第一篇.txt     # 只跑规则，不花钱
python -m yuban write samples/第一篇.txt --level B1
```

起网页：

```bash
python -m yuban serve      # http://127.0.0.1:8775
```

## 命令

| 命令 | 做什么 |
| --- | --- |
| `check <文件或文字>` | 只跑本地规则 |
| `write <文件> [--title] [--level] [--no-model]` | 规则 + 模型批改，入库 |
| `list` / `show <id>` / `rm <id>` | 记录管理 |
| `stats` | 常犯错误统计 |
| `serve [--port]` | 网页 |

## 网页

左边贴英文，`只跑规则` 立刻出结果（不花钱、不等），`让模型看一遍` 才发请求。右边逐句列出，每句下面挂问题，最后是整段改写。

模型挂了给 502，左边规则结果照样在——网页不因为一次请求失败就白屏。

## 设计取舍

- **零第三方依赖**，Python 3.10+，标准库。
- **词表宁少勿多**。拼写表只放 20 个真常见的。误报一次，人就不信这套检查了；漏报一次，损失小得多。
- **不判「这句话好不好」**。风格是个人选择，模型可以给一版改写，但不该给原文打风格分。
- **改写不存进原文**。改写单独存一列，原文永远原样保留——练的是改，不是覆盖。
- **同一篇可以重复提交**。没有去重：同一个人隔三天重新写一遍同样的段落，是练习，不是重复。

## 局限

- 中式表达的词表只有 22 条，语义层面的问题（比如「这句其实在回答上一句」）只能靠模型。
- 不做口语、不做发音。
- 长文会被截断，模型一次看不完全篇——超过几百词请分段。

## 测试

```bash
python -m unittest discover -s tests
```

97 个用例，全离线。模型一律用替身，网页用 `port=0` 起真服务再打。

覆盖：句长与重复统计、a/an 的元音判定与六类例外、拼写表命中、中式搭配命中原样大小写、跨词片段被放过、span 查不到被丢、句数错位的顺序兜底、类型白名单归并、JSON 带围栏和带前言、SQLite 级联删除与坏 JSON 兜底、CLI 各子命令、网页 404/400/502 三条失败路径。

## 配置

`.env`（在 `.gitignore` 里）：

```
LLM_API_KEY=...
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4.6
```

兼容任何 OpenAI 风格 `/chat/completions`。`--api-key --base-url --model` 可覆盖。

---

作者：shiyi
邮箱：wushiyi105@gmail.com
GitHub：[wushiyi105-jpg](https://github.com/wushiyi105-jpg)
