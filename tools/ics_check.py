"""Structural check of an .ics file against RFC 5545 basics. Usage: python tools/ics_check.py file.ics

Checks: CRLF line endings, no physical line over 75 octets, balanced BEGIN/END, required
calendar and event properties, VTIMEZONE present when TZID is referenced, unique UIDs.
Optionally parses with the `icalendar` package if it is installed.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


def check(path: Path) -> list[str]:
    raw = path.read_bytes()
    problems: list[str] = []
    if b"\r\n" not in raw:
        problems.append("no CRLF line endings found")
    if re.search(rb"(?<!\r)\n", raw):
        problems.append("bare LF line ending found")
    lines = raw.split(b"\r\n")
    for i, line in enumerate(lines, 1):
        if len(line) > 75:
            problems.append(f"line {i} is {len(line)} octets (> 75)")
    # unfold
    text = raw.decode("utf-8").replace("\r\n ", "").replace("\r\n\t", "")
    logical = [l for l in text.split("\r\n") if l]
    stack: list[str] = []
    uids = Counter()
    events = 0
    tzids_used = set()
    tz_defined = set()
    for l in logical:
        name, _, value = l.partition(":")
        if name == "BEGIN":
            stack.append(value)
            if value == "VEVENT":
                events += 1
        elif name == "END":
            if not stack or stack[-1] != value:
                problems.append(f"unbalanced END:{value}")
            else:
                stack.pop()
        elif name.startswith("UID"):
            uids[value] += 1
        elif name == "TZID":
            tz_defined.add(value)
        m = re.match(r"^(DTSTART|DTEND);TZID=([^:;]+)", l)
        if m:
            tzids_used.add(m.group(2))
    if stack:
        problems.append(f"unterminated components: {stack}")
    for req in ("BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:", "END:VCALENDAR"):
        if not any(l.startswith(req) for l in logical):
            problems.append(f"missing {req}")
    for tz in tzids_used - tz_defined:
        problems.append(f"TZID {tz} referenced but no VTIMEZONE defines it")
    for uid, n in uids.items():
        if n > 1:
            problems.append(f"duplicate UID {uid}")
    # per-event required properties
    ev: dict | None = None
    for l in logical:
        if l == "BEGIN:VEVENT":
            ev = {}
        elif l == "END:VEVENT" and ev is not None:
            for k in ("UID", "DTSTAMP", "DTSTART", "SUMMARY"):
                if k not in ev:
                    problems.append(f"event missing {k}: {ev.get('SUMMARY', '?')}")
            ev = None
        elif ev is not None:
            ev[l.split(":", 1)[0].split(";", 1)[0]] = l
    try:
        import icalendar  # type: ignore

        cal = icalendar.Calendar.from_ical(raw)
        n = sum(1 for c in cal.walk("VEVENT"))
        if n != events:
            problems.append(f"icalendar parsed {n} events, expected {events}")
        for e in cal.walk("VEVENT"):
            _ = e.decoded("DTSTART")
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"icalendar failed to parse: {exc}")
    print(f"{path}: {events} events, {len(logical)} logical lines, {len(lines)} physical lines")
    return problems


if __name__ == "__main__":
    p = Path(sys.argv[1])
    probs = check(p)
    for x in probs:
        print("PROBLEM:", x)
    print("OK" if not probs else f"{len(probs)} problem(s)")
    sys.exit(1 if probs else 0)
