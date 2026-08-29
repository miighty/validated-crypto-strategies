"""Fetch supplemental daily OHLCV for the cross-sectional residual momentum universe.

Adds ~20 additional liquid Binance spot symbols (beyond the existing 10-coin
core universe) so the cross-sectional residual-momentum test has enough
breadth to rank into terciles. Real Binance public spot klines only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import Paths, START, END_EXCLUSIVE, project_root
from crypto_regime_backtest.data import fetch_klines, validate_ohlcv

EXTRA_SYMBOLS = {
    "LTC": "LTCUSDT",
    "BCH": "BCHUSDT",
    "XLM": "XLMUSDT",
    "ETC": "ETCUSDT",
    "VET": "VETUSDT",
    "ZEC": "ZECUSDT",
    "DASH": "DASHUSDT",
    "THETA": "THETAUSDT",
    "ENJ": "ENJUSDT",
    "ZIL": "ZILUSDT",
    "BAT": "BATUSDT",
    "IOST": "IOSTUSDT",
    "ICX": "ICXUSDT",
    "ONT": "ONTUSDT",
    "NEO": "NEOUSDT",
    "QTUM": "QTUMUSDT",
    "IOTA": "IOTAUSDT",
    "TRX": "TRXUSDT",
    "ATOM": "ATOMUSDT",
    "ALGO": "ALGOUSDT",
}

# All listed on Binance spot well before 2020-01-01; use the shared repo window
# start (2018-01-01) but Binance will simply return data from actual listing.
FETCH_START = "2020-01-01T00:00:00Z"


def main() -> None:
    paths = Paths(project_root())
    paths.create()
    for coin, symbol in EXTRA_SYMBOLS.items():
        dest = paths.raw / f"{coin}_1d.csv.gz"
        if dest.exists():
            print(f"{coin}: cached, skipping")
            continue
        print(f"Fetching {coin} ({symbol}) 1d from {FETCH_START}...", flush=True)
        frame = fetch_klines(symbol, "1d", FETCH_START, END_EXCLUSIVE)
        if frame.empty:
            print(f"  WARNING: no data for {coin}")
            continue
        validate_ohlcv(frame, coin, "1d")
        frame.to_csv(dest, index=False, compression="gzip", float_format="%.10g")
        print(f"  {len(frame):,} finalized candles -> {dest}")


if __name__ == "__main__":
    main()
