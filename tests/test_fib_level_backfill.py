"""Backfill of L1-L4 labels on fib alerts saved before the scanner wrote them (lakky, 2026-10-19)."""
import importlib.util
import json
from pathlib import Path

import fib_trendline_scanner as fts

SPEC = importlib.util.spec_from_file_location(
    "fib_level_backfill", Path(__file__).resolve().parents[1] / "research" / "fib_level_backfill.py")
backfill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backfill)

# A live record as the scanner saved it on 2026-10-17 (AAVE 1D buy fib).
NEW = {"market": "crypto", "symbol": "AAVEUSD", "tf": "1d", "price": 148.5, "kind": "fib",
       "plan": {"side": "long", "entry": 146.719, "sl": 136.48625}, "zone": 2, "base": 113.23, "top": 187.65,
       "levels": {"L1": 162.34720000000002, "L2": 154.161, "L3": 146.719, "L4": 138.5328},
       "id": "fib|AAVEUSD|1d|1|1789516800|187.65|2@1792418622", "key": "fib|AAVEUSD|1d|1|1789516800|187.65|2",
       "sent_ts": 1792418622}


def old(record):
    """The same alert as a pre-Oct 12 record: plan only."""
    return {k: v for k, v in record.items() if k not in ("base", "top", "levels")}


def test_an_old_record_gets_the_levels_the_scanner_would_have_saved():
    rec = old(NEW)
    assert backfill.label(rec)
    assert rec["level"] == "L3"
    assert abs(rec["base"] - 113.23) < 1e-6 and rec["top"] == 187.65
    for k, v in NEW["levels"].items():
        assert abs(rec["levels"][k] - v) < 1e-6
    want = fts.fib_levels(1, 113.23, 187.65)
    assert all(abs(rec["levels"][k] - want[k]) < 1e-6 for k in want)


def test_a_sell_fib_mirrors():
    # Sell fib: origin high 200, top (low) 100. L1 = 134, L3 = 155, L4 = 166.
    rec = {"kind": "fib", "id": "s@1", "key": "fib|X|4h|-1|1|100|2", "plan": {"side": "short", "entry": 155.0, "sl": 168.75}}
    backfill.label(rec)
    want = fts.fib_levels(-1, 200, 100)
    assert abs(rec["base"] - 200) < 1e-9
    assert all(abs(rec["levels"][k] - want[k]) < 1e-9 for k in want)


def test_a_labelled_record_only_gains_its_entry_level():
    rec = dict(NEW)
    assert backfill.label(rec)
    assert rec["levels"] is NEW["levels"] and rec["level"] == "L3"
    assert not backfill.label(rec)


def test_trendlines_are_left_alone():
    tl = {"kind": "trendline", "id": "t@1", "key": "tl|X|4h|1|1|2", "plan": {"side": "long", "entry": 1, "sl": 0.9}}
    assert not backfill.label(tl) and "levels" not in tl


def test_derived_levels_match_saved_ones():
    assert backfill.check_geometry([NEW]) < 1e-9


def test_apply_rewrites_only_october_fibs_and_keeps_a_backup(tmp_path, monkeypatch):
    sept = dict(old(NEW), id="fib|A|1d|1|1|187.65|2@1790000000", key="fib|A|1d|1|1|187.65|2", sent_ts=1_790_000_000)
    octo = old(NEW)
    tl = {"kind": "trendline", "id": "t@1", "key": "tl", "sent_ts": 1_792_000_000, "market": "crypto", "tf": "4h",
          "plan": {"side": "long", "entry": 1, "sl": 0.9}}
    lines = [json.dumps(sept), json.dumps(octo), json.dumps(tl)]
    (tmp_path / backfill.RECORDS).write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(backfill.whatif, "score_levels", lambda recs, res, now, fetch: {r["id"]: {} for r in recs})
    monkeypatch.setattr(backfill, "OUT", tmp_path / "out")
    monkeypatch.setattr("sys.argv", ["x", "--state", str(tmp_path), "--apply"])
    backfill.main()
    out = (tmp_path / backfill.RECORDS).read_text().splitlines()
    assert out[0] == lines[0] and out[2] == lines[2]          # September and trendlines untouched
    assert json.loads(out[1])["level"] == "L3" and "levels" in json.loads(out[1])
    assert (tmp_path / backfill.BACKUP).read_text().splitlines() == lines
    assert json.loads((tmp_path / backfill.LEVELS).read_text()) == {octo["id"]: {}}


def test_a_fill_beside_a_cpi_release_is_flagged():
    cpi = backfill._ny("2026-10-14", "08:30")
    assert backfill.near_news({"filled": True, "fill_ts": cpi - 300}, "4h", "crypto")
    assert not backfill.near_news({"filled": True, "fill_ts": cpi + 3600}, "4h", "crypto")
