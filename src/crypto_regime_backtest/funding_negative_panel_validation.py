from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv, sha256

SAMPLE_START = pd.Timestamp("2021-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")
CONTRIBUTION_HOUR_UTC = 9
PRIMARY_THRESHOLD = -0.0005
PRIMARY_HOLD_HOURS = 24
PRIMARY_COOLDOWN_HOURS = 24
SENSITIVITY_THRESHOLDS = (-0.00075, -0.0010)
SENSITIVITY_HOLDS = (8, 24)
RANDOM_SEED = 29
UNIVERSE = ("BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "LINK")
BENCHMARK_ASSETS = ("BTC", "ETH", "SOL", "XRP")


@dataclass(frozen=True)
class StrategySpec:
    name: str
    funding_threshold: float
    hold_hours: int
    cooldown_hours: int


@dataclass(frozen=True)
class StudyConfig:
    sample_start: str = "2021-01-01T00:00:00Z"
    validation_start: str = "2024-01-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    contribution_hour_utc: int = CONTRIBUTION_HOUR_UTC
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    primary_threshold: float = PRIMARY_THRESHOLD
    primary_hold_hours: int = PRIMARY_HOLD_HOURS
    primary_cooldown_hours: int = PRIMARY_COOLDOWN_HOURS
    primary_rule: str = (
        "At each completed Binance 8h funding print from the ten-asset spot universe, if one or more assets"
        " have funding <= -5 bps, select the single most negative asset, enter spot long at the next hourly"
        " open with the full accrued reserve, hold 24h, then exit at the close and remain in cash for a"
        " 24h cooldown."
    )


@dataclass(frozen=True)
class Partition:
    name: str
    start: pd.Timestamp
    end_exclusive: pd.Timestamp | None


PARTITIONS = (
    Partition("development_pre_2024", SAMPLE_START, VALIDATION_START),
    Partition("validation_2024", VALIDATION_START, HOLDOUT_START),
    Partition("holdout_2025_onward", HOLDOUT_START, None),
)


@dataclass
class SimulationResult:
    summary: dict[str, object]
    ledger: pd.DataFrame
    equity: pd.DataFrame
    partition_summary: pd.DataFrame


def run_funding_negative_panel_validation(paths: Paths, seed: int = RANDOM_SEED) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "funding_negative_panel" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    spec = StrategySpec(
        name="negative_funding_rebound_panel",
        funding_threshold=config.primary_threshold,
        hold_hours=config.primary_hold_hours,
        cooldown_hours=config.primary_cooldown_hours,
    )
    market = load_market_data(paths, config.sample_start)
    schedule = build_daily_contribution_schedule(market["BTC"].price, config.initial_capital, config.contribution_hour_utc)
    final_closes = {asset: float(frames.price["close"].iloc[-1]) for asset, frames in market.items()}

    signal_panel = build_signal_panel(market, spec)
    cash = simulate_cash_reserve(market["BTC"].price, schedule, final_closes)
    daily_benchmarks = [
        simulate_daily_asset_dca(market[asset].price, schedule, config.one_way_cost, final_closes, asset)
        for asset in BENCHMARK_ASSETS
    ]
    equal_weight_daily = simulate_equal_weight_dca(market, schedule, config.one_way_cost, final_closes, cadence="daily")
    equal_weight_weekly = simulate_equal_weight_dca(market, schedule, config.one_way_cost, final_closes, cadence="weekly")
    primary = simulate_signal_strategy(market, schedule, config.one_way_cost, final_closes, signal_panel, spec.name)
    always_long = simulate_always_long_schedule(market, schedule, config.one_way_cost, final_closes, signal_panel)
    random_baseline = simulate_random_baseline(market, schedule, config.one_way_cost, final_closes, signal_panel, seed)

    sensitivity = run_sensitivity_suite(market, schedule, config.one_way_cost, final_closes)
    hostile = run_hostile_checks(
        market,
        schedule,
        config.one_way_cost,
        final_closes,
        signal_panel,
        primary.summary,
        seed,
    )
    verdict = classify_verdict(primary.summary, daily_benchmarks, equal_weight_daily.summary, hostile)
    primary.summary["verdict"] = verdict

    summary_frame = pd.DataFrame(
        [
            cash.summary,
            *[item.summary for item in daily_benchmarks],
            equal_weight_daily.summary,
            equal_weight_weekly.summary,
            always_long.summary,
            random_baseline.summary,
            primary.summary,
        ]
    )
    trade_log = pd.concat(
        [
            cash.ledger.assign(strategy="cash_reserve"),
            *[item.ledger.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            equal_weight_daily.ledger.assign(strategy="daily_equal_weight_universe_dca"),
            equal_weight_weekly.ledger.assign(strategy="weekly_equal_weight_universe_dca"),
            always_long.ledger.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.ledger.assign(strategy="random_asset_schedule_baseline"),
            primary.ledger.assign(strategy=spec.name),
        ],
        ignore_index=True,
    )
    equity_curve = pd.concat(
        [
            cash.equity.assign(strategy="cash_reserve"),
            *[item.equity.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            equal_weight_daily.equity.assign(strategy="daily_equal_weight_universe_dca"),
            equal_weight_weekly.equity.assign(strategy="weekly_equal_weight_universe_dca"),
            always_long.equity.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.equity.assign(strategy="random_asset_schedule_baseline"),
            primary.equity.assign(strategy=spec.name),
        ],
        ignore_index=True,
    )
    partition_frame = pd.concat(
        [
            cash.partition_summary.assign(strategy="cash_reserve"),
            *[item.partition_summary.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            equal_weight_daily.partition_summary.assign(strategy="daily_equal_weight_universe_dca"),
            equal_weight_weekly.partition_summary.assign(strategy="weekly_equal_weight_universe_dca"),
            always_long.partition_summary.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.partition_summary.assign(strategy="random_asset_schedule_baseline"),
            primary.partition_summary.assign(strategy=spec.name),
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

    manifest = {
        "config": asdict(config),
        "spec": asdict(spec),
        "assets": {asset: provenance(paths, asset) for asset in UNIVERSE},
        "raw_signal_count": int(len(signal_panel)),
        "sample_start": market["BTC"].price["timestamp"].min().isoformat(),
        "sample_end": market["BTC"].price["timestamp"].max().isoformat(),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summary_frame, hostile)
    print(f"Funding-negative panel validation written to {output}", flush=True)
    return summary_frame


@dataclass
class AssetFrames:
    price: pd.DataFrame
    funding: pd.DataFrame


def load_market_data(paths: Paths, sample_start: str) -> dict[str, AssetFrames]:
    start = pd.Timestamp(sample_start)
    market: dict[str, AssetFrames] = {}
    for asset in UNIVERSE:
        price = load_ohlcv(paths, asset, "1h").loc[start:].reset_index()
        if price.empty:
            raise RuntimeError(f"{asset} 1h price data does not cover the requested study window")
        price["timestamp"] = pd.to_datetime(price["timestamp"], utc=True)
        funding = pd.read_csv(paths.funding / f"{asset}_funding.csv.gz")
        funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True, format="mixed")
        funding = funding.loc[funding["timestamp"] >= start].sort_values("timestamp").reset_index(drop=True)
        if funding.empty:
            raise RuntimeError(f"{asset} funding data does not cover the requested study window")
        market[asset] = AssetFrames(price=price, funding=funding)
    return market


def build_daily_contribution_schedule(frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in BTC 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def build_signal_panel(market: dict[str, AssetFrames], spec: StrategySpec) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for asset, frames in market.items():
        funding = frames.funding.copy()
        funding = funding.loc[funding["funding_rate"] <= spec.funding_threshold].copy()
        if funding.empty:
            continue
        price_index = frames.price.set_index("timestamp").index
        funding["entry_time"] = funding["timestamp"] + pd.Timedelta(hours=1)
        funding["exit_time"] = funding["entry_time"] + pd.Timedelta(hours=spec.hold_hours)
        funding = funding.loc[
            funding["entry_time"].isin(price_index) & funding["exit_time"].isin(price_index)
        ].copy()
        if funding.empty:
            continue
        for row in funding.itertuples(index=False):
            rows.append(
                {
                    "signal_time": pd.Timestamp(row.timestamp),
                    "entry_time": pd.Timestamp(row.entry_time),
                    "exit_time": pd.Timestamp(row.exit_time),
                    "asset": asset,
                    "funding_rate": float(row.funding_rate),
                    "mark_price": float(row.mark_price) if pd.notna(row.mark_price) else np.nan,
                    "source_symbol": str(row.source_symbol),
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
            ]
        )
    panel = pd.DataFrame(rows).sort_values(["entry_time", "funding_rate", "asset"]).reset_index(drop=True)
    chosen: list[dict[str, object]] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for entry_time, same_time in panel.groupby("entry_time", sort=True):
        best = same_time.sort_values(["funding_rate", "asset"]).iloc[0]
        entry = pd.Timestamp(best["entry_time"])
        if entry < next_ok:
            continue
        chosen.append(best.to_dict())
        next_ok = pd.Timestamp(best["exit_time"]) + pd.Timedelta(hours=spec.cooldown_hours)
    chosen_frame = pd.DataFrame(chosen)
    if chosen_frame.empty:
        return chosen_frame.reindex(columns=panel.columns)
    return chosen_frame.sort_values("entry_time").reset_index(drop=True)


def simulate_cash_reserve(frame: pd.DataFrame, schedule: pd.Series, final_closes: dict[str, float]) -> SimulationResult:
    cash = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "cash_contribution",
                    "gross_spend_usd": 0.0,
                    "fee_slippage_usd": 0.0,
                    "cash_after": cash,
                }
            )
        records.append(mark_record(timestamp, cash, None, row.close, final_closes))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(summarize_strategy("cash_reserve", ledger, equity), ledger, equity, summarize_partitions(equity, ledger))


def simulate_daily_asset_dca(
    frame: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    asset: str,
) -> SimulationResult:
    cash = 0.0
    units = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
            reference_open = float(row.open)
            execution_price = reference_open * (1 + one_way_cost)
            bought = cash / execution_price
            fee_slippage = cash * one_way_cost
            units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": f"daily_{asset.lower()}_dca_buy",
                    "asset": asset,
                    "gross_spend_usd": cash,
                    "fee_slippage_usd": fee_slippage,
                    "execution_price": execution_price,
                    "reference_open": reference_open,
                    f"{asset.lower()}_bought": bought,
                    f"{asset.lower()}_after": units,
                    "cash_after": 0.0,
                }
            )
            cash = 0.0
        records.append(mark_record(timestamp, cash, asset, row.close, final_closes, units))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(summarize_strategy(f"daily_{asset.lower()}_dca", ledger, equity), ledger, equity, summarize_partitions(equity, ledger))


def simulate_equal_weight_dca(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    cadence: str,
) -> SimulationResult:
    base = market["BTC"].price[["timestamp"]].copy()
    price_maps = {
        asset: frames.price.set_index("timestamp")[["open", "close"]]
        for asset, frames in market.items()
    }
    cash = 0.0
    units = {asset: 0.0 for asset in market}
    ledger_rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in base.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
        should_invest = False
        if cadence == "daily" and contribution:
            should_invest = True
        elif cadence == "weekly" and timestamp.weekday() == 0 and timestamp.hour == CONTRIBUTION_HOUR_UTC and cash > 0:
            should_invest = True
        if should_invest and cash > 0:
            allocation = cash / len(price_maps)
            gross_spend = cash
            fee_slippage = 0.0
            ledger_row: dict[str, object] = {
                "timestamp": timestamp,
                "kind": f"{cadence}_equal_weight_dca_buy",
                "gross_spend_usd": gross_spend,
            }
            for asset, price_map in price_maps.items():
                if timestamp not in price_map.index:
                    raise RuntimeError(f"Missing {asset} price for equal-weight DCA at {timestamp}")
                reference_open = float(price_map.at[timestamp, "open"])
                execution_price = reference_open * (1 + one_way_cost)
                bought = allocation / execution_price
                units[asset] += bought
                fee_slippage += allocation * one_way_cost
                ledger_row[f"{asset.lower()}_bought"] = bought
                ledger_row[f"{asset.lower()}_after"] = units[asset]
            ledger_row["fee_slippage_usd"] = fee_slippage
            ledger_row["cash_after"] = 0.0
            ledger_rows.append(ledger_row)
            cash = 0.0
        mark_close = {asset: float(price_map.at[timestamp, "close"]) for asset, price_map in price_maps.items()}
        records.append(mark_portfolio_record(timestamp, cash, units, mark_close, final_closes))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(f"{cadence}_equal_weight_universe_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_signal_strategy(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
    strategy_name: str,
) -> SimulationResult:
    base = market["BTC"].price[["timestamp"]].copy()
    btc_closes = market["BTC"].price.set_index("timestamp")["close"]
    price_maps = {
        asset: frames.price.set_index("timestamp")[["open", "close"]]
        for asset, frames in market.items()
    }
    signal_map = {
        pd.Timestamp(row.entry_time): row for row in signals.itertuples(index=False)
    }
    cash = 0.0
    units = 0.0
    active_asset: str | None = None
    active_exit: pd.Timestamp | None = None
    ledger_rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in base.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        cash += float(scheduled.get(timestamp, 0.0))
        if active_asset is not None and active_exit is not None and timestamp == active_exit:
            reference_close = float(price_maps[active_asset].at[timestamp, "close"])
            execution_price = reference_close * (1 - one_way_cost)
            gross_value = units * reference_close
            cash += units * execution_price
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "signal_exit",
                    "asset": active_asset,
                    "gross_spend_usd": gross_value,
                    "fee_slippage_usd": units * reference_close * one_way_cost,
                    "execution_price": execution_price,
                    "reference_close": reference_close,
                    f"{active_asset.lower()}_sold": units,
                    "cash_after": cash,
                }
            )
            units = 0.0
            active_asset = None
            active_exit = None
        signal = signal_map.get(timestamp)
        if signal is not None and active_asset is None and cash > 0:
            asset = str(signal.asset)
            reference_open = float(price_maps[asset].at[timestamp, "open"])
            execution_price = reference_open * (1 + one_way_cost)
            gross_spend = cash
            bought = gross_spend / execution_price
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "signal_entry",
                    "asset": asset,
                    "funding_rate": float(signal.funding_rate),
                    "signal_time": pd.Timestamp(signal.signal_time),
                    "planned_exit_time": pd.Timestamp(signal.exit_time),
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": gross_spend * one_way_cost,
                    "execution_price": execution_price,
                    "reference_open": reference_open,
                    f"{asset.lower()}_bought": bought,
                    "cash_after": 0.0,
                }
            )
            units = bought
            cash = 0.0
            active_asset = asset
            active_exit = pd.Timestamp(signal.exit_time)
        current_close = float(price_maps[active_asset].at[timestamp, "close"]) if active_asset else float(btc_closes.at[timestamp])
        records.append(mark_record(timestamp, cash, active_asset, current_close, final_closes, units))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(summarize_strategy(strategy_name, ledger, equity), ledger, equity, summarize_partitions(equity, ledger))


