import json
from pathlib import Path

from scraper import build


def _stats(**kw):
    base = dict(unitsDiscovered=7000, unitsWithCurrentOutline=3000, outlineFetchAttempts=3200,
                outlineFetchFailures=10, unitsWithZeroAssessments=50)
    base.update(kw)
    return base


def test_thresholds_pass_on_healthy_full_run():
    assert build.check_thresholds(_stats(), partial=False, previous=None, force=False) == []


def test_thresholds_catch_structure_changes():
    p = build.check_thresholds(_stats(unitsDiscovered=100), partial=False, previous=None, force=False)
    assert any("codes discovered" in x for x in p)
    p = build.check_thresholds(_stats(unitsWithZeroAssessments=2000), partial=False, previous=None, force=False)
    assert any("zero assessments" in x for x in p)
    p = build.check_thresholds(_stats(outlineFetchFailures=1000), partial=False, previous=None, force=False)
    assert any("fetches failed" in x for x in p)


def test_partial_run_skips_absolute_minimums_but_keeps_ratios():
    assert build.check_thresholds(_stats(unitsDiscovered=4, unitsWithCurrentOutline=4, outlineFetchAttempts=4,
                                         outlineFetchFailures=0, unitsWithZeroAssessments=0),
                                  partial=True, previous=None, force=False) == []
    p = build.check_thresholds(_stats(unitsDiscovered=4, unitsWithCurrentOutline=4, outlineFetchAttempts=4,
                                      outlineFetchFailures=0, unitsWithZeroAssessments=4),
                               partial=True, previous=None, force=False)
    assert p


def test_refuses_to_shrink_existing_data_unless_forced():
    prev = {"unitsWithCurrentOutline": 3000}
    p = build.check_thresholds(_stats(unitsWithCurrentOutline=900), partial=False, previous=prev, force=False)
    assert any("refusing to overwrite" in x for x in p)
    assert build.check_thresholds(_stats(unitsWithCurrentOutline=900), partial=False, previous=prev, force=True) == []


def test_swap_preserves_override_and_replaces_old(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "index.json").write_text("[]")
    (data / "weeks.override.json").write_text('{"x": 1}')
    new = tmp_path / "new"
    new.mkdir()
    (new / "index.json").write_text('[{"a":1}]')
    build.swap_into_place(new, data)
    assert json.loads((data / "index.json").read_text()) == [{"a": 1}]
    assert (data / "weeks.override.json").read_text() == '{"x": 1}'
    assert not new.exists()
    assert not (tmp_path / "data.previous").exists()
