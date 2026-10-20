"""L1 / L2 / L4 what-ifs of a fib alert (lakky, 2026-10-19): same stop, the level's own band moment."""
import fib_level_whatif as flw

H = 3600
T0 = 1_790_000_000


def c(i, high, low):
    return [T0 + i * H, 0, high, low, 0]


# A buy fib: base 100 (origin), top 110. L1 106.6, L2 105.5, L3 104.5, L4 103.4; stop 103.125.
RECORD = {"id": "x@1", "key": "fib|XUSD|4h|1|%d|110|2" % T0, "kind": "fib", "market": "crypto", "tf": "4h",
          "symbol": "XUSD", "plan": {"side": "long", "entry": 104.5, "sl": 103.125}, "sent_ts": T0 + 7 * H}
CANDLES = [c(0, 101, 100), c(1, 105, 101), c(2, 108, 104.8), c(3, 110, 107.5),     # up to the top
           c(4, 109, 106.9),                       # inside L1's band, not at it yet
           c(5, 107, 106.5),                       # L1 fills
           c(6, 106, 105.4),                       # L2 fills
           c(7, 105, 104.6), c(8, 104.7, 104.4),   # the real alert, then L3 fills
           c(9, 104.0, 103.3),                     # L4 fills, stop (103.125) holds
           c(10, 104.0, 103.5),                    # L4 +2R = 103.95
           ]


def test_levels_come_back_from_the_key_and_entry():
    _, top, lv = flw.geometry(RECORD)
    assert top == 110
    assert {k: round(v, 6) for k, v in lv.items()} == {"L1": 106.6, "L2": 105.5, "L3": 104.5, "L4": 103.4}


def test_levels_match_the_scanners_own_on_a_live_record():
    xaut = {"kind": "fib", "key": "fib|XAUTUSD|4h|1|1791374400|4215.9|2", "plan": {"entry": 4142.134}}
    want = {"L1": 4170.2991999999995, "L2": 4155.546, "L3": 4142.134, "L4": 4127.3808}
    _, _, lv = flw.geometry(xaut)
    for k, v in want.items():
        assert abs(lv[k] - v) < 1e-6


def test_each_level_is_scored_from_its_own_band_with_the_alerts_stop():
    out = flw.score_record(RECORD, CANDLES, now=T0 + 11 * H)
    assert out["L1"]["filled"] and out["L1"]["alert_ts"] == T0 + 4 * H - 1
    assert out["L2"]["filled"] and out["L2"]["fill_ts"] == T0 + 6 * H
    assert out["L4"]["outcome"] == "2R" and out["L4"]["fill_ts"] == T0 + 9 * H
    assert out["L1"]["outcome"] == "open" and not out["L1"]["resolved"]   # still running
    assert "L3" not in out                       # the real alert is scored as before


def test_a_level_never_reached_gives_up_after_the_trades_time():
    early = CANDLES[:8]                          # price never got near L4
    out = flw.score_record(RECORD, early, now=T0 + 8 * H)
    assert out["L4"]["outcome"] == "open" and not out["L4"]["resolved"]
    out = flw.score_record(RECORD, early, now=RECORD["sent_ts"] + 26 * 4 * H)
    assert out["L4"]["outcome"] == "not reached" and out["L4"]["resolved"]


def test_a_top_missing_from_the_candles_scores_nothing():
    wrong = [c(i, h * 0.9, l * 0.9) for i, (_t, _o, h, l, _c) in enumerate(CANDLES)]
    out = flw.score_record(RECORD, wrong, now=T0 + 11 * H)
    assert all(out[k]["outcome"] == "open" and out[k]["alert_ts"] is None for k in flw.WHAT_IF)


def test_resolved_levels_are_not_scored_again(monkeypatch):
    done = {k: {"resolved": True, "outcome": "SL"} for k in flw.WHAT_IF}
    results = flw.score_levels([RECORD], {"x@1": done}, T0, fetch=lambda *a: (_ for _ in ()).throw(AssertionError))
    assert results["x@1"] == done


def test_non_fib_records_are_left_alone():
    tl = dict(RECORD, kind="trendline", key="tl|X|4h|1|1|2")
    assert flw.geometry(tl) is None
    assert flw.score_levels([tl], {}, T0, fetch=lambda *a: []) == {}


def test_a_level_alert_is_not_given_what_ifs():
    # 2026-10-20: L1/L2/L4 alert on their own (key ends |Lx), so they have no L1/L2/L4 what-ifs
    assert flw.geometry(dict(RECORD, key=RECORD["key"] + "|L4")) is None
