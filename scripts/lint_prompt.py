#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt 门禁：把 SKILL.md 红线 4 的「5 项自检」变成可执行检查。

用法：
    python scripts/lint_prompt.py "Dieter Rams 风格的大疆 pocket3 说明书"
    python scripts/lint_prompt.py --file prompt.txt
    echo "..." | python scripts/lint_prompt.py -
    python scripts/lint_prompt.py "..." --json

退出码：
    0  通过（可以有警告）
    1  有必须修的项（FAIL）—— 禁止交付
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 伪 section header：模型默认输出的「结构化」写法，实测是 AI 味来源
PSEUDO_HEADERS = (
    "subject", "style", "constraints", "composition", "output",
    "negative", "aspect ratio", "color palette", "mood", "background",
)

# 形容词堆砌：单个词没问题，堆 3 个以上就是模糊寻址
FUZZY_WORDS = (
    "高级感", "高级", "简约", "质感", "精致", "大气", "时尚", "优雅", "精美",
    "奢华", "创意", "唯美", "震撼", "惊艳", "极致", "完美", "专业", "有feel",
    "modern", "minimalist", "elegant", "premium", "sophisticated", "stunning",
)

CJK = re.compile(r"[\u4e00-\u9fff]")
SIZE = re.compile(r"\d{3,4}\s*[×xX*·]\s*\d{3,4}")
PSEUDO = re.compile(r"^\s*(" + "|".join(PSEUDO_HEADERS) + r")\s*:", re.I | re.M)
# 真名锚点：连续的大写开头英文词（Dieter Rams / Penguin Books）+ 中文「××风格 / ××式」
PROPER_EN = re.compile(r"\b[A-Z][A-Za-z0-9&.\-]{2,}(?:\s+[A-Z][A-Za-z0-9&.\-]{2,})*")
PROPER_ZH = re.compile(r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z ]{1,12}?)(?:风格|式|设计语言|视觉)")
# 型号类真名：pocket3 / GPT-4 / iPhone15
MODEL = re.compile(r"\b[A-Za-z]{2,}\d{1,2}\b")

VIBE_TABLE = Path(__file__).resolve().parent.parent / "references" / "vibe-to-name.md"
KNOWN_EXTRA = ("大疆", "故宫", "敦煌", "荣宝斋", "景德镇", "苏州博物馆")


def load_known_names():
    """从 vibe-to-name.md 抽取全部真名，作为中文品牌名的识别词典。"""
    names = list(KNOWN_EXTRA)
    try:
        text = VIBE_TABLE.read_text(encoding="utf-8")
    except OSError:
        return names
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln.startswith("|") or ln.startswith("|---") or "候选真名" in ln:
            continue
        cell = ln.strip("|").split("|")[0].replace("🌐", "").strip()
        if cell and cell != "—":
            for part in re.split(r"[（(]/|、|/", cell):
                part = part.strip("（(）) ")
                if len(part) >= 2:
                    names.append(part)
    return names


def count_words(text: str) -> int:
    """粗略计数：中文按字，英文按词。"""
    cjk = len(CJK.findall(text))
    en = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", text))
    return cjk + en


def find_proper_nouns(text: str):
    names = []
    for m in PROPER_EN.finditer(text):
        w = m.group(0).strip()
        # 排除句首的普通英文词（那是句子开头，不是真名）
        before = text[: m.start()].rstrip()
        if not before and w.lower() in ("the", "a", "an", "this", "that"):
            continue
        names.append(w)
    for m in PROPER_ZH.finditer(text):
        names.append(m.group(1).strip())
    pseudo = {h.lower() for h in PSEUDO_HEADERS}
    known = load_known_names()
    for n in known:
        if len(n) >= 2 and n in text:
            names.append(n)
    for m in MODEL.finditer(text):
        names.append(m.group(0))
    # 去重保序（长名优先，避免「Rams」覆盖「Dieter Rams」）
    seen, out = set(), []
    for n in sorted(names, key=len, reverse=True):
        low = n.lower()
        if low in pseudo:          # 伪 section 名不算真名
            continue
        if low in seen:
            continue
        if any(low in s or s in low for s in seen):
            continue
        seen.add(low)
        out.append(n)
    return sorted(out, key=lambda x: text.find(x))


