from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv, sha256
from .funding_negative_panel_validation import (
    AssetFrames,
    dataframe_to_markdown,
    remove_best_trade,
    simulate_always_long_schedule,
    simulate_cash_reserve,
    simulate_daily_asset_dca,
    simulate_random_baseline,
    simulate_signal_strategy,
)
from .polymarket_crypto_validation import _public_search, load_or_fetch_hourly_series

SAMPLE_START = pd.Timestamp("2023-12-18T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-04-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2024-06-01T00:00:00Z")
DAILY_CONTRIBUTION_HOUR_UTC = 9
PRIMARY_LOOKBACK_HOURS = 24
PRIMARY_DELTA_THRESHOLD = 0.12
PRIMARY_LEVEL_THRESHOLD = 0.45
PRIMARY_HOLD_HOURS = 72
PRIMARY_COOLDOWN_HOURS = 24
SENSITIVITY_DELTAS = (0.08, 0.12, 0.15)
SENSITIVITY_LEVELS = (0.35, 0.45)
SENSITIVITY_HOLDS = (48, 72, 96)
BENCHMARK_ASSETS = ("BTC", "ETH", "SOL", "XRP")
RANDOM_SEED = 73
FED_MARKETS: tuple[tuple[str, str], ...] = (
    ("fed-rate-cut-by-march-20", "Fed rate cut by March 20?"),
    ("fed-rate-cut-by-may-1", "Fed rate cut by May 1?"),
    ("fed-rate-cut-by-june-12", "Fed rate cut by June 12?"),
    ("fed-rate-cut-by-september-18", "Fed rate cut by September 18?"),
    ("will-fed-cut-interest-rates-6-times-by-dec-meeting", "Will Fed cut interest rates 6+ times in 2024?"),
)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    lookback_hours: int
    delta_threshold: float
    level_threshold: float
    hold_hours: int
    cooldown_hours: int = PRIMARY_COOLDOWN_HOURS


@dataclass(frozen=True)
class StudyConfig:
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    contribution_hour_utc: int = DAILY_CONTRIBUTION_HOUR_UTC
    sample_start: str = "2023-12-18T00:00:00Z"
    validation_start: str = "2024-04-01T00:00:00Z"
    holdout_start: str = "2024-06-01T00:00:00Z"
    primary_lookback_hours: int = PRIMARY_LOOKBACK_HOURS
    primary_delta_threshold: float = PRIMARY_DELTA_THRESHOLD
    primary_level_threshold: float = PRIMARY_LEVEL_THRESHOLD
    primary_hold_hours: int = PRIMARY_HOLD_HOURS
    primary_cooldown_hours: int = PRIMARY_COOLDOWN_HOURS
    primary_rule: str = (
        "Across the real Polymarket Fed-cut family, if YES odds fall by at least 12 points over the prior "
        "24 completed hours and remain at or below 45%, enter spot BTC long at the next hourly open, hold "
        "72h, then exit and wait 24h before the next entry."
    )


@dataclass(frozen=True)
class Partition:
    name: str
    start: pd.Timestamp
    end_exclusive: pd.Timestamp | None


PARTITIONS = (
    Partition("development_2023q4_2024q1", SAMPLE_START, VALIDATION_START),
    Partition("validation_2024q2_pre_june", VALIDATION_START, HOLDOUT_START),
    Partition("holdout_2024june_onward", HOLDOUT_START, None),
)


