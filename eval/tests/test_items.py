# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""The evaluation set is well formed, and the checker catches bad items."""

import copy
import unittest

from eval import items
from eval.questions import BANK


class TestShippedItems(unittest.TestCase):
    def setUp(self):
        self.items = items.load()

    def test_count_in_range(self):
        self.assertGreaterEqual(len(self.items), items.MIN_ITEMS)
        self.assertLessEqual(len(self.items), items.MAX_ITEMS)

    def test_all_chosen_with_reasoning(self):
        for item in self.items:
            self.assertEqual(item["provenance"], "chosen", item["id"])
            self.assertGreater(len(item["reasoning"]), 20, item["id"])

    def test_every_question_is_scored_somewhere(self):
        used = {k for item in self.items for k in item["expected"]}
        self.assertEqual(used, set(BANK.keys()))

    def test_out_of_vocabulary_cases_exist(self):
        n = sum(1 for i in self.items if i["expected"].get("in_vocabulary") is False)
        self.assertGreaterEqual(n, 5)


class TestChecker(unittest.TestCase):
    def setUp(self):
        self.good = items.load()

    def check(self, mutate):
        bad = copy.deepcopy(self.good)
        mutate(bad[0])
        return items.problems(bad)

    def test_valid_set_has_no_problems(self):
        self.assertEqual(items.problems(self.good), [])

    def test_unknown_option(self):
        self.assertTrue(self.check(lambda i: i["expected"].update(shaper="laser")))

    def test_unknown_question(self):
        self.assertTrue(self.check(lambda i: i["expected"].update(colour="blue")))

    def test_score_out_of_range(self):
        self.assertTrue(self.check(lambda i: i["expected"].update(drive_amount=[3, 9])))
        self.assertTrue(self.check(lambda i: i["expected"].update(drive_amount=[3, 1])))

    def test_noul_must_be_bool(self):
        self.assertTrue(self.check(lambda i: i["expected"].update(needs_drive="yes")))

    def test_provenance_and_reasoning(self):
        self.assertTrue(self.check(lambda i: i.update(provenance="ground truth")))
        self.assertTrue(self.check(lambda i: i.update(reasoning="")))

    def test_too_few_items(self):
        self.assertTrue(items.problems(self.good[:5]))


if __name__ == "__main__":
    unittest.main()
