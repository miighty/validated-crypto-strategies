from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .config import load_yaml, resolve_from_root

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
INTERVALS = {
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}
RAW_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_base_volume",
    "taker_quote_volume",
    "ignore",
]
KNOWN_QUOTE_ASSETS = (
    "FDUSD",
    "USDT",
    "USDC",
    "TUSD",
    "BUSD",
    "BTC",
    "ETH",
    "BNB",
    "EUR",
    "GBP",
    "TRY",
    "BRL",
    "AUD",
)


def normalize_symbols(values: list[str], default_quote: str = "USDT") -> list[str]:
    """Normalize user-friendly base tickers and slash pairs to exchange symbols."""
    normalized = []
    quote = default_quote.strip().upper()
    if not quote or not quote.isalnum():
        raise ValueError(f"Invalid default quote asset: {default_quote!r}")
    for value in values:
        for token in value.split(","):
            raw = re.sub(r"\s+", "", token).upper()
            if not raw:
                continue
            if "/" in raw:
                parts = raw.split("/")
                if len(parts) != 2 or not parts[0]:
                    raise ValueError(f"Invalid symbol: {value!r}")
                symbol = parts[0] + (parts[1] or quote)
            elif any(raw.endswith(item) and len(raw) > len(item) for item in KNOWN_QUOTE_ASSETS):
                symbol = raw
            else:
                symbol = raw + quote
            if not symbol.isalnum():
                raise ValueError(f"Invalid symbol: {value!r}")
            if symbol not in normalized:
                normalized.append(symbol)
    if not normalized:
        raise ValueError("At least one symbol is required")
    return normalized


