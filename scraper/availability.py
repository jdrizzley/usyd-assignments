"""Unit landing page -> list of availabilities for the target year (BUILD-SPEC §3.3, §6.4)."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from . import config
from .fetch import Fetcher

log = logging.getLogger("scraper.availability")

RE_OUTLINE_HREF = re.compile(
    r"/units/([A-Z]{4}\d{4})/(\d{4})-([A-Z0-9]+)-([A-Z]+)-([A-Z]+)"
)


def normalise_session_label(text: str) -> str:
    """'Semester 2 2026' -> 'Semester 2, 2026'; leaves already-good labels alone."""
    t = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"^(.*?[^,])\s+(\d{4})$", t)
    if m:
        return f"{m.group(1)}, {m.group(2)}"
    return t


def _row_cells_for_link(a) -> list[str] | None:
    tr = a.find_parent("tr")
    if tr is None:
        return None
    cells = tr.find_all(["td", "th"], recursive=False)
    return [c.get_text(" ", strip=True) for c in cells]


def parse_availabilities(html: str, code: str, year: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        m = RE_OUTLINE_HREF.search(a["href"])
        if not m:
            continue
        link_code, y, session, moa, loc = m.groups()
        if link_code != code or int(y) != year:
            continue
        slug = f"{y}-{session}-{moa}-{loc}"
        if slug in seen:
            continue
        mode = config.MODE_CODES.get(moa, moa)
        location = config.LOCATION_CODES.get(loc, loc)
        session_label = ""
        cells = _row_cells_for_link(a)
        if cells and len(cells) >= 4:
            # Session | MoA | Location | Outline
            session_label = normalise_session_label(cells[0])
            if cells[1]:
                mode = cells[1]
            if cells[2]:
                location = cells[2]
        seen[slug] = {
            "code": code,
            "availability": slug,
            "year": int(y),
            "session": session,
            "mode": mode,
            "location": location,
            "sessionLabel": session_label,
            "outlineUrl": f"{config.BASE}/units/{code}/{slug}",
        }
    return sorted(seen.values(), key=lambda d: d["availability"])


def get_availabilities(fetcher: Fetcher, code: str, year: int) -> list[dict] | None:
    """Returns None when the landing page itself is missing (404)."""
    html = fetcher.get(f"{config.BASE}/units/{code}")
    if html is None:
        return None
    avail = parse_availabilities(html, code, year)
    if config.TARGET_SESSIONS:
        avail = [a for a in avail if a["session"] in config.TARGET_SESSIONS]
    return avail


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys

    logging.basicConfig(level=logging.INFO)
    code = sys.argv[1] if len(sys.argv) > 1 else "AMME2200"
    print(json.dumps(get_availabilities(Fetcher(), code, config.TARGET_YEAR), indent=2))
