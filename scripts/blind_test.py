#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""九宫格盲测：让不懂设计的用户「指认」而不是「描述」。

两条硬原则 —— 这是本脚本存在的全部理由：

1. **检索优先**：盲测阶段只做检索。查 references/vibe-to-name.md 拿候选真名，
   再从本地参考图库里检索出对应的风格示意图，拼成一张带编号的看板。
   **不调用任何生图接口。**
2. **生成克制**：用户指认之后默认只生成选中的那 1 张。
   只有用户明确要求多种风格（--variants N）时才生成 N 张。

生图接口很贵。在「还不知道自己要什么」的时候烧 9 次额度是最蠢的花法；
等用户看清九种可能、指认出一种之后再生成，成本是 1 次。
所以这里的「九宫格」默认是**检索回来的参考图**，不是新生成的九张图。

用法：
    python scripts/blind_test.py 高级感                    # 检索 + 出编号看板（不生图）
    python scripts/blind_test.py 高级感 --top 9             # 候选数量，默认 9
    python scripts/blind_test.py 高级感 --images-dir DIR    # 本地参考图库（或设 $IMAGE_LIB）
    python scripts/blind_test.py 高级感 --board board.png   # 看板输出路径
    python scripts/blind_test.py 高级感 --pick 3            # 选 3 号，给出最终 prompt
    python scripts/blind_test.py 高级感 --pick 3 --generate --subject "大疆 pocket3 说明书"
    python scripts/blind_test.py 高级感 --variants 4 --generate --subject "..."   # 明确要 4 种
    python scripts/blind_test.py 高级感 --json              # 结构化输出，给 agent 用
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vibe  # noqa: E402  复用 vibe.py 的查表逻辑

TABLE = ROOT / "references" / "vibe-to-name.md"
GEN_SCRIPT = HERE / "gen_via_codex.py"
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

# 文件名别名：参考图库里的文件很少叫「无印良品.png」，多半是 muji / MUJI-style
ALIASES = {
    "无印良品": ["muji", "wuyinliangpin", "无印"],
    "Dieter Rams": ["rams", "braun", "dieterrams", "博朗"],
    "Jil Sander": ["sander", "jilsander"],
    "吉卜力背景美术": ["ghibli", "吉卜力", "宫崎骏"],
    "Dick Bruna（米菲）": ["bruna", "miffy", "米菲"],
    "Apple 设计语言": ["apple", "苹果"],
    "Penguin Books": ["penguin", "企鹅"],
    "原研哉": ["hara", "kenyahara", "原研哉"],
    "包豪斯": ["bauhaus", "包豪斯"],
    "赛博朋克": ["cyberpunk", "赛博"],
    "故宫文创": ["gugong", "故宫", "forbidden"],
    "苏联构成主义": ["constructivism", "构成主义"],
    "老上海月份牌": ["yuefenpai", "月份牌", "shanghai"],
    "北欧童书插画": ["nordic", "北欧"],
    "NASA 控制台": ["nasa"],
    "乐高": ["lego", "乐高"],
    "宜家": ["ikea", "宜家"],
}

# 没有参考图时的占位底色（本地渲染，不是 AIGC）
SWATCH = [
    (232, 230, 225), (226, 234, 226), (238, 232, 220), (222, 230, 238),
    (238, 226, 226), (230, 226, 238), (226, 238, 236), (238, 236, 222),
    (228, 228, 232),
]

FONTS = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

META_PROMPT = (
    "[需求一句话]。我不确定该用什么风格参照，请你先说出 3 个最匹配的\n"
    "（设计师 / 品牌 / 媒介范式）参照，各用一句话说明你会从它身上借什么，\n"
    "然后选一个最合适的，按它生成。"
)


def norm(s):
    """归一化：小写 + 只保留字母数字和中文，用于文件名匹配。"""
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(s).lower())


