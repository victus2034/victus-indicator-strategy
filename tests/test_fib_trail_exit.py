"""The fib trailing-stop exit (config.FIB_EXIT "trail", lakky 2026-10-19)."""
import random

import fib_trendline_trades as trades
from fib_trendline_data import CRYPTO, NSE

PLAN = {"side": "long", "entry": 100.0, "sl": 98.0, "exit": "trail"}


def bars(rows, start=1):
    return [(start + i, o, h, l, c) for i, (o, h, l, c) in enumerate(rows)]


def test_new_fib_plans_trail():
    assert trades.fib_plan(1, {"entry": 100, "sl": 97})["exit"] == "trail"


def test_stop_follows_quarter_r_behind_the_best_price():
    # Fill on bar 1 (risk 2); +1.5R on bar 3 raises the stop to +1.25R = 102.5;
    # bar 4 trades down to 102 and closes the trade at 102.5 less slip.
    c = bars([(101, 101, 99.5, 100), (100.5, 100.8, 100.1, 100.5), (101, 103, 100.5, 102.5), (102.6, 102.8, 102, 102.2)])
    res = trades.simulate(PLAN, CRYPTO, "4h", 0, c)
    assert res["outcome"] == "TRAIL" and res["filled"] and res["resolved"] and res["r1"] and not res["r2"]
    want = (trades.slipped(102.5, PLAN) - 100) / 2
    assert abs(res["exit_r"] - want) < 1e-12
    net1, net2 = trades.booked_r(PLAN, CRYPTO, res)
    assert net1 == net2 and abs(net1 - (want - trades.COST_PCT[CRYPTO] / trades.risk_pct(PLAN))) < 1e-12


def test_first_stop_is_sl_and_timeout_closes_at_the_close():
    stop = trades.simulate(PLAN, CRYPTO, "4h", 0, bars([(100, 100.5, 99.8, 100), (99.5, 99.6, 97.9, 98)]))
    assert stop["outcome"] == "SL" and abs(stop["exit_r"] - trades.stop_r(PLAN)) < 1e-12
    hold = trades.EVAL_PER_BAR[NSE]["4h"] * trades.FIB_TL_MAX_HOLD_BARS
    quiet = [(100, 100.4, 99.9, 100.2)] + [(100.2, 100.4, 99.9, 100.3)] * (hold + 2)
    res = trades.simulate(PLAN, NSE, "4h", 0, bars(quiet))
    assert res["outcome"] == "timeout" and abs(res["exit_r"] - 0.15) < 1e-12


def test_open_trade_has_no_result_yet():
    res = trades.simulate(PLAN, CRYPTO, "1w", 0, bars([(101, 101, 99.9, 100.5)]))
    assert res["filled"] and not res["resolved"] and trades.booked_r(PLAN, CRYPTO, res) == (None, None)


def test_old_fib_records_keep_their_rules():
    old = {k: v for k, v in PLAN.items() if k != "exit"}
    c = bars([(101, 101, 99.5, 100), (100.5, 104.5, 100.5, 104)])
    assert trades.simulate(old, CRYPTO, "4h", 0, c)["outcome"] == "2R"
