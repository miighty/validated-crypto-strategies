"""Fetch real Coinbase Exchange hourly OHLCV for BTC-USD and ETH-USD.

Used to compute a Coinbase-vs-Binance price premium (a real, widely-cited
institutional order-flow indicator -- "Coinbase Premium Index", popularized by
CryptoQuant -- never used in this repo before). This script only fetches and
caches real data; no synthetic/proxy data is generated.

Coinbase Exchange public REST API: GET /products/{id}/candles
Max 300 candles per request at granularity=3600 (1h). We paginate backwards
from EFFECTIVE END to the start of the Binance-cached window (2018-01-01) so
the premium can be computed on the exact same aligned hourly grid already
used throughout this repo.
"""
from __future__ import annotations

import gzip
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import Paths, project_root

ROOT = project_root()
PATHS = Paths(ROOT)

BASE = "https://api.exchange.coinbase.com"
PRODUCTS = {"BTC": "BTC-USD", "ETH": "ETH-USD"}
GRANULARITY = 3600  # 1h
MAX_CANDLES = 300
START = datetime(2018, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 7, 28, tzinfo=timezone.utc)  # exclusive, matches repo pin


def fetch_symbol(product_id: str) -> pd.DataFrame:
    rows = []
    window = timedelta(seconds=GRANULARITY * MAX_CANDLES)
    cursor_end = END
    session = requests.Session()
    session.headers.update({"User-Agent": "validated-crypto-strategies-research/1.0"})
    n_req = 0
    while cursor_end > START:
        cursor_start = max(START, cursor_end - window)
        params = {
            "granularity": GRANULARITY,
            "start": cursor_start.isoformat(),
            "end": cursor_end.isoformat(),
        }
        resp = None
        for attempt in range(5):
            resp = session.get(f"{BASE}/products/{product_id}/candles", params=params, timeout=20)
            if resp.status_code == 200:
                break
            time.sleep(1.0 + attempt)
        if resp is None or resp.status_code != 200:
            status = resp.status_code if resp is not None else "no response"
            text = resp.text[:200] if resp is not None else ""
            raise RuntimeError(f"Failed to fetch {product_id} window {cursor_start}-{cursor_end}: {status} {text}")
        data = resp.json()
        if isinstance(data, dict) and data.get("message"):
            raise RuntimeError(f"Coinbase API error for {product_id}: {data}")
        for row in data:
            # [time, low, high, open, close, volume]
            rows.append({
                "timestamp": datetime.fromtimestamp(row[0], tz=timezone.utc),
                "open": row[3], "high": row[2], "low": row[1], "close": row[4], "volume": row[5],
            })
        n_req += 1
        cursor_end = cursor_start
        time.sleep(0.35)  # stay well under Coinbase's public rate limit (~10 req/s, be conservative)
        if n_req % 50 == 0:
            print(f"  {product_id}: {n_req} requests, cursor now at {cursor_end.isoformat()}, rows so far {len(rows)}")

    df = pd.DataFrame(rows).drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    df = df[(df["timestamp"] >= START) & (df["timestamp"] < END)]
    return df


def main() -> None:
    out_dir = ROOT / "data" / "coinbase_premium"
    out_dir.mkdir(parents=True, exist_ok=True)
    for coin, product_id in PRODUCTS.items():
        print(f"Fetching {product_id} hourly candles from Coinbase Exchange ({START.date()} -> {END.date()})...")
        df = fetch_symbol(product_id)
        print(f"  {coin}: {len(df)} rows, {df['timestamp'].min()} -> {df['timestamp'].max()}")
        out_path = out_dir / f"{coin}_coinbase_1h.csv.gz"
        with gzip.open(out_path, "wt") as f:
            df.to_csv(f, index=False)
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
