# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Load and check the evaluation set (eval/data/items.json).

Each item is a description a player might type, the answers its author
expects for some of the bank's questions, and the reasoning. Expected answers
are chosen (the author's judgement), not ground truth; every item must say so.
"""

import json
from pathlib import Path

from eval.questions import BANK

DEFAULT_ITEMS = Path(__file__).parent / "data" / "items.json"

# Chosen: the brief asks for a small hand-written set of 30 to 50 items.
MIN_ITEMS, MAX_ITEMS = 30, 50


def problems(items, bank=BANK):
    """Every problem with the item list, as messages; empty if it is valid."""
    out = []
    if not MIN_ITEMS <= len(items) <= MAX_ITEMS:
        out.append(f"{len(items)} items; expected {MIN_ITEMS} to {MAX_ITEMS}")
    seen = set()
    for i, item in enumerate(items):
        where = item.get("id", f"#{i}")
        for k in ("id", "description", "expected", "reasoning", "provenance"):
            if not item.get(k):
                out.append(f"{where}: missing {k}")
        if item.get("id") in seen:
            out.append(f"{where}: duplicate id")
        seen.add(item.get("id"))
        if item.get("provenance") != "chosen":
            out.append(f"{where}: provenance must be 'chosen'")
        for key, exp in (item.get("expected") or {}).items():
            try:
                q = bank[key]
            except KeyError:
                out.append(f"{where}: unknown question {key!r}")
                continue
            opts = q.options()
            if q.type == "choice":
                vals = exp if isinstance(exp, list) else [exp]
                if not vals or any(v not in opts for v in vals):
                    out.append(f"{where}: {key} expects {exp!r}, not among {opts}")
            elif q.type == "score":
                ok = (
                    isinstance(exp, list)
                    and len(exp) == 2
                    and all(isinstance(v, int) and not isinstance(v, bool) for v in exp)
                    and 0 <= exp[0] <= exp[1] <= opts[-1]
                )
                if not ok:
                    out.append(f"{where}: {key} expects [lo, hi] within 0..{opts[-1]}, got {exp!r}")
            elif not isinstance(exp, bool):
                out.append(f"{where}: {key} expects true or false, got {exp!r}")
    return out


def load(path=DEFAULT_ITEMS, bank=BANK):
    """The items, after checking them; raises ValueError listing every problem."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    errs = problems(items, bank)
    if errs:
        raise ValueError(f"{path}:\n  " + "\n  ".join(errs))
    return items
