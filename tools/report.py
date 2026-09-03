"""Chart primitives for build.py: the palette, a number formatter, and the cost/score scatter."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTE = ["#8c6a3f", "#b08d57", "#5f7d6b", "#6a7fa0", "#8a6a8a", "#a06a5f",
           "#5f8a8a", "#9a8a4f", "#7a6aa0", "#6a9a6a"]


def scatter(points, w=620, h=400, ylab="character error rate"):
    """Cost (x, log scale) against error (y). points = [(label, cost, err, colour)]."""
    pts = [p for p in points if p[1] and p[2] is not None]
    if not pts:
        return "<p class='muted'>no priced arms</p>"
    xs = [math.log10(p[1]) for p in pts]
    ys = [p[2] for p in pts]
    x0, x1 = min(xs), max(xs)
    lo, hi_ = min(ys), max(ys)
    pad_y = max((hi_ - lo) * 0.18, 0.02)
    y0, y1 = max(0.0, lo - pad_y), min(1.0, hi_ + pad_y) if hi_ <= 1 else hi_ + pad_y
    if x1 - x0 < 1e-9:
        x0, x1 = x0 - 0.5, x1 + 0.5
    pad = 58

    def px(x):
        return pad + (x - x0) / (x1 - x0) * (w - pad - 24)

    def py(y):
        return h - pad - (y - y0) / (y1 - y0) * (h - pad - 28)

    s = ["<svg viewBox='0 0 " + str(w) + " " + str(h) + "' class='chart' role='img'>"]
    s.append(f"<line x1='{pad}' y1='{h-pad}' x2='{w-16}' y2='{h-pad}' class='axis'/>")
    s.append(f"<line x1='{pad}' y1='16' x2='{pad}' y2='{h-pad}' class='axis'/>")
    for frac in (0, .25, .5, .75, 1):
        y = y0 + frac * (y1 - y0)
        s.append(f"<line x1='{pad}' y1='{py(y):.1f}' x2='{w-16}' y2='{py(y):.1f}' class='grid'/>")
        s.append(f"<text x='{pad-8}' y='{py(y)+4:.1f}' class='tick' text-anchor='end'>{y*100:.0f}%</text>")
    # X ticks at the 1-2-5 decade steps that bracket the data, labelled in real dollars. Without
    # these the horizontal axis carries no readable information at all — the points just sit
    # somewhere on an unlabelled log scale.
    def money(v):
        return f"${v:.5f}".rstrip("0").rstrip(".") if v < 0.01 else f"${v:.3f}"
    dec = math.floor(x0)
    ticks = []
    while dec <= math.ceil(x1):
        for m_ in (1, 2, 5):
            v = m_ * (10 ** dec)
            lx = math.log10(v)
            if x0 - 1e-9 <= lx <= x1 + 1e-9:
                ticks.append(v)
        dec += 1
    if len(ticks) < 2:
        ticks = [10 ** x0, 10 ** x1]
    for v in ticks:
        vx = px(math.log10(v))
        s.append(f"<line x1='{vx:.1f}' y1='16' x2='{vx:.1f}' y2='{h-pad}' class='grid'/>")
        s.append(f"<text x='{vx:.1f}' y='{h-pad+15}' class='tick' "
                 f"text-anchor='middle'>{money(v)}</text>")
    # Labels are placed INWARD: a point on the right half gets its label to its left, so nothing
    # can run past the plot edge. Then near-colliding labels are nudged apart vertically.
    placed = []
    mid = (pad + w - 16) / 2
    for label, cost, err, colour in sorted(pts, key=lambda t: t[2]):
        cx, cy = px(math.log10(cost)), py(err)
        ly = cy + 4
        while any(abs(ly - q) < 24 for q in placed):
            ly += 24
        if ly > h - pad - 4:                      # ran out of room below; go up instead
            ly = cy + 4
            while any(abs(ly - q) < 24 for q in placed):
                ly -= 24
        placed.append(ly)
        right = cx > mid
        tx = cx - 11 if right else cx + 11
        anchor = "end" if right else "start"
        tip = f"{label} — ${cost:.5f} per page — {err*100:.2f}%"
        s.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='7' fill='{colour}' opacity='.9'>"
                 f"<title>{tip}</title></circle>")
        # a generous invisible target so the tooltip is reachable without pixel-hunting
        s.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='15' fill='transparent'>"
                 f"<title>{tip}</title></circle>")
        if abs(ly - (cy + 4)) > 6:                # leader line when the label had to move
            s.append(f"<line x1='{cx:.1f}' y1='{cy:.1f}' x2='{tx:.1f}' y2='{ly-4:.1f}' "
                     f"class='grid'/>")
        s.append(f"<text x='{tx:.1f}' y='{ly:.1f}' class='pt' "
                 f"text-anchor='{anchor}'>{label}<title>{tip}</title></text>")
        s.append(f"<text x='{tx:.1f}' y='{ly+11:.1f}' class='tick' "
                 f"text-anchor='{anchor}'>${cost:.5f}</text>")
    s.append(f"<text x='{(w+pad)/2:.0f}' y='{h-14}' class='axlab' text-anchor='middle'>"
             "cost per page (USD, log scale)</text>")
    s.append(f"<text x='14' y='{h/2:.0f}' class='axlab' text-anchor='middle' "
             f"transform='rotate(-90 14 {h/2:.0f})'>{ylab}</text>")
    s.append("</svg>")
    return "".join(s)



def num(v, fmt="{:.3f}"):
    """An unmeasured metric renders as an em dash. It must never render as zero."""
    return "&mdash;" if v is None else fmt.format(v)


