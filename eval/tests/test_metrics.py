# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Metrics against hand-worked values."""

import math
import unittest

from eval import metrics
from eval.questions import BANK


class TestCorrect(unittest.TestCase):
    def test_choice_single_and_list(self):
        q = BANK["shaper"]
        self.assertTrue(metrics.is_correct(q, "soft", "soft"))
        self.assertFalse(metrics.is_correct(q, "soft", "knee"))
        self.assertTrue(metrics.is_correct(q, ["soft", "asym"], "asym"))

    def test_score_range_inclusive(self):
        q = BANK["drive_amount"]
        self.assertTrue(metrics.is_correct(q, [1, 2], 1))
        self.assertTrue(metrics.is_correct(q, [1, 2], 2))
        self.assertFalse(metrics.is_correct(q, [1, 2], 3))
        self.assertFalse(metrics.is_correct(q, [1, 2], None))

    def test_noul_is_identity_not_truthiness(self):
        q = BANK["needs_drive"]
        self.assertTrue(metrics.is_correct(q, True, True))
        self.assertFalse(metrics.is_correct(q, True, 1))
        self.assertFalse(metrics.is_correct(q, False, None))


class TestCalibration(unittest.TestCase):
    def test_perfectly_calibrated_bin(self):
        # Four answers at 0.75, three right: accuracy equals confidence.
        confs = [0.75] * 4
        hits = [True, True, True, False]
        self.assertAlmostEqual(metrics.ece(confs, hits), 0.0)

    def test_hand_worked_ece(self):
        # Bin [0.9, 1.0]: 2 answers, mean 0.95, 1 right -> gap 0.45, weight 2/4.
        # Bin [0.5, 0.6): 2 answers, mean 0.55, 2 right -> gap 0.45, weight 2/4.
        confs = [0.9, 1.0, 0.5, 0.6 - 1e-9]
        hits = [True, False, True, True]
        self.assertAlmostEqual(metrics.ece(confs, hits), 0.45, places=6)

    def test_confidence_one_in_last_bin(self):
        rows = metrics.reliability([1.0], [True])
        self.assertEqual(rows[-1][2], 1)
        self.assertEqual(sum(r[2] for r in rows), 1)

    def test_brier(self):
        self.assertAlmostEqual(metrics.brier([1.0, 0.5], [True, False]), (0 + 0.25) / 2)

    def test_empty_is_nan(self):
        self.assertTrue(math.isnan(metrics.ece([], [])))
        self.assertTrue(math.isnan(metrics.brier([], [])))


class TestPercentile(unittest.TestCase):
    def test_interpolates(self):
        self.assertEqual(metrics.percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(metrics.percentile([5], 95), 5)
        self.assertAlmostEqual(metrics.percentile(list(range(101)), 95), 95)
        self.assertTrue(math.isnan(metrics.percentile([], 50)))


class TestSummarise(unittest.TestCase):
    def row(self, status="ok", correct=True, confidence=0.9, threshold=0.5, fallback=None):
        return {
            "status": status,
            "correct": correct,
            "confidence": confidence,
            "threshold": threshold,
            "fallback_correct": correct if fallback is None else fallback,
        }

    def test_rates(self):
        rows = [
            self.row(),
            self.row(correct=False, confidence=0.4, fallback=True),
            self.row(status="error", correct=False, confidence=None, fallback=False),
            self.row(confidence=None),
        ]
        s = metrics.summarise(rows, [10.0, 20.0, 30.0])
        self.assertEqual(s["accuracy"], (2 / 4, 4))
        self.assertEqual(s["error_rate"], (1 / 4, 4))
        # Of the 3 ok answers, one is below threshold and one has no confidence.
        self.assertEqual(s["low_confidence_rate"], (2 / 3, 3))
        self.assertEqual(s["accuracy_when_confident"], (1.0, 1))
        self.assertEqual(s["accuracy_with_fallback"], (3 / 4, 4))
        self.assertEqual(s["ece"][1], 2)
        self.assertEqual(s["latency_p50_ms"], (20.0, 3))


if __name__ == "__main__":
    unittest.main()
