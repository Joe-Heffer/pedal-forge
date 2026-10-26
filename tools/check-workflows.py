#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Fail on an over-permissioned or unpinned GitHub Actions workflow.

Usage: check-workflows.py FILE...

actionlint checks syntax, expressions and types but not how much a workflow
is allowed to do, so this adds three rules to each FILE:

1. The workflow sets a top-level `permissions:` block, and it grants nothing
   above `read`. Write scopes go on the job that needs them, so the other
   jobs keep a read-only token.
2. No `write-all`, at any level.
3. Every `uses:` names a version tag (`@v7`, `@v1.2.3`) or a commit SHA, not a
   branch such as `@main`, so an action only changes when Dependabot bumps
   it. Local (`./…`) and `docker://` references are skipped.

Used by the workflow-permissions pre-commit hook.
"""

import re
import sys

import yaml

PINNED_REF = re.compile(r"^(v?\d[\w.\-]*|[0-9a-f]{40})$")


def permission_errors(perms, where):
    if perms == "write-all":
        return [f"{where}: `write-all` grants every scope; list only the scopes needed"]
    if perms != "read-all" and not isinstance(perms, dict):
        return [f"{where}: unrecognised `permissions:` value {perms!r}"]
    return []


def check(path):
    with open(path) as f:
        wf = yaml.safe_load(f) or {}
    errors = []

    if "permissions" not in wf:
        errors.append("no top-level `permissions:`; add `permissions: contents: read` (or `{}`)")
    else:
        perms = wf["permissions"]
        errors += permission_errors(perms, "top level")
        if isinstance(perms, dict):
            for scope, level in perms.items():
                if level == "write":
                    errors.append(f"top level: `{scope}: write` reaches every job; move it to one")

    for name, job in (wf.get("jobs") or {}).items():
        if "permissions" in job:
            errors += permission_errors(job["permissions"], f"job `{name}`")
        refs = [job["uses"]] if "uses" in job else []
        refs += [step["uses"] for step in job.get("steps") or [] if "uses" in step]
        for ref in refs:
            if ref.startswith(("./", "docker://")):
                continue
            _, _, version = ref.partition("@")
            if not PINNED_REF.match(version):
                errors.append(
                    f"job `{name}`: `uses: {ref}` is not pinned to a version tag or commit SHA"
                )

    return [f"{path}: {e}" for e in errors]


def main(argv):
    errors = [e for path in argv for e in check(path)]
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
