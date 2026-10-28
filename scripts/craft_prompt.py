#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""craft_prompt.py — 把 SKILL.md 的 prompt 加工规则脚本化，让「加工」真实发生在生图链路里。

背景：README 宣称「本仓库先拆三槽位、再补约束、再自检」，但如果生图脚本只是
把用户原话透传给模型，那加工就只存在于文档里，不存在于链路里——输出英文、
输出 nameplate 就是这么来的。本脚本把规则固化成代码，gen_via_*.py 默认调用它。

加工规则（全部来自 SKILL.md，不发明新规则）：
  1. 识别三槽位真名（复用 lint_prompt.find_proper_nouns）—— 报告，不改写
  2. 追加约束（默认开，--raw 关闭；已含的约束不重复加）：
     - 红线 1.2：图里描述性文字默认中文（用户明确要外文时除外）
     - 实测标准收尾：无水印
     - 红线 3 出版物陷阱：风格锚点是报刊品牌时加「严禁左上角 nameplate」
     - 尺寸（--size 传入时）
  3. invite 建议（--invite 才写入 prompt）：包装/手册类载体且用户没明说时，
     建议「请你贡献品牌名/slogan/命名逻辑」——默认只建议不自动加，不替用户改意图
  4. 跑 lint_prompt 5 项自检（红线 4），有 FAIL 时退出码 1，调用方应拒绝生图

用法：
    python scripts/craft_prompt.py "Dieter Rams 风格的大疆 pocket3 说明书" --size 1024x1024
    python scripts/craft_prompt.py "..." --json          # 全量结构化输出
    python scripts/craft_prompt.py "..." --raw           # 不加工，原样返回（调试用）

退出码：0 通过 / 1 自检有 FAIL / 2 用法错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint_prompt import find_proper_nouns, lint  # noqa: E402

# 红线 3 实测陷阱：出版物品牌名会被模型画成 nameplate 且自然走全英文排版。
# 只对「报刊/杂志」类生效；设计师人名、图书/产品品牌（Penguin Books / Apple）不拦。
PUBLICATION_BRANDS = (
    "The Economist", "WSJ", "Wall Street Journal", "Field Notes",
    "NYT Magazine", "New York Times Magazine", "Wired", "The New Yorker",
    "经济学人", "卫报", "金融时报",
)

# 用户明确要外文时不加中文约束（说明书场景：德文/英文/日文说明书本身合理）
FOREIGN_INTENT = ("德文", "德语", "英文", "英语", "日文", "日语", "法文", "法语", "韩文", "德语说明书")

# invite 模式的高潜载体（SKILL.md：「创造贡献空间：包装空间大」）
INVITE_CARRIERS = ("包装", "手册", "说明书", "品牌", "海报", "封面")

CN_TEXT = "图里描述性文字用中文"
NO_WATERMARK = "无水印"
NO_NAMEPLATE = "严禁左上角外文 nameplate"


def _has(text: str, frag: str) -> bool:
    return frag in text


def craft(prompt: str, size: str | None = None, invite: bool = False) -> dict:
    """加工主函数。返回 {crafted, steps, names, invites, lint}。"""
    steps: list[str] = []
    text = prompt.strip()

    # 1) 三槽位真名识别（只报告，不改写——真名是用户/ vibe 表给的，不是脚本编的）
    names = find_proper_nouns(text)
    steps.append(f"识别真名 {len(names)} 个：" + (" / ".join(names[:6]) if names else "（无）"))

    out = text

    # 2a) 红线 1.2：图里描述性文字默认中文
    if not any(k in text for k in FOREIGN_INTENT) and not _has(out, CN_TEXT) and not _has(out, "中文"):
        out += f"，{CN_TEXT}"
        steps.append(f"补中文约束（红线 1.2，防模型默认跳英文）：{CN_TEXT}")
    elif any(k in text for k in FOREIGN_INTENT):
        steps.append("检测到外文意图 → 跳过中文约束")

    # 2b) 出版物 nameplate 陷阱防护（红线 3）
    hit_pub = [b for b in PUBLICATION_BRANDS if b.lower() in text.lower()]
    if hit_pub and not _has(out, "nameplate"):
        out += f"，{NO_NAMEPLATE}"
        steps.append(f"风格锚点是报刊品牌（{' / '.join(hit_pub)}）→ 补 nameplate 禁令（红线 3 实测陷阱）")

    # 2c) 无水印（SKILL.md 实测案例的标准收尾）
    if not _has(out, "水印"):
        out += f"，{NO_WATERMARK}"
        steps.append(f"补无水印约束：{NO_WATERMARK}")

    # 2d) 尺寸
    if size and not _has(out, size):
        out += f"，{size}"
        steps.append(f"补尺寸：{size}")

    # 3) invite 建议（默认只建议，不自动写）
    invite_hint = None
    if not invite:
        carrier = next((c for c in INVITE_CARRIERS if c in text), None)
        if carrier and "品牌名" not in text and "slogan" not in text.lower():
            invite_hint = (f"载体「{carrier}」有命名贡献空间 → 可加 --invite 写入"
                           "「请你贡献品牌名/slogan/命名逻辑」（SKILL.md 实测 9→9.5 分）")
            steps.append("invite 建议：" + invite_hint)
    else:
        if "品牌名" not in out and "slogan" not in out.lower():
            out += "。请你贡献品牌名/slogan/命名逻辑"
            steps.append("写入 invite：请你贡献品牌名/slogan/命名逻辑")

    # 4) 5 项自检（红线 4）
    results, fails, warns = lint(out)

    return {
        "original": prompt.strip(),
        "crafted": out,
        "steps": steps,
        "names": names,
        "invite_hint": invite_hint,
        "lint": {"results": results, "fails": len(fails), "warns": len(warns)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SKILL.md prompt 加工规则脚本化")
    ap.add_argument("prompt", nargs="?", help="待加工的 prompt")
    ap.add_argument("--size", help="尺寸，如 1024x1024")
    ap.add_argument("--invite", action="store_true", help="写入 invite 命名贡献指令")
    ap.add_argument("--raw", action="store_true", help="不加工，原样返回（调试用）")
    ap.add_argument("--json", action="store_true", dest="as_json", help="JSON 输出")
    args = ap.parse_args()

    if not args.prompt:
        ap.error("给一个 prompt")

    if args.raw:
        print(args.prompt.strip())
        return 0

    r = craft(args.prompt, size=args.size, invite=args.invite)

    if args.as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for s in r["steps"]:
            print(f"· {s}", file=sys.stderr)
        if r["invite_hint"]:
            print(f"💡 {r['invite_hint']}", file=sys.stderr)
        for item in r["lint"]["results"]:
            mark = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[item["level"]]
            print(f"{mark} {item['item']}：{item['msg']}", file=sys.stderr)
        # stdout 只吐加工后的 prompt，方便管道接力
        print(r["crafted"])

    return 1 if r["lint"]["fails"] else 0


if __name__ == "__main__":
    sys.exit(main())
