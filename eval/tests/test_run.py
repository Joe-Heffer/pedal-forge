# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""End-to-end run with the mock backend: CSVs in long format and plots."""

import csv
import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from eval import items, run

HAVE_MPL = importlib.util.find_spec("matplotlib") is not None


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestRun(unittest.TestCase):
    def go(self, *args):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        out = Path(self.tmp.name)
        with redirect_stdout(io.StringIO()) as so, redirect_stderr(io.StringIO()):
            code = run.main(["--out", str(out), *args])
        return code, out, so.getvalue()

    def test_mock_run_writes_long_csv(self):
        code, out, log = self.go("--no-plots", "--repeat", "2")
        self.assertEqual(code, 0)
        self.assertIn("skip openjev", log)
        rows = read(out / "results.csv")
        n_expected = sum(len(i["expected"]) for i in items.load())
        self.assertEqual(len(rows), 2 * n_expected)
        self.assertEqual(list(rows[0]), run.RESULT_FIELDS)
        self.assertEqual({r["backend"] for r in rows}, {"mock"})
        summary = read(out / "summary.csv")
        self.assertEqual(list(summary[0]), ["backend", "metric", "value", "n"])
        metrics = {r["metric"]: float(r["value"]) for r in summary}
        for m in ("accuracy", "ece", "low_confidence_rate", "error_rate", "latency_p50_ms"):
            self.assertIn(m, metrics)
        self.assertEqual(metrics["error_rate"], 0.0)
        rel = read(out / "reliability.csv")
        self.assertEqual(len(rel), 10)
        self.assertEqual(sum(int(r["n"]) for r in rel), len(rows))
        self.assertEqual(len(read(out / "latency.csv")), 2 * len(items.load()))
        self.assertTrue(read(out / "per_question.csv"))

    def test_unknown_backend(self):
        code, _, _ = self.go("--backend", "nonesuch", "--no-plots")
        self.assertEqual(code, 2)

    def test_only_unconfigured_backend(self):
        code, _, log = self.go("--backend", "openjev", "--no-plots")
        self.assertEqual(code, 1)
        self.assertIn("skip openjev", log)

    @unittest.skipUnless(HAVE_MPL, "matplotlib not installed")
    def test_plots(self):
        code, out, _ = self.go()
        self.assertEqual(code, 0)
        for name in ("reliability.svg", "metrics.svg", "latency.svg"):
            text = (out / name).read_text()
            self.assertTrue(text.lstrip().startswith("<?xml"), name)


if __name__ == "__main__":
    unittest.main()
