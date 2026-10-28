"""Validate generated images and publish them atomically on every platform."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageOps


def parse_size(size: str | None) -> tuple[int, int] | None:
    if size is None:
        return None
    if not isinstance(size, str):
        raise ValueError("尺寸必须是字符串，例如 1410x600")
    match = re.fullmatch(r"\s*([1-9][0-9]*)\s*[x×X]\s*([1-9][0-9]*)\s*", size)
    if not match:
        raise ValueError("尺寸必须为正整数 WxH，例如 1410x600")
    return tuple(map(int, match.groups()))


def publish_image(source: Path, destination: Path, size: str | None = None) -> str:
    """Decode, center-crop to the requested ratio, then save a real PNG.

    Keep an existing destination intact if decoding or writing fails.
    """
    target = parse_size(size)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.load()
        image = ImageOps.exif_transpose(image).convert("RGBA")
        if target and image.size != target:
            image = ImageOps.fit(image, target, method=Image.Resampling.LANCZOS)
        dims = f"{image.width}x{image.height}"
        fd, name = tempfile.mkstemp(suffix=".png", dir=destination.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            image.save(temporary, format="PNG")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    return dims


def validate_jobs(jobs: list[dict]) -> None:
    """Reject malformed jobs and duplicate outputs before dispatching anything."""
    if not jobs:
        raise ValueError("批量文件没有有效 job")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("每个 job 必须是 JSON 对象")
        for field in ("prompt", "out"):
            if not isinstance(job.get(field), str) or not job[field].strip():
                raise ValueError(f"job 缺少非空字符串 {field}")
        parse_size(job.get("size"))
        if job.get("quality") is not None and job["quality"] not in ("low", "medium", "high"):
            raise ValueError("quality 必须是 low / medium / high")
        if job.get("model") is not None and (not isinstance(job["model"], str) or not job["model"].strip()):
            raise ValueError("model 必须是非空字符串")
        refs = job.get("ref")
        if refs is not None and not isinstance(refs, str):
            if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                raise ValueError("ref 必须是路径字符串或路径字符串列表")
        output = os.path.normcase(str(Path(job["out"]).resolve()))
        if output in seen:
            raise ValueError(f"批量任务输出路径重复: {job['out']}")
        seen.add(output)
