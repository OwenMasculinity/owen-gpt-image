<div align="center">

# owen-gpt-image

> *「你缺的不是 prompt 技巧，是那个名字。」*
> *GPT-image-2 的 prompt 方法论 —— 外加一条已经跑通的落地链路。*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent-Agnostic](https://img.shields.io/badge/Agent-Agnostic-blueviolet)](https://skills.sh)
[![GitHub](https://img.shields.io/badge/GitHub-OwenMasculinity%2Fowen--gpt--image-181717?logo=github)](https://github.com/OwenMasculinity/owen-gpt-image)

<br>

**封面 · 海报 · 信息图 · UI mockup · 产品包装 · 批量 icon/角色/卡牌 · 中文书法**

<br>

大多数人写 AI 生图 prompt 的方式是堆形容词：「高级感、现代、简约、有质感、
专业的、精致的」。堆得越多，出来的图越像所有 AI 图。

而这条 prompt 只有 16 个字：

```
Dieter Rams 风格的大疆 pocket3 说明书
```

拿到的是一份完整 A4 说明书，含真实参数，视觉精度到官方手册级别。

差别不在技巧，在**你知不知道 Dieter Rams 是谁**——他的东西长什么样、
为什么他配这个产品。**模型的视觉记忆里有他，前提是你去调他。**

</div>

---

## 这个仓库里有什么

不是一篇教程，是一个能装进 agent 的 skill + 一套可执行的出图工具。

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 主体：行为硬约束（4 条红线）、5 项自检、决策路由、失败模式树。agent 真正读的是这份 |
| `references/single-image-playbook.md` | 单图方法论：概念库、三维质量模型、平台尺寸全表 |
| `references/prompt-patterns.md` | 批量网格的提示词模板（icon / 角色 / 卡牌 / 中文卡 / 书法 / sprite） |
| `references/extraction-strategies.md` | 网格抠图策略与故障排查（bbox / density 两种模式） |
| `references/capabilities.md` | GPT-image-2 能力边界实测数据 |
| `references/real-world-cases.md` | 真实案例复盘 |
| `references/video-reference-board.md` | AI 视频参考板（角色三视图 + 分镜 + 机位合成一张图） |
| `scripts/gen_via_codex.py` | 生成执行：单图 / JSONL 并发批量，走 codex 订阅额度 |
| `scripts/gen_via_chatgpt_web.py` | 生成执行：走 **ChatGPT 网页版**额度（见下方网页桥） |
| `scripts/extract_grid.py` | 网格大图 → 多个独立透明 PNG |
| `scripts/contact_sheet.py` | 拼预览图，批量出图后肉眼验收 |
| `scripts/chroma_key.py` | 纯色幕布抠透明（没有 API key 时的透明 PNG 方案） |
| `chatgpt-web-bridge/` | **本仓库独有**：把 chatgpt.com 网页版桥接成本地 HTTP API（本地桥 + Chrome 扩展） |

---

## 核心方法：概念压缩比

**prompt 的有效信息 ≠ prompt 的字数。决定输出质量的是单字承载的设计决策密度。**

写 prompt 之前先问一句：**主体 / 风格 / 媒介**三个槽位，能不能各填一个模型
熟知的高频名字？

| | 堆形容词 | 填名字 |
|---|---|---|
| 主体 | 「一个便携相机」 | 大疆 pocket3 |
| 风格 | 「简约、高级、德国工业感」 | Dieter Rams |
| 媒介 | 「产品介绍页面」 | 说明书 |

三个槽都填上了 → 短 prompt 就够。有空槽 → 那个槽位才需要结构化描述补足。

所以这个 skill 真正在训练的不是 prompt 写法，是**你脑子里的概念库**：
设计师、品牌、媒介范式，每多认识一个精准的名字，你的上限就抬高一点。

---

## 实测案例：5 个 9.5 分 prompt

全部 ≤ 30 字，全部实测。共同点：三槽位各有真名，没有一个形容词在管「氛围」。

| Prompt | 实测分 | 为什么强 |
|---|---|---|
| `Dieter Rams 风格的大疆 pocket3 说明书` | 9.5/10 | 三槽位都强，每词都打包几百条设计决策 |
| `The Criterion Collection 风格的 Cursor 产品页` | 9.5/10 | Criterion 的编号 / manifesto / curated stamp 全自动迁移 |
| `Penguin Books 风格的 Cursor 产品手册` | 9.5/10 | 三段橙、MODERN [X] CLASSICS 命名传统全到位 |
| `Brutalism 风格的婴儿米粉包装` | 9.5/10 | 模型自发贡献了「禾筑」这个品牌名 |
| `Apple 设计语言的中药包装。请你也贡献品牌名/slogan/命名逻辑` | 9.5/10 | 主动 invite，输出完整品牌系统而不只是一张图 |

### 反面教材（真实失败案例）

```
Editorial poster illustration for a tech magazine cover.

Subject: a single human hand entering from the lower-right corner,
index finger extended, pointing precisely at a coordinate marker...

Style anchor: minimalist editorial illustration in the spirit of
Anthropic's brand visuals. Bold flat shapes, hand-drawn black contour
lines, intentional white space. Mid-century modern feel.

Constraints: NO Chinese characters, NO watermark...
```

三宗罪：英文段落式（模型训练数据的默认输出，也就是 AI 味的来源）、
`Subject:` / `Style:` 伪结构化 header、形容词堆砌而没有真名。

改成这样：

```
Anthropic 风格的编辑插画封面：一只手从右下伸入，食指点向左上几何迷宫
图案上的某个坐标点 (357, 369)，指尖发光。1410×600，无中文无水印。
```

约 50 字中文，三槽位都有真名，技术参数最后给。

---

## 执行逻辑：从想法到一个 png 文件

方法论只解决「写什么」。这个仓库还解决「怎么真的生出来」——6 步，每步都有失败回路。

| 步 | 做什么 | 关键约束 |
|---|---|---|
| 1 | 确认平台尺寸 | 公众号首图 2.35:1 = **1410×600**；小红书 3:4 = **1242×1660**；B站封面 16:9 = **1280×720**。凭记忆写尺寸是常见 bug |
| 2 | 选工作模式 | 执行（目标清晰）/ 混合（有方向）/ 探索（没方向，先开 5-10 张看路） |
| 3 | 写中文短 prompt | 三槽位各填真名；简单单图 30 字内，构图型封面 / infographic 可到 200 字 |
| 4 | 跑 5 项自检 | 中英文？长度匹配？真名 ≥2 个？有没有伪 section？删掉一半字还能懂吗？—— 任何一条不过，禁止交付 |
| 5 | 调脚本生成 | 见下方三条生成路 |
| 6 | 验收 | 尺寸精确？中文每个字都对？关键信息在安全区？设计史细节有没有串台？ |

### 三条生成路

| | **订阅路径** `gen_via_codex.py` | **网页版路径** `gen_via_chatgpt_web.py` | **API 路径** |
|---|---|---|---|
| 计费 | codex 订阅额度，0 API 费 | ChatGPT **网页版**订阅额度，0 API 费 | 按量计费，需 `OPENAI_API_KEY` |
| 额度桶 | 较紧，用几次容易 429 | **宽得多**，独立于 codex 桶 | 看钱包 |
| 参数控制 | 靠自然语言传给 agent | 同左 | 精确 `--size/--quality/--n/--background` |
| 批量 | 多进程并发（建议 ≤3） | 浏览器侧串行 | 并发 5-25 |
| 透明背景 | 不稳 | 不稳 | 稳 |
| 适合 | 日常配图、省钱 | **codex 桶 429 时的主力 fallback** | 大批量（>20 张）/ 要精确参数 |

**默认走订阅路径；报 429 或额度耗尽 → 切网页版路径**（吃另一个更宽的桶，仍然 0 API 费）。

```bash
# 订阅路径
python3 scripts/gen_via_codex.py \
  --prompt "Kenya Hara 风格的越窑青瓷茶碗特写，米白背景" \
  --out out.png --size 1410x600 --quality high

# 批量：写个 JSONL，每行一个 job
python3 scripts/gen_via_codex.py --batch jobs.jsonl --concurrency 3
```

---

## ChatGPT 网页桥（本仓库独有）

`chatgpt-web-bridge/` 是一个本地 HTTP 服务（`127.0.0.1:8765`）+ 一个 Chrome 扩展，
把 chatgpt.com 网页版的生图能力桥接成本地 API。**它让你在 codex 额度打满时，
还能继续吃 ChatGPT 网页版那个更宽的额度桶，且不花一分 API 费。**

```bash
python3 chatgpt-web-bridge/server.py          # 起桥（只监听 127.0.0.1）

curl -s http://127.0.0.1:8765/health          # 确认桥 + 扩展在线

python3 scripts/gen_via_chatgpt_web.py \
  --prompt "画一只在窗台上晒太阳的橘猫，水彩风格" \
  --out ./out.png --size 1024x1024 --quality high

curl -s http://127.0.0.1:8765/diag            # 卡住时看步骤时间线
curl -s http://127.0.0.1:8765/reload          # 改完扩展代码让它自我重载
```

首次部署只需一次：`chrome://extensions` → 开发者模式 → 加载 `chatgpt-web-bridge/extension/`，
且该 Chrome profile 里 chatgpt.com 已登录。

桥操纵的是真实页面，所以坑是实测撞出来的，不是猜的（`SKILL.md` 里逐条列了根因与修法）：

| 坑 | 已修方案 |
|---|---|
| 合成 DOM 事件填得进输入框，发出去却是空的 | ChatGPT 用 ProseMirror，合成事件不更新其内部 state → 改用 `chrome.debugger` 浏览器级真实输入 |
| 操作落在另一个窗口的后台标签，用户看不到 | 派发前把目标窗口提到前台；按候选评分选页，排除错误页死标签 |
| 消息列表虚拟化，计数判不出新回复 | 改用发送前后的图片 src 集合比对 |
| 生成图是 blob / 跨域 URL，取不到字节 | 在页面上下文用 canvas `toDataURL` 编码 |
| 明明在生成却报超时 | 网页版实测 30-130s，超时参数已放宽 |
| 改一次扩展就要手动去 Chrome 点刷新 | 桥新增 `/reload`，扩展自调 `chrome.runtime.reload()` |

---

## 批量生成：网格法

icon 集 / 角色集 / 卡牌集 / sprite sheet / 中文长文本，走网格：一次生成一张大图
（如 4×3），再用 `scripts/extract_grid.py` 切成单张。

比逐张生成快一个数量级，而且**同一张图里的元素风格天然一致**——
这是逐张生成很难做到的。

但有个实测踩出来的坑：**别硬性锁死画布尺寸，让比例匹配内容**。
早期用 1:1 画布生成 5×5 的 2:3 纵向卡，末行被压缩了 18%——
模型在约束冲突时会自发牺牲末行来「保住构图完整」，而且不会告诉你。

| 场景 | 布局 | 抠图模式 |
|---|---|---|
| icon 集 | 4×4 方形 | `--mode=bbox` |
| 角色集 | 3×3 方形 | `--mode=bbox` |
| TCG 卡牌集 | 4×4 或 5×5 | `--mode=density` |
| 中文成语 / 知识卡 | 4×4 方形 | `--mode=bbox` |
| 古诗竖幅 | 1:3 竖幅 | 单张，不抠 |
| 对联 / 横幅书法 | 3:1 横幅 | `--mode=density` |
| 逐帧 sprite sheet | 4×3 = 12 帧 | `--mode=bbox` |

---

## 失败模式树

出图后不要「再试一次」碰运气。`SKILL.md` 里每个失败模式都给了
「触发条件 → 一线修复 → 仍失败兜底」三段式，覆盖三层：

- **prompt 层**：英文段落、形容词堆砌、真名不够、输出「安全好看」但没惊喜
- **渲染层**：中文错字 / 缺笔画、出版品牌名被画成左上角英文 nameplate、风格 transfer 不像
- **执行层**：订阅路径 429 → 切网页版路径；透明底不稳 → 纯色幕布 + `chroma_key.py`；大批量 → 切 API 路径

---

## 装上就能用

**仓库**：https://github.com/OwenMasculinity/owen-gpt-image

方式一 · skills 安装：

```bash
npx skills add OwenMasculinity/owen-gpt-image
```

方式二 · 直接克隆到你的 skills 目录：

```bash
git clone https://github.com/OwenMasculinity/owen-gpt-image.git ~/.claude/skills/owen-gpt-image
```

装完直接说人话：

```
"给这篇文章做个封面"     → 走配图 SOP，定家族 → 挑 ref → 生成
"做一套 12 个 icon"     → 批量生成，网格切图
"这张图重新出，字太小"   → 按失败模式树对症改
"做个产品对比信息图"     → 单图 playbook
```

> **发布版说明**：`SKILL.md` 里的 `$IMAGE_LIB`（配图库）与 `$LOGO_LIB`（品牌 Logo 库）
> 是占位符，对应你自己机器上的真实目录——克隆后替换即可。
> 品牌配图 SOP 中的示例 IP（`花叔`）来自原作者的自有品牌资产，
> 换成你自己的主角 ref / logo / 风格垫图即可照跑。
> 本仓库不含任何本机绝对路径、密钥或个人凭据。

---

## License

MIT
