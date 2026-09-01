from __future__ import annotations

"""Fetch real Binance USD-M futures open-interest + long/short-ratio metrics.

Source: https://data.binance.vision/data/futures/um/daily/metrics/{SYMBOL}/{SYMBOL}-metrics-{date}.zip
This is Binance's own public historical-data archive (5-minute snapshots of
sum_open_interest, sum_open_interest_value, top-trader and global long/short
ratios). No synthetic/proxy data -- if a symbol/date has no archive file
(404), it is skipped and recorded as missing, never fabricated.

Per-symbol earliest available date (checked via binary search against the
live archive, 2026-09-01):
  BTCUSDT: 2020-09-01
  ETHUSDT/SOLUSDT/XRPUSDT: 2021-12-01 (all three, coincidentally identical)
"""

import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from .config import Paths

BASE_URL = "https://data.binance.vision/data/futures/um/daily/metrics"

EARLIEST_AVAILABLE = {
    "BTCUSDT": pd.Timestamp("2020-09-01", tz="UTC"),
    "ETHUSDT": pd.Timestamp("2021-12-01", tz="UTC"),
    "SOLUSDT": pd.Timestamp("2021-12-01", tz="UTC"),
    "XRPUSDT": pd.Timestamp("2021-12-01", tz="UTC"),
}

METRICS_COLUMNS = [
    "create_time",
    "symbol",
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
]


def _fetch_day_zip(symbol: str, date: pd.Timestamp, attempts: int = 3) -> bytes | None:
    date_str = date.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{symbol}/{symbol}-metrics-{date_str}.zip"
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "edge-research/0.1"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if attempt == attempts - 1:
                raise
            time.sleep(min(2**attempt, 8))
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(min(2**attempt, 8))
    return None


def _parse_day_zip(raw: bytes, symbol: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as handle:
            frame = pd.read_csv(handle)
    frame.columns = [c.strip() for c in frame.columns]
    frame = frame.rename(columns={"symbol": "source_symbol"})
    frame["create_time"] = pd.to_datetime(frame["create_time"], utc=True, format="mixed")
    for column in (
        "sum_open_interest",
        "sum_open_interest_value",
        "count_toptrader_long_short_ratio",
        "sum_toptrader_long_short_ratio",
        "count_long_short_ratio",
        "sum_taker_long_short_vol_ratio",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def fetch_daily_oi_series(symbol: str, start: pd.Timestamp, end_exclusive: pd.Timestamp) -> pd.DataFrame:
    """Fetch daily OI/long-short-ratio snapshots (last 5-min print of each UTC day)."""
    earliest = EARLIEST_AVAILABLE.get(symbol)
    if earliest is not None and start < earliest:
        start = earliest
    dates = pd.date_range(start.normalize(), (end_exclusive - pd.Timedelta(days=1)).normalize(), freq="D", tz="UTC")
    rows = []
    missing_dates = []
    for date in dates:
        raw = _fetch_day_zip(symbol, date)
        if raw is None:
            missing_dates.append(date.strftime("%Y-%m-%d"))
            continue
        day_frame = _parse_day_zip(raw, symbol)
        if day_frame.empty:
            missing_dates.append(date.strftime("%Y-%m-%d"))
            continue
        last_row = day_frame.sort_values("create_time").iloc[-1]
        rows.append(
            {
                "timestamp": date,
                "sum_open_interest": last_row["sum_open_interest"],
                "sum_open_interest_value": last_row["sum_open_interest_value"],
                "count_toptrader_long_short_ratio": last_row["count_toptrader_long_short_ratio"],
                "sum_toptrader_long_short_ratio": last_row["sum_toptrader_long_short_ratio"],
                "count_long_short_ratio": last_row["count_long_short_ratio"],
                "sum_taker_long_short_vol_ratio": last_row["sum_taker_long_short_vol_ratio"],
            }
        )
        time.sleep(0.03)
    frame = pd.DataFrame(rows)
    if missing_dates:
        print(f"  {symbol}: {len(missing_dates)} missing daily OI files (archive gaps, not fabricated)")
    return frame


def collect_open_interest(paths: Paths, symbols: dict[str, str], refresh: bool = False) -> None:
    """symbols: mapping ASSET -> Binance futures symbol, e.g. {'BTC': 'BTCUSDT'}."""
    oi_dir = paths.data / "open_interest"
    oi_dir.mkdir(parents=True, exist_ok=True)
    end_exclusive = pd.Timestamp.now(tz="UTC").normalize()
    for asset, symbol in symbols.items():
        destination = oi_dir / f"{asset}_oi_daily.csv.gz"
        if destination.exists() and not refresh:
            existing = pd.read_csv(destination, parse_dates=["timestamp"])
            existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
            last_ts = existing["timestamp"].max()
            start = last_ts + pd.Timedelta(days=1)
            if start >= end_exclusive:
                print(f"{asset}: OI data already current through {last_ts.date()}")
                continue
            print(f"Fetching {asset} ({symbol}) OI from {start.date()}...")
            fresh = fetch_daily_oi_series(symbol, start, end_exclusive)
            combined = pd.concat([existing, fresh], ignore_index=True) if not fresh.empty else existing
        else:
            earliest = EARLIEST_AVAILABLE.get(symbol, pd.Timestamp("2020-01-01", tz="UTC"))
            print(f"Fetching {asset} ({symbol}) OI from {earliest.date()} (full history)...")
            combined = fetch_daily_oi_series(symbol, earliest, end_exclusive)
        combined = combined.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
        combined.to_csv(destination, index=False, compression="gzip", float_format="%.10g")
        print(f"  {asset}: {len(combined):,} daily OI rows saved -> {destination}")


def load_oi(paths: Paths, asset: str) -> pd.DataFrame:
    path = paths.data / "open_interest" / f"{asset}_oi_daily.csv.gz"
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.set_index("timestamp").sort_index()
