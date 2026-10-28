#!/usr/bin/env python3
"""gen_via_codex.py — 走 codex 订阅额度的 GPT-image-2 生成链路（不需 OPENAI_API_KEY）。

owen-gpt-image 负责把 prompt 写到 9.5 分，这个脚本负责把图真的生出来。
底层调用 `codex exec -s workspace-write` 里的内置 $imagegen skill（gpt-image-2），
吃的是 codex login 的 ChatGPT 订阅额度，不按 API 计费。

为什么不直接调 ~/.codex/skills/.system/imagegen/scripts/image_gen.py？
  那个 fallback CLI 精确控参数（--size/--quality/--n/generate-batch 并发），
  但 hardcode 要 OPENAI_API_KEY、按量计费。花叔选了走订阅额度，所以走 codex agent。
  代价：尺寸/quality 靠自然语言指令传给 agent，脚本用 Pillow 校验并处理到目标尺寸。

用法：
  # 单图
  python gen_via_codex.py --prompt "Anthropic 风格的越文化青铜器特写" \
      --out 配图/bronze.png --size 1410x600 --quality high

  # 图生图（参考图改写）。-i 用 stdin 传 prompt 规避 codex 变长参数吞 prompt 的陷阱
  python gen_via_codex.py --prompt "改成蓝色调" --out out.png --ref base.png

  # 多参考图叠加：花叔品牌资产 + 产品 logo（封面涉及具体 AI 产品时）。ref 传 PNG（底层 -i 不吃 SVG）
  python gen_via_codex.py --prompt "用参考图1的花叔像素品牌 DNA 生成封面，参考图2是 ChatGPT 官方 logo 用于画面里的产品标识" \
      --out 配图/封面.png --size 1600x900 --quality high \
      --ref _archive/像素品牌资产.png --ref "04-写作参考/品牌Logo库/OpenAI/ChatGPT.png"

  # 批量并发（JSONL，每行一个 job：{"prompt":..., "out":..., "size":..., "quality":...}）
  python gen_via_codex.py --batch jobs.jsonl --concurrency 3

退出码：0 全部成功 / 1 有失败。失败的 job 会打印到 stderr，不中断其余。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from image_output import parse_size, publish_image, validate_jobs
# codex exec 单张实测 150-280s（high+大图），给足超时；可用环境变量覆盖
PER_IMAGE_TIMEOUT = int(os.environ.get("GEN_IMAGE_TIMEOUT", "600"))


def _eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def _build_codex_prompt(prompt: str, out: str, size: str | None, quality: str | None,
                        use_craft: bool = True) -> str:
    """构造给 codex agent 的中文生成指令。保持简短——agent 自己会调 $imagegen。

    默认先过 craft_prompt（SKILL.md 红线 1.2/3/4 的脚本化）：识别真名、
    补「图里文字用中文」「无水印」、出版物 nameplate 防护。--no-craft 透传。
    """
    if use_craft:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from craft_prompt import craft as craft_prompt
        r = craft_prompt(prompt, size=None)
        for s in r["steps"]:
            _eprint(f"  · craft: {s}")
        prompt = r["crafted"]
        if r["lint"]["fails"]:
            raise ValueError(f"craft 自检有 {r['lint']['fails']} 个 FAIL，禁止生图（先改 prompt）")
    lines = [f"用 $imagegen 生成图片，保存到 {out}。"]
    if size:
        lines.append(f"尺寸严格 {size} 像素（生成后如不符请裁剪/缩放到精确尺寸）。")
    if quality:
        lines.append(f"quality 用 {quality}。")
    lines.append(f"图片内容：{prompt}")
    lines.append("只生成这一张图，保存后直接结束，不要追问、不要多余解释。")
    return "\n".join(lines)


def _quota_error(text: str) -> bool:
    return bool(re.search(
        r"\b429\b|insufficient_quota|quota exceeded|quota exhausted|"
        r"usage limit|rate limit|rate_limit|额度.{0,8}(耗尽|用完|不足)|达到.{0,8}上限",
        text, re.IGNORECASE,
    ))


def generate_one(prompt: str, out: str, size: str | None = None,
                 quality: str | None = None, ref=None,
                 use_craft: bool = True, fallback: bool = True,
                 model: str | None = None) -> tuple[bool, str]:
    """Run each job into its own staging directory; publish only validated output.

    Never infer ownership from the shared generated_images directory. A failed
    process or a pre-existing --out file cannot count as a successful generation.
    """
    try:
        parse_size(size)
        out_path = Path(out).resolve()
        refs = [] if not ref else ([ref] if isinstance(ref, str) else list(ref))
        refs = [str(Path(r).resolve()) for r in refs]
        for r in refs:
            if not Path(r).is_file():
                return False, f"参考图不存在: {r}"
        # Check prompt policy before starting either backend.
        instruction = _build_codex_prompt(prompt, "__JOB_OUTPUT__", size, quality, use_craft)
        executable = shutil.which("codex")
        if not executable:
            return False, "找不到 codex CLI。请先安装并运行 codex login。"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".image-job-", dir=out_path.parent) as directory:
            staged = Path(directory) / "generated.png"
            full_prompt = instruction.replace("保存到 __JOB_OUTPUT__。", f"保存到 {staged}。", 1)
            cmd = [executable, "exec", "-s", "workspace-write"]
            selected_model = model or os.environ.get("GEN_CODEX_MODEL")
            if selected_model:
                cmd += ["--model", selected_model]
            for r in refs:
                cmd += ["-i", r]
            cmd += ["-"]
            started = time.monotonic()
            result = subprocess.run(
                cmd, input=full_prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=PER_IMAGE_TIMEOUT,
            )
            diagnostic = (result.stderr or "") + "\n" + (result.stdout or "")
            if result.returncode != 0 or not staged.is_file():
                if fallback and _quota_error(diagnostic):
                    from gen_via_chatgpt_web import check_health, generate_one as generate_web
                    _eprint("Codex 额度受限，自动切换到 ChatGPT 网页桥。")
                    healthy, message = check_health()
                    if not healthy:
                        return False, f"Codex 额度受限；网页桥不可用: {message}"
                    ok, message = generate_web(prompt, str(out_path), size, quality, refs, use_craft)
                    return ok, f"[fallback: chatgpt-web] {message}"
                hint = ""
                if "model_not_found" in diagnostic or "not supported" in diagnostic and "model" in diagnostic:
                    hint = "模型不可用；请用 --model 或 GEN_CODEX_MODEL 指定当前账户支持的模型。\n"
                return False, f"{hint}Codex 失败 (exit={result.returncode}) 或未产出任务文件: {diagnostic[-500:]}"
            dims = publish_image(staged, out_path, size)
            return True, f"{out_path} [{dims}] {time.monotonic() - started:.0f}s"
    except subprocess.TimeoutExpired:
        return False, f"超时 (>{PER_IMAGE_TIMEOUT}s)"
    except (OSError, ValueError) as error:
        return False, str(error)


def run_batch(jobs: list[dict], concurrency: int, fallback: bool = True,
              model: str | None = None) -> int:
    try:
        validate_jobs(jobs)
    except (ValueError, TypeError) as error:
        _eprint(f"Error: {error}")
        return 2
    _eprint(f"批量 {len(jobs)} 张，并发 {concurrency}")
    failed = 0

    def _do(i: int, job: dict) -> tuple[int, bool, str]:
        ok, msg = generate_one(
            prompt=job["prompt"], out=job["out"],
            size=job.get("size"), quality=job.get("quality"), ref=job.get("ref"),
            use_craft=job.get("craft", True), fallback=fallback,
            model=job.get("model") or model,
        )
        return i, ok, msg

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = [ex.submit(_do, i, j) for i, j in enumerate(jobs, 1)]
        for fut in as_completed(futs):
            i, ok, msg = fut.result()
            mark = "✅" if ok else "❌"
            _eprint(f"{mark} [{i}/{len(jobs)}] {msg}")
            if not ok:
                failed += 1
    _eprint(f"完成：{len(jobs) - failed} 成功 / {failed} 失败")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="走 codex 订阅额度的 gpt-image-2 生成链路")
    ap.add_argument("--prompt", help="图片内容描述（单图模式）")
    ap.add_argument("--out", help="输出路径（单图模式）")
    ap.add_argument("--size", help="如 1410x600；脚本居中裁剪并缩放到精确尺寸")
    ap.add_argument("--quality", choices=["low", "medium", "high"], help="密集/中文/卡牌用 high")
    ap.add_argument("--ref", action="append",
                    help="参考图路径（图生图）。可多次传入叠加多张参考图，"
                         "如 --ref 像素品牌资产.png --ref 品牌Logo库/OpenAI/ChatGPT.svg")
    ap.add_argument("--batch", help="JSONL 文件，每行一个 job")
    ap.add_argument("--concurrency", type=int, default=3, help="批量并发数（默认3，订阅额度勿过高）")
    ap.add_argument("--craft", action="store_true", default=True,
                    help="先过 craft_prompt 加工再发（默认开）")
    ap.add_argument("--no-craft", dest="craft", action="store_false",
                    help="关闭 prompt 加工，原样透传（调试用）")
    ap.add_argument("--no-fallback", dest="fallback", action="store_false",
                    help="额度耗尽时不自动切换网页桥")
    ap.add_argument("--model", help="覆盖 Codex 模型（也可设置 GEN_CODEX_MODEL；默认使用 CLI 配置）")
    args = ap.parse_args()

    if args.batch:
        path = Path(args.batch)
        if not path.exists():
            _eprint(f"Error: 批量文件不存在 {path}")
            return 2
        jobs = []
        for ln_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            ln = raw.strip()
            if not ln or ln.startswith("#"):
                continue
            try:
                job = json.loads(ln)
            except json.JSONDecodeError as e:
                _eprint(f"Error: 第 {ln_no} 行 JSON 解析失败: {e}")
                return 2
            if not isinstance(job, dict) or "prompt" not in job or "out" not in job:
                _eprint(f"Error: 第 {ln_no} 行缺 prompt 或 out")
                return 2
            jobs.append(job)
        if not jobs:
            _eprint("Error: 批量文件没有有效 job")
            return 2
        return run_batch(jobs, max(1, args.concurrency), args.fallback, args.model)

    if not args.prompt or not args.out:
        _eprint("Error: 单图模式需要 --prompt 和 --out（或用 --batch）")
        return 2
    ok, msg = generate_one(args.prompt, args.out, args.size, args.quality, args.ref, args.craft, args.fallback, args.model)
    _eprint(("✅ " if ok else "❌ ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
