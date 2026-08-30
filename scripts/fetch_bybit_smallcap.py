"""Fetch real Bybit spot daily OHLCV for the 42/54 coins from the small/mid-cap
Amihud universe (EXP-2026-08-30-AMIHUD-SMALLCAP-001) that are actually listed
on Bybit spot USDT markets. Cross-exchange replication data source.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import ccxt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crypto_regime_backtest.config import Paths, project_root

ROOT = project_root()
PATHS = Paths(ROOT)
OUT_DIR = ROOT / "data" / "bybit_raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE = [
    "1INCH", "APE", "APT", "AR", "AXS", "BONK", "CHZ", "COMP", "CRV", "EGLD",
    "EIGEN", "ENS", "ETHFI", "FET", "FLOKI", "GRT", "IMX", "INJ", "JASMY",
    "JTO", "KAIA", "KMNO", "LDO", "LUNC", "MANA", "OP", "PENDLE", "PYTH",
    "RUNE", "S", "SAND", "SEI", "SNX", "STRK", "STX", "THETA", "TIA", "TWT",
    "VIRTUAL", "WIF", "XTZ", "ZRO",
]

SINCE = "2017-01-01T00:00:00Z"


def fetch_all_ohlcv(exchange, symbol: str, since_iso: str, timeframe="1d") -> list:
    since = exchange.parse8601(since_iso)
    all_rows = []
    retries = 0
    while True:
        try:
            batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        except Exception as e:
            retries += 1
            if retries >= 3:
                print(f"  {symbol}: FAILED after 3 retries: {e}")
                return all_rows
            time.sleep(2)
            continue
        if not batch:
            break
        all_rows.extend(batch)
        last_ts = batch[-1][0]
        if last_ts <= since:
            break
        since = last_ts + 1
        if len(batch) < 1000:
            break
        time.sleep(exchange.rateLimit / 1000.0)
    return all_rows


def main() -> None:
    ex = ccxt.bybit({"enableRateLimit": True})
    ex.load_markets()
    log_lines = []
    for coin in UNIVERSE:
        sym = f"{coin}/USDT"
        if sym not in ex.markets or not ex.markets[sym]["spot"]:
            log_lines.append(f"{coin}: SKIPPED not listed spot")
            continue
        rows = fetch_all_ohlcv(ex, sym, SINCE)
        if not rows:
            log_lines.append(f"{coin}: FAILED no data")
            continue
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
        if len(df) < 300:
            log_lines.append(f"{coin}: too short ({len(df)} rows)")
            continue
        out_path = OUT_DIR / f"{coin}_1d.csv.gz"
        df.to_csv(out_path, index=False, compression="gzip")
        log_lines.append(f"{coin}: {len(df)} rows -> {out_path.name}")
        print(log_lines[-1])
    with open("/tmp/fetch_bybit_smallcap.log", "w") as f:
        f.write("\n".join(log_lines))
    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
