# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Run the evaluation set against every configured backend.

Usage: python -m eval.run [--out out] [--backend NAME ...] [--repeat N]
                          [--items FILE] [--config FILE] [--no-plots]

Writes, in long format (one row per data point):
  results.csv       backend, item, repeat, question: answer, confidence, correct, ...
  summary.csv       backend, metric, value, n
  per_question.csv  backend, question, metric, value, n
  reliability.csv   backend, bin: the numbers behind reliability.svg
and the plots reliability.svg, metrics.svg and latency.svg.

Backends that are not configured are skipped with a message. The mock backend
always runs unless --backend leaves it out.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from eval import backends as be
from eval import items as it
from eval import metrics
from eval.questions import BANK

RESULT_FIELDS = [
    "backend",
    "item",
    "repeat",
    "question",
    "type",
    "expected",
    "answer",
    "status",
    "correct",
    "confidence",
    "backend_confidence",
    "threshold",
    "low_confidence",
    "used",
    "fallback_correct",
    "latency_ms",
    "error",
]


def score_response(backend, item, repeat, response, bank=BANK):
    """One result row per question the item has an expected answer for."""
    rows = []
    for key, expected in item["expected"].items():
        q = bank[key]
        a = response.answers.get(key) or be.Answer(status=be.INVALID, error="missing")
        ok = a.status == be.OK
        correct = ok and metrics.is_correct(q, expected, a.value)
        conf = a.confidence if ok else None
        low = not ok or conf is None or conf < q.threshold
        used = q.default if low else a.value
        rows.append(
            {
                "backend": backend,
                "item": item["id"],
                "repeat": repeat,
                "question": key,
                "type": q.type,
                "expected": json.dumps(expected),
                "answer": json.dumps(a.value) if ok else "",
                "status": a.status,
                "correct": correct,
                "confidence": conf,
                "backend_confidence": a.backend_confidence,
                "threshold": q.threshold,
                "low_confidence": low,
                "used": json.dumps(used),
                "fallback_correct": metrics.is_correct(q, expected, used),
                "latency_ms": response.latency_ms,
                "error": a.error,
            }
        )
    return rows


def run_backend(backend, items, repeat=1, bank=BANK):
    rows, latencies = [], []
    for r in range(repeat):
        for item in items:
            resp = backend.ask(item["description"], bank)
            latencies.append(resp.latency_ms)
            rows.extend(score_response(backend.name, item, r, resp, bank))
    return rows, latencies


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return "" if math.isnan(v) else f"{v:.6g}"
    return v


def per_question(name, rows, bank=BANK):
    out = []
    for q in bank:
        qr = [r for r in rows if r["question"] == q.key]
        if not qr:
            continue
        ok = [r for r in qr if r["status"] == be.OK]
        out.append((name, q.key, "accuracy", sum(r["correct"] for r in qr) / len(qr), len(qr)))
        if ok:
            low = sum(r["low_confidence"] for r in ok) / len(ok)
            out.append((name, q.key, "low_confidence_rate", low, len(ok)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="out", type=Path)
    ap.add_argument("--backend", action="append", help="run only these (repeatable)")
    ap.add_argument("--repeat", type=int, default=1, help="passes over the set, for latency")
    ap.add_argument("--items", default=it.DEFAULT_ITEMS, type=Path)
    ap.add_argument("--config", default=be.DEFAULT_CONFIG, type=Path)
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)

    items = it.load(args.items)
    selected = []
    for b in be.load(args.config):
        if args.backend and b.name not in args.backend:
            continue
        ok, why = b.available()
        if not ok:
            print(f"skip {b.name}: {why}")
            continue
        selected.append(b)
    if args.backend:
        unknown = set(args.backend) - {b.name for b in be.load(args.config)}
        if unknown:
            print(f"unknown backend(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
    if not selected:
        print("no backend to run", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    all_rows, summary, perq, rel, lat = [], [], [], [], {}
    for b in selected:
        print(f"run {b.name}: {len(items)} items x {args.repeat}")
        rows, latencies = run_backend(b, items, args.repeat)
        all_rows.extend(rows)
        lat[b.name] = latencies
        for metric, (value, n) in metrics.summarise(rows, latencies).items():
            summary.append((b.name, metric, value, n))
        perq.extend(per_question(b.name, rows))
        scored = [r for r in rows if r["confidence"] is not None]
        for lo, hi, n, mc, acc in metrics.reliability(
            [r["confidence"] for r in scored], [r["correct"] for r in scored]
        ):
            rel.append((b.name, lo, hi, n, mc, acc))

    with open(args.out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, RESULT_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in all_rows:
            w.writerow({k: _fmt(v) for k, v in r.items()})
    write_rows(args.out / "summary.csv", ["backend", "metric", "value", "n"], summary)
    write_rows(args.out / "per_question.csv", ["backend", "question", "metric", "value", "n"], perq)
    write_rows(
        args.out / "reliability.csv",
        ["backend", "bin_lo", "bin_hi", "n", "mean_confidence", "accuracy"],
        rel,
    )
    latency_rows = [(name, i, v) for name, vs in lat.items() for i, v in enumerate(vs)]
    write_rows(args.out / "latency.csv", ["backend", "request", "latency_ms"], latency_rows)

    for name, metric, value, n in summary:
        if metric in (
            "accuracy",
            "accuracy_with_fallback",
            "low_confidence_rate",
            "ece",
            "latency_p50_ms",
        ):
            print(f"  {name:12s} {metric:24s} {_fmt(value)!s:>10} (n={n})")

    if not args.no_plots:
        try:
            from eval import plots
        except ImportError as e:
            print(f"plots skipped: {e}")
        else:
            names = [b.name for b in selected]
            plots.reliability(args.out / "reliability.svg", names, rel)
            plots.metrics(args.out / "metrics.svg", names, summary)
            plots.latency(args.out / "latency.svg", names, lat)
    print(f"wrote {args.out}/")
    return 0


def write_rows(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow([_fmt(v) for v in row])


if __name__ == "__main__":
    sys.exit(main())
