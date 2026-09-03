"""Fetch real Binance spot hourly klines including the taker-buy-base-volume
field for BTC/ETH/SOL/XRP, full available history matching the repo's
existing cached OHLCV range. This is a genuinely new real data field for this
repo: every prior study used OHLCV (open/high/low/close/volume) or funding/OI
data, never the taker buy/sell trade-flow split that Binance's standard
klines endpoint already discloses (field index 9 = taker_buy_base_asset_volume,
out of total base volume in field index 5). No proxy/synthetic order flow --
this is the exchange's own aggressor-side trade classification.

Cached to data/taker_flow/{ASSET}_taker_flow_1h.csv.gz
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crypto_regime_backtest.config import project_root

ROOT = project_root()
OUT_DIR = ROOT / "data" / "taker_flow"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT"}
START = {"BTC": "2018-01-01", "ETH": "2018-01-01", "SOL": "2020-08-11", "XRP": "2018-05-04"}
END_MS = int(pd.Timestamp("2026-07-28", tz="UTC").timestamp() * 1000)

BASE_URL = "https://api.binance.com/api/v3/klines"


def fetch_symbol(symbol: str, start_ms: int, end_ms: int) -> list[list]:
    all_rows = []
    since = start_ms
    while since < end_ms:
        params = {"symbol": symbol, "interval": "1h", "startTime": since, "limit": 1000}
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_rows.extend(batch)
        new_since = batch[-1][0] + 1
        if new_since <= since:
            break
        since = new_since
        if len(batch) < 1000:
            break
        time.sleep(0.15)
    return all_rows


def main():
    for coin, symbol in ASSETS.items():
        out_path = OUT_DIR / f"{coin}_taker_flow_1h.csv.gz"
        start_ms = int(pd.Timestamp(START[coin], tz="UTC").timestamp() * 1000)
        print(f"Fetching {coin} ({symbol}) from {START[coin]}...")
        rows = fetch_symbol(symbol, start_ms, END_MS)
        df = pd.DataFrame(rows, columns=[
            "open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "n_trades", "taker_buy_base_volume", "taker_buy_quote_volume", "ignore",
        ])
        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for col in ["open", "high", "low", "close", "volume", "taker_buy_base_volume"]:
            df[col] = df[col].astype(float)
        df = df[["timestamp", "open", "high", "low", "close", "volume", "taker_buy_base_volume", "n_trades"]]
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
        df.to_csv(out_path, index=False, compression="gzip")
        print(f"  {coin}: {len(df)} rows, {df['timestamp'].min()} -> {df['timestamp'].max()} -> {out_path}")


if __name__ == "__main__":
    main()
