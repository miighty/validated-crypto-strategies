from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .config import COINS, END_EXCLUSIVE, START, TIMEFRAMES, Paths

SPOT_ENDPOINT = "https://api.binance.com/api/v3/klines"
FUNDING_ENDPOINT = "https://fapi.binance.com/fapi/v1/fundingRate"
INTERVAL_MS = {"1d": 86_400_000, "4h": 14_400_000, "1h": 3_600_000}
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


def to_ms(value: str) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def _request_json(endpoint: str, params: dict[str, object], attempts: int = 6) -> list:
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "crypto-regime-validation/0.1"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(
                    f"Public exchange request failed after {attempts} attempts: {url}"
                ) from error
            time.sleep(min(2**attempt, 16))
    raise AssertionError("unreachable")


def fetch_klines(symbol: str, timeframe: str, start: str, end_exclusive: str) -> pd.DataFrame:
    cursor = to_ms(start)
    end_ms = to_ms(end_exclusive)
    rows: list[list[object]] = []
    while cursor < end_ms:
        batch = _request_json(
            SPOT_ENDPOINT,
            {
                "symbol": symbol,
                "interval": timeframe,
                "startTime": cursor,
                "endTime": end_ms - 1,
                "limit": 1000,
            },
        )
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + INTERVAL_MS[timeframe]
        if next_cursor <= cursor:
            raise RuntimeError(f"Pagination stalled for {symbol} {timeframe}")
        cursor = next_cursor
        time.sleep(0.035)
    frame = pd.DataFrame(rows, columns=RAW_COLUMNS)
    if frame.empty:
        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume", "source_symbol"]
        )
    frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["source_symbol"] = symbol
    return frame[["timestamp", "open", "high", "low", "close", "volume", "source_symbol"]]


def fetch_coin(coin: str, timeframe: str) -> pd.DataFrame:
    pieces = [
        fetch_klines(segment.symbol, timeframe, segment.start, segment.end_exclusive)
        for segment in COINS[coin]
    ]
    frame = pd.concat(pieces, ignore_index=True)
    if frame.empty:
        raise RuntimeError(f"No public spot candles returned for {coin} {timeframe}")
    frame = (
        frame.drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    validate_ohlcv(frame, coin, timeframe)
    return frame


def validate_ohlcv(frame: pd.DataFrame, coin: str, timeframe: str) -> None:
    if frame["timestamp"].duplicated().any():
        raise ValueError(f"Duplicate timestamps in {coin} {timeframe}")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError(f"Unsorted timestamps in {coin} {timeframe}")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any() or (frame["volume"] < 0).any():
        raise ValueError(f"Invalid non-positive prices or negative volume in {coin} {timeframe}")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError(f"Invalid high in {coin} {timeframe}")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError(f"Invalid low in {coin} {timeframe}")
    if frame["timestamp"].max() >= pd.Timestamp(END_EXCLUSIVE):
        raise ValueError(f"Unfinalized/out-of-window candle in {coin} {timeframe}")


def fetch_funding(
    symbol: str, start: str = START, end_exclusive: str = END_EXCLUSIVE
) -> pd.DataFrame:
    cursor = to_ms(start)
    end_ms = to_ms(end_exclusive)
    rows: list[dict[str, object]] = []
    while cursor < end_ms:
        batch = _request_json(
            FUNDING_ENDPOINT,
            {"symbol": symbol, "startTime": cursor, "endTime": end_ms - 1, "limit": 1000},
        )
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1]["fundingTime"]) + 1
        if next_cursor <= cursor:
            raise RuntimeError(f"Funding pagination stalled for {symbol}")
        cursor = next_cursor
        time.sleep(0.035)
    if not rows:
        return pd.DataFrame(columns=["timestamp", "funding_rate", "mark_price", "source_symbol"])
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["fundingRate"], errors="raise")
    frame["mark_price"] = pd.to_numeric(frame.get("markPrice"), errors="coerce")
    frame["source_symbol"] = symbol
    return (
        frame[["timestamp", "funding_rate", "mark_price", "source_symbol"]]
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(paths: Paths, refresh: bool = False) -> pd.DataFrame:
    paths.create()
    records: list[dict[str, object]] = []
    for coin in COINS:
        for timeframe in TIMEFRAMES:
            destination = paths.raw / f"{coin}_{timeframe}.csv.gz"
            if refresh or not destination.exists():
                print(f"Fetching {coin} {timeframe}...", flush=True)
                frame = fetch_coin(coin, timeframe)
                frame.to_csv(destination, index=False, compression="gzip", float_format="%.10g")
            else:
                frame = pd.read_csv(destination, parse_dates=["timestamp"])
                validate_ohlcv(frame, coin, timeframe)
            records.append(_provenance_record(destination, frame, coin, timeframe, "spot_ohlcv"))
            print(f"  {len(frame):,} finalized candles", flush=True)

        funding_destination = paths.funding / f"{coin}_funding.csv.gz"
        if refresh or not funding_destination.exists():
            pieces = []
            for segment in COINS[coin]:
                print(f"Fetching {segment.symbol} funding...", flush=True)
                piece = fetch_funding(segment.symbol, segment.start, segment.end_exclusive)
                if not piece.empty:
                    pieces.append(piece)
            funding = (
                pd.concat(pieces, ignore_index=True)
                if pieces
                else pd.DataFrame(
                    columns=["timestamp", "funding_rate", "mark_price", "source_symbol"]
                )
            )
            funding = funding.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
            funding.to_csv(
                funding_destination, index=False, compression="gzip", float_format="%.12g"
            )
        else:
            funding = pd.read_csv(funding_destination, parse_dates=["timestamp"])
        records.append(
            _provenance_record(funding_destination, funding, coin, "8h", "perpetual_funding")
        )
        print(f"  {len(funding):,} real funding observations", flush=True)

    provenance = pd.DataFrame(records).sort_values(["kind", "coin", "timeframe"])
    provenance.to_csv(paths.data / "provenance.csv", index=False)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "window_start": START,
        "window_end_exclusive": END_EXCLUSIVE,
        "source": "Binance public spot and USD-M futures REST APIs",
        "synthetic_data_used": False,
        "files": records,
    }
    (paths.data / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return provenance


def _provenance_record(
    path: Path, frame: pd.DataFrame, coin: str, timeframe: str, kind: str
) -> dict[str, object]:
    timestamps = (
        pd.to_datetime(frame["timestamp"], utc=True)
        if not frame.empty
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    source_symbols = (
        sorted(frame["source_symbol"].dropna().astype(str).unique()) if not frame.empty else []
    )
    return {
        "path": str(path.relative_to(path.parents[2])),
        "kind": kind,
        "coin": coin,
        "timeframe": timeframe,
        "source": "Binance",
        "source_symbols": ";".join(source_symbols),
        "first_timestamp": timestamps.min().isoformat() if not timestamps.empty else "",
        "last_timestamp": timestamps.max().isoformat() if not timestamps.empty else "",
        "rows": len(frame),
        "sha256": sha256(path),
    }


def load_ohlcv(paths: Paths, coin: str, timeframe: str) -> pd.DataFrame:
    frame = pd.read_csv(paths.raw / f"{coin}_{timeframe}.csv.gz", parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.set_index("timestamp").sort_index()
