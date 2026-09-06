"""Refresh the chart panel of assets/post-hero.png from the current chart.

The hero is a hand-composited social image: annotated page on the left, the accuracy-vs-cost
chart on the right, a caption underneath. Only the chart goes stale when an arm is added, so
this repaints that panel and leaves every other pixel — including the caption's typeface, which
is not one this repo can render — exactly as it was. Idempotent: the panel is cleared to the
paper colour before the chart is drawn back into it.

    python tools/hero.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PAPER = (240, 239, 233)
PANEL = (702, 203, 1165, 690)   # x, y, max width, max height of the chart panel, measured off the composite


def main() -> None:
    hero_path, chart_path = ROOT / "assets" / "post-hero.png", ROOT / "assets" / "accuracy-vs-cost.png"
    hero = Image.open(hero_path).convert("RGB")
    chart = Image.open(chart_path).convert("RGB")

    x, y, w, h = PANEL
    scale = min(w / chart.width, h / chart.height)
    size = (round(chart.width * scale), round(chart.height * scale))
    hero.paste(PAPER, (x, y, x + w, y + h))
    hero.paste(chart.resize(size, Image.LANCZOS), (x, y))
    hero.save(hero_path)
    print(f"assets/post-hero.png written - chart panel {size[0]}x{size[1]} at ({x}, {y})")


if __name__ == "__main__":
    main()
