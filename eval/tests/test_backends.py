# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Answer normalisation, the mock backend and backend configuration."""

import tempfile
import unittest
from pathlib import Path

from eval import backends as be
from eval.questions import BANK


class TestNormalise(unittest.TestCase):
    def test_choice_dict(self):
        a = be.normalise(
            BANK["tone_filter"],
            {
                "choice": "lowpass",
                "probabilities": {"lowpass": 0.6, "none": 0.2, "peak": 0.2},
                "confidence": 0.3,
            },
        )
        self.assertEqual(a.status, be.OK)
        self.assertEqual(a.value, "lowpass")
        self.assertAlmostEqual(sum(a.probabilities.values()), 1.0)
        self.assertEqual(a.probabilities["highpass"], 0.0)
        # Confidence is the top probability, not the backend's own field.
        self.assertAlmostEqual(a.confidence, 0.6)
        self.assertEqual(a.backend_confidence, 0.3)

    def test_choice_openai_list(self):
        a = be.normalise(
            BANK["instrument"],
            {
                "probabilities": [
                    {"value": "bass", "probability": 0.8},
                    {"value": "guitar", "probability": 0.2},
                ]
            },
        )
        self.assertEqual(a.value, "bass")
        self.assertAlmostEqual(a.confidence, 0.8)

    def test_choice_unknown_option_is_invalid(self):
        a = be.normalise(BANK["instrument"], {"choice": "drums"})
        self.assertEqual(a.status, be.INVALID)

    def test_score_dict_keyed_by_level(self):
        a = be.normalise(
            BANK["drive_amount"],
            {"score": 2.4, "probabilities": {"0": 0.0, "1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1}},
        )
        self.assertEqual(a.value, 2)
        self.assertAlmostEqual(a.confidence, 0.5)

    def test_score_uses_mode_not_rounded_mean(self):
        # Bimodal: mean 2.0, but level 2 has no mass.
        a = be.normalise(BANK["brightness"], {"score": 2.0, "probabilities": [0.5, 0, 0, 0, 0.5]})
        self.assertIn(a.value, (0, 4))

    def test_score_without_probabilities(self):
        a = be.normalise(BANK["brightness"], {"score": 3.2})
        self.assertEqual(a.value, 3)
        self.assertIsNone(a.confidence)
        self.assertEqual(be.normalise(BANK["brightness"], {"score": 7}).status, be.INVALID)

    def test_noul(self):
        a = be.normalise(BANK["needs_drive"], {"noul": 0.2})
        self.assertIs(a.value, False)
        self.assertAlmostEqual(a.confidence, 0.8)
        a = be.normalise(BANK["needs_drive"], {"type": "predicate", "probability": 0.9})
        self.assertIs(a.value, True)

    def test_bad_probability_is_invalid(self):
        self.assertEqual(be.normalise(BANK["needs_drive"], {"noul": 1.5}).status, be.INVALID)
        self.assertEqual(be.normalise(BANK["needs_drive"], {"noul": "yes"}).status, be.INVALID)
        self.assertEqual(be.normalise(BANK["needs_drive"], []).status, be.INVALID)


class TestMock(unittest.TestCase):
    def test_deterministic_and_well_formed(self):
        m = be.MockBackend()
        a = m.ask("Warm bass overdrive with the lows kept tight", BANK)
        b = m.ask("Warm bass overdrive with the lows kept tight", BANK)
        for q in BANK:
            x, y = a.answers[q.key], b.answers[q.key]
            self.assertEqual(x.value, y.value)
            self.assertEqual(x.probabilities, y.probabilities)
            self.assertIn(x.value, q.options())
            self.assertAlmostEqual(sum(x.probabilities.values()), 1.0)
        self.assertEqual(a.answers["instrument"].value, "bass")
        self.assertIs(a.answers["needs_drive"].value, True)
        self.assertIs(a.answers["keep_lows"].value, True)

    def test_no_cue_falls_to_default(self):
        r = be.MockBackend().ask("hmm", BANK)
        for q in BANK:
            self.assertEqual(r.answers[q.key].value, q.default, q.key)


class TestConfig(unittest.TestCase):
    def test_shipped_config_skips_unconfigured(self):
        bs = be.load(env={})
        names = [b.name for b in bs]
        self.assertEqual(names[0], "mock")
        self.assertIn("openjev", names)
        for b in bs[1:]:
            ok, why = b.available()
            self.assertFalse(ok)
            self.assertIn("is not set", why)

    def test_key_required(self):
        jev = {b.name: b for b in be.load(env={"PF_JEV_URL": "https://example.invalid"})}["jev"]
        self.assertFalse(jev.available()[0])
        env = {"PF_JEV_URL": "https://example.invalid", "TYPESAFE_API_KEY": "k"}
        jev = {b.name: b for b in be.load(env=env)}["jev"]
        self.assertTrue(jev.available()[0])

    def test_unknown_kind(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "b.toml"
            p.write_text('[backends.x]\nkind = "telepathy"\n')
            with self.assertRaises(ValueError):
                be.load(p)


if __name__ == "__main__":
    unittest.main()
