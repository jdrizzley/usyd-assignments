"""Parser tests against a real saved copy of the AMME2200 S2 2026 outline (BUILD-SPEC §6.5)."""
import json
from pathlib import Path

import pytest

from scraper.outline import parse_due, parse_outline, parse_weight

FIXTURES = Path(__file__).parent / "fixtures"
META = {
    "code": "AMME2200",
    "availability": "2026-S2C-ND-CC",
    "session": "S2C",
    "mode": "Normal day",
    "location": "Camperdown/Darlington, Sydney",
    "sessionLabel": "Semester 2, 2026",
    "sourceUrl": "https://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC",
}


@pytest.fixture(scope="module")
def unit():
    html = (FIXTURES / "outline_amme2200_2026s2.html").read_text(encoding="utf-8")
    return parse_outline(html, META)


def test_eight_assessments(unit):
    assert len(unit["assessments"]) == 8
    assert unit["parseWarnings"] == []


def test_unit_metadata(unit):
    assert unit["code"] == "AMME2200"
    assert unit["name"] == "Introductory Thermofluids"
    assert unit["sessionLabel"] == "Semester 2, 2026"
    assert unit["mode"] == "Normal day"
    assert unit["location"] == "Camperdown/Darlington, Sydney"
    assert unit["censusDate"] == "2026-08-31"
    assert unit["sourceUrl"].endswith("/units/AMME2200/2026-S2C-ND-CC")


def test_final_exam_is_exam_period(unit):
    exam = next(a for a in unit["assessments"] if a["name"] == "Final exam")
    assert exam["dateKind"] == "exam_period"
    assert exam["dueDate"] is None
    assert exam["weight"] == 50
    assert exam["dueRaw"] == "Formal exam period"
    assert exam["type"] == "Written exam"
    assert exam["description"] == "Open book exam."


def test_preliminary_assessment(unit):
    prelim = next(a for a in unit["assessments"] if a["name"] == "Preliminary Assessment")
    assert prelim["week"] == 3
    assert prelim["dateKind"] == "absolute"
    assert prelim["dueDate"] == "2026-08-17"
    assert prelim["dueTime"] == "23:00"
    assert prelim["timeAssumed"] is False
    assert prelim["closingDate"] == "2026-11-06"
    assert prelim["earlyFeedback"] is True
    assert prelim["weight"] == 2
    assert prelim["type"] == "Practical skill"


def test_only_one_early_feedback(unit):
    assert sum(a["earlyFeedback"] for a in unit["assessments"]) == 1


def test_weights_sum_to_100(unit):
    assert sum(a["weight"] for a in unit["assessments"]) == 100


def test_typo_preserved_verbatim(unit):
    names = [a["name"] for a in unit["assessments"]]
    assert "Assignment-Theromdynamics" in names


def test_ids_are_stable(unit):
    ids = [a["id"] for a in unit["assessments"]]
    assert ids == [f"AMME2200-2026-S2C-ND-CC-{i}" for i in range(8)]


def test_all_rows_have_expected_fields(unit):
    keys = {
        "id", "name", "description", "type", "weight", "weightRaw", "week", "dateKind",
        "dueDate", "dueTime", "timeAssumed", "closingDate", "length", "aiPolicy",
        "earlyFeedback", "dueRaw",
    }
    for a in unit["assessments"]:
        assert set(a) == keys
        assert a["dateKind"] in ("absolute", "week_only", "exam_period", "unparsed")
        assert a["aiPolicy"] in ("AI allowed", "AI prohibited")


def test_no_staff_email_stored(unit):
    assert "@" not in json.dumps(unit)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Week 03 Due date: 17 Aug 2026 at 23:00 Closing date: 06 Nov 2026",
         dict(week=3, dateKind="absolute", dueDate="2026-08-17", dueTime="23:00", timeAssumed=False, closingDate="2026-11-06")),
        ("Week 05 Due date : 04 Sep 2026 at 11:00 Closing date : 04 Sep 2026",
         dict(week=5, dateKind="absolute", dueDate="2026-09-04", dueTime="11:00", timeAssumed=False)),
        ("Week 07 Due date: 20 Sep 2026",
         dict(week=7, dateKind="absolute", dueDate="2026-09-20", dueTime="23:59", timeAssumed=True)),
        ("Formal exam period", dict(week=None, dateKind="exam_period", dueDate=None)),
        ("Week 08", dict(week=8, dateKind="week_only", dueDate=None)),
        ("Week 08 Closing date: 01 Nov 2026", dict(week=8, dateKind="week_only", closingDate="2026-11-01")),
        ("Multiple weeks", dict(week=None, dateKind="unparsed", dueRaw="Multiple weeks")),
        ("Ongoing", dict(dateKind="unparsed")),
        ("Week 01 to Week 13", dict(dateKind="unparsed", week=1)),
        ("Due date: 5 Sept 2026 at 9:05", dict(dateKind="absolute", dueDate="2026-09-05", dueTime="09:05")),
    ],
)
def test_parse_due_variants(raw, expected):
    got = parse_due(raw)
    for k, v in expected.items():
        assert got[k] == v, (k, got)


def test_parse_weight():
    assert parse_weight("6%") == (6, "6%")
    assert parse_weight("12.5 %") == (12.5, "12.5 %")
    assert parse_weight("0%") == (0, "0%")
    assert parse_weight("Pass/Fail") == (None, "Pass/Fail")


def test_no_table_returns_zero_assessments():
    unit = parse_outline("<html><body><h1>ABCD1234: Nothing</h1></body></html>", META)
    assert unit["assessments"] == []
    assert any("table" in w for w in unit["parseWarnings"])
