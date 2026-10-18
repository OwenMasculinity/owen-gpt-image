<div align="center">

# 知名则图精，堆词则图庸

`owen-gpt-image` **不是教你写 prompt，是让你不用再写 prompt。**

> 「我语言的界限，就是我世界的界限。」  
> —— 维特根斯坦《逻辑哲学论》

模型记得 Dieter Rams、Penguin Books、原研哉长什么样。  
**你叫不出他们的名字，就到不了那个精度。**

所以这里给你的不是 prompt 模板，是**一套叫得出名字的方法论**，  
外加一条**不花 API 钱也能跑通**的出图链路。

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

![Agent-Agnostic](https://img.shields.io/badge/Agent-Agnostic-blueviolet)

![GitHub](https://img.shields.io/badge/GitHub-OwenMasculinity%2Fowen--gpt--image-181717?logo=github)

</div>

---

## 一 · 装上之后怎么用

| 你说              | 它做                            |
| --------------- | ----------------------------- |
| "给这篇文章做个封面"     | 定风格家族 → 挑 ref 垫图 → 出图 → 逐字验收  |
| "做一套 12 个 icon" | 一次生成 4×3 网格 → 自动切成 12 张透明 PNG |
| "这张字太小，重出"      | 查失败模式树对症改，不是「再试一次」            |
| "做个产品对比信息图"     | 走单图 playbook，三槽位各填一个真名        |

四条卖点，每一条都对着一个真实痛点：

|                |                                                                    |
| -------------- | ------------------------------------------------------------------ |
| 🗣 **说人话就出图**  | 装进 agent 即可。不用学语法、不用背模板、不用手抄提示词合集——你说中文短句，它负责把这句人话变成能打的 prompt     |
| 💸 **0 API 费** | 默认吃 codex 订阅额度；额度打满自动切 ChatGPT **网页版**额度（本仓库自带网页桥）——两条路都不花一分 API 钱 |
| ✅ **不靠重抽卡**    | 出图前 5 项自检卡住质量，出图后有失败模式树对症修。抽卡十次，不如改对一处                             |
| ⚡ **批量一次到位**   | 网格法一次出 12 张，同一张图里的元素风格天然一致，再自动切成独立透明 PNG                           |

同一件事，四种做法的差别：

|           | 提示词合集 / 教程 | 通用 agent 直接生图 | 直接调 OpenAI API | **本仓库**                   |
| --------- | ---------- | ------------- | -------------- | ------------------------- |
| 形态        | 文章、词表，靠人抄  | 靠模型临场发挥       | 脚本 + 参数        | **装进 agent 的 skill**      |
| prompt 质量 | 固定模板，换题就废  | 波动大，容易 AI 味   | 等于你自己写的水平      | **出图前 5 项自检，不达标不许交付**     |
| 出图成本      | 自己另找工具     | 看平台           | **按量付费**       | **0 API 费**（订阅额度 + 网页版额度） |
| 额度打满      | —          | 排队等           | 继续烧钱           | **自动切网页版额度**（自带桥）         |
| 出错了       | 自己猜        | 「再试一次」        | 「再试一次」         | **失败模式树对症改**              |
| 批量        | 无          | 慢             | 要自己写并发         | **网格法一次 12 张 + 自动切图**     |
| 图上中文      | 容易冒出英文     | 不稳            | 看 prompt 怎么写   | **默认中文，验收逐字查**            |

---

## 二 · 实测案例：输入 → 加工 → 输出

以下 5 条全部 ≤ 30 字、全部实测 9.5/10。看「本仓库做了什么」那一列——  
它不照抄你的话，它先把这句话拆成三槽位，再决定补什么、验什么。

| 输入 prompt                                 | 本仓库做了什么加工                                         | 输出                                 |
| ----------------------------------------- | ------------------------------------------------- | ---------------------------------- |
| `Dieter Rams 风格的大疆 pocket3 说明书`           | 三槽位各认出一个真名（风格 / 产品 / 载体）→ 补尺寸与「无水印」约束 → 出图后逐字验收中文 | 完整 A4 说明书，含真实参数，官方手册级 · **9.5/10** |
| `The Criterion Collection 风格的 Cursor 产品页` | 把 Criterion 的编号、manifesto、curated stamp 整套迁移到新主体上 | 产品页 · **9.5/10**                   |
| `Penguin Books 风格的 Cursor 产品手册`           | 套用三段橙配色 + MODERN [X] CLASSICS 命名传统                | 手册 · **9.5/10**                    |
| `Brutalism 风格的婴儿米粉包装`                     | 判定缺品牌名 → 主动 invite 模型一起想                          | 模型自发给出「禾筑」这个品牌名 · **9.5/10**       |
| `Apple 设计语言的中药包装。请你也贡献品牌名/slogan/命名逻辑`    | 主动 invite → 输出的不只是一张图，是一套命名逻辑                     | 完整品牌系统 · **9.5/10**                |

---

## 三 · 装上就能用

**仓库**：<https://github.com/OwenMasculinity/owen-gpt-image>

方式一 · skills 安装：

```bash
npx skills add OwenMasculinity/owen-gpt-image
```

方式二 · 直接克隆到你的 skills 目录：

```bash
git clone https://github.com/OwenMasculinity/owen-gpt-image.git ~/.claude/skills/owen-gpt-image
```

> **发布版说明**：`SKILL.md` 里的 `$IMAGE_LIB`（配图库）与 `$LOGO_LIB`（品牌 Logo 库）  
> 是占位符，对应你自己机器上的真实目录——克隆后替换即可。

---

## 四 · 核心概念

方法论、`SKILL.md` 里的规则、几条生成路、批量和排错——都在这里。  
不读也能用（agent 会替你读），读了才知道它为什么这么干。

### 4.1 概念压缩比：三槽位各填一个真名

> 「好的设计是尽可能少的设计。」  
> —— Dieter Rams

**prompt 的有效信息 ≠ prompt 的字数。决定输出质量的是单字承载的设计决策密度。**

写 prompt 之前先问一句：**主体 / 风格 / 媒介**三个槽位，能不能各填一个模型  
熟知的高频名字？

|    | 堆形容词          | 填名字         |
| -- | ------------- | ----------- |
| 主体 | 「一个便携相机」      | 大疆 pocket3  |
| 风格 | 「简约、高级、德国工业感」 | Dieter Rams |
| 媒介 | 「产品介绍页面」      | 说明书         |

三个槽都填上了 → 短 prompt 就够。有空槽 → 那个槽位才需要结构化描述补足。

所以这个 skill 真正在训练的不是 prompt 写法，是**你脑子里的概念库**：  
设计师、品牌、媒介范式，每多认识一个精准的名字，你的上限就抬高一点。

### 4.2 执行逻辑：6 步到一张 png

| 步 | 做什么         | 关键约束                                                                                       |
| - | ----------- | ------------------------------------------------------------------------------------------ |
| 1 | 确认平台尺寸      | 公众号首图 2.35:1 = **1410×600**；小红书 3:4 = **1242×1660**；B站封面 16:9 = **1280×720**。凭记忆写尺寸是常见 bug |
| 2 | 选工作模式       | 执行（目标清晰）/ 混合（有方向）/ 探索（没方向，先开 5-10 张看路）                                                     |
| 3 | 写中文短 prompt | 三槽位各填真名；简单单图 30 字内，构图型封面 / infographic 可到 200 字                                            |
| 4 | 跑 5 项自检     | 中英文？长度匹配？真名 ≥2 个？有没有伪 section？删掉一半字还能懂吗？—— 任何一条不过，禁止交付                                     |
| 5 | 调脚本生成       | 见 4.3                                                                                      |
| 6 | 验收          | 尺寸精确？中文每个字都对？关键信息在安全区？设计史细节有没有串台？                                                          |

### 4.3 三条生成路

|      | **订阅路径** `gen_via_codex.py` | **网页版路径** `gen_via_chatgpt_web.py` | **API 路径**                             |
| ---- | --------------------------- | ---------------------------------- | -------------------------------------- |
| 计费   | codex 订阅额度，0 API 费          | ChatGPT **网页版**订阅额度，0 API 费        | 按量计费，需 `OPENAI_API_KEY`                |
| 额度桶  | 较紧，用几次容易 429                | **宽得多**，独立于 codex 桶                | 看钱包                                    |
| 参数控制 | 靠自然语言传给 agent               | 同左                                 | 精确 `--size/--quality/--n/--background` |
| 批量   | 多进程并发（建议 ≤3）                | 浏览器侧串行                             | 并发 5-25                                |
| 透明背景 | 不稳                          | 不稳                                 | 稳                                      |
| 适合   | 日常配图、省钱                     | **codex 桶 429 时的主力 fallback**      | 大批量（>20 张）/ 要精确参数                      |

**默认走订阅路径；报 429 或额度耗尽 → 切网页版路径**（吃另一个更宽的桶，仍然 0 API 费）。

```bash
# 订阅路径
python3 scripts/gen_via_codex.py \
  --prompt "Kenya Hara 风格的越窑青瓷茶碗特写，米白背景" \
  --out out.png --size 1410x600 --quality high

# 批量：写个 JSONL，每行一个 job
python3 scripts/gen_via_codex.py --batch jobs.jsonl --concurrency 3
```

### 4.4 ChatGPT 网页桥（本仓库独有）

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

| 坑                        | 已修方案                                                                   |
| ------------------------ | ---------------------------------------------------------------------- |
| 合成 DOM 事件填得进输入框，发出去却是空的  | ChatGPT 用 ProseMirror，合成事件不更新其内部 state → 改用 `chrome.debugger` 浏览器级真实输入 |
| 操作落在另一个窗口的后台标签，用户看不到     | 派发前把目标窗口提到前台；按候选评分选页，排除错误页死标签                                          |
| 消息列表虚拟化，计数判不出新回复         | 改用发送前后的图片 src 集合比对                                                     |
| 生成图是 blob / 跨域 URL，取不到字节 | 在页面上下文用 canvas `toDataURL` 编码                                          |
| 明明在生成却报超时                | 网页版实测 30-130s，超时参数已放宽                                                  |
| 改一次扩展就要手动去 Chrome 点刷新    | 桥新增 `/reload`，扩展自调 `chrome.runtime.reload()`                           |

### 4.5 批量生成：网格法

icon 集 / 角色集 / 卡牌集 / sprite sheet / 中文长文本，走网格：一次生成一张大图  
（如 4×3），再用 `scripts/extract_grid.py` 切成单张。

比逐张生成快一个数量级，而且**同一张图里的元素风格天然一致**——  
这是逐张生成很难做到的。

但有个实测踩出来的坑：**别硬性锁死画布尺寸，让比例匹配内容**。  
早期用 1:1 画布生成 5×5 的 2:3 纵向卡，末行被压缩了 18%——  
模型在约束冲突时会自发牺牲末行来「保住构图完整」，而且不会告诉你。

| 场景              | 布局         | 抠图模式             |
| --------------- | ---------- | ---------------- |
| icon 集          | 4×4 方形     | `--mode=bbox`    |
| 角色集             | 3×3 方形     | `--mode=bbox`    |
| TCG 卡牌集         | 4×4 或 5×5  | `--mode=density` |
| 中文成语 / 知识卡      | 4×4 方形     | `--mode=bbox`    |
| 古诗竖幅            | 1:3 竖幅     | 单张，不抠            |
| 对联 / 横幅书法       | 3:1 横幅     | `--mode=density` |
| 逐帧 sprite sheet | 4×3 = 12 帧 | `--mode=bbox`    |

### 4.6 失败模式树

出图后不要「再试一次」碰运气。`SKILL.md` 里每个失败模式都给了  
「触发条件 → 一线修复 → 仍失败兜底」三段式，覆盖三层：

- **prompt 层**：英文段落、形容词堆砌、真名不够、输出「安全好看」但没惊喜
- **渲染层**：中文错字 / 缺笔画、出版品牌名被画成左上角英文 nameplate、风格 transfer 不像
- **执行层**：订阅路径 429 → 切网页版路径；透明底不稳 → 纯色幕布 + `chroma_key.py`；大批量 → 切 API 路径

---

## 附录 · 这个仓库里有什么

不是一篇教程，是一个能装进 agent 的 skill + 一套可执行的出图工具。

```text
owen-gpt-image/
├── SKILL.md                        # 主体：4 条红线、5 项自检、决策路由、失败模式树（agent 真正读的是这份）
├── README.md
├── LICENSE
├── .gitignore
├── test-prompts.json               # 一组回归测试用 prompt
├── references/
│   ├── single-image-playbook.md    # 单图方法论：概念库、三维质量模型、平台尺寸全表
│   ├── prompt-patterns.md          # 批量网格模板：icon / 角色 / 卡牌 / 中文卡 / 书法 / sprite
│   ├── extraction-strategies.md    # 网格抠图策略与故障排查（bbox / density 两种模式）
│   ├── capabilities.md             # GPT-image-2 能力边界实测数据
│   ├── real-world-cases.md         # 真实案例复盘
│   ├── video-reference-board.md    # AI 视频参考板：角色三视图 + 分镜 + 机位合成一张图
│   └── *.png                       # 上面那份参考板的样图
├── scripts/
│   ├── gen_via_codex.py            # 生成：单图 / JSONL 并发批量，走 codex 订阅额度（见 4.3）
│   ├── gen_via_chatgpt_web.py      # 生成：走 ChatGPT 网页版额度（见 4.4）
│   ├── extract_grid.py             # 网格大图 → 多个独立透明 PNG（见 4.5）
│   ├── contact_sheet.py            # 拼预览图，批量出图后肉眼验收
│   └── chroma_key.py               # 纯色幕布抠透明（没有 API key 时的透明 PNG 方案）
└── chatgpt-web-bridge/             # 本仓库独有：把 chatgpt.com 网页版桥接成本地 HTTP API
    ├── server.py                   # 本地桥 127.0.0.1:8765：/poll /submit /result /health /diag /reload
    ├── README.md                   # 桥的部署与排错说明
    └── extension/                  # Chrome MV3 扩展：CDP 浏览器级真实输入 + canvas 取图
        ├── manifest.json
        ├── background.js
        ├── content.js
        └── popup.html / popup.js
```



```

---

## License

[MIT](LICENSE) © 2026 OwenMasculinity
```
