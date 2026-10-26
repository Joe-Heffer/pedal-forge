# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""SVG plots of the evaluation results (needs matplotlib).

Each plot has a CSV with the same numbers next to it in out/, so nobody has
to read values off an image. Colours follow the backend's place in
eval/backends.toml, never its rank, so a backend keeps its colour from run to
run. The palette is a validated categorical order (blue, orange, aqua,
yellow, magenta, green, violet, red) on a light surface; chosen.
"""

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, INK, INK2, MUTED, GRID, AXIS = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)

plt.rcParams.update(
    {
        "svg.hashsalt": "pedal-forge",  # stable element IDs, so reruns diff cleanly
        "svg.fonttype": "none",
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "legend.frameon": False,
        "legend.labelcolor": INK2,
        "font.size": 10,
    }
)


def colour(names, name):
    return SERIES[names.index(name) % len(SERIES)]


def save(fig, path):
    fig.savefig(path, format="svg", metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)


def reliability(path, names, rows):
    """Accuracy against mean confidence per bin; the diagonal is perfect calibration."""
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], color=AXIS, linewidth=1, linestyle="--", label="Perfect calibration")
    for name in names:
        pts = [(mc, acc, n) for b, _, _, n, mc, acc in rows if b == name and n]
        if not pts:
            continue
        xs, ys, ns = zip(*pts, strict=True)
        ax.plot(xs, ys, color=colour(names, name), linewidth=2, label=name)
        ax.scatter(
            xs,
            ys,
            s=[24 + 4 * math.sqrt(n) for n in ns],
            color=colour(names, name),
            edgecolors=SURFACE,
            linewidths=1.5,
            zorder=3,
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_aspect("equal")
    ax.set_xlabel("Mean confidence in bin")
    ax.set_ylabel("Fraction correct in bin")
    ax.set_title("Reliability (marker area grows with answers in the bin)", loc="left")
    ax.legend(loc="upper left")
    save(fig, path)


BAR_METRICS = [
    ("accuracy", "Accuracy"),
    ("accuracy_with_fallback", "Accuracy\nwith fallback"),
    ("low_confidence_rate", "Low-confidence\nrate"),
    ("error_rate", "Error\nrate"),
    ("ece", "ECE"),
]


def metrics(path, names, summary):
    """Rates between 0 and 1 per backend, grouped by metric (one shared scale)."""
    values = {(b, m): v for b, m, v, _ in summary}
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.8 / max(len(names), 1)
    for j, name in enumerate(names):
        xs = [i + (j - (len(names) - 1) / 2) * width for i in range(len(BAR_METRICS))]
        ys = [values.get((name, m), math.nan) for m, _ in BAR_METRICS]
        bars = ax.bar(xs, ys, width * 0.9, color=colour(names, name), label=name, edgecolor=SURFACE)
        # Value labels only while they fit; summary.csv holds every value.
        for bar, y in zip(bars, ys, strict=True):
            if len(names) <= 2 and not math.isnan(y):
                ax.annotate(
                    f"{y:.2f}",
                    (bar.get_x() + bar.get_width() / 2, y),
                    xytext=(0, 2),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=INK2,
                )
    ax.set_xticks(range(len(BAR_METRICS)), [label for _, label in BAR_METRICS])
    ax.set_ylim(0, 1.1)
    ax.grid(axis="x", visible=False)
    ax.set_title("Decision quality by backend", loc="left")
    if len(names) > 1:
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    save(fig, path)


def latency(path, names, latencies):
    """Each request's time per backend, on a log scale, with the median marked."""
    fig, ax = plt.subplots(figsize=(7, 1.2 + 0.6 * len(names)))
    for i, name in enumerate(names):
        vs = [max(v, 1e-3) for v in latencies.get(name, [])]
        if not vs:
            continue
        jitter = [i + ((k * 0.618) % 1 - 0.5) * 0.3 for k in range(len(vs))]
        ax.scatter(vs, jitter, s=10, color=colour(names, name), alpha=0.6, linewidths=0)
        med = sorted(vs)[len(vs) // 2]
        ax.plot([med, med], [i - 0.25, i + 0.25], color=INK, linewidth=2)
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(LogLocator(subs=(1, 2, 5)))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_yticks(range(len(names)), names)
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Request time (ms, log scale); bar = median")
    ax.set_title("Latency per request (all questions in one request)", loc="left")
    save(fig, path)
