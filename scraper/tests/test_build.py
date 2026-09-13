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


def test_relative_guard_uses_total_after_merge():
    prev = {"unitsWithCurrentOutline": 3000}
    small = _stats(unitsDiscovered=200, unitsWithCurrentOutline=177, outlineFetchAttempts=177,
                   outlineFetchFailures=0, unitsWithZeroAssessments=2)
    # a 177-unit partial run merged into 3000 existing units must not trip the guard
    assert build.check_thresholds(small, partial=True, previous=prev, force=False, total_units=3050) == []
    # but a partial run that would genuinely leave the dataset thin still does
    p = build.check_thresholds(small, partial=True, previous=prev, force=False, total_units=177)
    assert any("refusing to overwrite" in x for x in p)


def _unit(code, avail, name="n"):
    return {"code": code, "availability": avail, "name": name, "session": "S1C", "sessionLabel": "",
            "mode": "", "location": "", "assessments": []}


def test_merge_replaces_rescraped_codes_and_keeps_the_rest(tmp_path: Path):
    data = tmp_path / "data"
    build.write_output(data, [_unit("AAAA1001", "2026-S1C-ND-CC", "old"),
                              _unit("AAAA1001", "2026-S2C-ND-CC", "old"),
                              _unit("BBBB2002", "2026-S1C-ND-CC", "keep")], {}, {})
    existing = build.load_existing_units(data)
    assert len(existing) == 3
    merged = build.merge_units(existing, [_unit("AAAA1001", "2026-S1C-ND-CC", "new")], {"AAAA1001"})
    by_key = {(u["code"], u["availability"]): u["name"] for u in merged}
    assert by_key == {("AAAA1001", "2026-S1C-ND-CC"): "new", ("BBBB2002", "2026-S1C-ND-CC"): "keep"}
