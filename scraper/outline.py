"""Outline page -> unit JSON with assessments (BUILD-SPEC §3.4, §5.3, §6.5)."""
from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup, Tag

from . import config

log = logging.getLogger("scraper.outline")

# The live site renders "Due date : 17 Aug 2026" (space before the colon) once the cell's
# <b>/<br> structure is flattened with get_text(" "), so allow optional whitespace there.
RE_DUE = re.compile(
    r"Due date\s*:\s*(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})(?:\s*at\s*(\d{1,2}:\d{2}))?", re.I
)
RE_CLOSE = re.compile(
    r"Closing date\s*:\s*(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})(?:\s*at\s*(\d{1,2}:\d{2}))?", re.I
)
RE_WEEK = re.compile(r"Week\s*(\d{1,2})", re.I)
RE_WEEK_ONLY = re.compile(r"^Week\s*(\d{1,2})\.?$", re.I)
RE_EXAM = re.compile(r"formal exam period", re.I)
RE_CENSUS = re.compile(
    r"census date for this unit availability is\s*(\d{1,2}\s+\w+\s+\d{4})", re.I
)
RE_SESSION_HEADING = re.compile(
    r"^\s*([^\[\n]+?\d{4})\s*\[([^\]]+)\]\s*[-–]\s*(.+?)\s*$"
)
RE_WEIGHT = re.compile(r"(\d+(?:\.\d+)?)\s*%")

COLUMN_KEYS = {
    "type": ("type",),
    "description": ("description",),
    "weight": ("weight",),
    "due": ("due",),
    "length": ("length",),
    "ai": ("use of ai", "ai"),
}


class OutlineParseError(Exception):
    pass


def _parse_date(s: str) -> str | None:
    s = re.sub(r"\s+", " ", s.strip().replace(".", ""))
    parts = s.split(" ")
    if len(parts) == 3 and len(parts[1]) > 3:
        # "Sept" / "September" -> try full name first, then 3-letter abbreviation
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                pass
        s = f"{parts[0]} {parts[1][:3]} {parts[2]}"
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _norm_time(t: str) -> str:
    h, m = t.split(":")
    return f"{int(h):02d}:{int(m):02d}"


def parse_due(text: str) -> dict:
    """Parse the flattened Due cell text into the date fields of an assessment."""
    raw = re.sub(r"\s+", " ", text).strip()
    out: dict = {
        "week": None,
        "dateKind": "unparsed",
        "dueDate": None,
        "dueTime": None,
        "timeAssumed": False,
        "closingDate": None,
        "dueRaw": raw,
    }
    mw = RE_WEEK.search(raw)
    if mw:
        out["week"] = int(mw.group(1))
    mc = RE_CLOSE.search(raw)
    if mc:
        out["closingDate"] = _parse_date(mc.group(1))
    md = RE_DUE.search(raw)
    if md:
        d = _parse_date(md.group(1))
        if d:
            out["dateKind"] = "absolute"
            out["dueDate"] = d
            if md.group(2):
                out["dueTime"] = _norm_time(md.group(2))
            else:
                out["dueTime"] = "23:59"
                out["timeAssumed"] = True
            return out
    if RE_EXAM.search(raw):
        out["dateKind"] = "exam_period"
        return out
    remaining = RE_CLOSE.sub("", raw).strip()
    if RE_WEEK_ONLY.match(remaining):
        out["dateKind"] = "week_only"
        return out
    return out


def parse_weight(text: str) -> tuple[float | int | None, str]:
    raw = re.sub(r"\s+", " ", text).strip()
    m = RE_WEIGHT.search(raw)
    if not m:
        return None, raw
    v = float(m.group(1))
    return (int(v) if v.is_integer() else v), raw