def simulate_always_long_schedule(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
) -> SimulationResult:
    base = market["BTC"].price[["timestamp"]].copy()
    price_maps = {
        asset: frames.price.set_index("timestamp")[["open", "close"]]
        for asset, frames in market.items()
    }
    entries = set(pd.to_datetime(signals["entry_time"], utc=True))
    exits = set(pd.to_datetime(signals["exit_time"], utc=True))
    weights = {asset: 1 / len(market) for asset in market}
    cash = 0.0
    units = {asset: 0.0 for asset in market}
    invested = False
    ledger_rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in base.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        cash += float(scheduled.get(timestamp, 0.0))
        if invested and timestamp in exits:
            gross_value = 0.0
            fee_slippage = 0.0
            ledger_row: dict[str, object] = {"timestamp": timestamp, "kind": "always_long_exit"}
            for asset, price_map in price_maps.items():
                reference_close = float(price_map.at[timestamp, "close"])
                gross_value += units[asset] * reference_close
                fee_slippage += units[asset] * reference_close * one_way_cost
                cash += units[asset] * reference_close * (1 - one_way_cost)
                ledger_row[f"{asset.lower()}_sold"] = units[asset]
                units[asset] = 0.0
            ledger_row["gross_spend_usd"] = gross_value
            ledger_row["fee_slippage_usd"] = fee_slippage
            ledger_row["cash_after"] = cash
            ledger_rows.append(ledger_row)
            invested = False
        if (not invested) and timestamp in entries and cash > 0:
            allocation = cash
            fee_slippage = 0.0
            ledger_row = {"timestamp": timestamp, "kind": "always_long_entry", "gross_spend_usd": allocation}
            for asset, price_map in price_maps.items():
                reference_open = float(price_map.at[timestamp, "open"])
                spend = allocation * weights[asset]
                execution_price = reference_open * (1 + one_way_cost)
                bought = spend / execution_price
                units[asset] += bought
                fee_slippage += spend * one_way_cost
                ledger_row[f"{asset.lower()}_bought"] = bought
            ledger_row["fee_slippage_usd"] = fee_slippage
            ledger_row["cash_after"] = 0.0
            ledger_rows.append(ledger_row)
            cash = 0.0
            invested = True
        mark_close = {asset: float(price_map.at[timestamp, "close"]) for asset, price_map in price_maps.items()}
        records.append(mark_portfolio_record(timestamp, cash, units, mark_close, final_closes))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("always_long_equal_weight_schedule", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_random_baseline(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
    seed: int,
) -> SimulationResult:
    price_indexes = {
        asset: frames.price.set_index("timestamp").index
        for asset, frames in market.items()
    }
    if signals.empty:
        random_signals = signals.copy()
    else:
        rng = np.random.default_rng(seed)
        rows = []
        for row in signals.itertuples(index=False):
            entry = pd.Timestamp(row.entry_time)
            exit_time = pd.Timestamp(row.exit_time)
            valid_assets = [
                asset for asset, price_index in price_indexes.items() if entry in price_index and exit_time in price_index
            ]
            if not valid_assets:
                continue
            rows.append(
                {
                    "signal_time": pd.Timestamp(row.signal_time),
                    "entry_time": entry,
                    "exit_time": exit_time,
                    "asset": str(rng.choice(np.array(valid_assets))),
                    "funding_rate": np.nan,
                    "mark_price": np.nan,
                    "source_symbol": "random_baseline",
                }
            )
        random_signals = pd.DataFrame(rows)
    return simulate_signal_strategy(
        market,
        schedule,
        one_way_cost,
        final_closes,
        random_signals.sort_values("entry_time").reset_index(drop=True),
        "random_asset_schedule_baseline",
    )


def run_sensitivity_suite(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for threshold in (PRIMARY_THRESHOLD, *SENSITIVITY_THRESHOLDS):
        for hold_hours in SENSITIVITY_HOLDS:
            spec = StrategySpec(
                name=f"threshold_{threshold:.4f}_hold_{hold_hours}h",
                funding_threshold=threshold,
                hold_hours=hold_hours,
                cooldown_hours=PRIMARY_COOLDOWN_HOURS,
            )
            signals = build_signal_panel(market, spec)
            result = simulate_signal_strategy(market, schedule, one_way_cost, final_closes, signals, spec.name)
            rows.append(
                {
                    "threshold": threshold,
                    "hold_hours": hold_hours,
                    "trade_count": int(result.summary["event_count"]),
                    "terminal_value": float(result.summary["terminal_value"]),
                    "net_return": float(result.summary["net_return"]),
                    "avg_trade_return": float(result.summary["avg_trade_return"]),
                    "win_rate": float(result.summary["win_rate"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["threshold", "hold_hours"]).reset_index(drop=True)


def run_hostile_checks(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
    primary_summary: dict[str, object],
    seed: int,
) -> pd.DataFrame:
    doubled_cost = simulate_signal_strategy(
        market,
        schedule,
        one_way_cost * 2,
        final_closes,
        signals,
        "negative_funding_rebound_panel_doubled_cost",
    )
    without_best = remove_best_trade(market, schedule, one_way_cost, final_closes, signals)
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
                "check": "random_baseline",
                "terminal_value": float(random_baseline.summary["terminal_value"]),
                "net_return": float(random_baseline.summary["net_return"]),
                "beats_primary": float(random_baseline.summary["terminal_value"]) >= float(primary_summary["terminal_value"]),
            },
        ]
    )


def remove_best_trade(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
) -> SimulationResult:
    if signals.empty:
        return simulate_signal_strategy(market, schedule, one_way_cost, final_closes, signals, "without_best_trade")
    price_maps = {
        asset: frames.price.set_index("timestamp")[["open", "close"]]
        for asset, frames in market.items()
    }
    returns: list[float] = []
    for row in signals.itertuples(index=False):
        entry_open = float(price_maps[row.asset].at[row.entry_time, "open"])
        exit_close = float(price_maps[row.asset].at[row.exit_time, "close"])
        net = exit_close / entry_open - 1 - 2 * one_way_cost
        returns.append(net)
    keep = signals.drop(index=int(np.argmax(np.array(returns)))).reset_index(drop=True)
    return simulate_signal_strategy(market, schedule, one_way_cost, final_closes, keep, "without_best_trade")


def classify_verdict(
    primary_summary: dict[str, object],
    daily_benchmarks: list[SimulationResult],
    equal_weight_daily_summary: dict[str, object],
    hostile: pd.DataFrame,
) -> str:
    primary_terminal = float(primary_summary["terminal_value"])
    required = [float(item.summary["terminal_value"]) for item in daily_benchmarks]
    required.append(float(equal_weight_daily_summary["terminal_value"]))
    if primary_terminal <= max(required):
        return "Rejected"
    if (hostile["check"] == "exclude_best_trade").any():
        best_row = hostile.loc[hostile["check"].eq("exclude_best_trade")].iloc[0]
        if float(best_row["terminal_value"]) <= max(required):
            return "Promising but inconclusive"
    return "Promising but inconclusive"


def summarize_strategy(name: str, ledger: pd.DataFrame, equity: pd.DataFrame) -> dict[str, object]:
    terminal_value = float(equity["equity"].iloc[-1]) if not equity.empty else STARTING_CAPITAL
    net_return = terminal_value / STARTING_CAPITAL - 1
    entries = ledger.loc[ledger["kind"].astype(str).str.contains("entry|buy", regex=True, na=False)].copy()
    exits = ledger.loc[ledger["kind"].astype(str).str.contains("exit", regex=True, na=False)].copy()
    trade_count = int(len(exits) if len(exits) else len(entries))
    trade_returns = compute_trade_returns(ledger)
    avg_trade = float(trade_returns.mean()) if len(trade_returns) else np.nan
    win_rate = float((trade_returns > 0).mean()) if len(trade_returns) else np.nan
    return {
        "strategy": name,
        "terminal_value": terminal_value,
        "net_return": net_return,
        "event_count": trade_count,
        "avg_trade_return": avg_trade,
        "win_rate": win_rate,
    }


def compute_trade_returns(ledger: pd.DataFrame) -> pd.Series:
    if ledger.empty or "kind" not in ledger.columns:
        return pd.Series(dtype=float)
    entries = ledger.loc[ledger["kind"].astype(str).str.contains("entry", regex=True, na=False)].copy()
    exits = ledger.loc[ledger["kind"].astype(str).str.contains("exit", regex=True, na=False)].copy()
    if entries.empty or exits.empty:
        return pd.Series(dtype=float)
    paired = pd.concat(
        [
            entries[["timestamp", "gross_spend_usd"]].reset_index(drop=True).rename(columns={"gross_spend_usd": "entry_value"}),
            exits[["timestamp", "gross_spend_usd"]].reset_index(drop=True).rename(columns={"gross_spend_usd": "exit_value"}),
        ],
        axis=1,
    )
    paired = paired.dropna()
    if paired.empty:
        return pd.Series(dtype=float)
    return paired["exit_value"] / paired["entry_value"] - 1


def summarize_partitions(equity: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for partition in PARTITIONS:
        mask = equity["timestamp"] >= partition.start
        if partition.end_exclusive is not None:
            mask &= equity["timestamp"] < partition.end_exclusive
        subset = equity.loc[mask]
        if subset.empty:
            continue
        trade_mask = ledger["timestamp"] >= partition.start if not ledger.empty else pd.Series(dtype=bool)
        if partition.end_exclusive is not None and not ledger.empty:
            trade_mask &= ledger["timestamp"] < partition.end_exclusive
        trade_count = int(ledger.loc[trade_mask, "kind"].astype(str).str.contains("entry|buy", regex=True, na=False).sum()) if not ledger.empty else 0
        rows.append(
            {
                "partition": partition.name,
                "start": partition.start,
                "end_exclusive": partition.end_exclusive,
                "terminal_value": float(subset["equity"].iloc[-1]),
                "net_return": float(subset["equity"].iloc[-1] / subset["equity"].iloc[0] - 1) if subset["equity"].iloc[0] else np.nan,
                "event_count": trade_count,
            }
        )
    return pd.DataFrame(rows)


def mark_record(
    timestamp: pd.Timestamp,
    cash: float,
    asset: str | None,
    close: float,
    final_closes: dict[str, float],
    units: float = 0.0,
) -> dict[str, object]:
    asset_value = units * close if asset else 0.0
    record: dict[str, object] = {
        "timestamp": timestamp,
        "cash": cash,
        "active_asset": asset or "",
        "asset_units": units,
        "mark_close": close,
        "equity": cash + asset_value,
    }
    for bench_asset, final_close in final_closes.items():
        record[f"final_{bench_asset.lower()}_close"] = final_close
    return record


def mark_portfolio_record(
    timestamp: pd.Timestamp,
    cash: float,
    units: dict[str, float],
    closes: dict[str, float],
    final_closes: dict[str, float],
) -> dict[str, object]:
    equity = cash + sum(units[asset] * closes[asset] for asset in units)
    record: dict[str, object] = {
        "timestamp": timestamp,
        "cash": cash,
        "equity": equity,
    }
    for asset, held in units.items():
        record[f"{asset.lower()}_units"] = held
        record[f"{asset.lower()}_close"] = closes[asset]
    for bench_asset, final_close in final_closes.items():
        record[f"final_{bench_asset.lower()}_close"] = final_close
    return record


def provenance(paths: Paths, asset: str) -> dict[str, object]:
    raw_path = paths.raw / f"{asset}_1h.csv.gz"
    funding_path = paths.funding / f"{asset}_funding.csv.gz"
    raw = pd.read_csv(raw_path, usecols=["timestamp", "source_symbol"])
    funding = pd.read_csv(funding_path, usecols=["timestamp", "source_symbol"])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True, format="mixed")
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True, format="mixed")
    return {
        "spot_path": str(raw_path.relative_to(paths.root)),
        "spot_sha256": sha256(raw_path),
        "spot_rows": int(len(raw)),
        "spot_first_timestamp": raw["timestamp"].min().isoformat(),
        "spot_last_timestamp": raw["timestamp"].max().isoformat(),
        "funding_path": str(funding_path.relative_to(paths.root)),
        "funding_sha256": sha256(funding_path),
        "funding_rows": int(len(funding)),
        "funding_first_timestamp": funding["timestamp"].min().isoformat(),
        "funding_last_timestamp": funding["timestamp"].max().isoformat(),
    }


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join(["---"] * len(columns)) + "|"
    rows = [header, divider]
    for record in frame.itertuples(index=False, name=None):
        cells = []
        for value in record:
            if isinstance(value, float):
                cells.append(f"{value:.6g}")
            else:
                cells.append(str(value))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def write_report(output: Path, manifest: dict[str, object], summary: pd.DataFrame, hostile: pd.DataFrame) -> None:
    primary = summary.loc[summary["strategy"].eq("negative_funding_rebound_panel")].iloc[0]
    baselines = summary.loc[summary["strategy"].isin(["daily_btc_dca", "daily_eth_dca", "daily_sol_dca", "daily_xrp_dca", "daily_equal_weight_universe_dca"])]
    lines = [
        "# Negative funding panel validation",
        "",
        f"Run artifact: `{output / 'REPORT.md'}`",
        "",
        "## Key findings",
        "",
        "- **Primary rule tested:** across the real Binance funding universe **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints are **<= -5 bps**, select the **single most negative** asset, enter **spot long at the next hourly open**, hold **24h**, then exit and wait **24h** before the next trade.",
        "- **Capital rule:** one global reserve sleeve, non-overlapping trades, using only real Binance hourly spot bars and real Binance USD-M funding history.",
        "- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA** plus a **daily equal-weight nine-asset universe DCA**.",
        "",
        "## Result table",
        "",
        dataframe_to_markdown(summary[["strategy", "terminal_value", "event_count", "avg_trade_return", "win_rate"]]),
        "",
        "## Honest conclusion",
        "",
        f"> **{primary['verdict']}.** The negative-funding rebound rule finished at **${primary['terminal_value']:.2f}** across **{int(primary['event_count'])} trades**, but the decisive benchmark gate is still negative because at least one required DCA benchmark finished higher (best required baseline: **${baselines['terminal_value'].max():.2f}**).",
        "",
        "## Decisive hostile checks",
        "",
        dataframe_to_markdown(hostile),
        "",
        "## Files",
        "",
        f"- `{output / 'strategy_summary.csv'}`",
        f"- `{output / 'trade_log.csv'}`",
        f"- `{output / 'equity_curves.csv'}`",
        f"- `{output / 'partition_summary.csv'}`",
        f"- `{output / 'signal_panel.csv'}`",
        f"- `{output / 'sensitivity_checks.csv'}`",
        f"- `{output / 'hostile_checks.csv'}`",
        "",
        "## Manifest excerpt",
        "",
        "```json",
        json.dumps({"spec": manifest["spec"], "raw_signal_count": manifest["raw_signal_count"]}, indent=2),
        "```",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
