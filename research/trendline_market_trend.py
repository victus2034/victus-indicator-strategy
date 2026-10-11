"""Trendline results split by market trend (Lakky, 2026-10-11).

Reads the Jun 1 - now trendline replay (out/trendline_sl/long/trades.csv) and labels
each alert by the market's daily trend on the last closed day before it:
BTC for crypto (Bitunix), NIFTY 50 for NSE (Yahoo).

  up:       close > EMA20 > EMA50
  down:     close < EMA20 < EMA50
  sideways: anything else

Also the symbol's own trend is not used here - the crypto zone filter already does
that (CRYPTO_TREND_FILTER); this asks about the whole market.

    python research/trendline_market_trend.py
"""
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT = Path(__file__).resolve().parent / "out" / "trendline_sl" / "long"
RULES = (("live", "2R+BE", None), ("touch", "1R no cap", 5.0), ("touch", "1.5R no cap", 5.0),
         ("lakky", "1R no cap", 5.0), ("lakky", "2R+BE", 5.0))


def regimes(daily):
    """[(day_open_ts, label)] for each closed daily candle."""
    df = pd.DataFrame(daily, columns=["ts", "o", "h", "l", "c"])
    e20 = df.c.ewm(span=20, adjust=False).mean()
    e50 = df.c.ewm(span=50, adjust=False).mean()
    label = ["up" if c > a > b else "down" if c < a < b else "sideways" for c, a, b in zip(df.c, e20, e50)]
    return pd.DataFrame({"ts": df.ts, "regime": label})


def btc_daily(now):
    from bitunix_compare import candles
    return [c[:5] for c in candles("bitunix", "BTCUSD", "1d", now - 600 * 86400, now)]


def nifty_daily():
    import yfinance as yf
    d = yf.download("^NSEI", period="2y", interval="1d", progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return [(int(ts.timestamp()), r.Open, r.High, r.Low, r.Close) for ts, r in d.iterrows()]


def label(trades, reg, day_seconds):
    # the last daily candle that had closed when the alert went out
    reg = reg.assign(closed=reg.ts + day_seconds).sort_values("closed")
    t = trades.sort_values("alert_ts")
    return pd.merge_asof(t, reg[["closed", "regime"]], left_on="alert_ts", right_on="closed", direction="backward")


def main():
    now = int(time.time())
    t = pd.read_csv(OUT / "trades.csv")
    parts = []
    btc = regimes(btc_daily(now))
    btc.ts = btc.ts // 1000 if btc.ts.max() > 1e11 else btc.ts
    parts.append(label(t[t.market == "crypto"], btc, 86400))
    nifty = regimes(nifty_daily())
    parts.append(label(t[t.market == "nse"], nifty, 6 * 3600 + 15 * 60))
    t = pd.concat(parts)
    # Lakky, 2026-10-11: trendline results always as two sides, 4H and 1D and above
    t["tfs"] = t.tf.map(lambda tf: "4H" if tf == "4h" else "1D+")
    rows = []
    for stop, exit_rule, cap in RULES:
        col = f"{stop}|{exit_rule}"
        for (market, tfs, regime, long), g in t.groupby(["market", "tfs", "regime", "long"]):
            if cap:
                g = g[g[f"risk_{stop}"] <= cap]
            r = g[col].dropna()
            if r.empty:
                continue
            pct = (g[col] * g[f"risk_{stop}"]).dropna()
            rows.append({"rule": f"{stop} SL, {exit_rule}", "market": market, "tf": tfs, "market trend": regime,
                         "side": "BUY" if long else "SELL", "trades": len(r),
                         "wins_%": round(100 * (r > 0.05).mean()), "R_per_trade": round(r.mean(), 3),
                         "%_per_trade": round(pct.mean(), 3), "net_R": round(r.sum(), 1)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "market_trend.csv", index=False)
    text = ["# Trendline results by market trend, Jun 1 to now", "",
            "Market trend on the last closed day before the alert: BTC (crypto), NIFTY 50 (NSE). "
            "up = close > EMA20 > EMA50, down = close < EMA20 < EMA50, else sideways. "
            "Touch rules count stops up to 5% only.", "",
            df.to_markdown(index=False), "",
            "## Days per trend", "",
            t.groupby(["market", "tfs", "regime"]).size().rename("alerts").to_frame().to_markdown(), ""]
    (OUT / "MARKET_TREND.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