def _header_map(table: Tag) -> dict[str, int] | None:
    header_row = None
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
    if header_row is None:
        for tr in table.find_all("tr"):
            if tr.find("th"):
                header_row = tr
                break
    if header_row is None:
        return None
    cells = header_row.find_all(["th", "td"], recursive=False)
    labels = [c.get_text(" ", strip=True).lower() for c in cells]
    mapping: dict[str, int] = {}
    for key, needles in COLUMN_KEYS.items():
        for i, label in enumerate(labels):
            if any(n in label for n in needles) and i not in mapping.values():
                mapping[key] = i
                break
    if "weight" not in mapping or "due" not in mapping:
        return None
    return mapping


def _find_table(soup: BeautifulSoup) -> tuple[Tag | None, dict[str, int] | None]:
    panel = soup.find(id="assessment_panel")
    if panel:
        t = panel.find("table")
        if t:
            hm = _header_map(t)
            if hm:
                return t, hm
    for t in soup.find_all("table"):
        hm = _header_map(t)
        if hm:
            return t, hm
    return None, None


def _is_legend_row(cells: list[Tag]) -> bool:
    text = " ".join(c.get_text(" ", strip=True) for c in cells).lower()
    text = re.sub(r"[^a-z ]", "", text).strip()
    return "early feedback task" in text and len(text) <= len("early feedback task") + 4


def _cell(cells: list[Tag], hm: dict[str, int], key: str) -> Tag | None:
    i = hm.get(key)
    if i is None or i >= len(cells):
        return None
    return cells[i]


def _text(cell: Tag | None) -> str:
    return cell.get_text(" ", strip=True) if cell is not None else ""


def _name_and_description(cell: Tag | None) -> tuple[str, str]:
    if cell is None:
        return "", ""
    strong = cell.find(["strong", "b"])
    if strong is None:
        return _text(cell), ""
    name = strong.get_text(" ", strip=True)
    clone = copy.copy(cell)
    first = clone.find(["strong", "b"])
    if first is not None:
        first.decompose()
    desc = clone.get_text(" ", strip=True)
    return name, desc


def _early_feedback(cell: Tag | None) -> bool:
    if cell is None:
        return False
    for img in cell.find_all("img"):
        for attr in ("alt", "title"):
            if (img.get(attr) or "").strip().lower() == "early feedback task":
                return True
    return False


def _unit_title(soup: BeautifulSoup) -> tuple[str, str]:
    h1 = soup.find("h1")
    if not h1:
        return "", ""
    t = h1.get_text(" ", strip=True)
    if ": " in t:
        code, name = t.split(": ", 1)
        return code.strip(), name.strip()
    return "", t


def _session_heading(soup: BeautifulSoup) -> tuple[str, str, str] | None:
    for tag in soup.find_all(["h3", "h2", "h4", "h5", "p", "span", "div"]):
        if tag.find(["h1", "h2", "h3", "h4", "h5", "p", "div", "table"]):
            continue  # not a leaf; would swallow neighbouring text
        t = tag.get_text(" ", strip=True)
        if "[" not in t or len(t) > 160:
            continue
        m = RE_SESSION_HEADING.match(t)
        if m:
            return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    return None


def _census(soup: BeautifulSoup) -> str | None:
    txt = soup.get_text(" ", strip=True)
    m = RE_CENSUS.search(txt)
    if not m:
        return None
    return _parse_date(m.group(1))


