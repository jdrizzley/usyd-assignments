from datetime import date, timedelta

from scraper.calendar_infer import infer_session


def _samples(week1: date, break_after: int, weeks=range(1, 14), per_week=4):
    out = []
    for w in weeks:
        monday = week1 + timedelta(days=7 * (w - 1) + (7 if w > break_after else 0))
        for i in range(per_week):
            out.append((w, monday + timedelta(days=i % 5)))
    # one noisy outlier that must lose the vote
    out.append((5, week1 + timedelta(days=60)))
    return out


def test_infers_all_weeks_with_one_break():
    week1 = date(2026, 8, 3)
    res = infer_session(_samples(week1, break_after=7))
    assert res["confidence"] == "inferred"
    assert res["1"] == "2026-08-03"
    assert res["7"] == "2026-09-14"
    assert res["8"] == "2026-09-28"  # after the two-week break
    assert res["13"] == "2026-11-02"
    assert res["samples"] > 30


def test_gaps_are_interpolated_and_extrapolated():
    week1 = date(2026, 2, 23)
    res = infer_session(_samples(week1, break_after=7, weeks=[3, 5, 9, 11], per_week=10))
    assert res["1"] == "2026-02-23"
    assert res["4"] == "2026-03-16"
    assert res["13"] == "2026-05-25"


def test_low_confidence_when_sparse_or_odd():
    res = infer_session([(1, date(2026, 8, 3)), (2, date(2026, 8, 14))])
    assert res["confidence"] == "low"
    assert any("samples" in e for e in res["errors"])
