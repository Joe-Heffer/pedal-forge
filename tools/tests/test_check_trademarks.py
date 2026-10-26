# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""The trademark check (tools/check-trademarks.py) against hand-picked names."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "check-trademarks.py"
spec = importlib.util.spec_from_file_location("check_trademarks", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class TestPattern(unittest.TestCase):
    def test_spacing_case_and_punctuation_ignored(self):
        pat = check.pattern("Sans Amp")
        for text in ("SansAmp", "sans_amp", "SANSAMP", "sans-amp", "sans amp"):
            self.assertTrue(pat.search(check.words(text)), text)

    def test_whole_word_only(self):
        pat = check.pattern("Boss")
        self.assertTrue(pat.search(check.words("BossDrive")))
        self.assertFalse(pat.search(check.words("emboss the lows")))

    def test_ordinary_prose_not_flagged(self):
        deny = [(n, check.pattern(n)) for n in ("Boss", "Tube Screamer")]
        self.assertEqual(list(check.scan("warm, tight bass with the lows kept", deny)), [])


class TestScan(unittest.TestCase):
    def test_reports_line_numbers(self):
        deny = [("Tube Screamer", check.pattern("Tube Screamer"))]
        text = "clean line\nthe TubeScreamer clone\nclean again\n"
        self.assertEqual(list(check.scan(text, deny)), [(2, "Tube Screamer")])


class TestMain(unittest.TestCase):
    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            with mock.patch.object(sys, "argv", ["check-trademarks.py", *args]):
                code = check.main()
        return code, out.getvalue()

    def test_flags_deny_listed_file_name(self):
        with tempfile.TemporaryDirectory() as d:
            deny = Path(d, "trademarks.txt")
            deny.write_text("# comment\nBoss\n")
            code, out = self.run_main("--list", str(deny), "eval/boss_drive.py")
        self.assertEqual(code, 1)
        self.assertIn("file name contains 'Boss'", out)

    def test_flags_deny_listed_content_under_eval(self):
        with tempfile.TemporaryDirectory() as d:
            deny = Path(d, "trademarks.txt")
            deny.write_text("Boss\n")
            with contextlib.chdir(d):
                Path(d, "eval").mkdir()
                Path(d, "eval", "items.json").write_text('{"text": "a Boss sound"}\n')
                code, out = self.run_main("--list", str(deny), "eval/items.json")
        self.assertEqual(code, 1)
        self.assertIn("eval/items.json:1: contains 'Boss'", out)

    def test_content_outside_scanned_dirs_is_not_read(self):
        with tempfile.TemporaryDirectory() as d:
            deny = Path(d, "trademarks.txt")
            deny.write_text("Boss\n")
            with contextlib.chdir(d):
                Path(d, "docs").mkdir()
                Path(d, "docs", "notes.md").write_text("The Boss pedal is the reference.\n")
                code, _ = self.run_main("--list", str(deny), "docs/notes.md")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
