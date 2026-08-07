from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import END_EXCLUSIVE, ONE_WAY_COST, Paths
from .data import load_ohlcv, sha256

GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
POLY_TRADES_URL = "https://data-api.polymarket.com/trades"
KALSHI_MARKETS_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
KALSHI_CANDLES_URL = "https://api.elections.kalshi.com/trade-api/v2/series/{ticker}/candlesticks"
POLY_NATIVE_ONE_WAY_COST = 0.002


@dataclass(frozen=True)
class MarketSeed:
    slug: str
    query: str
    asset: str
    family: str
    bullish_when_yes: bool = True
    notes: str = ""


@dataclass(frozen=True)
class EventTrade:
    strategy: str
    market_slug: str
    asset: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int
    entry_price: float
    exit_price: float
    return_pct: float
    note: str


SEEDS: tuple[MarketSeed, ...] = (
    MarketSeed(
        slug="bitcoin-etf-approved-by-jan-15",
        query="bitcoin etf approved by jan 15",
        asset="BTC",
        family="btc_etf",
        notes="Spot BTC ETF approval catalyst",
    ),
    MarketSeed(
        slug="ethereum-etf-approved-by-may-31",
        query="ethereum etf approved",
        asset="ETH",
        family="eth_etf",
        notes="Spot ETH ETF approval catalyst",
    ),
    MarketSeed(
        slug="will-donald-trump-win-the-2024-us-presidential-election",
        query="presidential election winner 2024",
        asset="BTC",
        family="trump_election",
        notes="Trump odds used as pro-crypto policy proxy",
    ),
    MarketSeed(
        slug="will-trump-create-a-national-bitcoin-reserve-in-his-first-100-days",
        query="bitcoin reserve",
        asset="BTC",
        family="bitcoin_reserve",
        notes="Bitcoin strategic reserve policy odds",
    ),
    MarketSeed(
        slug="solana-etf-approved-by-july-31-2025",
        query="solana etf approved",
        asset="SOL",
        family="sol_etf",
        notes="Spot SOL ETF approval catalyst",
    ),
    MarketSeed(
        slug="fed-rate-cut-by-march-20",
        query="fed cut interest rates",
        asset="ETH",
        family="fed_cut",
        notes="Front-end Fed easing odds",
    ),
    MarketSeed(
        slug="fed-rate-cut-by-may-1",
        query="fed cut interest rates",
        asset="ETH",
        family="fed_cut",
        notes="Front-end Fed easing odds",
    ),
    MarketSeed(
        slug="fed-rate-cut-by-june-12",
        query="fed cut interest rates",
        asset="ETH",
        family="fed_cut",
        notes="Front-end Fed easing odds",
    ),
    MarketSeed(
        slug="us-recession-by-end-of-2026",
        query="us recession by end of 2026",
        asset="BTC",
        family="recession",
        bullish_when_yes=False,
        notes="Macro risk-off odds",
    ),
)


