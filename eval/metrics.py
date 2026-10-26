# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Scoring: correctness, calibration, low-confidence rate and latency.

All functions take plain lists so they can be tested with hand-worked values.
Constants are chosen; docs/design-notes.md, section 5, says why.
"""

import math

# Chosen: 10 equal-width bins, the common default in Guo et al. (2017),
# https://arxiv.org/abs/1706.04599. With a 40-item set many bins hold only a
# few answers, so read ECE alongside the reliability table's counts.
ECE_BINS = 10


def is_correct(question, expected, value):
    """Whether `value` meets the expected answer for this question.

    choice: `expected` is an option or a list of acceptable options.
    score: `expected` is [lo, hi], inclusive level indices.
    noul: `expected` is true or false.
    """
    if question.type == "choice":
        allowed = expected if isinstance(expected, list) else [expected]
        return value in allowed
    if question.type == "score":
        lo, hi = expected
        return value is not None and lo <= value <= hi
    if question.type == "noul":
        return value is expected
    raise ValueError(question.type)


def reliability(confidences, correct, bins=ECE_BINS):
    """Per-bin (lo, hi, n, mean confidence, accuracy); empty bins have n = 0.

    A confidence of exactly 1 falls in the last bin.
    """
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [
            i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)
        ]
        n = len(idx)
        mean_c = sum(confidences[i] for i in idx) / n if n else math.nan
        acc = sum(1 for i in idx if correct[i]) / n if n else math.nan
        rows.append((lo, hi, n, mean_c, acc))
    return rows


def ece(confidences, correct, bins=ECE_BINS):
    """Expected calibration error over top-label confidence."""
    total = len(confidences)
    if not total:
        return math.nan
    return sum(
        n / total * abs(acc - mc)
        for _, _, n, mc, acc in reliability(confidences, correct, bins)
        if n
    )


def brier(confidences, correct):
    """Top-label Brier score: mean of (confidence - correct)^2."""
    if not confidences:
        return math.nan
    return sum(
        (c - (1.0 if k else 0.0)) ** 2 for c, k in zip(confidences, correct, strict=True)
    ) / len(confidences)


def percentile(values, q):
    """Linear-interpolated percentile, q in [0, 100]; NaN for no values."""
    if not values:
        return math.nan
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def is_low(row):
    """Below its question's threshold, or no confidence at all."""
    return row["confidence"] is None or row["confidence"] < row["threshold"]


def summarise(rows, request_latencies):
    """Metrics for one backend.

    `rows` are scored answers: dicts with `status`, `correct`, `confidence`,
    `threshold`, `fallback_correct`. `request_latencies` are per-request
    times in milliseconds. Returns {metric: (value, n)}.

    `accuracy` counts errors as wrong. `accuracy_with_fallback` scores what the
    assembler would use: the answer when confident, else the question's default.
    """
    n = len(rows)
    ok = [r for r in rows if r["status"] == "ok"]
    with_conf = [r for r in ok if r["confidence"] is not None]
    confs = [r["confidence"] for r in with_conf]
    hits = [r["correct"] for r in with_conf]
    low = [r for r in ok if is_low(r)]
    acted = [r for r in ok if not is_low(r)]

    def frac(k, d):
        return (k / d if d else math.nan), d

    return {
        "accuracy": frac(sum(r["correct"] for r in ok), n),
        "accuracy_when_confident": frac(sum(r["correct"] for r in acted), len(acted)),
        "accuracy_with_fallback": frac(sum(r["fallback_correct"] for r in rows), n),
        "low_confidence_rate": frac(len(low), len(ok)),
        "error_rate": frac(n - len(ok), n),
        "ece": (ece(confs, hits), len(confs)),
        "brier": (brier(confs, hits), len(confs)),
        "mean_confidence": frac(sum(confs), len(confs)),
        "latency_p50_ms": (percentile(request_latencies, 50), len(request_latencies)),
        "latency_p95_ms": (percentile(request_latencies, 95), len(request_latencies)),
    }