def parse_outline(html: str, meta: dict) -> dict:
    """Parse an outline page. `meta` supplies code, availability, session, mode, location,
    sessionLabel and sourceUrl from the landing page; page content overrides where present.
    """
    soup = BeautifulSoup(html, "lxml")
    warnings: list[str] = []

    code_from_page, name = _unit_title(soup)
    code = meta.get("code") or code_from_page
    if code_from_page and meta.get("code") and code_from_page != meta["code"]:
        warnings.append(f"h1 code {code_from_page!r} != expected {meta['code']!r}")

    session_label = meta.get("sessionLabel") or ""
    mode = meta.get("mode") or ""
    location = meta.get("location") or ""
    heading = _session_heading(soup)
    if heading:
        session_label, mode, location = heading
    else:
        warnings.append("session heading not found")

    availability = meta.get("availability") or ""
    session = meta.get("session") or (availability.split("-")[1] if "-" in availability else "")
    slug = f"{code}-{availability}" if availability else code

    table, hm = _find_table(soup)
    assessments: list[dict] = []
    if table is None or hm is None:
        warnings.append("assessment table not found")
    else:
        idx = 0
        for tr in table.find_all("tr"):
            if tr.find_parent("thead") is not None:
                continue
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            first = _text(cells[0])
            if first.lower().startswith("outcomes assessed"):
                continue
            if len(cells) < 4:
                continue
            if _is_legend_row(cells):
                continue
            if tr.find("th") and all(_text(c).lower() in ("type", "description", "weight", "due", "length", "use of ai", "ai") for c in cells):
                continue  # a repeated header row
            type_cell = _cell(cells, hm, "type")
            desc_cell = _cell(cells, hm, "description")
            weight, weight_raw = parse_weight(_text(_cell(cells, hm, "weight")))
            due = parse_due(_text(_cell(cells, hm, "due")))
            a_name, a_desc = _name_and_description(desc_cell)
            assessments.append(
                {
                    "id": f"{slug}-{idx}",
                    "name": a_name,
                    "description": a_desc,
                    "type": _text(type_cell),
                    "weight": weight,
                    "weightRaw": weight_raw,
                    "week": due["week"],
                    "dateKind": due["dateKind"],
                    "dueDate": due["dueDate"],
                    "dueTime": due["dueTime"],
                    "timeAssumed": due["timeAssumed"],
                    "closingDate": due["closingDate"],
                    "length": _text(_cell(cells, hm, "length")),
                    "aiPolicy": _text(_cell(cells, hm, "ai")),
                    "earlyFeedback": _early_feedback(type_cell),
                    "dueRaw": due["dueRaw"],
                }
            )
            idx += 1
        if not assessments:
            warnings.append("assessment table found but no rows parsed")

    return {
        "code": code,
        "name": name,
        "availability": availability,
        "session": session,
        "sessionLabel": session_label,
        "mode": mode,
        "location": location,
        "censusDate": _census(soup),
        "sourceUrl": meta.get("sourceUrl") or f"{config.BASE}/units/{code}/{availability}",
        "scrapedAt": meta.get("scrapedAt")
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "assessments": assessments,
        "parseWarnings": warnings,
    }


def _meta_from_url(url: str) -> dict:
    m = re.search(r"/units/([A-Z]{4}\d{4})/((\d{4})-([A-Z0-9]+)-([A-Z]+)-([A-Z]+))", url)
    if not m:
        raise OutlineParseError(f"not an outline URL: {url}")
    code, slug, year, session, moa, loc = m.groups()
    return {
        "code": code,
        "availability": slug,
        "session": session,
        "mode": config.MODE_CODES.get(moa, moa),
        "location": config.LOCATION_CODES.get(loc, loc),
        "sourceUrl": f"{config.BASE}/units/{code}/{slug}",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse one unit outline page to JSON.")
    ap.add_argument("--url", help="outline URL, e.g. https://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC")
    ap.add_argument("--file", help="parse a saved HTML file instead of fetching")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    if not args.url:
        ap.error("--url is required (optionally with --file to read from disk)")
    meta = _meta_from_url(args.url)
    if args.file:
        html = open(args.file, encoding="utf-8").read()
    else:
        from .fetch import Fetcher

        html = Fetcher().get(args.url)
        if html is None:
            print(f"404 or disallowed: {args.url}", file=sys.stderr)
            return 2
    unit = parse_outline(html, meta)
    json.dump(unit, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0 if unit["assessments"] else 1


if __name__ == "__main__":
    sys.exit(main())
