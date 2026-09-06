"""Social assets for a post: a square leaderboard image and a four-slide carousel PDF.

Every benchmark number here — model counts, scores, prices, the gate, which arms are tied — is
read from results.json, so a slide cannot drift from the result it quotes. The only hand-written
figures are slide 1's production audit (365 defects over 100 pages), which is not a benchmark
number. Sized for a feed: type large enough to read at 552px without tapping, which the full
chart is not.

    python tools/social.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.ticker import FixedLocator  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import chart as CH  # noqa: E402
import gold as GOLD  # noqa: E402

OUT = ROOT / "assets" / "social"
REPO = "github.com/MarioMagdy/arabic-page-extraction-bench"
XTICKS, XLABELS = [0.2, 0.5, 1, 2, 5, 10], ["$0.20", "$0.50", "$1", "$2", "$5", "$10"]


def page(fig):
    """A blank square slide in the benchmark's own palette."""
    fig.patch.set_facecolor(CH.PAPER)
    return fig


def footer(fig, note: str = REPO):
    fig.text(0.06, 0.045, note, fontsize=13, color=CH.MUTED)


def headline(fig, eyebrow: str, text: str, y: float = 0.88):
    fig.text(0.06, y + 0.06, eyebrow, fontsize=14, color=CH.GOOD, fontweight="semibold")
    fig.text(0.06, y, text, fontsize=32, color=CH.INK, fontweight="semibold", va="top", linespacing=1.35)


def leaderboard(fig, rows, y0: float, dy: float = 0.075, size: int = 19):
    """Colour dot, model, task score, price for the whole book — one row per model."""
    for i, r in enumerate(rows):
        y = y0 - i * dy
        fig.text(0.075, y, "●", fontsize=size + 3, color=r["c"], va="center", ha="center")
        fig.text(0.11, y, r["name"], fontsize=size, color=CH.INK, va="center")
        fig.text(0.68, y, f"{r['y']*100:.1f}%", fontsize=size, color=CH.INK, va="center", ha="right",
                 family="DejaVu Sans Mono")
        fig.text(0.93, y, f"${r['x']:.2f}", fontsize=size, color=CH.MUTED, va="center", ha="right",
                 family="DejaVu Sans Mono")


