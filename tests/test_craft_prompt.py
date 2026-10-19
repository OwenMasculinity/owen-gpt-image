#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/craft_prompt.py 的验收测试。

跑法：
    python tests/test_craft_prompt.py
    python -m unittest discover -s tests -v

重点验收：
    A. 门禁层只追加、不改写用户原话（真名是用户/查表给的，不是脚本编的）
    B. 已含的约束不重复追加
    C. 用户明确要外文时不加中文约束（红线 1.2 的合法例外）
    D. 报刊品牌触发 nameplate 禁令；设计师/图书品牌不触发（红线 3 边界）
    E. --invite 才写 invite，默认只建议
    F. 自检 FAIL 的 prompt 拒绝放行（退出码 1）
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import craft_prompt  # noqa: E402


class TestCraft(unittest.TestCase):
    def test_append_only(self):
        """门禁层只追加后缀，不改写用户原话。"""
        r = craft_prompt.craft("Dieter Rams 风格的大疆 pocket3 说明书")
        self.assertTrue(r["crafted"].startswith("Dieter Rams 风格的大疆 pocket3 说明书"))
        self.assertIn("图里描述性文字用中文", r["crafted"])
        self.assertIn("无水印", r["crafted"])

    def test_no_duplicate_constraints(self):
        """已含「无水印」不重复加；已含中文约束不重复加。"""
        r = craft_prompt.craft("Brutalism 风格的婴儿米粉包装，无水印，图里描述性文字用中文")
        self.assertEqual(r["crafted"].count("无水印"), 1)
        self.assertEqual(r["crafted"].count("图里描述性文字用中文"), 1)

    def test_foreign_intent_exempt(self):
        """用户明确要德文说明书 → 不加中文约束（红线 1.2 合法例外）。"""
        r = craft_prompt.craft("Dieter Rams 风格的德文说明书")
        self.assertNotIn("图里描述性文字用中文", r["crafted"])
        self.assertTrue(any("外文意图" in s for s in r["steps"]))

    def test_size_appended(self):
        r = craft_prompt.craft("无印良品风格的杂志封面", size="1024x1024")
        self.assertIn("1024x1024", r["crafted"])

    def test_publication_nameplate(self):
        """The Economist 触发 nameplate 禁令。"""
        r = craft_prompt.craft("The Economist 风格的 AI 行业周报封面")
        self.assertIn("严禁左上角外文 nameplate", r["crafted"])

    def test_designer_brand_no_nameplate(self):
        """设计师/图书品牌（红线 3：风险低）不触发 nameplate 禁令。"""
        for p in ("Dieter Rams 风格的大疆 pocket3 说明书",
                  "Penguin Books 风格的 Cursor 产品手册",
                  "Apple 设计语言的中药包装"):
            r = craft_prompt.craft(p)
            self.assertNotIn("nameplate", r["crafted"], p)

    def test_invite_hint_default_off(self):
        """默认只给 invite 建议，不写进 prompt。"""
        r = craft_prompt.craft("Brutalism 风格的婴儿米粉包装")
        self.assertIsNotNone(r["invite_hint"])
        self.assertNotIn("品牌名", r["crafted"])

    def test_invite_explicit_on(self):
        """--invite 显式开启才写入。"""
        r = craft_prompt.craft("Brutalism 风格的婴儿米粉包装", invite=True)
        self.assertIn("请你贡献品牌名/slogan/命名逻辑", r["crafted"])

    def test_invite_not_duplicated(self):
        """用户 prompt 自带 invite 时不重复写。"""
        r = craft_prompt.craft("Apple 设计语言的中药包装。请你也贡献品牌名/slogan/命名逻辑", invite=True)
        self.assertEqual(r["crafted"].count("品牌名"), 1)

    def test_lint_fail_blocks(self):
        """真名一个都没有 → 自检 FAIL → 调用方应拒绝生图。"""
        r = craft_prompt.craft("一个高端大气上档次精致优雅的唯美震撼惊艳极致完美的图")
        self.assertGreater(r["lint"]["fails"], 0)

    def test_readme_cases_reproducible(self):
        """README 2.2 表格里的 5 条 prompt，craft 输出必须与表中逐字一致。"""
        cases = [
            ("Dieter Rams 风格的大疆 pocket3 说明书",
             "Dieter Rams 风格的大疆 pocket3 说明书，图里描述性文字用中文，无水印，1024x1024"),
            ("The Criterion Collection 风格的 Cursor 产品页",
             "The Criterion Collection 风格的 Cursor 产品页，图里描述性文字用中文，无水印，1024x1024"),
            ("Penguin Books 风格的 Cursor 产品手册",
             "Penguin Books 风格的 Cursor 产品手册，图里描述性文字用中文，无水印，1024x1024"),
            ("Brutalism 风格的婴儿米粉包装",
             "Brutalism 风格的婴儿米粉包装，图里描述性文字用中文，无水印，1024x1024"),
            ("Apple 设计语言的中药包装。请你也贡献品牌名/slogan/命名逻辑",
             "Apple 设计语言的中药包装。请你也贡献品牌名/slogan/命名逻辑，图里描述性文字用中文，无水印，1024x1024"),
        ]
        for raw, expect in cases:
            r = craft_prompt.craft(raw, size="1024x1024")
            self.assertEqual(r["crafted"], expect, raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
