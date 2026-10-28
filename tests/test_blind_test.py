#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/blind_test.py 的验收测试。

跑法：
    python tests/test_blind_test.py
    python -m unittest discover -s tests -v

重点验收的是两条硬原则：
    A. 检索优先 —— 不传 --generate 就绝不调生图脚本
    B. 生成克制 —— 默认只生成选中的 1 张，只有 --variants N 才生成 N 张
"""

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import blind_test  # noqa: E402


class FakeGen:
    """顶替 run_generator，只记录被要求生成几个 job。"""

    def __init__(self):
        self.jobs = []
        self.kwargs = None

    def __call__(self, jobs, **kw):
        self.jobs = list(jobs)
        self.kwargs = kw
        return [{"ok": True, "out": str(j["out"])} for j in jobs]


def run_main(argv):
    """调 main 并返回 (返回码, 捕获的 stdout)。"""
    buf = StringIO()
    real = sys.stdout
    sys.stdout = buf
    try:
        code = blind_test.main(argv)
    finally:
        sys.stdout = real
    return code, buf.getvalue()


class TestCandidates(unittest.TestCase):
    def test_json_reports_reference_coverage(self):
        code, output = run_main(["高级感", "--json", "--images-dir", "/nonexistent-dir-xyz"])
        data = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(data["reference_count"], 0)
        self.assertEqual(data["placeholder_count"], len(data["candidates"]))

    def setUp(self):
        self.all = blind_test.vibe.load_table(blind_test.TABLE)
        self.hits = blind_test.vibe.match(self.all, ["高级感"])

    def test_hit_found(self):
        self.assertTrue(self.hits, "「高级感」应该能在 vibe-to-name.md 里查到")

    def test_first_candidate_is_popular(self):
        c = blind_test.spread(self.hits, 9)
        self.assertTrue(c[0]["popular"], "第一个候选应当是大众可识别的（🌐）")

    def test_spread_caps_at_top(self):
        self.assertEqual(len(blind_test.spread(self.hits, 4, self.all)), 4)
        self.assertEqual(len(blind_test.spread(self.hits, 9, self.all)), 9)

    def test_spread_crosses_families(self):
        """多个感觉词命中多组时，前几个候选必须来自不同家族（否则九张雷同）。"""
        hits = blind_test.vibe.match(self.all, ["高级感", "暖", "科技感"])
        groups = {g["keys"][0] for g in hits}
        self.assertGreaterEqual(len(groups), 3, "测试前提：至少命中 3 个家族")
        cands = blind_test.spread(hits, 9, self.all)
        head = [c["group"] for c in cands[:3]]
        self.assertEqual(len(set(head)), 3, f"前三个候选应当跨家族，实际：{head}")

    def test_no_duplicate_names(self):
        cands = blind_test.spread(self.hits, 9, self.all)
        names = [c["name"] for c in cands]
        self.assertEqual(len(names), len(set(names)), "候选不应重复")


class TestPrompt(unittest.TestCase):
    def test_compose_prompt_has_three_slots(self):
        p = blind_test.compose_prompt("无印良品", "大疆 pocket3 说明书")
        self.assertIn("大疆 pocket3 说明书", p)
        self.assertIn("无印良品", p)
        self.assertIn("1410×600", p)

    def test_compose_prompt_placeholder(self):
        self.assertIn("[主体]", blind_test.compose_prompt("无印良品", ""))


class TestReferenceSearch(unittest.TestCase):
    def test_find_ref_by_alias(self):
        with tempfile.TemporaryDirectory() as d:
            buf = b"\x89PNG\r\n\x1a\n" + b"\0" * 40
            (Path(d) / "muji-poster.png").write_bytes(buf)
            (Path(d) / "rams-braun.jpg").write_bytes(buf)
            self.assertIsNotNone(blind_test.find_ref("无印良品", d))
            self.assertIsNotNone(blind_test.find_ref("Dieter Rams", d))
            self.assertIsNone(blind_test.find_ref("故宫文创", d))

    def test_find_ref_no_dir(self):
        self.assertIsNone(blind_test.find_ref("无印良品", "/nonexistent-dir-xyz"))
        self.assertIsNone(blind_test.find_ref("无印良品", ""))


class TestBoard(unittest.TestCase):
    def test_build_board_size(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow 不可用")
        with tempfile.TemporaryDirectory() as d:
            items = [{"n": i, "name": f"风格{i}", "ref": None} for i in range(1, 10)]
            out = blind_test.build_board(items, Path(d) / "b.png", cols=3, cell=100, pad=10)
            self.assertIsNotNone(out)
            self.assertTrue(Path(out).exists())
            from PIL import Image
            with Image.open(out) as im:
                self.assertEqual(im.size, (3 * 100 + 4 * 10, 3 * 100 + 4 * 10))


class TestGenerationPolicy(unittest.TestCase):
    """这一组是重点：生图额度的守门测试。"""

    def setUp(self):
        self.fake = FakeGen()
        self.orig = blind_test.run_generator
        blind_test.run_generator = self.fake

    def tearDown(self):
        blind_test.run_generator = self.orig

    def test_no_generate_flag_means_no_generation(self):
        code, out = run_main(["高级感", "--no-board"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.fake.jobs), 0, "不传 --generate 就绝不能生图")
        self.assertIn("未生图", out)

    def test_pick_generates_exactly_one(self):
        code, _ = run_main(["高级感", "--no-board", "--pick", "1",
                            "--generate", "--subject", "大疆 pocket3 说明书"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.fake.jobs), 1, "默认只生成选中的那 1 张")
        self.assertIn("无印良品", self.fake.jobs[0]["prompt"])

    def test_variants_generates_n(self):
        code, _ = run_main(["高级感", "--no-board", "--variants", "4",
                            "--generate", "--subject", "封面"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.fake.jobs), 4, "--variants 4 应生成 4 张")

    def test_dry_run_does_not_execute(self):
        """--dry-run 只回显命令，不产生真实文件（用原始 run_generator 验）。"""
        jobs = [{"prompt": "x", "out": Path("outputs") / "never.png"}]
        res = self.orig(jobs, dry=True)
        self.assertTrue(res[0].get("dry"))
        self.assertFalse(Path("outputs/never.png").exists())

    def test_pick_and_variants_conflict(self):
        code, _ = run_main(["高级感", "--no-board", "--pick", "1", "--variants", "3"])
        self.assertEqual(code, 2)

    def test_variants_without_generate_rejected(self):
        code, _ = run_main(["高级感", "--no-board", "--variants", "3"])
        self.assertEqual(code, 2)

    def test_pick_out_of_range(self):
        code, _ = run_main(["高级感", "--no-board", "--pick", "99"])
        self.assertEqual(code, 2)


class TestIO(unittest.TestCase):
    def test_json_output(self):
        code, out = run_main(["高级感", "--no-board", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertEqual(data["generate_count"], 0, "默认不生图")
        self.assertFalse(data["will_generate"])
        self.assertEqual(len(data["candidates"]), 9)
        self.assertEqual(data["chosen"][0]["n"], 1)

    def test_unknown_vibe_returns_2(self):
        code, out = run_main(["这个词肯定查不到xyz", "--no-board"])
        self.assertEqual(code, 2)
        self.assertIn("元 prompt", out)

    def test_history_written(self):
        with tempfile.TemporaryDirectory() as d:
            hp = Path(d) / "h.jsonl"
            run_main(["高级感", "--no-board", "--pick", "1", "--history", str(hp)])
            self.assertTrue(hp.exists())
            line = json.loads(hp.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(line["vibe"], "高级感")
            self.assertEqual(line["n"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
