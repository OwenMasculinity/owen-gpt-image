#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""感觉词 → 真名 查询：把 references/vibe-to-name.md 变成可脚本化的查表工具。

用法：
    python scripts/vibe.py 高级感
    python scripts/vibe.py "温暖 治愈"          # 多个感觉词，任一命中即可
    python scripts/vibe.py 科技感 --pick 2      # 直接取第 2 个候选
    python scripts/vibe.py 高级感 --json

设计上刻意不调任何 LLM：离线查表，零 token，秒回。
真正的兜底（连表都查不到时）走 SKILL.md 里的「元 prompt」，让模型自己报名字。
"""

import argparse
import json
import re
import sys
from pathlib import Path

TABLE = Path(__file__).resolve().parent.parent / "references" / "vibe-to-name.md"


def load_table(path: Path):
    """解析 vibe-to-name.md，返回 [{keys, names:[{name, borrow, popular}], warn}]"""
    if not path.exists():
        sys.exit(f"找不到映射表：{path}")
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^### ", text, flags=re.M)[1:]
    groups = []
    for b in blocks:
        lines = b.splitlines()
        head = lines[0].strip()
        if not head or head.startswith("使用规则"):
            continue
        # 标题形如「1 · 高级感 / 简约 / 性冷淡 / 克制」
        head = re.sub(r"^\d+\s*·\s*", "", head)
        keys = [k.strip() for k in re.split(r"[/、,，]", head) if k.strip()]

        names = []
        for ln in lines:
            ln = ln.strip()
            if not ln.startswith("|") or ln.startswith("|---") or "候选真名" in ln:
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) < 2 or not cells[0] or cells[0] == "—":
                continue
            popular = "🌐" in cells[0]
            name = cells[0].replace("🌐", "").strip()
            borrow = cells[1] if len(cells) > 1 and cells[1] != "—" else ""
            names.append({"name": name, "borrow": borrow, "popular": popular})

        warn = ""
        for ln in lines:
            if "⚠️" in ln and ("翻车" in ln or "事故" in ln):
                warn = re.sub(r"^>\s*⚠️\s*", "", ln.strip()).strip()
                break
        groups.append({"keys": keys, "names": names, "warn": warn})
    return groups


def match(groups, words):
    hits = []
    for g in groups:
        for w in words:
            if any(w in k or k in w for k in g["keys"]):
                hits.append(g)
                break
    return hits


def main():
    ap = argparse.ArgumentParser(description="感觉词 → 设计真名 查表")
    ap.add_argument("vibe", help="感觉词，如 高级感 / 温暖 / 科技感；可空格分隔多个")
    ap.add_argument("--pick", type=int, help="直接取第 N 个候选（1-based）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    words = [w for w in re.split(r"[\s,，、]+", args.vibe.strip()) if w]
    groups = load_table(TABLE)
    hits = match(groups, words)

    if not hits:
        print(f"没查到「{args.vibe}」对应的真名。")
        print("兜底方案：用元 prompt，让模型自己报 3 个参照 ——")
        print()
        print("  [需求一句话]。我不确定该用什么风格参照，请你先说出 3 个最匹配的")
        print("  （设计师 / 品牌 / 媒介范式）参照，各用一句话说明你会从它身上借什么，")
        print("  然后选一个最合适的，按它生成。")
        return 2

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return 0

    for g in hits:
        print(f"\n{' / '.join(g['keys'])}")
        print("-" * 60)
        ordered = sorted(g["names"], key=lambda n: (not n["popular"],))
        for i, n in enumerate(ordered, 1):
            flag = "🌐 " if n["popular"] else "   "
            print(f"  {i}. {flag}{n['name']}")
            if n["borrow"]:
                print(f"       借：{n['borrow']}")
        if g["warn"]:
            print(f"\n  ⚠️ {g['warn']}")

        chosen = None
        if args.pick and 1 <= args.pick <= len(ordered):
            chosen = ordered[args.pick - 1]
        elif len(ordered):
            chosen = ordered[0]
        if chosen:
            print(f"\n  拼好的 prompt（把 [主体] 换成你要画的东西）：")
            print(f"    [主体]，{chosen['name']}风格，1410×600，无中文无水印。")

    print("\n提示：拿到真名后跑 python scripts/lint_prompt.py \"<prompt>\" 过一遍 5 项自检。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
