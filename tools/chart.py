"""Render assets/accuracy-vs-cost.png from results.json — one point per model.

Same selection rule as RESULTS.md's ranking table: P2 arms with gold scores, second-pass arms
excluded (their transcription is another arm's). Filled marker = clears every gate; hollow = fails
one. The shaded band is the set the evidence cannot separate from the leader, by the same
`gold.separated` test the written results use.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gold as GOLD  # noqa: E402

PAPER, CARD, INK, MUTED, RULE = "#f0efe9", "#fbfaf6", "#1a1815", "#6a675e", "#d9d6cc"
GOOD, BAD, BAND = "#2f6f5e", "#a8452f", "#2f6f5e"


def main() -> None:
    data = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
    gpages = data["_meta"]["gold_pages"]
    rows = []
    for k, a in data["arms"].items():
        g = a.get("gold")
        if not g or a["prompt"] != "P2" or a.get("derived_from"):
            continue
        rows.append(dict(id=k, name=a["label"].split(" · ")[0], x=a["summary"]["cost_per_page_usd"],
                         y=g["task_score"], lo=g["ci"][0], hi=g["ci"][1],
                         ok=not g["gate_failures"], gold=g))
    rows.sort(key=lambda r: -r["y"])
    passing = [r for r in rows if r["ok"]]
    top = passing[0]
    tied = [top] + [r for r in passing[1:] if not GOLD.separated(top["gold"], r["gold"])]

    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=200)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(CARD)
    ax.set_xscale("log")

    band_lo = min(r["y"] for r in tied)
    ax.axhspan(band_lo - 0.003, 1.003, color=BAND, alpha=0.08, lw=0)
    ax.text(0.0024, (band_lo + 1.0) / 2, f"indistinguishable from the leader on {len(gpages)} pages",
            color=GOOD, fontsize=8.5, va="center", ha="center")

    for r in rows:
        c = GOOD if r["ok"] else BAD
        ax.errorbar(r["x"], r["y"], yerr=[[r["y"] - r["lo"]], [r["hi"] - r["y"]]],
                    fmt="none", ecolor=c, elinewidth=1, capsize=2.5, alpha=0.7)
        ax.scatter(r["x"], r["y"], s=60, facecolors=c if r["ok"] else CARD, edgecolors=c,
                   linewidths=1.6, zorder=3)

    # Label placement — manual nudges for the crowded top cluster, default elsewhere.
    nudge = {"Gemini 3.7 Flash": (7, 7), "Gemini 3.5 Flash": (7, -8), "Claude Sonnet 5": (7, 7),
             "Qwen 3.8 Max": (-7, 8), "GPT 5.6 Terra": (-7, -3), "Kimi K3": (7, -7)}
    for r in rows:
        dx, dy = nudge.get(r["name"], (7, 0))
        ax.annotate(r["name"], (r["x"], r["y"]), xytext=(dx, dy), textcoords="offset points",
                    fontsize=8.5, color=INK, ha="left" if dx > 0 else "right", va="center")

    ax.set_xlim(0.0004, 0.025)
    ax.set_ylim(0.38, 1.02)
    ax.set_xlabel("price per page, USD (log scale; list rate × measured output)", color=MUTED, fontsize=9)
    ax.set_ylabel("task score on the gold pages", color=MUTED, fontsize=9)
    ax.set_xticks([0.0005, 0.001, 0.002, 0.005, 0.01, 0.02])
    ax.set_xticklabels(["$0.0005", "$0.001", "$0.002", "$0.005", "$0.01", "$0.02"])
    ax.set_yticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_yticklabels([f"{int(t*100)}%" for t in ax.get_yticks()])
    ax.tick_params(colors=MUTED, labelsize=8.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(RULE)
    ax.grid(True, which="major", color=RULE, lw=0.6, alpha=0.7)
    ax.grid(False, which="minor")

    fig.suptitle("Which model reads a scanned Arabic scholarly page correctly, and at what price",
                 x=0.06, ha="left", fontsize=12.5, color=INK, fontweight="semibold")
    ax.set_title(f"{len(rows)} models · same prompt · same {len(gpages)} pages, verified independently"
                 " · filled = clears every gate, hollow = fails one · whiskers = 90% band",
                 loc="left", fontsize=8.5, color=MUTED, pad=8)

    out = ROOT / "assets" / "accuracy-vs-cost.png"
    out.parent.mkdir(exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(f"{out.relative_to(ROOT)} written - {len(rows)} models, band holds {len(tied)}")


if __name__ == "__main__":
    main()