def spread(hits, top, all_groups=None):
    """跨家族轮转取候选。

    直接按组顺序取会拿到同一感觉下的 3 个近亲（九张雷同），
    所以这里按「每组先出第 1 个、再出第 2 个」轮转，保证前几个候选来自不同家族。

    一个感觉词往往只命中 1 组（3 个候选），凑不满九宫格。
    这时从其他感觉家族轮转补足，并标记 extended=True ——
    输出时会区分「直接命中」和「拓展候选」，避免用户以为它们同样贴题。
    """
    pools = []
    for g in hits:
        names = sorted(g["names"], key=lambda n: (not n["popular"],))
        if not names:
            continue
        pools.append([
            {**n, "group": " / ".join(g["keys"]), "warn": g.get("warn", ""),
             "extended": False}
            for n in names
        ])

    out, i = [], 0
    while len(out) < top:
        added = False
        for p in pools:
            if i < len(p):
                out.append(p[i])
                added = True
                if len(out) >= top:
                    break
        if not added:
            break
        i += 1

    if len(out) < top and all_groups:
        hit_keys = [set(g["keys"]) for g in hits]
        extras = []
        for g in all_groups:
            if set(g["keys"]) in hit_keys:
                continue
            names = sorted(g["names"], key=lambda n: (not n["popular"],))
            extras.append([
                {**n, "group": " / ".join(g["keys"]), "warn": g.get("warn", ""),
                 "extended": False}
                for n in names
            ])
        seen = {c["name"] for c in out}
        i = 0
        while len(out) < top:
            added = False
            for p in extras:
                if i < len(p):
                    n = p[i]
                    if n["name"] not in seen:
                        n["extended"] = True
                        out.append(n)
                        seen.add(n["name"])
                        added = True
                        if len(out) >= top:
                            break
            if not added:
                break
            i += 1
    return out


def find_ref(name, images_dir):
    """在本地参考图库里按名字 / 别名检索示意图。找不到返回 None。"""
    if not images_dir:
        return None
    d = Path(os.path.expanduser(str(images_dir)))
    if not d.is_dir():
        return None

    keys = [norm(name)] + [norm(a) for a in ALIASES.get(name, [])]
    keys += [norm(w) for w in re.findall(r"[A-Za-z]{3,}", name)]
    keys = [k for k in keys if k]

    for p in sorted(d.rglob("*")):
        # 跳过 0 字节文件
        if p.stat().st_size == 0:
            continue
        if p.suffix.lower() in IMG_EXT:
            stem = norm(p.stem)
            if any(k and k in stem for k in keys):
                return p
    return None


