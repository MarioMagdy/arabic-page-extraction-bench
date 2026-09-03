"""Render assets/accuracy-vs-cost.png from results.json — one point per model.

Same selection rule as RESULTS.md's ranking table: arms with gold scores, derived arms
excluded (their transcription is another arm's). Filled marker = clears every gate; hollow = fails
one. The inset zooms on the gate-clearing models, where the differences are a few points and the
main axis cannot show them; the dotted line inside it is the lowest score the evidence cannot
separate from the leader, by the same `gold.separated` test the written results use.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FixedLocator, MultipleLocator  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gold as GOLD  # noqa: E402

PAPER, CARD, INK, MUTED, RULE = "#f0efe9", "#fbfaf6", "#1a1815", "#6a675e", "#d9d6cc"
GOOD, BAD = "#2f6f5e", "#a8452f"
XTICKS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02]
XLABELS = ["$0.0005", "$0.001", "$0.002", "$0.005", "$0.01", "$0.02"]


def load():
    data = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    rows = []
    for k, a in data["arms"].items():
        g = a.get("gold")
        if not g or a["prompt"] != "P2" or a.get("derived_from"):
            continue
        rows.append(dict(id=k, name=a["label"].split(" · ")[0], x=a["summary"]["cost_per_page_usd"],
                         y=g["task_score"], lo=g["ci"][0], hi=g["ci"][1],
                         ok=not g["gate_failures"], gold=g))
    rows.sort(key=lambda r: -r["y"])
    return data["_meta"]["gold_pages"], rows


def draw_points(ax, rows, size):
    for r in rows:
        c = GOOD if r["ok"] else BAD
        ax.errorbar(r["x"], r["y"], yerr=[[r["y"] - r["lo"]], [r["hi"] - r["y"]]],
                    fmt="none", ecolor=c, elinewidth=1, capsize=2.5, alpha=0.8, zorder=2)
        ax.scatter(r["x"], r["y"], s=size, facecolors=c if r["ok"] else CARD, edgecolors=c,
                   linewidths=1.6, zorder=3)


def style(ax):
    ax.set_facecolor(CARD)
    ax.set_xscale("log")
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(RULE)
    ax.grid(True, which="major", color=RULE, lw=0.7)
    ax.grid(True, which="minor", color=RULE, lw=0.4, alpha=0.6)
    ax.xaxis.set_major_locator(FixedLocator(XTICKS))
    ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.set_xticklabels(XLABELS)


def main() -> None:
    gpages, rows = load()
    passing = [r for r in rows if r["ok"]]
    failing = [r for r in rows if not r["ok"]]
    top = passing[0]
    tied = [top] + [r for r in passing[1:] if not GOLD.separated(top["gold"], r["gold"])]
    band_lo = min(r["y"] for r in tied)

    fig, ax = plt.subplots(figsize=(10, 7.4), dpi=200)
    fig.patch.set_facecolor(PAPER)
    style(ax)
    draw_points(ax, rows, 60)

    # Main axis: every whisker inside the frame, a 2% minor grid, 10% major.
    lo = min(r["lo"] for r in rows)
    ax.set_xlim(0.0004, 0.025)
    ax.set_ylim(max(0.0, lo - 0.04), 1.015)
    yt = np.arange(0.1, 1.001, 0.1)
    ax.set_yticks(yt)
    ax.set_yticklabels([f"{int(round(t*100))}%" for t in yt])
    ax.yaxis.set_minor_locator(MultipleLocator(0.02))
    ax.set_xlabel("price per page, USD (log scale; list rate × measured output)", color=MUTED, fontsize=9)
    ax.set_ylabel("task score on the gold pages", color=MUTED, fontsize=9)

    # Labels: the failing models here; the passing ones are labelled in the inset.
    for r in failing:
        ax.annotate(r["name"], (r["x"], r["y"]), xytext=(7, 0), textcoords="offset points",
                    fontsize=8.5, color=INK, ha="left", va="center")

    # Inset over the empty middle of the plot, zoomed on the gate-clearing models.
    ins = ax.inset_axes([0.30, 0.10, 0.42, 0.50])
    style(ins)
    draw_points(ins, passing, 46)
    ins.set_xlim(0.0004, 0.025)
    ylo = min(r["lo"] for r in passing) - 0.008
    ins.set_ylim(ylo, 1.003)
    yt = np.arange(0.94, 1.001, 0.02)
    ins.set_yticks(yt)
    ins.set_yticklabels([f"{t*100:.0f}%" for t in yt])
    ins.yaxis.set_minor_locator(MultipleLocator(0.01))
    ins.tick_params(labelsize=7.5)
    ins.set_title("the six that clear every gate", fontsize=8.5, color=MUTED, loc="left", pad=4)
    ins.axhline(band_lo, color=GOOD, lw=0.9, ls=(0, (2, 3)), zorder=1)
    ins.text(0.00046, ylo + 0.002, f"dotted line: lowest score not separable from the leader on {len(gpages)} pages",
             color=GOOD, fontsize=7, va="bottom", ha="left")
    nudge = {"Gemini 3.7 Flash": (7, 6), "Gemini 3.5 Flash": (7, -8), "Claude Sonnet 5": (7, 7),
             "Qwen 3.8 Max": (-7, 7), "GPT 5.6 Terra": (-7, -7), "Kimi K3": (7, -7)}
    for r in passing:
        dx, dy = nudge.get(r["name"], (7, 0))
        ins.annotate(r["name"], (r["x"], r["y"]), xytext=(dx, dy), textcoords="offset points",
                     fontsize=7.5, color=INK, ha="left" if dx > 0 else "right", va="center")
    # A quiet dotted frame around the strip the inset magnifies; no connector lines.
    ax.add_patch(Rectangle((0.00043, ylo), 0.0245 - 0.00043, 1.003 - ylo, fill=False,
                           ec=MUTED, lw=0.8, ls=(0, (2, 3)), zorder=1))
    ax.text(0.0025, ylo + 0.004, "magnified in the inset below", color=MUTED, fontsize=7, ha="center", va="bottom")

    fig.suptitle("Which model reads a scanned Arabic scholarly page correctly, and at what price",
                 x=0.06, ha="left", fontsize=12.5, color=INK, fontweight="semibold")
    ax.set_title(f"{len(rows)} models · same prompt · same {len(gpages)} pages, verified independently"
                 " · filled = clears every gate, hollow = fails one · whiskers = 90% band",
                 loc="left", fontsize=8.5, color=MUTED, pad=8)

    out = ROOT / "assets" / "accuracy-vs-cost.png"
    out.parent.mkdir(exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(f"{out.relative_to(ROOT)} written - {len(rows)} models, {len(passing)} clear gates, "
          f"{len(tied)} not separable from the leader")


if __name__ == "__main__":
    main()