def run_fed_hawkish_btc_validation(paths: Paths, seed: int = RANDOM_SEED) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "fed_hawkish_btc" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    metadata = fetch_fed_market_metadata()
    hourly = load_or_fetch_hourly_series(paths, metadata)
    hourly = hourly.loc[hourly["timestamp"] >= pd.Timestamp(config.sample_start)].copy().sort_values(["slug", "timestamp"])
    if hourly.empty:
        raise RuntimeError("No Fed-cut Polymarket hourly series found")

    market = load_market_data(paths, pd.Timestamp(config.sample_start))
    btc_index = market["BTC"].price.set_index("timestamp").index
    sample_end = min(pd.Timestamp(hourly["timestamp"].max()), pd.Timestamp(btc_index.max()))
    hourly = hourly.loc[hourly["timestamp"] <= sample_end].copy().reset_index(drop=True)
    if hourly.empty:
        raise RuntimeError("Fed-cut markets do not overlap the BTC sample")

    for asset in BENCHMARK_ASSETS:
        market[asset].price = market[asset].price.loc[market[asset].price["timestamp"] <= sample_end].reset_index(drop=True)
        if market[asset].price.empty:
            raise RuntimeError(f"{asset} price series does not overlap the Fed-cut sample")

    schedule = build_daily_contribution_schedule(
        market["BTC"].price,
        config.initial_capital,
        config.contribution_hour_utc,
        end_time=sample_end,
    )
    final_closes = {asset: float(frames.price["close"].iloc[-1]) for asset, frames in market.items()}

    signal_panel = build_signal_panel(
        hourly,
        market["BTC"].price.set_index("timestamp").index,
        StrategySpec(
            name="fed_hawkish_btc_swing",
            lookback_hours=config.primary_lookback_hours,
            delta_threshold=config.primary_delta_threshold,
            level_threshold=config.primary_level_threshold,
            hold_hours=config.primary_hold_hours,
        ),
    )

    cash = simulate_cash_reserve(market["BTC"].price, schedule, final_closes)
    daily_benchmarks = [
        simulate_daily_asset_dca(market[asset].price, schedule, config.one_way_cost, final_closes, asset)
        for asset in BENCHMARK_ASSETS
    ]
    primary = simulate_signal_strategy(
        market,
        schedule,
        config.one_way_cost,
        final_closes,
        signal_panel,
        "fed_hawkish_btc_swing",
    )
    always_long = simulate_always_long_schedule(
        market,
        schedule,
        config.one_way_cost,
        final_closes,
        signal_panel,
    )
    random_baseline = simulate_random_baseline(
        market,
        schedule,
        config.one_way_cost,
        final_closes,
        signal_panel,
        seed,
    )

    sensitivity = run_sensitivity_suite(market, hourly, schedule, final_closes, config.one_way_cost)
    hostile = run_hostile_checks(
        market,
        schedule,
        final_closes,
        signal_panel,
        primary.summary,
        config.one_way_cost,
        seed,
    )
    primary_partition = summarize_partitions(primary.equity, primary.ledger)
    primary.summary = enrich_primary_summary(primary.summary, primary_partition)
    verdict, reason = classify_verdict(primary.summary, daily_benchmarks, hostile, sensitivity)

    summary_frame = pd.DataFrame(
        [
            cash.summary | {"verdict": "Baseline"},
            *[item.summary | {"verdict": "Baseline"} for item in daily_benchmarks],
            always_long.summary | {"verdict": "Baseline"},
            random_baseline.summary | {"verdict": "Baseline"},
            primary.summary | {"verdict": verdict},
        ]
    )
    trade_log = pd.concat(
        [
            cash.ledger.assign(strategy="cash_reserve"),
            *[item.ledger.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            always_long.ledger.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.ledger.assign(strategy="random_asset_schedule_baseline"),
            primary.ledger.assign(strategy="fed_hawkish_btc_swing"),
        ],
        ignore_index=True,
    )
    equity_curve = pd.concat(
        [
            cash.equity.assign(strategy="cash_reserve"),
            *[item.equity.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            always_long.equity.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.equity.assign(strategy="random_asset_schedule_baseline"),
            primary.equity.assign(strategy="fed_hawkish_btc_swing"),
        ],
        ignore_index=True,
    )
    partition_frame = pd.concat(
        [
            summarize_partitions(cash.equity, cash.ledger).assign(strategy="cash_reserve"),
            *[
                summarize_partitions(item.equity, item.ledger).assign(strategy=str(item.summary["strategy"]))
                for item in daily_benchmarks
            ],
            summarize_partitions(always_long.equity, always_long.ledger).assign(strategy="always_long_equal_weight_schedule"),
            summarize_partitions(random_baseline.equity, random_baseline.ledger).assign(strategy="random_asset_schedule_baseline"),
            primary_partition.assign(strategy="fed_hawkish_btc_swing"),
        ],
        ignore_index=True,
    )

    summary_frame.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    trade_log.to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    equity_curve.to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    partition_frame.to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    signal_panel.to_csv(output / "signal_panel.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    hourly[["timestamp", "slug", "yes_price", "trade_count", "traded_notional"]].to_csv(
        output / "fed_cut_hourly_odds.csv", index=False, float_format="%.17g"
    )

    manifest = {
        "config": asdict(config),
        "assets": {asset: spot_provenance(paths, asset) for asset in BENCHMARK_ASSETS},
        "market_slugs": [slug for slug, _ in FED_MARKETS],
        "market_questions": metadata[["slug", "question"]].to_dict("records"),
        "market_paths": {
            slug: str((paths.data / "polymarket_validation" / "hourly" / f"{slug}.csv.gz").relative_to(paths.root))
            for slug, _ in FED_MARKETS
        },
        "market_sha256": {
            slug: sha256(paths.data / "polymarket_validation" / "hourly" / f"{slug}.csv.gz")
            for slug, _ in FED_MARKETS
            if (paths.data / "polymarket_validation" / "hourly" / f"{slug}.csv.gz").exists()
        },
        "sample_start": str(hourly["timestamp"].min().isoformat()),
        "sample_end": str(sample_end.isoformat()),
        "raw_signal_count": int(len(signal_panel)),
        "verdict_reason": reason,
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, summary_frame, hostile, reason)
    print(f"Fed hawkish BTC validation written to {output}", flush=True)
    return summary_frame


def fetch_fed_market_metadata() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for slug, question_hint in FED_MARKETS:
        payload = _public_search("fed cut interest rates")
        found = None
        for event in payload.get("events", []):
            for market in event.get("markets", []):
                if market.get("slug") == slug:
                    found = market
                    break
            if found:
                break
        if not found:
            raise RuntimeError(f"Could not find Polymarket slug {slug}")
        rows.append(
            {
                "slug": slug,
                "query": "fed cut interest rates",
                "asset": "BTC",
                "family": "fed_cut_hawkish",
                "bullish_when_yes": True,
                "notes": "Front-end Fed easing odds used inversely as a hawkish repricing trigger",
                "question": found.get("question") or question_hint,
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
    return pd.DataFrame(rows).sort_values("slug").reset_index(drop=True)


def load_market_data(paths: Paths, sample_start: pd.Timestamp) -> dict[str, AssetFrames]:
    market: dict[str, AssetFrames] = {}
    for asset in BENCHMARK_ASSETS:
        price = load_ohlcv(paths, asset, "1h").loc[sample_start:].reset_index()
        price["timestamp"] = pd.to_datetime(price["timestamp"], utc=True)
        market[asset] = AssetFrames(price=price, funding=pd.DataFrame())
    return market


def build_daily_contribution_schedule(
    frame: pd.DataFrame,
    initial_capital: float,
    contribution_hour_utc: int,
    end_time: pd.Timestamp | None = None,
) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if end_time is not None:
        slots = slots.loc[slots <= end_time]
    if slots.empty:
        raise RuntimeError("No BTC contribution slots available in the sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def build_signal_panel(hourly: pd.DataFrame, price_index: pd.Index, spec: StrategySpec) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for slug, frame in hourly.groupby("slug", sort=False):
        ordered = frame.copy().sort_values("timestamp").reset_index(drop=True)
        ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True)
        ordered["odds_delta"] = ordered["yes_price"] - ordered["yes_price"].shift(spec.lookback_hours)
        signals = ordered.loc[
            (ordered["odds_delta"] <= -spec.delta_threshold) & (ordered["yes_price"] <= spec.level_threshold)
        ].copy()
        if signals.empty:
            continue
        signals["entry_time"] = signals["timestamp"] + pd.Timedelta(hours=1)
        signals["exit_time"] = signals["entry_time"] + pd.Timedelta(hours=int(spec.hold_hours))
        signals = signals.loc[signals["entry_time"].isin(price_index) & signals["exit_time"].isin(price_index)]
        for row in signals.itertuples(index=False):
            rows.append(
                {
                    "signal_time": pd.Timestamp(row.timestamp),
                    "entry_time": pd.Timestamp(row.entry_time),
                    "exit_time": pd.Timestamp(row.exit_time),
                    "asset": "BTC",
                    "funding_rate": float(row.odds_delta),
                    "mark_price": float(row.yes_price),
                    "source_symbol": str(slug),
                    "yes_price": float(row.yes_price),
                    "odds_delta": float(row.odds_delta),
                    "trade_count": float(row.trade_count),
                    "traded_notional": float(row.traded_notional),
                    "slug": str(slug),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "signal_time",
                "entry_time",
                "exit_time",
                "asset",
                "funding_rate",
                "mark_price",
                "source_symbol",
                "yes_price",
                "odds_delta",
                "trade_count",
                "traded_notional",
                "slug",
            ]
        )
    frame = pd.DataFrame(rows).sort_values(["entry_time", "slug"]).reset_index(drop=True)
    chosen: list[dict[str, object]] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for row in frame.itertuples(index=False):
        entry = pd.Timestamp(row.entry_time)
        if entry < next_ok:
            continue
        chosen.append(row._asdict())
        next_ok = pd.Timestamp(row.exit_time) + pd.Timedelta(hours=int(spec.cooldown_hours))
    return pd.DataFrame(chosen).sort_values("entry_time").reset_index(drop=True)


def run_sensitivity_suite(
    market: dict[str, AssetFrames],
    hourly: pd.DataFrame,
    schedule: pd.Series,
    final_closes: dict[str, float],
    one_way_cost: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    btc_index = market["BTC"].price.set_index("timestamp").index
    for delta in SENSITIVITY_DELTAS:
        for level in SENSITIVITY_LEVELS:
            for hold_hours in SENSITIVITY_HOLDS:
                spec = StrategySpec(
                    name=f"delta_{delta:.2f}_level_{level:.2f}_hold_{hold_hours}h",
                    lookback_hours=PRIMARY_LOOKBACK_HOURS,
                    delta_threshold=delta,
                    level_threshold=level,
                    hold_hours=hold_hours,
                )
                signals = build_signal_panel(hourly, btc_index, spec)
                result = simulate_signal_strategy(
                    market,
                    schedule,
                    one_way_cost,
                    final_closes,
                    signals,
                    spec.name,
                )
                rows.append(
                    {
                        "delta_threshold": delta,
                        "level_threshold": level,
                        "hold_hours": hold_hours,
                        "trade_count": int(result.summary["event_count"]),
                        "terminal_value": float(result.summary["terminal_value"]),
                        "net_return": float(result.summary["net_return"]),
                        "avg_trade_return": float(result.summary["avg_trade_return"]),
                        "win_rate": float(result.summary["win_rate"]),
                    }
                )
    return pd.DataFrame(rows).sort_values(["delta_threshold", "level_threshold", "hold_hours"]).reset_index(drop=True)


def run_hostile_checks(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
    primary_summary: dict[str, object],
    one_way_cost: float,
    seed: int,
) -> pd.DataFrame:
    doubled_cost = simulate_signal_strategy(
        market,
        schedule,
        one_way_cost * 2,
        final_closes,
        signals,
        "fed_hawkish_btc_swing_doubled_cost",
    )
    without_best = remove_best_trade(market, schedule, one_way_cost, final_closes, signals)
    always_long = simulate_always_long_schedule(market, schedule, one_way_cost, final_closes, signals)
    random_baseline = simulate_random_baseline(market, schedule, one_way_cost, final_closes, signals, seed)
    return pd.DataFrame(
        [
            {
                "check": "doubled_cost",
                "terminal_value": float(doubled_cost.summary["terminal_value"]),
                "net_return": float(doubled_cost.summary["net_return"]),
                "beats_primary": float(doubled_cost.summary["terminal_value"]) >= float(primary_summary["terminal_value"]),
            },
            {
                "check": "exclude_best_trade",
                "terminal_value": float(without_best.summary["terminal_value"]),
                "net_return": float(without_best.summary["net_return"]),
                "beats_primary": float(without_best.summary["terminal_value"]) >= float(primary_summary["terminal_value"]),
            },
            {
                "check": "always_long_same_schedule",
                "terminal_value": float(always_long.summary["terminal_value"]),
                "net_return": float(always_long.summary["net_return"]),
                "beats_primary": float(always_long.summary["terminal_value"]) >= float(primary_summary["terminal_value"]),
            },
            {
                "check": "random_asset_schedule",
                "terminal_value": float(random_baseline.summary["terminal_value"]),
                "net_return": float(random_baseline.summary["net_return"]),
                "beats_primary": float(random_baseline.summary["terminal_value"]) >= float(primary_summary["terminal_value"]),
            },
        ]
    )


def classify_verdict(
    primary_summary: dict[str, object],
    daily_benchmarks: list,
    hostile: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> tuple[str, str]:
    btc_dca = next(item for item in daily_benchmarks if item.summary["strategy"] == "daily_btc_dca")
    holdout_trades = int(primary_summary.get("holdout_trade_count", 0))
    if int(primary_summary["event_count"]) < 5:
        return "Inconclusive", "Too few total trades to claim a repeatable edge."
    if float(primary_summary["terminal_value"]) <= float(btc_dca.summary["terminal_value"]):
        return "Rejected", "The strategy failed the decisive BTC DCA benchmark on the same released-capital schedule."
    if holdout_trades < 3:
        return "Inconclusive", "The rule produced fewer than three holdout trades after 2024-06-01."
    robust_nearby = sensitivity.loc[sensitivity["terminal_value"] >= float(btc_dca.summary["terminal_value"])]
    nearby_pass_rate = float(len(robust_nearby) / len(sensitivity)) if len(sensitivity) else 0.0
    hostile_fail = hostile.loc[hostile["check"].isin(["always_long_same_schedule", "random_asset_schedule"]), "beats_primary"].any()
    if hostile_fail:
        return "Rejected", "A same-schedule baseline matched or beat the signal, so the Fed-odds filter added no value."
    if nearby_pass_rate < 0.25:
        return "Rejected", "Only a small minority of nearby parameter choices beat BTC DCA, so the edge is not robust."
    return "Paper-trading candidate", "The preregistered rule beat BTC DCA and cleared the main robustness checks."


def summarize_partitions(equity: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for partition in PARTITIONS:
        mask = equity["timestamp"] >= partition.start
        if partition.end_exclusive is not None:
            mask = mask & (equity["timestamp"] < partition.end_exclusive)
        subset = equity.loc[mask]
        if subset.empty:
            continue
        if ledger.empty:
            trade_count = 0
        else:
            trade_mask = ledger["timestamp"] >= partition.start
            if partition.end_exclusive is not None:
                trade_mask = trade_mask & (ledger["timestamp"] < partition.end_exclusive)
            trade_count = int(
                ledger.loc[trade_mask, "kind"].astype(str).str.contains("entry|buy", regex=True, na=False).sum()
            )
        start_equity = float(subset["equity"].iloc[0])
        end_equity = float(subset["equity"].iloc[-1])
        rows.append(
            {
                "partition": partition.name,
                "start": partition.start,
                "end_exclusive": partition.end_exclusive,
                "terminal_value": end_equity,
                "net_return": end_equity / start_equity - 1 if start_equity else float("nan"),
                "event_count": trade_count,
            }
        )
    return pd.DataFrame(rows)


def enrich_primary_summary(primary_summary: dict[str, object], partition_frame: pd.DataFrame) -> dict[str, object]:
    holdout = partition_frame.loc[partition_frame["partition"].eq("holdout_2024june_onward")]
    if holdout.empty:
        primary_summary["holdout_trade_count"] = 0
        primary_summary["holdout_net_return"] = float("nan")
    else:
        primary_summary["holdout_trade_count"] = int(holdout["event_count"].iloc[0])
        primary_summary["holdout_net_return"] = float(holdout["net_return"].iloc[0])
    return primary_summary


def spot_provenance(paths: Paths, asset: str) -> dict[str, object]:
    raw_path = paths.raw / f"{asset}_1h.csv.gz"
    raw = pd.read_csv(raw_path, usecols=["timestamp", "source_symbol"])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True, format="mixed")
    return {
        "spot_path": str(raw_path.relative_to(paths.root)),
        "spot_sha256": sha256(raw_path),
        "spot_rows": int(len(raw)),
        "spot_first_timestamp": raw["timestamp"].min().isoformat(),
        "spot_last_timestamp": raw["timestamp"].max().isoformat(),
    }


def write_report(
    output: Path,
    summary: pd.DataFrame,
    hostile: pd.DataFrame,
    verdict_reason: str,
) -> None:
    primary = summary.loc[summary["strategy"].eq("fed_hawkish_btc_swing")].iloc[0]
    baselines = summary.loc[
        summary["strategy"].isin(
            [
                "daily_btc_dca",
                "daily_eth_dca",
                "daily_sol_dca",
                "daily_xrp_dca",
                "always_long_equal_weight_schedule",
                "random_asset_schedule_baseline",
            ]
        )
    ]
    lines = [
        "# Falling Fed-cut Odds → BTC Swing Validation",
        "",
        f"Run artifact: `{output / 'REPORT.md'}`",
        "",
        "## Key findings",
        "",
        "- **Primary rule tested:** across the real Polymarket **Fed-cut family** (March / May / June / September cut-deadline markets plus the `6+ cuts in 2024` market), if YES odds fall by at least **12 points over 24h** and remain at or below **45%**, enter **spot BTC long** at the **next hourly open**, hold **72h**, then exit and wait **24h** before the next entry.",
        "- **Sample:** `2023-12-18` through the final overlapping Fed-market observation in the pinned repo, using only real Polymarket hourly YES odds plus real Binance BTC/ETH/SOL/XRP hourly spot candles.",
        "- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA**, plus **same-schedule always-long equal-weight** and **random-asset schedule** baselines.",
        "",
        "## Result table",
        "",
        dataframe_to_markdown(
            pd.concat([baselines, primary.to_frame().T], ignore_index=True)[
                ["strategy", "terminal_value", "event_count", "avg_trade_return", "win_rate", "verdict"]
            ]
        ),
        "",
        "## Honest conclusion",
        "",
        f"> **{primary['verdict']}.** {verdict_reason}",
        "",
        "## Decisive hostile checks",
        "",
        dataframe_to_markdown(hostile[["check", "terminal_value", "net_return", "beats_primary"]]),
        "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
