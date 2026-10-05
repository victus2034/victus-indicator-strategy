import pytest

import bitunix_data


@pytest.fixture(autouse=True)
def _delta_candles_in_tests(monkeypatch):
    """Live crypto candles come from Bitunix, but the suite's fakes are Delta's.

    Without this a test that mocks only Delta's endpoint would reach the real
    Bitunix API first - slow, and on a runner that can reach it, live data in
    a test. Tests of the Bitunix path set the source back themselves.
    """
    monkeypatch.setattr(bitunix_data, "CRYPTO_CANDLE_SOURCE", "delta")