def scatter(fig, rect, rows, nudge):
    ax = fig.add_axes(rect)
    CH.style(ax)
    ax.xaxis.set_major_locator(FixedLocator(XTICKS))
    ax.set_xticklabels(XLABELS)
    ax.tick_params(labelsize=14)
    CH.draw_points(ax, rows, 420)
    ax.set_xlim(0.18, 20)
    lo, hi = min(r["lo"] for r in rows), max(r["hi"] for r in rows)
    ax.set_ylim(lo - 0.006, min(1.004, hi + 0.004))
    yt = [t for t in (0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.0) if ax.get_ylim()[0] <= t <= ax.get_ylim()[1]]
    ax.set_yticks(yt)
    ax.set_yticklabels([f"{t*100:.0f}%" for t in yt])
    for r in rows:
        dx, dy = nudge.get(r["name"], (16, 0))
        ax.annotate(f"{r['name']}\n{r['y']*100:.1f}%  ·  ${r['x']:.2f}", (r["x"], r["y"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=15, color=CH.INK,
                    ha="center" if dx == 0 else ("left" if dx > 0 else "right"), va="center", linespacing=1.5)
    return ax


# Hand-placed: Sonnet and Kimi sit at almost the same price, Terra and Kimi at almost the same
# score, so left/right alternation is the only thing that keeps six labels off each other.
# The middle of the price axis is crowded: 3.8 and its thinking-off twin sit on top of each other
# at ~$2.3, Qwen is a third of a decade away, and Sonnet and Kimi share a price. Everything in that
# cluster labels leftward so no label crosses a neighbour's error bar.
NUDGE = {"Gemini 3.7 Flash": (18, 0), "Gemini 3.5 Flash": (18, 0), "Claude Sonnet 5": (18, 0),
         "Kimi K3": (18, 0), "GPT 5.6 Terra": (-18, 0), "Qwen 3.8 Max": (0, 40),
         "Gemini 3.8 Flash": (-18, 0), "Gemini 3.8 Flash, thinking off": (-18, -6)}


def square(passing, span, F):
    fig = page(plt.figure(figsize=(12, 12), dpi=100))
    fig.text(0.06, 0.945, "Which model reads a scanned Arabic scholarly\npage correctly — and at what price",
             fontsize=30, color=CH.INK, fontweight="semibold", va="top", linespacing=1.3)
    fig.text(0.06, 0.815, f"{F['arms']} arms across {F['models']} vision models, one request, the same {F['truth']} pages. "
                          f"These are the "
                          f"{len(passing)} that clear\nevery gate — and they span {span:.0f}× in price for the "
                          f"same {F['book']}-page book.",
             fontsize=16, color=CH.MUTED, va="top", linespacing=1.5)
    ax = scatter(fig, [0.10, 0.14, 0.86, 0.60], passing, NUDGE)
    ax.set_xlabel(f"price to read the whole {F['book']}-page book, USD (log scale)", color=CH.MUTED, fontsize=15, labelpad=10)
    ax.set_ylabel("task score on the verified pages", color=CH.MUTED, fontsize=15)
    footer(fig)
    fig.savefig(OUT / "leaderboard-square.png", facecolor=fig.get_facecolor())
    plt.close(fig)


def slide_problem(pdf):
    fig = page(plt.figure(figsize=(12, 12), dpi=100))
    headline(fig, "THE PROBLEM", "365 defects across\n100 pages. 75% were\nstructure, not\nmisread letters.", 0.90)
    fig.text(0.06, 0.52, "Running heads swallowed into\nthe body text. Footnotes merged\ninto the paragraph above them.\n"
                         "Page numbers left sitting inline.\n\nSo I stopped asking the model to\nread the page, and started asking\n"
                         "for an ordered sequence of typed\nblocks with footnote anchors.",
             fontsize=19, color=CH.MUTED, va="top", linespacing=1.7)
    im = Image.open(ROOT / "assets" / "p093-annotated.png").convert("RGB")
    ax = fig.add_axes([0.58, 0.13, 0.38, 0.70])
    ax.imshow(im)
    ax.axis("off")
    footer(fig)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def slide_answer(pdf, passing, tied, span, F):
    fig = page(plt.figure(figsize=(12, 12), dpi=100))
    headline(fig, "THE ANSWER", f"{len(tied)} of them cannot be\nseparated on this evidence.\nThey span {span:.0f}× in price.", 0.90)
    fig.text(0.06, 0.66, f"{len(passing)} clear every gate; the top {len(tied)} cannot be separated on the\n"
                         f"{F['gold']} hand-verified pages. Score, then the price for a {F['book']}-page book.",
             fontsize=17, color=CH.MUTED, va="top", linespacing=1.6)
    # Fit whatever clears the gates between the subtitle and the kicker, rather than a
    # spacing that happened to suit six rows.
    top_y, bottom_y = 0.56, 0.19
    dy = min(0.068, (top_y - bottom_y) / max(len(passing) - 1, 1))
    leaderboard(fig, passing, top_y, dy=dy, size=19 if len(passing) <= 7 else 17)
    fig.text(0.06, 0.105, "When accuracy ties, the answer is cost.", fontsize=20, color=CH.GOOD,
             fontweight="semibold")
    footer(fig)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def slide_incumbent(pdf, old, cheap, F):
    fig = page(plt.figure(figsize=(12, 12), dpi=100))
    headline(fig, "THE ONE THAT STUNG", "The model I was already\nshipping on was the\nwrong one.", 0.90)
    fig.text(0.06, 0.58, f"{old['name']} places every footnote anchor\ncorrectly, then misreads the prose.",
             fontsize=20, color=CH.MUTED, va="top", linespacing=1.6)
    rows = [("task score", f"{old['y']*100:.1f}%", f"body accuracy {F['body']:.3f}, under the {F['gate']:.2f} gate"),
            (f"price, {F['book']} pages", f"${old['x']:.2f}", f"{old['x']/cheap['x']:.1f}× what {cheap['name']} costs"),
            ("that model scores", f"{cheap['y']*100:.1f}%", "for $%.2f" % cheap["x"])]
    for i, (k, v, note) in enumerate(rows):
        y = 0.44 - i * 0.105
        fig.text(0.06, y, k, fontsize=16, color=CH.MUTED, va="center")
        fig.text(0.44, y, v, fontsize=30, color=CH.INK, va="center", ha="right", fontweight="semibold",
                 family="DejaVu Sans Mono")
        fig.text(0.48, y, note, fontsize=16, color=CH.MUTED, va="center")
    fig.text(0.06, 0.115, "Older and cheaper are not the same thing.", fontsize=20, color=CH.GOOD,
             fontweight="semibold")
    footer(fig)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def slide_limits(pdf, F):
    fig = page(plt.figure(figsize=(12, 12), dpi=100))
    headline(fig, "WHAT IT CANNOT TELL YOU", "Enough to rule models\nout. Not enough to\ncrown a winner.", 0.90)
    bullets = [f"{F['gold']} pages verified by hand, not {F['truth']}. The top {F['tied']} sit\ninside each other's confidence bands.",
               "One book, one publisher's typography, one script.",
               "One run per model. No repeats, so no variance estimate.",
               f"The other {F['truth'] - F['gold']} pages measure agreement between models,\nwhich is not accuracy and cannot rank anything."]
    for i, b in enumerate(bullets):
        y = 0.56 - i * 0.115
        fig.text(0.065, y, "—", fontsize=18, color=CH.GOOD, va="top")
        fig.text(0.11, y, b, fontsize=18, color=CH.MUTED, va="top", linespacing=1.6)
    fig.text(0.06, 0.115, "The gates and the weights were fixed before I read a single score.",
             fontsize=18, color=CH.INK, fontweight="semibold")
    footer(fig)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gpages, rows = CH.load()
    passing = [r for r in rows if r["ok"]]
    top = passing[0]
    tied = [top] + [r for r in passing[1:] if not GOLD.separated(top["gold"], r["gold"])]
    span = max(r["x"] for r in tied) / min(r["x"] for r in tied)
    old = next(r for r in rows if r["name"] == "Gemini 2.5 Flash")
    cheap = min(passing, key=lambda r: r["x"])
    meta = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))["_meta"]
    F = {"arms": len(rows), "models": len({a["model"] for a in json.loads((ROOT / "results.json").read_text(encoding="utf-8"))["arms"].values() if a.get("gold") and a["prompt"] == "P2"}),
         "truth": len(meta["truth_pages"]), "gold": len(gpages),
         "tied": len(tied), "book": CH.BOOK_PAGES, "gate": meta["gates"]["body_accuracy"],
         "body": old["gold"]["scores"]["body_accuracy"]["v"]}

    square(passing, span, F)
    with PdfPages(OUT / "carousel.pdf") as pdf:
        slide_problem(pdf)
        slide_answer(pdf, passing, tied, span, F)
        slide_incumbent(pdf, old, cheap, F)
        slide_limits(pdf, F)

    print(f"assets/social/leaderboard-square.png - {len(passing)} models, {span:.1f}x price span")
    print(f"assets/social/carousel.pdf - 4 slides")


if __name__ == "__main__":
    main()
