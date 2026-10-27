"""Trace a few possibly-missed crypto alerts pass by pass (part discord-trace). Read-only."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import discord_alert_audit as audit   # noqa: E402

CASES = [("BTWUSD", "1d", "2026-10-23T05:00", "2026-10-23T09:30"),
         ("RLCUSD", "4h", "2026-10-26T11:00", "2026-10-26T13:00"),
         ("TSLAXUSD", "4h", "2026-10-26T12:30", "2026-10-26T14:30")]


def main():
    passes = audit.pass_times(".", datetime.fromisoformat("2026-10-21T00:00+00:00").timestamp())["crypto"]
    feed = audit.Crypto()
    for symbol, tf, a, b in CASES:
        lo = datetime.fromisoformat(a + "+00:00").timestamp()
        hi = datetime.fromisoformat(b + "+00:00").timestamp()
        print(f"\n== {symbol} {tf}")
        for p in [x for x in passes if lo <= x <= hi]:
            an, price = audit.analysis_at("crypto", symbol, tf, p, feed, passes)
            if an is None:
                print(audit.when(p), "no data")
                continue
            fibs = [(h["level"], round(h["entry"], 5), round(h["distance"], 3)) for h in an["fib"]]
            tls = [(h["kind"], round(h["level"], 5), round(h["distance"], 3), h.get("touched")) for h in an["touch"]]
            print(audit.when(p), price, "fib", fibs, "tl", tls)


if __name__ == "__main__":
    main()
