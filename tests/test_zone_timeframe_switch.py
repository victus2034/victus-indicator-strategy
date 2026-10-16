"""30m zone alerts are off (lakky, 2026-10-16): a scanner on a timeframe missing from
ZONE_ALERT_TIMEFRAMES exits before it loads state or scans, and ends the scan loop."""
import sys

import config
import nse_scanner
import scanner


def test_default_is_4h_only():
    assert config.ZONE_ALERT_TIMEFRAMES == ["4h"]
    assert config.zone_timeframe_enabled("4h")
    assert not config.zone_timeframe_enabled("30m")


def _boom(*_a, **_k):
    raise AssertionError("scanned a timeframe that is off")


def test_crypto_30m_exits_without_scanning(monkeypatch, tmp_path):
    stop = tmp_path / "stop"
    monkeypatch.setenv("SCAN_LOOP_STOP_FILE", str(stop))
    monkeypatch.setattr(scanner, "TIMEFRAME", "30m")
    monkeypatch.setattr(scanner, "load_state", _boom)
    monkeypatch.setattr(scanner, "run_scan_once", _boom)
    monkeypatch.setattr(sys, "argv", ["scanner.py", "--once"])
    scanner.main()
    assert stop.exists()


def test_nse_30m_exits_without_scanning(monkeypatch, tmp_path):
    stop = tmp_path / "stop"
    monkeypatch.setenv("SCAN_LOOP_STOP_FILE", str(stop))
    monkeypatch.setattr(nse_scanner, "TIMEFRAME", "30m")
    monkeypatch.setattr(nse_scanner, "load_state", _boom)
    monkeypatch.setattr(nse_scanner, "run_scan_once", _boom)
    monkeypatch.setattr(sys, "argv", ["nse_scanner.py", "--once"])
    nse_scanner.main()
    assert stop.exists()


def test_4h_still_scans(monkeypatch):
    ran = []
    monkeypatch.setattr(scanner, "TIMEFRAME", "4h")
    monkeypatch.setattr(scanner, "load_state", lambda: {})
    monkeypatch.setattr(scanner, "run_scan_once", lambda state: ran.append(1))
    monkeypatch.setattr(sys, "argv", ["scanner.py", "--once"])
    scanner.main()
    assert ran == [1]
