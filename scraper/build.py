"""Orchestrator: discover -> availabilities -> outlines -> weeks -> data/ (BUILD-SPEC §6.7, §6.8).

Writes to a temporary directory and swaps it into place only after every check passes, so a
broken run never replaces good data.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .availability import get_availabilities
from .calendar_infer import apply_override, infer_weeks
from .discover import DiscoveryError, discover_codes
from .fetch import FetchError, Fetcher
from .outline import parse_outline

log = logging.getLogger("scraper.build")


class BuildFailed(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def process_code(fetcher: Fetcher, code: str, year: int) -> dict:
    """Fetch one unit's landing page and every target-year outline. Never raises."""
    result = {
        "code": code,
        "landing_404": False,
        "landing_failed": False,
        "availabilities": 0,
        "units": [],
        "outline_failures": 0,
        "outline_404": 0,
    }
    try:
        avail = get_availabilities(fetcher, code, year)
    except FetchError as exc:
        log.warning("landing page failed for %s: %s", code, exc)
        result["landing_failed"] = True
        return result
    if avail is None:
        result["landing_404"] = True
        return result
    result["availabilities"] = len(avail)
    for a in avail:
        try:
            html = fetcher.get(a["outlineUrl"])
        except FetchError as exc:
            log.warning("outline fetch failed for %s: %s", a["outlineUrl"], exc)
            result["outline_failures"] += 1
            continue
        if html is None:
            # Outline not published yet (or disallowed). Normal, expected state.
            result["outline_404"] += 1
            continue
        meta = dict(a)
        meta["sourceUrl"] = a["outlineUrl"]
        meta["scrapedAt"] = _now_iso()
        try:
            unit = parse_outline(html, meta)
        except Exception as exc:  # parser bug on an odd page: record, don't crash the run
            log.error("parse crashed for %s: %s", a["outlineUrl"], exc)
            unit = {
                **{k: a.get(k, "") for k in ("code", "availability", "session", "sessionLabel", "mode", "location")},
                "name": "",
                "censusDate": None,
                "sourceUrl": a["outlineUrl"],
                "scrapedAt": meta["scrapedAt"],
                "assessments": [],
                "parseWarnings": [f"parser exception: {exc}"],
            }
        if not unit.get("name"):
            unit["name"] = a.get("name", "") or unit.get("name", "")
        result["units"].append(unit)
    return result