def lint(text: str):
    text = text.strip()
    results = []

    def add(level, name, msg):
        results.append({"level": level, "item": name, "msg": msg})

    cjk_n = len(CJK.findall(text))
    en_words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)
    total = count_words(text)

    # 1 · 语言：是否中文主体（红线 1）
    if cjk_n == 0 and len(en_words) > 12:
        add("FAIL", "语言", "整段英文且超过 12 个词 → 重写为中文短句（专有名词可保留原文）")
    elif cjk_n > 0 and cjk_n / max(total, 1) < 0.2 and len(en_words) > 15:
        add("WARN", "语言", "英文占比偏高 → 确认是不是段落式写法")
    else:
        add("PASS", "语言", "中文主体")

    # 2 · 长度（红线 2）
    if total < 5:
        add("FAIL", "长度", f"只有 {total} 字，信息量不足")
    elif total > 200:
        add("WARN", "长度", f"{total} 字偏长 → 删到一半还能懂就删（构图型 / infographic 可放宽）")
    else:
        add("PASS", "长度", f"{total} 字")

    # 3 · 真名锚点（红线 3）
    names = find_proper_nouns(text)
    if len(names) >= 2:
        add("PASS", "真名锚点", f"{len(names)} 个：" + " / ".join(names[:6]))
    elif len(names) == 1:
        add("WARN", "真名锚点", f"只有 1 个（{names[0]}）→ 再补 1 个，或查 references/vibe-to-name.md")
    else:
        add("FAIL", "真名锚点", "一个真名都没有 → 查 references/vibe-to-name.md 把感觉翻译成真名")

    # 4 · 伪 section（红线 4 第 4 条）
    hits = PSEUDO.findall(text)
    if hits:
        add("FAIL", "伪 section", "出现 " + " / ".join(sorted({h.title() for h in hits})) + " → 删掉，改成一句话")
    else:
        add("PASS", "伪 section", "无")

    # 5 · 形容词堆砌
    fuzzy = [w for w in FUZZY_WORDS if w in text.lower()]
    if len(fuzzy) >= 3:
        add("FAIL", "形容词堆砌", f"命中 {len(fuzzy)} 个（" + "、".join(fuzzy[:6]) + "）→ 换成真名")
    elif fuzzy:
        add("WARN", "形容词堆砌", "命中 " + "、".join(fuzzy) + " → 能用真名替换就替换")
    else:
        add("PASS", "形容词堆砌", "无")

    # 附 · 尺寸
    if SIZE.search(text):
        add("PASS", "尺寸", SIZE.search(text).group(0))
    else:
        add("WARN", "尺寸", "未指定 → 补上平台尺寸（公众号首图 1410×600 等）")

    fails = [r for r in results if r["level"] == "FAIL"]
    warns = [r for r in results if r["level"] == "WARN"]
    return results, fails, warns


def main():
    ap = argparse.ArgumentParser(description="prompt 5 项自检门禁")
    ap.add_argument("prompt", nargs="?", help="待检查的 prompt；'-' 表示从 stdin 读")
    ap.add_argument("--file", help="从文件读 prompt")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.prompt == "-":
        text = sys.stdin.read()
    elif args.prompt:
        text = args.prompt
    else:
        ap.error("给一个 prompt，或用 --file / -")

    results, fails, warns = lint(text)

    if args.json:
        print(json.dumps({"results": results, "fails": len(fails), "warns": len(warns)},
                         ensure_ascii=False, indent=2))
        return 1 if fails else 0

    print("prompt:", text.strip()[:80])
    print("-" * 60)
    mark = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]"}
    for r in results:
        print(f"{mark[r['level']]} {r['item']}：{r['msg']}")
    print("-" * 60)
    print(f"通过 {len([r for r in results if r['level'] == 'PASS'])} · "
          f"警告 {len(warns)} · 失败 {len(fails)}")
    if fails:
        print("\n🛑 有 FAIL 项 → 禁止交付，改完重跑（不要只改 FAIL 那一条，重跑全部）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