def merge_dataset_reports(
    existing: list[dict[str, Any]], fresh: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Upsert refreshed symbols without deleting previously downloaded markets."""
    by_symbol = {item["symbol"]: item for item in existing}
    by_symbol.update({item["symbol"]: item for item in fresh})
    return [by_symbol[symbol] for symbol in sorted(by_symbol)]


def latest_complete_boundary(timeframe: str, now: pd.Timestamp | None = None) -> pd.Timestamp:
    interval = INTERVALS[timeframe]
    timestamp = now if now is not None else pd.Timestamp.now(tz="UTC")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    complete_intervals = (timestamp - epoch) // interval
    return epoch + complete_intervals * interval


def _to_ms(value: pd.Timestamp) -> int:
    return int(value.timestamp() * 1000)


def _request(params: dict[str, object], attempts: int = 5) -> list[list[object]]:
    url = f"{BINANCE_KLINES}?{urllib.parse.urlencode(params)}"
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "edge-research/0.1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
            if not isinstance(payload, list):
                raise TypeError(f"Unexpected Binance response: {payload}")
            return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(f"Binance request failed: {url}") from error
            time.sleep(min(2**attempt, 8))
    raise AssertionError("unreachable")


def download_symbol(
    symbol: str, timeframe: str, start: pd.Timestamp, end_exclusive: pd.Timestamp
) -> tuple[pd.DataFrame, int]:
    interval_ms = int(INTERVALS[timeframe].total_seconds() * 1000)
    cursor = _to_ms(start)
    end_ms = _to_ms(end_exclusive)
    rows: list[list[object]] = []
    while cursor < end_ms:
        batch = _request(
            {
                "symbol": symbol,
                "interval": timeframe,
                "startTime": cursor,
                "endTime": end_ms - 1,
                "limit": 1000,
            }
        )
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + interval_ms
        if next_cursor <= cursor:
            raise RuntimeError(f"Pagination stalled for {symbol} {timeframe}")
        cursor = next_cursor
        time.sleep(0.025)
    frame = pd.DataFrame(rows, columns=RAW_COLUMNS)
    if frame.empty:
        raise RuntimeError(f"No candles returned for {symbol} {timeframe}")
    frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    duplicates = int(frame["timestamp"].duplicated().sum())
    frame = (
        frame.loc[frame["timestamp"] < end_exclusive]
        .drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    )
    return frame, duplicates


def validate_ohlcv(
    frame: pd.DataFrame,
    symbol: str,
    timeframe: str,
    end_exclusive: pd.Timestamp | None = None,
) -> dict[str, Any]:
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{symbol}: missing OHLCV columns {sorted(required - set(frame.columns))}")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError(f"{symbol}: index must be a DatetimeIndex")
    index = frame.index
    if index.tz is None or str(index.tz) != "UTC":
        raise ValueError(f"{symbol}: timestamps must use UTC")
    if index.duplicated().any():
        raise ValueError(f"{symbol}: duplicate candles")
    if not index.is_monotonic_increasing:
        raise ValueError(f"{symbol}: unsorted candles")
    if frame.empty:
        raise ValueError(f"{symbol}: empty dataset")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError(f"{symbol}: non-positive price")
    if (frame["volume"] < 0).any():
        raise ValueError(f"{symbol}: negative volume")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError(f"{symbol}: invalid high relationship")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError(f"{symbol}: invalid low relationship")
    if end_exclusive is not None and index.max() >= end_exclusive:
        raise ValueError(f"{symbol}: incomplete or out-of-window candle")
    expected = pd.date_range(index.min(), index.max(), freq=INTERVALS[timeframe], tz="UTC")
    missing = expected.difference(index)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": len(frame),
        "first_timestamp": index.min().isoformat(),
        "last_timestamp": index.max().isoformat(),
        "missing_candles": len(missing),
        "largest_gap_hours": _largest_gap_hours(index),
    }


def _largest_gap_hours(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 0.0
    return float(index.to_series().diff().max().total_seconds() / 3600)


def download(
    config_path: str | Path, symbols_override: list[str] | None = None
) -> dict[str, Any]:
    config = load_yaml(config_path)
    timeframe = str(config["timeframe"])
    if timeframe not in INTERVALS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    start = pd.Timestamp(config["start"])
    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    end_setting = config.get("end", "latest_complete")
    end_exclusive = (
        latest_complete_boundary(timeframe)
        if end_setting == "latest_complete"
        else pd.Timestamp(end_setting)
    )
    if end_exclusive.tzinfo is None:
        end_exclusive = end_exclusive.tz_localize("UTC")
    else:
        end_exclusive = end_exclusive.tz_convert("UTC")
    output = resolve_from_root(config["output_directory"])
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    symbols = normalize_symbols(
        symbols_override or config["symbols"], str(config.get("quote_asset", "USDT"))
    )
    for symbol in symbols:
        print(f"Downloading {symbol} {timeframe}...", flush=True)
        frame, duplicates_removed = download_symbol(symbol, timeframe, start, end_exclusive)
        quality = validate_ohlcv(frame, symbol, timeframe, end_exclusive)
        quality.update(
            {
                "source": "Binance spot REST /api/v3/klines",
                "source_symbol": symbol,
                "duplicates_removed": duplicates_removed,
                "downloaded_at": datetime.now(UTC).isoformat(),
                "end_exclusive": end_exclusive.isoformat(),
                "file": str((output / f"{symbol}_{timeframe}.parquet").relative_to(resolve_from_root("."))),
            }
        )
        frame.to_parquet(output / f"{symbol}_{timeframe}.parquet", compression="zstd")
        reports.append(quality)
        print(
            f"  {quality['rows']} candles, {quality['first_timestamp']} to "
            f"{quality['last_timestamp']}, missing={quality['missing_candles']}"
        )
    manifest_path = output / "quality_report.json"
    existing_reports: list[dict[str, Any]] = []
    if manifest_path.exists():
        existing_manifest = json.loads(manifest_path.read_text())
        compatible = (
            existing_manifest.get("dataset_version") == config["experiment_data_version"]
            and existing_manifest.get("source") == config["source"]
            and existing_manifest.get("timeframe") == timeframe
            and existing_manifest.get("start_requested") == start.isoformat()
        )
        if compatible:
            existing_reports = existing_manifest.get("datasets", [])
    manifest = {
        "dataset_version": config["experiment_data_version"],
        "source": config["source"],
        "timeframe": timeframe,
        "start_requested": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "datasets": merge_dataset_reports(existing_reports, reports),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_market_data(
    data_config_path: str | Path, symbols_override: list[str] | None = None
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    config = load_yaml(data_config_path)
    output = resolve_from_root(config["output_directory"])
    manifest_path = output / "quality_report.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {manifest_path}; run the download command first")
    manifest = json.loads(manifest_path.read_text())
    frames = {}
    symbols = normalize_symbols(
        symbols_override or config["symbols"], str(config.get("quote_asset", "USDT"))
    )
    dataset_by_symbol = {item["symbol"]: item for item in manifest["datasets"]}
    manifest_symbols = set(dataset_by_symbol)
    missing = [symbol for symbol in symbols if symbol not in manifest_symbols]
    if missing:
        raise FileNotFoundError(
            f"Symbols absent from the current data snapshot: {missing}; rerun download with --symbols"
        )
    for symbol in symbols:
        path = output / f"{symbol}_{config['timeframe']}.parquet"
        frame = pd.read_parquet(path)
        frame.index = pd.to_datetime(frame.index, utc=True)
        dataset_end = pd.Timestamp(
            dataset_by_symbol[symbol].get("end_exclusive", manifest["end_exclusive"])
        )
        validate_ohlcv(frame, symbol, config["timeframe"], dataset_end)
        frames[symbol] = frame
    return frames, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download finalized Binance OHLCV to Parquet")
    parser.add_argument("--config", default="configs/data.yaml")
    parser.add_argument("--symbols", nargs="+", help="Override symbols, e.g. SOL ETC")
    args = parser.parse_args()
    download(args.config, args.symbols)


if __name__ == "__main__":
    main()