def _request_json(url: str, params: dict[str, object], attempts: int = 5) -> object:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    final = f"{url}?{query}" if query else url
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(final, headers={"User-Agent": "validated-crypto-strategies/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(min(2**attempt, 10))
    raise AssertionError("unreachable")


def polymarket_dir(paths: Paths) -> Path:
    return paths.data / "polymarket_validation"


def polymarket_results_dir(paths: Paths) -> Path:
    return paths.results / "polymarket_validation"


def ensure_dirs(paths: Paths) -> tuple[Path, Path, Path]:
    base = polymarket_dir(paths)
    trades = base / "trades"
    hourly = base / "hourly"
    results = polymarket_results_dir(paths)
    for item in (base, trades, hourly, results):
        item.mkdir(parents=True, exist_ok=True)
    return base, trades, hourly


def _public_search(query: str) -> dict:
    return _request_json(GAMMA_SEARCH_URL, {"q": query})  # type: ignore[return-value]


def fetch_market_metadata(paths: Paths) -> pd.DataFrame:
    base, _, _ = ensure_dirs(paths)
    cache = base / "market_metadata.csv"
    rows: list[dict[str, object]] = []
    for seed in SEEDS:
        payload = _public_search(seed.query)
        found = None
        for event in payload.get("events", []):
            for market in event.get("markets", []):
                if market.get("slug") == seed.slug:
                    found = market
                    break
            if found:
                break
        if not found:
            raise RuntimeError(f"Could not find Polymarket slug {seed.slug} from query {seed.query!r}")
        rows.append(
            {
                "slug": seed.slug,
                "query": seed.query,
                "asset": seed.asset,
                "family": seed.family,
                "bullish_when_yes": seed.bullish_when_yes,
                "notes": seed.notes,
                "question": found.get("question"),
                "condition_id": found.get("conditionId"),
                "outcomes": found.get("outcomes"),
                "outcome_prices": found.get("outcomePrices"),
                "volume": float(found.get("volume") or 0),
                "active": bool(found.get("active")),
                "closed": bool(found.get("closed")),
                "end_date": found.get("endDate") or "",
                "description": found.get("description") or "",
            }
        )
    frame = pd.DataFrame(rows).sort_values(["family", "slug"]).reset_index(drop=True)
    frame.to_csv(cache, index=False)
    return frame


def fetch_polymarket_trades(condition_id: str) -> pd.DataFrame:
    offset = 0
    rows: list[dict[str, object]] = []
    while True:
        try:
            batch = _request_json(POLY_TRADES_URL, {"market": condition_id, "limit": 1000, "offset": offset})
        except Exception as error:
            if offset > 0 and "HTTP Error 400" in str(error):
                break
            raise
        if not batch:
            break
        assert isinstance(batch, list)
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < 1000:
            break
        time.sleep(0.05)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "yes_price", "outcome", "price", "size"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["size"] = pd.to_numeric(frame["size"], errors="coerce")
    frame["yes_price"] = frame["price"].where(frame["outcome"].eq("Yes"), 1.0 - frame["price"])
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame[["timestamp", "yes_price", "outcome", "price", "size", "slug", "title", "conditionId"]]


def fetch_market_universe(paths: Paths) -> pd.DataFrame:
    base, _, _ = ensure_dirs(paths)
    cache = base / "market_universe.csv"
    queries = [
        "bitcoin etf",
        "ethereum etf",
        "solana etf",
        "bitcoin reserve",
        "fed cut interest rates",
        "presidential election winner 2024",
        "us recession by end of 2026",
        "bitcoin etf flows on",
    ]
    seen: dict[str, dict[str, object]] = {}
    for query in queries:
        payload = _public_search(query)
        for event in payload.get("events", []):
            for market in event.get("markets", []):
                slug = market.get("slug")
                if not slug:
                    continue
                seen.setdefault(
                    slug,
                    {
                        "slug": slug,
                        "query": query,
                        "question": market.get("question") or "",
                        "condition_id": market.get("conditionId") or "",
                        "outcome_prices": market.get("outcomePrices") or "",
                        "volume": float(market.get("volume") or 0),
                        "closed": bool(market.get("closed")),
                        "active": bool(market.get("active")),
                        "end_date": market.get("endDate") or "",
                        "description": market.get("description") or "",
                    },
                )
    frame = pd.DataFrame(seen.values())
    frame["end_date"] = pd.to_datetime(frame["end_date"], utc=True, errors="coerce")
    frame = frame[frame["volume"] >= 25_000].sort_values(["volume", "slug"], ascending=[False, True])
    flows = frame[frame["slug"].astype(str).str.startswith("bitcoin-etf-flows-on-")].copy()
    non_flows = frame[~frame["slug"].astype(str).str.startswith("bitcoin-etf-flows-on-")].copy().head(30)
    frame = pd.concat([non_flows, flows], ignore_index=True).drop_duplicates(subset=["slug"], keep="first")
    frame.to_csv(cache, index=False)
    return frame.reset_index(drop=True)


def load_or_fetch_hourly_series(paths: Paths, metadata: pd.DataFrame) -> pd.DataFrame:
    _, trades_dir, hourly_dir = ensure_dirs(paths)
    all_frames: list[pd.DataFrame] = []
    for row in metadata.to_dict("records"):
        slug = str(row["slug"])
        condition_id = str(row["condition_id"])
        trade_cache = trades_dir / f"{slug}.csv.gz"
        hourly_cache = hourly_dir / f"{slug}.csv.gz"
        if trade_cache.exists():
            trades = pd.read_csv(trade_cache, parse_dates=["timestamp"])
            trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True)
        else:
            trades = fetch_polymarket_trades(condition_id)
            trades.to_csv(trade_cache, index=False, compression="gzip", float_format="%.10g")
        if trades.empty:
            continue
        if hourly_cache.exists():
            hourly = pd.read_csv(hourly_cache, parse_dates=["timestamp"])
            hourly["timestamp"] = pd.to_datetime(hourly["timestamp"], utc=True)
        else:
            hourly = (
                trades.set_index("timestamp")
                .resample("1h")
                .agg(
                    yes_price=("yes_price", "last"),
                    trade_count=("yes_price", "count"),
                    traded_notional=("size", "sum"),
                )
                .reset_index()
            )
            hourly["yes_price"] = hourly["yes_price"].ffill()
            hourly["trade_count"] = hourly["trade_count"].fillna(0)
            hourly["traded_notional"] = hourly["traded_notional"].fillna(0)
            hourly.to_csv(hourly_cache, index=False, compression="gzip", float_format="%.10g")
        for key in ("slug", "asset", "family", "question", "notes", "bullish_when_yes", "end_date"):
            hourly[key] = row.get(key)
        all_frames.append(hourly)
    if not all_frames:
        raise RuntimeError("No Polymarket hourly series available")
    return pd.concat(all_frames, ignore_index=True).sort_values(["slug", "timestamp"]).reset_index(drop=True)


def load_crypto_open_series(paths: Paths, coin: str) -> pd.DataFrame:
    frame = load_ohlcv(paths, coin, "1h").reset_index()[["timestamp", "open", "high", "low", "close"]]
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


def trade_open_to_open(series: pd.DataFrame, entry_time: pd.Timestamp, hold_hours: int) -> tuple[pd.Timestamp, float, float] | None:
    frame = series.set_index("timestamp")
    if entry_time not in frame.index:
        return None
    exit_time = entry_time + pd.Timedelta(hours=hold_hours)
    if exit_time not in frame.index:
        return None
    entry_price = float(frame.at[entry_time, "open"])
    exit_price = float(frame.at[exit_time, "open"])
    return exit_time, entry_price, exit_price


def spread_open_to_open(
    left: pd.DataFrame, right: pd.DataFrame, entry_time: pd.Timestamp, hold_hours: int
) -> tuple[pd.Timestamp, float, float, float, float] | None:
    l = left.set_index("timestamp")
    r = right.set_index("timestamp")
    exit_time = entry_time + pd.Timedelta(hours=hold_hours)
    if entry_time not in l.index or entry_time not in r.index or exit_time not in l.index or exit_time not in r.index:
        return None
    return (
        exit_time,
        float(l.at[entry_time, "open"]),
        float(l.at[exit_time, "open"]),
        float(r.at[entry_time, "open"]),
        float(r.at[exit_time, "open"]),
    )


def _equity_and_drawdown(returns: Iterable[float], starting_capital: float = 10_000.0) -> tuple[float, float]:
    equity = starting_capital
    peak = starting_capital
    max_drawdown = 0.0
    for r in returns:
        equity *= max(0.0, 1.0 + r)
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
    return equity, max_drawdown


def summarize_strategy(name: str, trades: list[EventTrade], note: str, status: str = "completed") -> dict[str, object]:
    returns = [t.return_pct for t in trades]
    equity, dd = _equity_and_drawdown(returns)
    wins = sum(1 for r in returns if r > 0)
    return {
        "strategy": name,
        "status": status,
        "trade_count": len(trades),
        "win_rate": wins / len(trades) if trades else math.nan,
        "avg_return": sum(returns) / len(returns) if trades else math.nan,
        "median_return": pd.Series(returns).median() if trades else math.nan,
        "ending_equity": equity,
        "total_return": equity / 10_000.0 - 1.0,
        "max_drawdown": dd,
        "note": note,
    }


def signal_backtest(
    name: str,
    market_frame: pd.DataFrame,
    asset_frame: pd.DataFrame,
    hold_hours: int,
    delta_threshold: float,
    level_threshold: float | None = None,
    cooldown_hours: int = 24,
    long_short: bool = True,
) -> list[EventTrade]:
    trades: list[EventTrade] = []
    last_exit = pd.Timestamp.min.tz_localize("UTC")
    for slug, frame in market_frame.groupby("slug"):
        sample = frame.sort_values("timestamp").copy()
        sample["delta_24h"] = sample["yes_price"].diff(24)
        sample["asset_return_24h"] = asset_frame.set_index("timestamp")["close"].pct_change(24).reindex(sample["timestamp"]).values
        sample = sample.dropna(subset=["delta_24h", "asset_return_24h", "yes_price"])
        if sample.empty:
            continue
        bullish_when_yes = bool(sample["bullish_when_yes"].iloc[0])
        sign = 1 if bullish_when_yes else -1
        for row in sample.itertuples(index=False):
            signal_time = pd.Timestamp(row.timestamp)
            if signal_time <= last_exit:
                continue
            delta = float(row.delta_24h)
            implied = sign * delta
            if abs(implied) < delta_threshold:
                continue
            if level_threshold is not None and implied > 0 and float(row.yes_price) < level_threshold:
                continue
            if abs(float(row.asset_return_24h)) > abs(implied) * 1.5:
                continue
            direction = 1 if implied > 0 else -1
            if not long_short and direction < 0:
                continue
            entry_time = signal_time + pd.Timedelta(hours=1)
            traded = trade_open_to_open(asset_frame, entry_time, hold_hours)
            if traded is None:
                continue
            exit_time, entry_price, exit_price = traded
            gross = direction * (exit_price / entry_price - 1.0)
            net = gross - 2 * ONE_WAY_COST
            trades.append(
                EventTrade(
                    strategy=name,
                    market_slug=str(slug),
                    asset=str(row.asset),
                    signal_time=signal_time,
                    entry_time=entry_time,
                    exit_time=exit_time,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    return_pct=net,
                    note=f"24h odds delta={delta:.3f}",
                )
            )
            last_exit = exit_time + pd.Timedelta(hours=cooldown_hours)
    return sorted(trades, key=lambda item: item.entry_time)


def eth_etf_spread_backtest(hourly: pd.DataFrame, eth: pd.DataFrame, btc: pd.DataFrame) -> list[EventTrade]:
    frame = hourly[hourly["family"].eq("eth_etf")].copy().sort_values("timestamp")
    frame["delta_24h"] = frame["yes_price"].diff(24)
    trades: list[EventTrade] = []
    last_exit = pd.Timestamp.min.tz_localize("UTC")
    for row in frame.dropna(subset=["delta_24h"]).itertuples(index=False):
        signal_time = pd.Timestamp(row.timestamp)
        if signal_time <= last_exit:
            continue
        if float(row.delta_24h) < 0.10 or float(row.yes_price) < 0.60:
            continue
        entry_time = signal_time + pd.Timedelta(hours=1)
        traded = spread_open_to_open(eth, btc, entry_time, 72)
        if traded is None:
            continue
        exit_time, eth_entry, eth_exit, btc_entry, btc_exit = traded
        gross = (eth_exit / eth_entry - 1.0) - (btc_exit / btc_entry - 1.0)
        net = gross - 4 * ONE_WAY_COST
        trades.append(
            EventTrade(
                strategy="eth_etf_spread",
                market_slug=str(row.slug),
                asset="ETH/BTC",
                signal_time=signal_time,
                entry_time=entry_time,
                exit_time=exit_time,
                direction=1,
                entry_price=eth_entry / btc_entry,
                exit_price=eth_exit / btc_exit,
                return_pct=net,
                note=f"24h odds delta={float(row.delta_24h):.3f}; level={float(row.yes_price):.3f}",
            )
        )
        last_exit = exit_time + pd.Timedelta(hours=24)
    return trades


def wick_with_odds_confirmation(
    hourly: pd.DataFrame, btc: pd.DataFrame, supportive_families: tuple[str, ...] = ("btc_etf", "eth_etf", "trump_election", "bitcoin_reserve")
) -> list[EventTrade]:
    support = hourly[hourly["family"].isin(supportive_families)].copy()
    grouped = support.groupby(["timestamp", "family"], as_index=False)["yes_price"].mean()
    pivot = grouped.pivot(index="timestamp", columns="family", values="yes_price").sort_index().ffill()
    support_signal = pivot.mean(axis=1).diff(24)

    frame = btc.copy().sort_values("timestamp")
    prior_high = frame["high"].shift(1).rolling(48).max()
    frame["drawdown"] = frame["low"] / prior_high - 1.0
    trades: list[EventTrade] = []
    last_exit = pd.Timestamp.min.tz_localize("UTC")
    for row in frame.itertuples(index=False):
        signal_time = pd.Timestamp(row.timestamp)
        if signal_time <= last_exit:
            continue
        if pd.isna(row.drawdown) or float(row.drawdown) > -0.20:
            continue
        support_delta = float(support_signal.reindex([signal_time]).iloc[0]) if signal_time in support_signal.index else math.nan
        if pd.isna(support_delta) or support_delta < -0.02:
            continue
        event_low = float(row.low)
        window = frame[(frame["timestamp"] > signal_time) & (frame["timestamp"] <= signal_time + pd.Timedelta(hours=24))].copy()
        trigger = window[window["close"] >= event_low * 1.05]
        if trigger.empty:
            continue
        entry_time = pd.Timestamp(trigger.iloc[0]["timestamp"]) + pd.Timedelta(hours=1)
        traded = trade_open_to_open(btc, entry_time, 72)
        if traded is None:
            continue
        exit_time, entry_price, exit_price = traded
        gross = exit_price / entry_price - 1.0
        net = gross - 2 * ONE_WAY_COST
        trades.append(
            EventTrade(
                strategy="wick_with_odds_confirmation",
                market_slug="supportive_composite",
                asset="BTC",
                signal_time=signal_time,
                entry_time=entry_time,
                exit_time=exit_time,
                direction=1,
                entry_price=entry_price,
                exit_price=exit_price,
                return_pct=net,
                note=f"wick drawdown={float(row.drawdown):.3f}; support_delta={support_delta:.3f}",
            )
        )
        last_exit = exit_time + pd.Timedelta(hours=48)
    return trades


def _price_before(frame: pd.DataFrame, when: pd.Timestamp) -> float | None:
    subset = frame[frame["timestamp"] <= when]
    if subset.empty:
        return None
    return float(subset.iloc[-1]["yes_price"])


def favorite_longshot_bias(universe: pd.DataFrame, hourly: pd.DataFrame) -> list[EventTrade]:
    resolved = universe[universe["closed"].astype(bool)].copy()
    trades: list[EventTrade] = []
    meta = fetch_metadata_lookup(hourly)
    for row in resolved.itertuples(index=False):
        slug = str(row.slug)
        if slug not in meta:
            continue
        market = hourly[hourly["slug"].eq(slug)].copy().sort_values("timestamp")
        end_date = pd.Timestamp(row.end_date)
        entry_time = end_date - pd.Timedelta(hours=24)
        yes_price = _price_before(market, entry_time)
        if yes_price is None:
            continue
        outcome = infer_final_yes(meta[slug]["outcome_prices"])
        if yes_price >= 0.65:
            gross = (1.0 if outcome else 0.0) / yes_price - 1.0
            direction = 1
            note = "buy_yes_24h_before"
            px_in = yes_price
            px_out = 1.0 if outcome else 0.0
        elif yes_price <= 0.35:
            no_price = 1.0 - yes_price
            gross = (1.0 if not outcome else 0.0) / no_price - 1.0
            direction = -1
            note = "buy_no_24h_before"
            px_in = no_price
            px_out = 1.0 if not outcome else 0.0
        else:
            continue
        net = gross - 2 * POLY_NATIVE_ONE_WAY_COST
        trades.append(
            EventTrade(
                strategy="favorite_longshot_bias",
                market_slug=slug,
                asset="POLY_NATIVE",
                signal_time=entry_time,
                entry_time=entry_time,
                exit_time=end_date,
                direction=direction,
                entry_price=px_in,
                exit_price=px_out,
                return_pct=net,
                note=note,
            )
        )
    return sorted(trades, key=lambda item: item.entry_time)


def resolution_time_decay(universe: pd.DataFrame, hourly: pd.DataFrame) -> list[EventTrade]:
    resolved = universe[universe["closed"].astype(bool)].copy()
    trades: list[EventTrade] = []
    meta = fetch_metadata_lookup(hourly)
    for row in resolved.itertuples(index=False):
        slug = str(row.slug)
        if slug not in meta:
            continue
        market = hourly[hourly["slug"].eq(slug)].copy().sort_values("timestamp")
        end_date = pd.Timestamp(row.end_date)
        six_h = _price_before(market, end_date - pd.Timedelta(hours=6))
        thirty_h = _price_before(market, end_date - pd.Timedelta(hours=30))
        if six_h is None or thirty_h is None:
            continue
        move = six_h - thirty_h
        outcome = infer_final_yes(meta[slug]["outcome_prices"])
        if six_h >= 0.85 and six_h <= 0.97 and move >= 0.10:
            no_price = 1.0 - six_h
            gross = (1.0 if not outcome else 0.0) / no_price - 1.0
            direction = -1
            px_in = no_price
            px_out = 1.0 if not outcome else 0.0
            note = f"fade_late_yes_surge move={move:.3f}"
        elif six_h <= 0.15 and six_h >= 0.03 and move <= -0.10:
            gross = (1.0 if outcome else 0.0) / six_h - 1.0
            direction = 1
            px_in = six_h
            px_out = 1.0 if outcome else 0.0
            note = f"fade_late_yes_collapse move={move:.3f}"
        else:
            continue
        net = gross - 2 * POLY_NATIVE_ONE_WAY_COST
        trades.append(
            EventTrade(
                strategy="resolution_time_decay",
                market_slug=slug,
                asset="POLY_NATIVE",
                signal_time=end_date - pd.Timedelta(hours=6),
                entry_time=end_date - pd.Timedelta(hours=6),
                exit_time=end_date,
                direction=direction,
                entry_price=px_in,
                exit_price=px_out,
                return_pct=net,
                note=note,
            )
        )
    return sorted(trades, key=lambda item: item.entry_time)


def infer_final_yes(outcome_prices: object) -> bool:
    text = str(outcome_prices)
    values = [float(piece.strip().strip('"')) for piece in text.strip('[]').split(',') if piece.strip()]
    if len(values) < 2:
        raise RuntimeError(f"Unexpected outcomePrices payload: {text}")
    return values[0] >= values[1]


def fetch_metadata_lookup(hourly: pd.DataFrame) -> dict[str, dict[str, object]]:
    base = hourly[["slug", "question"]].drop_duplicates().set_index("slug").to_dict("index")
    meta_path = hourly.attrs.get("metadata_path")
    if meta_path and Path(meta_path).exists():
        meta = pd.read_csv(meta_path).to_dict("records")
        for row in meta:
            base[str(row["slug"])] = row
    return base


def bitcoin_etf_flow_markets(paths: Paths) -> pd.DataFrame:
    universe = fetch_market_universe(paths)
    flows = universe[universe["slug"].astype(str).str.startswith("bitcoin-etf-flows-on-")].copy()
    return flows.sort_values("end_date")


def bitcoin_etf_flow_strategy(flows: pd.DataFrame, hourly: pd.DataFrame, btc: pd.DataFrame) -> list[EventTrade]:
    trades: list[EventTrade] = []
    btc = btc.copy().sort_values("timestamp")
    for row in flows.itertuples(index=False):
        market = hourly[hourly["slug"].eq(str(row.slug))].copy().sort_values("timestamp")
        if market.empty or pd.isna(row.end_date):
            continue
        end_date = pd.Timestamp(row.end_date)
        signal_time = end_date - pd.Timedelta(hours=24)
        yes_price = _price_before(market, signal_time)
        if yes_price is None:
            continue
        if yes_price >= 0.60:
            direction = 1
        elif yes_price <= 0.40:
            direction = -1
        else:
            continue
        entry_time = signal_time + pd.Timedelta(hours=1)
        traded = trade_open_to_open(btc, entry_time, 24)
        if traded is None:
            continue
        exit_time, entry_price, exit_price = traded
        gross = direction * (exit_price / entry_price - 1.0)
        net = gross - 2 * ONE_WAY_COST
        trades.append(
            EventTrade(
                strategy="bitcoin_etf_flow_prediction",
                market_slug=str(row.slug),
                asset="BTC",
                signal_time=signal_time,
                entry_time=entry_time,
                exit_time=exit_time,
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                return_pct=net,
                note=f"24h pre-end yes_price={yes_price:.3f}",
            )
        )
    return sorted(trades, key=lambda item: item.entry_time)


def cross_venue_disagreement_placeholder() -> tuple[list[EventTrade], str, str]:
    return [], "blocked", (
        "Kalshi historical API is publicly reachable, but matching and fetching the exact comparable market tickers/candles "
        "was not completed in this run. This strategy remains blocked rather than fabricated."
    )


def render_report(
    output: Path,
    summary: pd.DataFrame,
    details: pd.DataFrame,
    metadata: pd.DataFrame,
    universe: pd.DataFrame,
    notes: dict[str, str],
) -> None:
    lines = [
        "# Polymarket + Crypto Strategy Validation",
        "",
        "This report backtests ten strategy ideas using real Binance OHLCV plus public Polymarket trade data reconstructed into hourly YES-probability series.",
        "",
        "## Universe and evidence boundary",
        "",
        f"- BTC/ETH/SOL hourly spot data source: Binance public OHLCV pinned in this repo through {END_EXCLUSIVE}.",
        "- Polymarket data source: public Gamma search metadata + public Data API trade history reconstructed to hourly last-trade probability.",
        f"- Crypto trade costs: {ONE_WAY_COST:.2%} one-way (repo standard fee + slippage).",
        f"- Polymarket-native strategy cost assumption: {POLY_NATIVE_ONE_WAY_COST:.2%} one-way slippage/fee proxy.",
        f"- Curated event markets fetched: {len(metadata)}.",
        f"- Broader resolved/flow universe discovered from query basket: {len(universe)} markets.",
        "",
        "## Strategy summary",
        "",
        summary.to_string(index=False),
        "",
        "## Strategy notes",
        "",
    ]
    for strategy, note in notes.items():
        lines.append(f"### {strategy}")
        lines.append(note)
        lines.append("")
    lines.extend([
        "## Top trade samples",
        "",
        details.head(40).to_string(index=False) if not details.empty else "No completed trade ledgers.",
        "",
        "## Curated market metadata",
        "",
        metadata[["slug", "family", "asset", "volume", "end_date", "question"]].to_string(index=False),
        "",
    ])
    output.write_text("\n".join(lines) + "\n")


def run_polymarket_crypto_validation(paths: Paths) -> Path:
    base, _, _ = ensure_dirs(paths)
    metadata = fetch_market_metadata(paths)
    universe = fetch_market_universe(paths)
    catalog = pd.concat(
        [
            metadata,
            universe.assign(asset="POLY_NATIVE", family="universe", bullish_when_yes=True, notes="universe"),
        ],
        ignore_index=True,
        sort=False,
    ).drop_duplicates(subset=["slug"], keep="first")
    catalog_path = base / "market_catalog.csv"
    catalog.to_csv(catalog_path, index=False)
    hourly = load_or_fetch_hourly_series(paths, catalog)
    hourly.attrs["metadata_path"] = str(catalog_path)

    btc = load_crypto_open_series(paths, "BTC")
    eth = load_crypto_open_series(paths, "ETH")
    sol = load_crypto_open_series(paths, "SOL")

    strategy_trades: dict[str, list[EventTrade]] = {}
    notes: dict[str, str] = {}

    broad_markets = hourly[hourly["family"].isin(["btc_etf", "eth_etf", "trump_election", "bitcoin_reserve", "sol_etf", "fed_cut", "recession"])]
    strategy_trades["odds_shock_catchup"] = signal_backtest(
        "odds_shock_catchup", broad_markets, btc, hold_hours=24, delta_threshold=0.08, level_threshold=None, cooldown_hours=12
    )
    notes["odds_shock_catchup"] = "Buy/short BTC when a major Polymarket event reprices >8 points in 24h and BTC has not already overreacted."

    strategy_trades["eth_etf_spread"] = eth_etf_spread_backtest(hourly, eth, btc)
    notes["eth_etf_spread"] = "Long ETH / short BTC for 72h after large ETH ETF approval-odds shocks above a 60% level."

    trump_only = hourly[hourly["family"].eq("trump_election")]
    strategy_trades["trump_policy_beta"] = signal_backtest(
        "trump_policy_beta", trump_only, btc, hold_hours=72, delta_threshold=0.05, level_threshold=0.50, cooldown_hours=24, long_short=False
    )
    notes["trump_policy_beta"] = "Long BTC after positive Trump-election odds shocks when the market is already above 50%, treating odds as a pro-crypto policy proxy."

    fed_only = hourly[hourly["family"].eq("fed_cut")]
    strategy_trades["fed_cut_macro_beta"] = signal_backtest(
        "fed_cut_macro_beta", fed_only, eth, hold_hours=48, delta_threshold=0.08, level_threshold=None, cooldown_hours=24
    )
    notes["fed_cut_macro_beta"] = "Trade ETH on front-end Fed-cut probability shocks, using ETH as the higher-beta macro proxy."

    strategy_trades["wick_with_odds_confirmation"] = wick_with_odds_confirmation(hourly, btc)
    notes["wick_with_odds_confirmation"] = "Buy violent BTC wick flushes only when supportive ETF/election/reserve odds are not simultaneously collapsing."

    crypto_specific = hourly[hourly["family"].isin(["btc_etf", "eth_etf", "sol_etf", "bitcoin_reserve"])]
    # Split by asset to respect asset mappings.
    crypto_trades: list[EventTrade] = []
    for asset, frame in crypto_specific.groupby("asset"):
        asset_prices = {"BTC": btc, "ETH": eth, "SOL": sol}[str(asset)]
        crypto_trades.extend(
            signal_backtest(
                "crypto_specific_lead_lag", frame, asset_prices, hold_hours=48, delta_threshold=0.08, level_threshold=None, cooldown_hours=24
            )
        )
    strategy_trades["crypto_specific_lead_lag"] = sorted(crypto_trades, key=lambda item: item.entry_time)
    notes["crypto_specific_lead_lag"] = "Trade the coin directly when a crypto-specific Polymarket market reprices sharply and spot has not yet caught up."

    blocked_trades, blocked_status, blocked_note = cross_venue_disagreement_placeholder()
    strategy_trades["cross_venue_disagreement"] = blocked_trades
    notes["cross_venue_disagreement"] = blocked_note

    strategy_trades["favorite_longshot_bias"] = favorite_longshot_bias(universe, hourly)
    notes["favorite_longshot_bias"] = "On resolved markets, buy YES favorites >65% or buy NO against YES longshots <35% one day before resolution."

    strategy_trades["resolution_time_decay"] = resolution_time_decay(universe, hourly)
    notes["resolution_time_decay"] = "Fade late 24h-to-6h surges into the 85%-97% or 3%-15% zone, then hold to resolution."

    flows = bitcoin_etf_flow_markets(paths)
    strategy_trades["bitcoin_etf_flow_prediction"] = bitcoin_etf_flow_strategy(flows, hourly, btc)
    notes["bitcoin_etf_flow_prediction"] = "Trade BTC for 24h when pre-resolution ETF-flow odds are strongly skewed toward positive or negative flows."

    summary_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    for strategy, trades in strategy_trades.items():
        status = blocked_status if strategy == "cross_venue_disagreement" else "completed"
        summary_rows.append(summarize_strategy(strategy, trades, notes[strategy], status=status))
        for trade in trades:
            detail_rows.append(asdict(trade))
    summary = pd.DataFrame(summary_rows).sort_values(["status", "ending_equity"], ascending=[True, False])
    details = pd.DataFrame(detail_rows).sort_values("entry_time") if detail_rows else pd.DataFrame()

    run_dir = polymarket_results_dir(paths) / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata.to_csv(run_dir / "market_metadata.csv", index=False)
    catalog.to_csv(run_dir / "market_catalog.csv", index=False)
    universe.to_csv(run_dir / "market_universe.csv", index=False)
    summary.to_csv(run_dir / "strategy_summary.csv", index=False, float_format="%.10g")
    if not details.empty:
        details.to_csv(run_dir / "trade_log.csv", index=False, float_format="%.10g")
    hourly.to_csv(run_dir / "hourly_probabilities.csv", index=False, float_format="%.10g")
    report_path = run_dir / "REPORT.md"
    render_report(report_path, summary, details, metadata, universe, notes)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "report": str(report_path.relative_to(paths.root)),
        "metadata_sha256": sha256(run_dir / "market_metadata.csv"),
        "summary_sha256": sha256(run_dir / "strategy_summary.csv"),
        "hourly_sha256": sha256(run_dir / "hourly_probabilities.csv"),
        "strategy_count": len(summary),
        "completed_count": int(summary["status"].eq("completed").sum()),
        "blocked_count": int(summary["status"].eq("blocked").sum()),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return run_dir
