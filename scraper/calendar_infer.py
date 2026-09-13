"""Derive the teaching-week -> Monday-date map from the scraped corpus (BUILD-SPEC §6.6)."""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger("scraper.calendar_infer")

MAX_WEEK = 13
MIN_SAMPLES = 30


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def infer_session(samples: list[tuple[int, date]]) -> dict:
    """samples: (week_number, due_date) pairs for one session."""
    errors: list[str] = []
    by_week: dict[int, Counter] = defaultdict(Counter)
    over = sorted({w for w, _ in samples if w > MAX_WEEK})
    if over:
        errors.append(f"week numbers above {MAX_WEEK} appear in the data: {over}")
    for week, d in samples:
        if 1 <= week <= MAX_WEEK:
            by_week[week][_monday(d)] += 1

    observed: dict[int, date] = {}
    for week, counter in by_week.items():
        best = max(counter.items(), key=lambda kv: (kv[1], -kv[0].toordinal()))
        observed[week] = best[0]

    if len(samples) < MIN_SAMPLES:
        errors.append(f"only {len(samples)} samples (< {MIN_SAMPLES})")

    filled: dict[int, date] = dict(observed)
    known = sorted(observed)
    if known:
        # Interpolate interior gaps in 7-day steps. If the span between two known weeks
        # is one week longer than the count of steps, a mid-semester break sits inside it;
        # place the break immediately after the earlier known week.
        for lo, hi in zip(known, known[1:]):
            steps = hi - lo
            span_days = (observed[hi] - observed[lo]).days
            extra = span_days - 7 * steps
            for k in range(1, steps):
                offset = 7 * k + (extra if extra > 0 else 0)
                filled[lo + k] = observed[lo] + timedelta(days=offset)
        first, last = known[0], known[-1]
        for w in range(first - 1, 0, -1):
            filled[w] = filled[w + 1] - timedelta(days=7)
        for w in range(last + 1, MAX_WEEK + 1):
            filled[w] = filled[w - 1] + timedelta(days=7)

    gaps = []
    for w in range(1, MAX_WEEK):
        if w in filled and w + 1 in filled:
            gaps.append((filled[w + 1] - filled[w]).days)
    bad_gaps = [g for g in gaps if g not in (7, 14)]
    if bad_gaps:
        errors.append(f"consecutive weeks not 7 or 14 days apart: {sorted(set(bad_gaps))}")
    if gaps.count(14) > 1:
        errors.append(f"{gaps.count(14)} fourteen-day gaps (expected at most one, the mid-semester break)")

    out: dict = {str(w): filled[w].isoformat() for w in sorted(filled)}
    out["confidence"] = "low" if errors else "inferred"
    out["samples"] = len(samples)
    out["observedWeeks"] = sorted(observed)
    if errors:
        out["errors"] = errors
        for e in errors:
            log.error("week inference: %s", e)
    return out


def infer_weeks(units: list[dict], year: int) -> dict:
    per_session: dict[str, list[tuple[int, date]]] = defaultdict(list)
    for u in units:
        key = f"{year}-{u['session']}"
        for a in u.get("assessments", []):
            if a.get("week") is not None and a.get("dueDate"):
                try:
                    per_session[key].append((int(a["week"]), date.fromisoformat(a["dueDate"])))
                except ValueError:
                    continue
    result = {}
    for key in sorted(per_session):
        result[key] = infer_session(per_session[key])
        log.info(
            "%s: %d samples, confidence=%s, week1=%s",
            key, result[key]["samples"], result[key]["confidence"], result[key].get("1"),
        )
    return result


def apply_override(weeks: dict, override_path: Path) -> dict:
    if not override_path.exists():
        return weeks
    try:
        override = json.loads(override_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.error("weeks.override.json is not valid JSON: %s", exc)
        raise
    for key, entry in override.items():
        base = dict(weeks.get(key, {}))
        base.update({k: v for k, v in entry.items() if k not in ("confidence", "samples")})
        base["confidence"] = "override"
        base.setdefault("samples", 0)
        base.pop("errors", None)
        weeks[key] = base
        log.info("applied weeks.override.json for %s", key)
    return weeks
