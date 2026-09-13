from pathlib import Path

from scraper.availability import normalise_session_label, parse_availabilities

FIXTURES = Path(__file__).parent / "fixtures"


def test_amme2200_has_exactly_one_2026_availability():
    html = (FIXTURES / "unit_amme2200.html").read_text(encoding="utf-8")
    avail = parse_availabilities(html, "AMME2200", 2026)
    assert len(avail) == 1
    a = avail[0]
    assert a["availability"] == "2026-S2C-ND-CC"
    assert a["session"] == "S2C"
    assert a["mode"] == "Normal day"
    assert a["location"] == "Camperdown/Darlington, Sydney"
    assert a["sessionLabel"] == "Semester 2, 2026"
    assert a["outlineUrl"] == "https://www.sydney.edu.au/units/AMME2200/2026-S2C-ND-CC"


def test_previous_years_are_filtered_out():
    html = (FIXTURES / "unit_amme2200.html").read_text(encoding="utf-8")
    assert [a["availability"] for a in parse_availabilities(html, "AMME2200", 2022)] == [
        "2022-S2C-ND-CC",
        "2022-S2C-ND-RE",
    ]
    assert parse_availabilities(html, "AMME2200", 2019) == []


def test_normalise_session_label():
    assert normalise_session_label("Semester 2 2026") == "Semester 2, 2026"
    assert normalise_session_label("Semester 2, 2026") == "Semester 2, 2026"
    assert normalise_session_label("Intensive January 2026") == "Intensive January, 2026"
