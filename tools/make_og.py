"""Generate og.png (1200x630) and favicon-32.png. Reproducible: python tools/make_og.py

Paper background, the wordmark in Instrument Sans (the site's only typeface) at the left, and a
rendering of the term ruler across the lower third (STYLE-GUIDE §10). Fonts are fetched from Google Fonts into
tools/fonts/ on first run; if that fails, DejaVu is used so the script still completes.
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "tools" / "fonts"

PAPER = (251, 250, 248)
INK_900 = (26, 23, 20)
INK_500 = (125, 116, 106)
RULE = (229, 223, 215)
ACCENT = (194, 87, 26)
LADDER = [(194, 87, 26), (110, 91, 62), (46, 74, 70), (122, 62, 74), (61, 70, 104)]

FONTS = {
    "sans": ("Instrument Sans", "https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600&display=swap"),
}


def fetch_font(kind: str) -> Path | None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    name, css_url = FONTS[kind]
    target = FONT_DIR / f"{name.replace(' ', '')}.ttf"
    if target.exists():
        return target
    try:
        req = urllib.request.Request(css_url, headers={"User-Agent": "Mozilla/5.0"})  # TTF served for generic UAs
        css = urllib.request.urlopen(req, timeout=20).read().decode()
        urls = re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)", css)
        if not urls:
            return None
        # prefer the 600 weight for sans if present (second block), else first
        url = urls[-1] if kind == "sans" and len(urls) > 1 else urls[0]
        target.write_bytes(urllib.request.urlopen(url, timeout=20).read())
        return target
    except Exception as exc:  # noqa: BLE001
        print(f"font download failed ({exc}); falling back", file=sys.stderr)
        return None


def load(kind: str, size: int) -> ImageFont.FreeTypeFont:
    p = fetch_font(kind)
    if p:
        return ImageFont.truetype(str(p), size)
    fallback = "DejaVuSans.ttf"
    for cand in (Path("/usr/share/fonts/truetype/dejavu") / fallback,):
        if cand.exists():
            return ImageFont.truetype(str(cand), size)
    return ImageFont.load_default()


def draw_ruler(d: ImageDraw.ImageDraw, x0: int, x1: int, base_y: int, sans_small) -> None:
    d.line([(0, base_y), (1200, base_y)], fill=RULE, width=1)
    weeks = 13
    span = x1 - x0
    # 13 teaching weeks + a 1-week break after week 7 + 4 weeks of STUVAC/exams = 18 slots
    slots = weeks + 1 + 4
    step = span / slots
    for w in range(1, weeks + 1):
        idx = (w - 1) + (1 if w > 7 else 0)
        x = x0 + idx * step
        d.line([(x, base_y), (x, base_y + 8)], fill=RULE, width=1)
        label = f"{w:02d}"
        d.text((x + step / 2, base_y + 16), label, fill=INK_500, font=sans_small, anchor="mt")
    # break: dotted segment
    bx0 = x0 + 7 * step
    bx1 = x0 + 8 * step
    d.line([(bx0, base_y), (bx1, base_y)], fill=PAPER, width=3)
    for x in range(int(bx0), int(bx1), 6):
        d.point((x, base_y), fill=INK_500)
    # exam tail hatch
    ex0 = x0 + (weeks + 1) * step
    for x in range(int(ex0), x1, 7):
        d.line([(x, base_y + 2), (x, base_y + 9)], fill=RULE, width=1)
    d.text((ex0 + 6, base_y + 16), "EXAMS", fill=INK_500, font=sans_small, anchor="lt")
    # assessment ticks: (week, weight, unit)
    ticks = [
        (3, 2, 0), (5, 10, 0), (5, 6, 0), (9, 10, 0), (9, 6, 0), (13, 10, 0), (13, 6, 0),
        (2, 5, 1), (4, 15, 1), (6, 15, 1), (8, 10, 1), (11, 20, 1), (12, 5, 1),
        (3, 8, 2), (7, 25, 2), (10, 12, 2), (12, 20, 2), (13, 10, 2),
        (6, 30, 3), (11, 35, 3), (4, 10, 3),
    ]
    stacks: dict[float, int] = {}
    for week, weight, u in ticks:
        idx = (week - 1) + (1 if week > 7 else 0)
        # spread inside the week for realism
        x = x0 + idx * step + step * (0.15 + 0.7 * ((week * 7 + u * 3) % 10) / 10)
        x = round(x)
        n = stacks.get(x, 0)
        stacks[x] = n + 1
        hgt = round(max(6, min(80, 6 + (weight - 2) * (74 / 48))))
        xx = x + n * 4
        d.rectangle([(xx, base_y - hgt), (xx + 2, base_y - 1)], fill=LADDER[u % 5])
    # today
    tx = x0 + 6.4 * step
    d.line([(tx, base_y - 110), (tx, base_y + 9)], fill=ACCENT, width=2)
    d.text((tx + 8, base_y - 112), "TODAY", fill=ACCENT, font=sans_small, anchor="lt")


def make_og(out: Path) -> None:
    img = Image.new("RGB", (1200, 630), PAPER)
    d = ImageDraw.Draw(img)
    title = load("sans", 92)
    sans_label = load("sans", 22)
    sans_small = load("sans", 18)
    sans_body = load("sans", 28)
    d.text((80, 96), "Assessment Calendar", fill=INK_900, font=title, anchor="ls")
    d.text((84, 132), "U S Y D", fill=INK_500, font=sans_label, anchor="ls")
    d.text((84, 205), "Every due date for your units, in one place.", fill=(74, 67, 60), font=sans_body, anchor="ls")
    d.text((84, 240), "Unofficial. Canvas is the source of truth.", fill=INK_500, font=sans_small, anchor="ls")
    draw_ruler(d, 80, 1120, 500, sans_small)
    img.save(out, "PNG", optimize=True)


def make_favicon(out: Path) -> None:
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(0, 0), (31, 31)], radius=3, fill=PAPER)
    d.rectangle([(4, 24), (27, 24)], fill=(181, 171, 160))
    d.rectangle([(15, 6), (17, 24)], fill=ACCENT)
    img.save(out, "PNG", optimize=True)


if __name__ == "__main__":
    make_og(ROOT / "og.png")
    make_favicon(ROOT / "favicon-32.png")
    print("wrote og.png and favicon-32.png")