def write_output(out_dir: Path, units: list[dict], weeks: dict, meta: dict) -> None:
    units_dir = out_dir / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for u in sorted(units, key=lambda u: (u["code"], u["availability"])):
        fname = f"{u['code']}-{u['availability']}.json"
        (units_dir / fname).write_text(json.dumps(u, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        index.append(
            {
                "code": u["code"],
                "name": u["name"],
                "availability": u["availability"],
                "session": u["session"],
                "sessionLabel": u["sessionLabel"],
                "mode": u["mode"],
                "location": u["location"],
                "assessmentCount": len(u["assessments"]),
                "file": f"data/units/{fname}",
            }
        )
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (out_dir / "weeks.json").write_text(json.dumps(weeks, indent=2) + "\n", encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def swap_into_place(tmp_dir: Path, data_dir: Path) -> None:
    """Atomically-ish replace data_dir with tmp_dir, preserving weeks.override.json."""
    override = data_dir / "weeks.override.json"
    if override.exists():
        shutil.copy2(override, tmp_dir / "weeks.override.json")
    backup = data_dir.with_name(data_dir.name + ".previous")
    if backup.exists():
        shutil.rmtree(backup)
    if data_dir.exists():
        os.rename(data_dir, backup)
    try:
        shutil.move(str(tmp_dir), str(data_dir))
    except Exception:
        if backup.exists():
            os.rename(backup, data_dir)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def read_previous_meta(data_dir: Path) -> dict | None:
    p = data_dir / "meta.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def check_thresholds(stats: dict, partial: bool, previous: dict | None, force: bool) -> list[str]:
    problems: list[str] = []
    if not partial:
        if stats["unitsDiscovered"] < config.MIN_CODES_DISCOVERED:
            problems.append(f"only {stats['unitsDiscovered']} codes discovered (< {config.MIN_CODES_DISCOVERED})")
        if stats["unitsWithCurrentOutline"] < config.MIN_UNITS_WITH_OUTLINE:
            problems.append(f"only {stats['unitsWithCurrentOutline']} units with a current outline (< {config.MIN_UNITS_WITH_OUTLINE})")
    attempted = stats["outlineFetchAttempts"]
    if attempted:
        fail_ratio = stats["outlineFetchFailures"] / attempted
        if fail_ratio > config.MAX_OUTLINE_FETCH_FAIL_RATIO:
            problems.append(f"{fail_ratio:.1%} of outline fetches failed (> {config.MAX_OUTLINE_FETCH_FAIL_RATIO:.0%})")
    parsed = stats["unitsWithCurrentOutline"]
    if parsed:
        zero_ratio = stats["unitsWithZeroAssessments"] / parsed
        if zero_ratio > config.MAX_ZERO_ASSESSMENT_RATIO:
            problems.append(f"{zero_ratio:.1%} of outlines parsed to zero assessments (> {config.MAX_ZERO_ASSESSMENT_RATIO:.0%})")
    if previous and not force:
        prev_n = int(previous.get("unitsWithCurrentOutline") or 0)
        if prev_n and parsed < prev_n * config.MIN_RELATIVE_UNIT_COUNT:
            problems.append(
                f"new run has {parsed} units vs {prev_n} in the existing data; refusing to overwrite "
                f"(pass --force to override)"
            )
    return problems


def run(args: argparse.Namespace) -> int:
    year = args.year
    data_dir = Path(args.out).resolve()
    fetcher = Fetcher(use_cache=not args.no_cache)
    started = time.time()
    partial = bool(args.codes or args.limit)

    if args.codes:
        codes = sorted({c.strip().upper() for c in args.codes.split(",") if c.strip()})
        log.info("using %d codes from --codes (discovery skipped)", len(codes))
    else:
        codes = discover_codes(fetcher)
    if args.limit:
        codes = codes[: args.limit]
        log.info("limiting to first %d codes", len(codes))
    if args.also:
        extra = sorted({c.strip().upper() for c in args.also.split(",") if c.strip()} - set(codes))
        codes = sorted(set(codes) | set(extra))
        log.info("added %d codes from --also", len(extra))

    units: list[dict] = []
    stats = {
        "unitsDiscovered": len(codes),
        "landingPages404": 0,
        "landingPagesFailed": 0,
        "availabilitiesFound": 0,
        "outlineFetchAttempts": 0,
        "outlineFetchFailures": 0,
        "outlinesNotPublished": 0,
        "unitsWithCurrentOutline": 0,
        "unitsWithZeroAssessments": 0,
    }
    done = 0
    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENCY) as pool:
        futures = {pool.submit(process_code, fetcher, c, year): c for c in codes}
        for fut in as_completed(futures):
            r = fut.result()
            done += 1
            stats["landingPages404"] += r["landing_404"]
            stats["landingPagesFailed"] += r["landing_failed"]
            stats["availabilitiesFound"] += r["availabilities"]
            stats["outlineFetchAttempts"] += r["availabilities"]
            stats["outlineFetchFailures"] += r["outline_failures"]
            stats["outlinesNotPublished"] += r["outline_404"]
            for u in r["units"]:
                stats["unitsWithCurrentOutline"] += 1
                if not u["assessments"]:
                    stats["unitsWithZeroAssessments"] += 1
                units.append(u)
            if done % 100 == 0 or done == len(codes):
                log.info("%d/%d codes processed, %d units with outlines, %.0fs elapsed",
                         done, len(codes), stats["unitsWithCurrentOutline"], time.time() - started)

    weeks = infer_weeks(units, year)
    weeks = apply_override(weeks, data_dir / "weeks.override.json")

    assessments_total = sum(len(u["assessments"]) for u in units)
    assessments_abs = sum(1 for u in units for a in u["assessments"] if a["dateKind"] == "absolute")
    sessions = sorted({u["session"] for u in units})
    meta = {
        "generatedAt": _now_iso(),
        "targetYear": year,
        "targetSessions": config.TARGET_SESSIONS or sessions,
        "unitsDiscovered": stats["unitsDiscovered"],
        "unitsWithCurrentOutline": stats["unitsWithCurrentOutline"],
        "assessmentsTotal": assessments_total,
        "assessmentsWithAbsoluteDate": assessments_abs,
        "scraperVersion": config.SCRAPER_VERSION,
        "errors": stats["outlineFetchFailures"] + stats["landingPagesFailed"] + stats["unitsWithZeroAssessments"],
        "partialRun": partial,
        "stats": stats,
        "fetch": {
            "requests": fetcher.stats.requests,
            "cacheHits": fetcher.stats.cache_hits,
            "robotsSkipped": fetcher.stats.robots_skipped,
        },
        "durationSeconds": round(time.time() - started),
    }

    # -- summary table ---------------------------------------------------------
    rows = [
        ("Codes processed", len(codes)),
        ("Landing pages 404", stats["landingPages404"]),
        ("Landing pages failed", stats["landingPagesFailed"]),
        ("Availabilities in target year", stats["availabilitiesFound"]),
        ("Outlines not yet published", stats["outlinesNotPublished"]),
        ("Outline fetch failures", stats["outlineFetchFailures"]),
        ("Units with outline parsed", stats["unitsWithCurrentOutline"]),
        ("  of which zero assessments", stats["unitsWithZeroAssessments"]),
        ("Assessments total", assessments_total),
        ("  with absolute date", assessments_abs),
        ("HTTP requests / cache hits", f"{fetcher.stats.requests} / {fetcher.stats.cache_hits}"),
        ("robots.txt skips", fetcher.stats.robots_skipped),
        ("Elapsed", f"{time.time() - started:.0f}s"),
    ]
    width = max(len(r[0]) for r in rows)
    print("\n" + "\n".join(f"{k.ljust(width)}  {v}" for k, v in rows))
    for key, w in weeks.items():
        print(f"weeks {key}: confidence={w['confidence']} samples={w['samples']} week1={w.get('1')} week13={w.get('13')}")
    if fetcher.stats.skipped_urls:
        print("robots.txt disallowed:", ", ".join(fetcher.stats.skipped_urls[:20]))

    previous = read_previous_meta(data_dir)
    problems = check_thresholds(stats, partial, previous, args.force)
    if problems:
        print("\nBUILD FAILED — data/ left untouched:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="usyd-data-", dir=data_dir.parent))
    write_output(tmp_dir, units, weeks, meta)
    swap_into_place(tmp_dir, data_dir)
    print(f"\nOK — wrote {len(units)} unit files to {data_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scrape USyd unit outlines into data/")
    ap.add_argument("--codes", help="comma-separated unit codes; skips discovery")
    ap.add_argument("--year", type=int, default=config.TARGET_YEAR)
    ap.add_argument("--limit", type=int, default=0, help="stop after N unit codes")
    ap.add_argument("--also", help="comma-separated codes to include on top of discovery/--limit")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default="./data")
    ap.add_argument("--force", action="store_true", help="overwrite existing data even if the new run is much smaller")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return run(args)
    except (DiscoveryError, FetchError, BuildFailed) as exc:
        print(f"\nBUILD FAILED — data/ left untouched: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("\nBUILD FAILED — uncaught exception; data/ left untouched", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
