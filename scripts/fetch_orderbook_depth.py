"""Fetch real Binance USD-M futures order-book depth snapshots (bookDepth).

Source: https://data.binance.vision/data/futures/um/daily/bookDepth/{SYMBOL}/{SYMBOL}-bookDepth-{date}.zip
Binance's own public historical-data archive. Each daily file contains ~288
five-minute snapshots x 10 percentage levels (-5..-1, 1..5 from mid price),
each row giving cumulative depth (base-asset quantity) and notional (quote
value) standing on that side of the book at that % distance from mid.

This is a genuinely NEW real data source for this repo (first use of
order-book depth; every prior study used OHLCV, funding, OI, or external
sentiment/positioning/macro feeds). No synthetic/proxy data -- 404s are
recorded as missing days, never fabricated.

Archive coverage confirmed by direct HTTP probe on 2026-09-02:
  BTCUSDT/ETHUSDT/SOLUSDT/XRPUSDT: available from 2023-01-01 through current.

We do NOT keep the raw per-5-minute rows (would be gigabytes across 4 assets
x ~3.5 years). Instead we aggregate each daily zip in-memory into one row:
mean bid-side notional depth within 1%/2% of mid, mean ask-side notional
depth within 1%/2% of mid, and the resulting imbalance ratio.
"""
from __future__ import annotations

import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import Paths, project_root

BASE_URL = "https://data.binance.vision/data/futures/um/daily/bookDepth"
ASSETS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT"}
COVERAGE_START = pd.Timestamp("2023-01-01T00:00:00Z")


def _fetch_day(symbol: str, date: pd.Timestamp, attempts: int = 3) -> bytes | None:
    date_str = date.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{symbol}/{symbol}-bookDepth-{date_str}.zip"
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "edge-research/0.1"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == attempts - 1:
                return None
            time.sleep(min(2**attempt, 8))
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                return None
            time.sleep(min(2**attempt, 8))
    return None


def _aggregate_day(raw: bytes) -> dict | None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            name = archive.namelist()[0]
            with archive.open(name) as handle:
                df = pd.read_csv(handle)
    except Exception:
        return None
    if df.empty:
        return None
    df.columns = [c.strip() for c in df.columns]
    # percentage: -5..-1 (bid side, below mid) and 1..5 (ask side, above mid)
    bid1 = df.loc[df["percentage"] == -1, "notional"]
    bid2 = df.loc[df["percentage"] == -2, "notional"]
    ask1 = df.loc[df["percentage"] == 1, "notional"]
    ask2 = df.loc[df["percentage"] == 2, "notional"]
    bid_depth = pd.concat([bid1, bid2]).mean() if not (bid1.empty and bid2.empty) else None
    ask_depth = pd.concat([ask1, ask2]).mean() if not (ask1.empty and ask2.empty) else None
    if bid_depth is None or ask_depth is None or pd.isna(bid_depth) or pd.isna(ask_depth):
        return None
    n_snapshots = df["timestamp"].nunique()
    return {
        "bid_depth_1_2pct_mean": float(bid_depth),
        "ask_depth_1_2pct_mean": float(ask_depth),
        "n_snapshots": int(n_snapshots),
    }


def fetch_asset(asset: str, symbol: str, start: pd.Timestamp, end_exclusive: pd.Timestamp) -> pd.DataFrame:
    dates = pd.date_range(start.normalize(), (end_exclusive - pd.Timedelta(days=1)).normalize(), freq="D", tz="UTC")
    rows: list[dict] = []
    missing = 0

    def work(date: pd.Timestamp) -> tuple[pd.Timestamp, dict | None]:
        raw = _fetch_day(symbol, date)
        if raw is None:
            return date, None
        agg = _aggregate_day(raw)
        return date, agg

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(work, d): d for d in dates}
        for fut in as_completed(futures):
            date, agg = fut.result()
            if agg is None:
                missing += 1
                continue
            agg["timestamp"] = date
            rows.append(agg)

    if not rows:
        return pd.DataFrame(columns=["timestamp", "bid_depth_1_2pct_mean", "ask_depth_1_2pct_mean", "n_snapshots"])
    frame = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    frame["imbalance"] = (frame["bid_depth_1_2pct_mean"] - frame["ask_depth_1_2pct_mean"]) / (
        frame["bid_depth_1_2pct_mean"] + frame["ask_depth_1_2pct_mean"]
    )
    print(f"  {asset}: {len(frame)} daily rows, {missing} missing days (archive gaps, not fabricated)")
    return frame


def main() -> None:
    paths = Paths(project_root())
    out_dir = paths.data / "orderbook_depth"
    out_dir.mkdir(parents=True, exist_ok=True)
    end_exclusive = pd.Timestamp.now(tz="UTC").normalize()
    for asset, symbol in ASSETS.items():
        dest = out_dir / f"{asset}_depth_imbalance_1d.csv.gz"
        if dest.exists():
            existing = pd.read_csv(dest, parse_dates=["timestamp"])
            existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
            last = existing["timestamp"].max()
            start = last + pd.Timedelta(days=1)
            if start >= end_exclusive:
                print(f"{asset}: already current through {last.date()}")
                continue
            print(f"Fetching {asset} ({symbol}) depth from {start.date()}...")
            fresh = fetch_asset(asset, symbol, start, end_exclusive)
            combined = pd.concat([existing, fresh], ignore_index=True) if not fresh.empty else existing
        else:
            print(f"Fetching {asset} ({symbol}) depth from {COVERAGE_START.date()} (full history)...")
            combined = fetch_asset(asset, symbol, COVERAGE_START, end_exclusive)
        combined = combined.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        combined.to_csv(dest, index=False, compression="gzip", float_format="%.10g")
        print(f"  {asset}: {len(combined):,} total daily rows -> {dest}")


if __name__ == "__main__":
    main()
