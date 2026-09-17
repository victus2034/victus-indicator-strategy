import unittest
from unittest.mock import patch

import nse_config
import nse_scanner


def make_csv(symbols):
    header = "Symbol,Industry\n"
    rows = "\n".join(f"{s},Financial Services" for s in symbols)
    return header + rows


class FakeResponse:
    def __init__(self, text, ok=True):
        self.text = text
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("CSV fetch failed")


class LoadWatchlistTests(unittest.TestCase):
    def test_live_csv_is_sliced_to_the_rank_window(self):
        # Alphabetical order in the CSV, deliberately not rank order - the
        # sort against NSE_MARKET_CAP_RANK is what should decide the cut.
        symbols = list(nse_config.NSE_MARKET_CAP_RANK[:50])
        csv_text = make_csv(sorted(symbols))
        with patch.object(
            nse_scanner.requests, "get", return_value=FakeResponse(csv_text)
        ):
            with patch.object(nse_scanner, "NSE_RANK_START", 10):
                with patch.object(nse_scanner, "NSE_RANK_END", 20):
                    result = nse_scanner.load_watchlist()

        self.assertEqual(result, nse_config.NSE_MARKET_CAP_RANK[10:20])

    def test_a_failed_fetch_falls_back_to_the_same_rank_window(self):
        # FALLBACK_WATCHLIST only covers rank ~1-100 - it must not be
        # returned unsliced once the live path's job is to skip rank 1-100.
        # NSE_MARKET_CAP_RANK[100:300] is what the live path would have
        # produced too, so this is what a CSV outage should fall back to.
        with patch.object(
            nse_scanner.requests, "get", side_effect=RuntimeError("network down")
        ):
            result = nse_scanner.load_watchlist()

        expected = nse_config.NSE_MARKET_CAP_RANK[
            nse_config.NSE_RANK_START : nse_config.NSE_RANK_END
        ]
        self.assertEqual(result, expected)
        # The specific regression: none of the top-100 fallback names leak
        # through when the live fetch fails.
        top_100 = set(nse_config.NSE_MARKET_CAP_RANK[:100])
        self.assertFalse(top_100 & set(result))

    def test_a_short_csv_also_falls_back_to_the_rank_window(self):
        with patch.object(
            nse_scanner.requests,
            "get",
            return_value=FakeResponse(make_csv(["RELIANCE"])),
        ):
            result = nse_scanner.load_watchlist()

        expected = nse_config.NSE_MARKET_CAP_RANK[
            nse_config.NSE_RANK_START : nse_config.NSE_RANK_END
        ]
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
