# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""The workflow check (tools/check-workflows.py) against small hand-written workflows.

Needs PyYAML, which pre-commit installs, so it is present wherever make check runs.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check-workflows.py"
HAVE_YAML = importlib.util.find_spec("yaml") is not None

if HAVE_YAML:
    spec = importlib.util.spec_from_file_location("check_workflows", SCRIPT)
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)

GOOD = """\
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@0123456789abcdef0123456789abcdef01234567
      - run: make test
"""


@unittest.skipUnless(HAVE_YAML, "PyYAML is not installed")
class TestCheck(unittest.TestCase):
    def errors_for(self, body):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "ci.yml")
            path.write_text(body)
            return check.check(str(path))

    def test_good_workflow_passes(self):
        self.assertEqual(self.errors_for(GOOD), [])

    def test_missing_top_level_permissions(self):
        errors = self.errors_for(GOOD.replace("permissions:\n  contents: read\n", ""))
        self.assertTrue(any("no top-level `permissions:`" in e for e in errors), errors)

    def test_write_all_is_refused(self):
        body = GOOD.replace("permissions:\n  contents: read", "permissions: write-all")
        errors = self.errors_for(body)
        self.assertTrue(any("write-all" in e for e in errors), errors)

    def test_top_level_write_scope_is_refused(self):
        errors = self.errors_for(GOOD.replace("contents: read", "contents: write"))
        self.assertTrue(any("reaches every job" in e for e in errors), errors)

    def test_job_level_write_scope_is_allowed(self):
        body = GOOD.replace(
            "    runs-on: ubuntu-latest",
            "    permissions:\n      security-events: write\n    runs-on: ubuntu-latest",
        )
        self.assertEqual(self.errors_for(body), [])

    def test_branch_ref_is_refused(self):
        errors = self.errors_for(GOOD.replace("actions/checkout@v7", "actions/checkout@main"))
        self.assertTrue(any("not pinned" in e and "@main" in e for e in errors), errors)

    def test_local_and_docker_refs_are_skipped(self):
        body = GOOD.replace(
            "      - run: make test",
            "      - uses: ./.github/actions/local\n      - uses: docker://alpine:3.20",
        )
        self.assertEqual(self.errors_for(body), [])


if __name__ == "__main__":
    unittest.main()
