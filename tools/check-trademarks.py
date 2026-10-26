#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Fail if a manufacturer or product name appears where hard rule 2 forbids it.

Usage: check-trademarks.py [--list tools/trademarks.txt] FILE...

Every FILE's path is checked, wherever it lives. The contents are checked only
for files under CONTENT_DIRS: the evaluation harness and its items (whose
descriptions stand in for what a player types and whose questions become
prompts), and src/ and prompts/, which will hold plugin code, UI text and
prompts. docs/ is not scanned, because the notes may name hardware to identify
it. The deny-list sits in tools/, outside the scanned paths, so it does not
flag itself. Adapted from faust-pedalkit's tools/check-trademarks.py. Used by
the no-trademarks pre-commit hook.
"""

import argparse
import re
import sys
from pathlib import Path

CONTENT_DIRS = ("eval/", "prompts/", "src/")
DEFAULT_LIST = Path(__file__).with_name("trademarks.txt")


def words(text):
    """Split CamelCase and digit runs apart so they become separate words."""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])", " ", text)
    return text.lower()


def pattern(name):
    """Whole-word regex for a name, ignoring case, spacing and punctuation."""
    tokens = re.findall(r"[a-z0-9]+", words(name))
    return re.compile(r"(?<![a-z0-9])" + r"[\W_]*".join(tokens) + r"(?![a-z0-9])")


def load(path):
    names = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.append(line)
    return [(n, pattern(n)) for n in names]


def scan(text, deny):
    """Yield (line number, name) for each deny-listed name in text."""
    for lineno, line in enumerate(text.splitlines(), 1):
        normal = words(line)
        for name, pat in deny:
            if pat.search(normal):
                yield lineno, name


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", default=DEFAULT_LIST, help="deny-list file")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()
    deny = load(args.list)

    found = 0
    for f in args.files:
        path = Path(f).as_posix()
        for _, name in scan(path, deny):
            print(f"{path}: file name contains {name!r}")
            found += 1
        if path.startswith(CONTENT_DIRS):
            try:
                text = Path(f).read_text()
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            for lineno, name in scan(text, deny):
                print(f"{path}:{lineno}: contains {name!r}")
                found += 1

    if found:
        print(
            "\nHard rule 2: effect names, UI text, prompts, evaluation items and file names"
            "\nmust be neutral. Name hardware only in docs/ (see AGENTS.md)."
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
