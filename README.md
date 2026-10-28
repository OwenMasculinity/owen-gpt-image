<div align="center">

# owen-gpt-image

**你只说感觉，它自报名字。**

把「高级感」「温暖」「科技感」变成具体的风格参照，再完成提示词加工与出图。

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Agent-Agnostic-blueviolet" alt="Agent-Agnostic">
  <a href="https://github.com/OwenMasculinity/owen-gpt-image/actions/workflows/tests.yml"><img src="https://github.com/OwenMasculinity/owen-gpt-image/actions/workflows/tests.yml/badge.svg?branch=master" alt="Tests"></a>
  <a href="https://github.com/OwenMasculinity/owen-gpt-image"><img src="https://img.shields.io/badge/GitHub-Repository-181717?logo=github" alt="GitHub repository"></a>
</p>

[快速开始](#quick-start) · [使用示例](#examples) · [网页桥](#web-bridge) · [常见问题](#faq) · [文档](#docs)

</div>

---

你不必先认识 Dieter Rams、Penguin Books 或原研哉。描述想要的感觉，工具会从本地映射表里找出风格候选；拿不定主意时，还可以看编号参考卡再选。

这个仓库包含一份供 agent 使用的 [SKILL.md](SKILL.md)，以及可单独运行的 Python 工具。方法论可以供不同 agent 使用；Codex 生图入口需要 Codex CLI，网页生图入口需要本地桥与 Chrome 扩展。

| 你想做的事 | 项目提供什么 |
| --- | --- |
| 「给这篇文章做个高级点的封面」 | 感觉词查表，给出具体风格参照 |
| 「我也不知道哪种好看」 | 本地参考图库 → 编号看板 → 选中一种再生成 |
| 「用 Dieter Rams 风格做一页说明书」 | 加工提示词，补充中文、无水印等约束，再执行检查 |
| 「做一套 12 个图标」 | 网格生成方法、独立 PNG 切图和预览工具 |
| 「Codex 额度用完了」 | 检测额度错误，自动检查并切换已配置好的网页桥 |

**费用与前提：** 两条内置生图入口使用已登录账户的订阅能力，不需要 `OPENAI_API_KEY`，也不会自动调用按量付费 API。订阅本身、账户额度、模型权限和网络仍是运行前提。风格查表与看板渲染在本地完成，不调用生图接口。

<a id="quick-start"></a>

## 快速开始

### 1. 获取项目

```bash
git clone https://github.com/OwenMasculinity/owen-gpt-image.git
cd owen-gpt-image
```

如果只想把方法论装进支持 skills 的 agent，也可以使用：

```bash
npx skills add OwenMasculinity/owen-gpt-image
```

安装 skill 后可直接描述需求，例如：「给这篇文章做一张封面，风格温暖一点。」运行仓库脚本还需要下面的 Python 环境与对应生图后端。

### 2. 安装依赖

需要 **Python 3.10+**。先运行 `python --version` 确认版本，避免误用旧版 Anaconda。

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
source .venv/bin/activate
```

然后安装依赖：

```bash
python -m pip install .
```

此命令安装 Pillow、NumPy 等声明的依赖；以下脚本均从仓库根目录运行。Windows 如果 `python` 指向旧版本，可以用已安装的新版解释器（如 `py -3.11`）创建虚拟环境。

### 3. 先跑一个不生图的例子

```bash
python scripts/vibe.py 高级感
python scripts/craft_prompt.py "Dieter Rams 风格的大疆 pocket3 说明书" --size 1024x1024
```

第一条返回风格候选，第二条展示加工后的提示词与检查结果。它们不会消耗生图额度。

### 4. 生成第一张图

需要 PATH 中可找到的 Codex CLI、已完成 `codex login`，以及账户可用且支持图像生成工具的模型。

```bash
python scripts/gen_via_codex.py --prompt "无印良品风格的白色茶碗产品摄影，米白背景" --out outputs/tea-bowl.png --size 512x512 --quality high
```

若默认模型不可用，可加 `--model <可用模型>`，或设置 `GEN_CODEX_MODEL`。脚本不会修改全局模型配置。

想直接走 ChatGPT 网页版，按下方[网页桥](#web-bridge)步骤配置后端。

<a id="examples"></a>

## 使用示例

### 感觉词 → 风格候选 → 编号看板

```bash
python scripts/vibe.py 温暖
python scripts/blind_test.py 高级感 --images-dir "你的参考图库目录"
```

看完编号后，只生成选中的一种风格：

```bash
python scripts/blind_test.py 高级感 --pick 3 --generate --subject "大疆 pocket3 说明书"
```

默认只查表、渲染看板，不生成图片；传入 `--generate` 才会执行生图。明确需要多种风格时，可用 `--variants N --generate`。

默认图库为仓库的 `docs/cases`，内置案例数量有限。找不到参考图时显示文字占位卡，底色不代表实际风格；输出会报告缺图数量。可通过 `--images-dir` 或 `IMAGE_LIB` 指定自己的图库，使用 `--json` 获取候选及参考图覆盖数量。

<details>
<summary>查看九宫格工作流程</summary>

![九宫格盲测流程](docs/blind-test-flow.png)

</details>

### 提示词加工与检查

核心思路是把**主体、风格、媒介**写具体。例如「Dieter Rams 风格的大疆 pocket3 说明书」，比单写「简约、高级、德国工业感」更明确。

```bash
python scripts/craft_prompt.py "Dieter Rams 风格的大疆 pocket3 说明书" --size 1024x1024
```

加工后的提示词：

```text
Dieter Rams 风格的大疆 pocket3 说明书，图里描述性文字用中文，无水印，1024x1024
```

`craft_prompt.py` 保留原话，补充必要约束，再调用 `lint_prompt.py` 检查。两条生图入口默认经过这一步，有 FAIL 则拒绝生图；`--no-craft` 可在调试时关闭加工。

检查能够发现部分提示词问题，中文错字、事实准确性、构图和风格效果仍需出图后人工验收。完整方法见 [单图 playbook](references/single-image-playbook.md)。

### 一个真实案例

「给我弄个高级点的封面」→ 选择无印良品参照 → 生成生活方式杂志封面：

<p align="center">
  <img src="docs/cases/vibe-muji.png" width="420" alt="无印良品参照的生活方式杂志封面">
</p>

实际使用的提示词：

```text
一本生活方式杂志的封面，无印良品风格，米白素纸底色，无 logo 无装饰，大量留白，图里描述性文字用中文，无水印，1024x1024
```

更多案例与失败复盘见 [real-world-cases.md](references/real-world-cases.md)。

### 批量任务与网格切图

独立图片任务使用 JSONL，每行一个 job：

```jsonl
{"prompt":"无印良品风格的茶碗产品摄影","out":"outputs/tea.png","size":"1024x1024"}
{"prompt":"Dieter Rams 风格的大疆 pocket3 说明书","out":"outputs/manual.png","size":"1024x1024"}
```

```bash
python scripts/gen_via_codex.py --batch jobs.jsonl --concurrency 3
```

图标、角色或卡牌等需要统一风格的素材，可以先生成一张网格图，再切图和检查：

```bash
python scripts/extract_grid.py grid.png --grid 3 4 --mode bbox --out outputs/icons
python scripts/contact_sheet.py --input outputs/icons --out outputs/icons-preview.png
```

画布比例要匹配素材，避免把纵向卡牌硬塞进方形大图。白底网格可用 `bbox`，行列间距不均可尝试 `density`；纯色幕布素材可用 `chroma_key.py`。效果取决于背景与主体的可分离程度。模板和处理策略见 [prompt-patterns.md](references/prompt-patterns.md) 与 [extraction-strategies.md](references/extraction-strategies.md)。

<a id="web-bridge"></a>

## ChatGPT 网页桥

本地 HTTP 服务负责收发任务，Chrome 扩展负责操作已登录的 ChatGPT 页面：

```text
Python 脚本 → 本地桥 127.0.0.1:8765 → Chrome 扩展 → ChatGPT 页面
    ↑                                                    │
    └────────────── 图片回传、校验、保存 ←───────────────────┘
```

1. 在 Chrome 的 `chrome://extensions` 打开开发者模式，加载 `chatgpt-web-bridge/extension` 目录。
2. 在同一个 Chrome 配置中登录 ChatGPT，保持页面打开。
3. 启动本地桥，运行期间保持该终端开启：

```bash
python chatgpt-web-bridge/server.py
```

另开终端，激活同一个虚拟环境，检查连接并生图：

```bash
python scripts/gen_via_chatgpt_web.py --health
python scripts/gen_via_chatgpt_web.py --prompt "无印良品风格的白色茶碗产品摄影，米白背景" --out outputs/web-tea.png --size 512x512 --quality high
```

健康检查需显示 **桥 + 扩展均在线**。仅启动 `server.py` 还不足以生图。

| 接口 | 用途 |
| --- | --- |
| `/health` | 服务、扩展连接状态和当日任务计数 |
| `/diag` | 选页、填入、发送、出图、回传等步骤时间线 |
| `/reload` | 请求扩展自行重载，加载本地代码修改 |

这些接口位于 `http://127.0.0.1:8765`。根路径 `/` 不是控制台，请使用具体接口。网页桥依赖 ChatGPT 页面的结构和交互，页面更新后可能需要适配；它不等同于官方图片 API。部署与维护说明见 [网页桥 README](chatgpt-web-bridge/README.md)。

## 输出与切换规则

| 情况 | 脚本行为 |
| --- | --- |
| 指定 `--size` | 用 Pillow 居中裁剪并缩放到精确像素，保持主体比例；边缘可能被裁掉 |
| 未指定尺寸 | 保留原始像素尺寸，保存为 PNG |
| 图片损坏、进程失败或没有任务文件 | 报告失败，保留已有目标文件 |
| 并发任务 | 使用各自的临时目录，校验后原子替换；同一批次禁止重复输出路径 |
| Codex 额度错误 | 自动检查并切换已配置的网页桥；可用 `--no-fallback` 禁用 |
| 认证失败、模型不可用、超时或其他错误 | 返回错误，不自动切换、不调用付费 API |

不同脚本进程也应使用不同输出路径。模型选择优先级为 JSONL job 的 `model` → `--model` → `GEN_CODEX_MODEL` → Codex CLI 配置。

<a id="faq"></a>

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 启动就报 Python 语法错误 | 确认使用 Python 3.10+，并在虚拟环境里安装依赖 |
| 找不到 Codex CLI | 检查 PATH，并完成 CLI 安装和登录 |
| `model_not_found` 或模型不支持账户 | 用 `--model` 指定当前账户可用且支持生图工具的模型 |
| 桥在线、扩展离线 | 检查扩展是否加载、桥地址是否一致；打开 ChatGPT 页面 |
| 输入框有字但没发送 | 扩展会尝试发送按钮兜底；检查 `/diag` 的发送确认与错误 |
| 任务卡住或生图失败 | 先看 `/diag`，区分页面加载、发送、账户限额和网络问题 |
| 尺寸对了但边缘被裁 | 生成时预留安全区，或不传 `--size` 保留原始构图 |
| 中文有错字或出现品牌字样 | 调整提示词并人工验收，参考 [SKILL.md](SKILL.md) 的失败模式树 |

## 测试与验证边界

```bash
python -m unittest discover -s tests -v
node --test tests/test_bridge_send.cjs
```

Python 测试覆盖提示词加工、风格选择、任务隔离、输出保护和额度切换；Node.js 测试覆盖发送按钮兜底与重复提交防护。CI 在 Windows、macOS、Linux 的 Python 3.10 / 3.13 环境运行，结果见顶部 Tests 徽章。

**自动化测试不等于真实生图验收。** 最近一次网页桥实测已完成出图、回传和 512×512 保存，但发送步骤有人工协助；发送兜底修复后的全自动复测被浏览器控制中断，尚未完成。真实运行还需要可用账户、扩展、模型权限与网络。

<a id="docs"></a>

## 文档与目录

| 入口 | 内容 |
| --- | --- |
| [SKILL.md](SKILL.md) | agent 执行规则、工作模式与失败模式树 |
| [感觉词映射表](references/vibe-to-name.md) | 感觉 → 设计师、品牌和媒介参照 |
| [单图 playbook](references/single-image-playbook.md) | 主体、风格、媒介的组织方法 |
| [提示词模板](references/prompt-patterns.md) | 图标、卡牌、角色、中文卡片等网格模板 |
| [切图与抠图策略](references/extraction-strategies.md) | bbox、density 与失败排查 |
| [真实案例](references/real-world-cases.md) | 输出案例与经验复盘 |
| [视频参考板](references/video-reference-board.md) | 角色三视图、分镜与机位参考 |
| [网页桥说明](chatgpt-web-bridge/README.md) | 扩展部署、本地服务和维护 |

`scripts/` 存放命令行工具，`tests/` 存放回归测试，`docs/` 存放流程图与案例，生成结果默认可放在已被 Git 忽略的 `outputs/`。

`SKILL.md` 中的 `$IMAGE_LIB`、`$LOGO_LIB` 对应使用者自己的图库目录，需要按本机环境配置。

## License

[MIT](LICENSE) © 2026 OwenMasculinity