def load_font(size):
    from PIL import ImageFont
    for p in FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def build_board(items, out, cols=3, cell=320, pad=16):
    """把候选拼成一张带编号的看板。本地渲染，零 API 成本。

    有参考图就贴真实示意，没有就用底色块 + 编号 + 名字占位。
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    rows = (len(items) + cols - 1) // cols
    W = cols * cell + (cols + 1) * pad
    H = rows * cell + (rows + 1) * pad
    board = Image.new("RGB", (W, H), (250, 250, 248))
    d = ImageDraw.Draw(board)
    f_num = load_font(42)
    f_name = load_font(24)

    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad)
        d.rectangle([x, y, x + cell, y + cell],
                    fill=SWATCH[i % len(SWATCH)], outline=(150, 148, 140), width=1)

        ref = it.get("ref")
        if ref:
            try:
                im = Image.open(ref).convert("RGB")
                im.thumbnail((cell, cell))
                board.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2))
            except Exception:
                pass

        badge = 56
        d.rounded_rectangle([x + 12, y + 12, x + 12 + badge, y + 12 + badge],
                            radius=12, fill=(24, 24, 22))
        d.text((x + 12 + badge // 2, y + 12 + badge // 2), str(it["n"]),
               font=f_num, fill=(255, 255, 255), anchor="mm")

        label = it["name"]
        bar_w = min(cell - 24, max(96, 24 + len(label) * 28))
        d.rectangle([x + 12, y + cell - 62, x + 12 + bar_w, y + cell - 12], fill=(24, 24, 22))
        d.text((x + 22, y + cell - 37), label, font=f_name, fill=(255, 255, 255), anchor="lm")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out)
    return out


def compose_prompt(name, subject, size="1410x600"):
    """三槽位拼装：主体 + 真名 + 技术参数。"""
    subj = (subject or "").strip() or "[主体]"
    return f"{subj}，{name}风格，{size.replace('x', '×')}，无水印。"


def slug(text, n):
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text)).strip("-").lower()
    return (s or "cand")[:24] + f"-{n}"


def run_generator(jobs, size=None, quality="high", dry=False, runner=None):
    """真正调生图脚本。runner 可注入（测试用），dry 只回显命令。"""
    results = []
    for j in jobs:
        cmd = [sys.executable, str(GEN_SCRIPT), "--prompt", j["prompt"], "--out", str(j["out"])]
        if size:
            cmd += ["--size", size]
        if quality:
            cmd += ["--quality", quality]
        rec = {"out": str(j["out"]), "prompt": j["prompt"], "cmd": cmd}
        if dry:
            rec.update(ok=True, dry=True)
        elif runner is not None:
            rec.update(runner(cmd, j) or {})
            rec.setdefault("ok", True)
        else:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            rec.update(ok=(p.returncode == 0),
                       err=((p.stderr or "") + (p.stdout or ""))[-300:])
        results.append(rec)
    return results


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass

    ap = argparse.ArgumentParser(description="九宫格盲测：检索优先，生成克制")
    ap.add_argument("vibe", help="感觉词，如 高级感 / 温暖 / 科技感")
    ap.add_argument("--top", type=int, default=9, help="候选数量，默认 9")
    ap.add_argument("--images-dir", default=os.environ.get("IMAGE_LIB", str(ROOT / "docs" / "cases")),
                    help="本地参考图库目录（也可用环境变量 IMAGE_LIB）")
    ap.add_argument("--board", default="blind-test-board.png", help="看板输出路径")
    ap.add_argument("--no-board", action="store_true", help="不生成看板")
    ap.add_argument("--pick", type=int, help="选第 N 号（1-based）")
    ap.add_argument("--variants", type=int, help="明确要求生成 N 种风格（会烧 N 次额度）")
    ap.add_argument("--generate", action="store_true", help="真的去生图（默认不生）")
    ap.add_argument("--subject", default="", help="要画的东西，如「大疆 pocket3 说明书」")
    ap.add_argument("--size", default="1410x600")
    ap.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    ap.add_argument("--outdir", default="outputs")
    ap.add_argument("--dry-run", action="store_true", help="只回显要执行的命令")
    ap.add_argument("--json", action="store_true", help="结构化输出")
    ap.add_argument("--history", default="", help="把选择追加到该 JSONL 文件")
    args = ap.parse_args(argv)

    if args.pick and args.variants:
        print("--pick 和 --variants 只能给一个。", file=sys.stderr)
        return 2
    if args.variants and not args.generate:
        print("--variants 必须和 --generate 一起用（否则不会生图）。", file=sys.stderr)
        return 2

    words = [w for w in re.split(r"[\s,，、]+", args.vibe.strip()) if w]
    groups = vibe.load_table(TABLE)
    hits = vibe.match(groups, words)
    if not hits:
        if args.json:
            print(json.dumps({"ok": False, "reason": "no-hit", "meta_prompt": META_PROMPT},
                             ensure_ascii=False, indent=2))
        else:
            print(f"没查到「{args.vibe}」对应的真名。用元 prompt 让模型自己报名字：\n")
            print("  " + META_PROMPT.replace("\n", "\n  "))
        return 2

    cands = spread(hits, max(1, args.top), all_groups=groups)
    for i, c in enumerate(cands, 1):
        c["n"] = i
        ref = find_ref(c["name"], args.images_dir)
        c["ref"] = str(ref) if ref else None

    board_path = None
    if not args.no_board and not args.json:
        board_path = build_board(cands, args.board)

    # ---- 选哪个 ----
    if args.variants:
        chosen_idx = list(range(min(args.variants, len(cands))))
    else:
        idx = (args.pick or 1) - 1
        if not (0 <= idx < len(cands)):
            print(f"--pick {args.pick} 超出范围（共 {len(cands)} 个候选）。", file=sys.stderr)
            return 2
        chosen_idx = [idx]

    chosen = [cands[i] for i in chosen_idx]

    if args.json:
        print(json.dumps({
            "ok": True,
            "vibe": args.vibe,
            "candidates": cands,
            "chosen": chosen,
            "board": str(board_path) if board_path else None,
            "prompts": [compose_prompt(c["name"], args.subject, args.size) for c in chosen],
            "will_generate": bool(args.generate),
            "generate_count": len(chosen) if args.generate else 0,
            "reference_count": sum(bool(c["ref"]) for c in cands),
            "placeholder_count": sum(not c["ref"] for c in cands),
        }, ensure_ascii=False, indent=2))
        return 0

    # ---- 人读输出 ----
    families = len({c["group"] for c in cands})
    direct = sum(1 for c in cands if not c.get("extended"))
    print(f"\n「{args.vibe}」→ {len(cands)} 个候选：{direct} 个直接命中"
          f" + {len(cands) - direct} 个拓展候选"
          f"（跨 {families} 个感觉家族，避免九张雷同）\n")
    for c in cands:
        flag = "🌐 " if c["popular"] else "  "
        ext = "＋" if c.get("extended") else "  "
        mark = " ←" if c["n"] - 1 in chosen_idx else ""
        ref = f"  参考图 {Path(c['ref']).name}" if c["ref"] else ""
        print(f"  {c['n']:>2}.{ext} {flag}{c['name']}{mark}{ref}")
        if c["borrow"]:
            print(f"        借：{c['borrow']}")
    print("\n  ＋＝拓展候选（其他感觉家族），用来拓宽选择面，不一定同样贴题")
    # 只显示直接命中组的翻车提示：拓展候选来自别的家族，它们的警告跟本次需求无关
    warns, seen_w = [], set()
    for c in cands:
        w = c.get("warn")
        if w and not c.get("extended") and w not in seen_w:
            seen_w.add(w)
            warns.append(w)
    for w in warns:
        print(f"\n  ⚠️ {w}")

    if board_path:
        missing = sum(not c["ref"] for c in cands)
        print(f"\n  看板：{board_path}")
        if missing:
            print(f"  其中 {missing} 张是文字占位卡，不代表真实风格效果；可用 --images-dir 补充参考图库。")
        print(f"  下一步：python scripts/blind_test.py {args.vibe} --pick <编号>")
    elif not args.no_board:
        print("\n  （Pillow 不可用，跳过看板渲染；上面清单同样可以指认）")

    print("\n  已选：" + "、".join(f"{c['n']} 号 {c['name']}" for c in chosen))
    for c in chosen:
        print(f"    prompt → {compose_prompt(c['name'], args.subject, args.size)}")

    if args.history:
        try:
            hp = Path(args.history)
            hp.parent.mkdir(parents=True, exist_ok=True)
            with hp.open("a", encoding="utf-8") as f:
                for c in chosen:
                    f.write(json.dumps({"ts": int(time.time()), "vibe": args.vibe,
                                        "name": c["name"], "n": c["n"]},
                                       ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"  （历史写入失败：{e}）", file=sys.stderr)

    if not args.generate:
        print("\n  未生图（默认只检索）。要生成选中的这张：")
        print(f"    python scripts/blind_test.py {args.vibe} "
              f"--pick {chosen[0]['n']} --generate --subject \"{args.subject or '[主体]'}\"")
        print("  想要多种风格才加 --variants N —— 那会烧 N 次额度。")
        return 0

    # ---- 真的生图 ----
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for k, c in enumerate(chosen, 1):
        jobs.append({
            "prompt": compose_prompt(c["name"], args.subject, args.size),
            "out": outdir / (slug(c["name"], k) + ".png"),
        })

    if args.variants:
        print(f"\n  将生成 {len(jobs)} 张（--variants {args.variants}，烧 {len(jobs)} 次额度）")
    else:
        print(f"\n  将生成 1 张 —— 只生成选中的那一张，不是 {len(cands)} 张。")
    if args.dry_run:
        print("  （--dry-run，不真正执行）")

    results = run_generator(jobs, size=args.size, quality=args.quality, dry=args.dry_run)
    for r in results:
        state = "OK " if r.get("ok") else "FAIL"
        print(f"  [{state}] {r['out']}")
        if r.get("err"):
            print(f"         {r['err']}")
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
