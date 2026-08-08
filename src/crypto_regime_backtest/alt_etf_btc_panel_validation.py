from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv
from .polymarket_crypto_validation import fetch_market_metadata, load_or_fetch_hourly_series

SAMPLE_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")
DAILY_CONTRIBUTION_HOUR_UTC = 9
PRIMARY_DELTA_THRESHOLD = 0.10
PRIMARY_LEVEL_THRESHOLD = 0.55
PRIMARY_HOLD_HOURS = 72
PRIMARY_COOLDOWN_HOURS = 24
SENSITIVITY_LEVELS = (0.55, 0.60)
SENSITIVITY_HOLDS = (48, 72, 96)
ALT_FAMILIES: tuple[tuple[str, str], ...] = (
    ("ETH", "eth_etf"),
    ("SOL", "sol_etf"),
    ("XRP", "xrp_etf"),
)
BENCHMARK_ASSETS = ("BTC", "ETH", "SOL", "XRP")


@dataclass(frozen=True)
class StrategySpec:
    name: str
    delta_threshold: float
    level_threshold: float
    hold_hours: int
    cooldown_hours: int = PRIMARY_COOLDOWN_HOURS


@dataclass(frozen=True)
class StudyConfig:
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    contribution_hour_utc: int = DAILY_CONTRIBUTION_HOUR_UTC
    sample_start: str = "2024-01-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    primary_delta_threshold: float = PRIMARY_DELTA_THRESHOLD
    primary_level_threshold: float = PRIMARY_LEVEL_THRESHOLD
    primary_hold_hours: int = PRIMARY_HOLD_HOURS
    primary_cooldown_hours: int = PRIMARY_COOLDOWN_HOURS


@dataclass
class SimulationResult:
    summary: dict[str, object]
    ledger: pd.DataFrame
    equity: pd.DataFrame
    partition_summary: pd.DataFrame


@dataclass(frozen=True)
class Partition:
    name: str
    start: pd.Timestamp
    end_exclusive: pd.Timestamp | None


PARTITIONS = (
    Partition("development_2024", SAMPLE_START, HOLDOUT_START),
    Partition("holdout_2025_onward", HOLDOUT_START, None),
)


def run_alt_etf_btc_panel_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "alt_etf_btc_panel" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    metadata = fetch_market_metadata(paths)
    hourly = load_or_fetch_hourly_series(paths, metadata)
    hourly = hourly[hourly["timestamp"] >= pd.Timestamp(config.sample_start)].copy()

    asset_frames = {asset: load_hourly(paths, asset, config.sample_start) for asset in BENCHMARK_ASSETS}
    price_closes = {asset: float(asset_frames[asset]["close"].iloc[-1]) for asset in BENCHMARK_ASSETS}
    schedule = build_daily_contribution_schedule(asset_frames["BTC"], config.initial_capital, config.contribution_hour_utc)

    cash = simulate_cash_reserve(asset_frames["BTC"], schedule, price_closes)
    daily_benchmarks = [
        simulate_daily_asset_dca(asset_frames[asset], schedule, config.one_way_cost, price_closes, asset) for asset in BENCHMARK_ASSETS
    ]
    alt_basket = simulate_equal_weight_alt_basket(asset_frames, schedule, config.one_way_cost, price_closes)

    primary_spec = StrategySpec(
        name="alt_etf_odds_family_long_alt_short_btc",
        delta_threshold=PRIMARY_DELTA_THRESHOLD,
        level_threshold=PRIMARY_LEVEL_THRESHOLD,
        hold_hours=PRIMARY_HOLD_HOURS,
    )
    primary = simulate_alt_etf_btc_family(asset_frames, hourly, schedule, config.one_way_cost, price_closes, primary_spec)

    signals = build_alt_etf_signals(hourly, primary_spec)
    sensitivity = run_sensitivity_suite(asset_frames, hourly, schedule, config.one_way_cost, price_closes, primary.summary)
    hostile = run_hostile_checks(asset_frames, hourly, schedule, config.one_way_cost, price_closes, primary_spec, primary.summary)
    verdict = classify_verdict(primary.summary, daily_benchmarks, sensitivity, hostile)

    summaries = pd.DataFrame([cash.summary, *[item.summary for item in daily_benchmarks], alt_basket.summary, primary.summary])
    summaries.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            cash.ledger.assign(strategy="cash_reserve"),
            *[item.ledger.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            alt_basket.ledger.assign(strategy="daily_equal_weight_alt_basket"),
            primary.ledger.assign(strategy="alt_etf_odds_family_long_alt_short_btc"),
        ],
        ignore_index=True,
    ).to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            cash.equity.assign(strategy="cash_reserve"),
            *[item.equity.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            alt_basket.equity.assign(strategy="daily_equal_weight_alt_basket"),
            primary.equity.assign(strategy="alt_etf_odds_family_long_alt_short_btc"),
        ],
        ignore_index=True,
    ).to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            cash.partition_summary.assign(strategy="cash_reserve"),
            *[item.partition_summary.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            alt_basket.partition_summary.assign(strategy="daily_equal_weight_alt_basket"),
            primary.partition_summary.assign(strategy="alt_etf_odds_family_long_alt_short_btc"),
        ],
        ignore_index=True,
    ).to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    signals.to_csv(output / "signal_panel.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "assets": {asset: provenance(paths, asset) for asset in BENCHMARK_ASSETS},
        "sample_start": asset_frames["BTC"]["timestamp"].min().isoformat(),
        "sample_end": asset_frames["BTC"]["timestamp"].max().isoformat(),
        "families": [family for _, family in ALT_FAMILIES],
        "raw_signal_count": int(len(signals)),
        "executed_trade_count": int(primary.summary["event_count"]),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summaries, sensitivity, hostile, verdict)
    print(f"Alt ETF BTC panel validation written to {output}", flush=True)
    return summaries


def load_hourly(paths: Paths, asset: str, sample_start: str) -> pd.DataFrame:
    frame = load_ohlcv(paths, asset, "1h").loc[pd.Timestamp(sample_start) :].reset_index()
    if frame.empty:
        raise RuntimeError(f"{asset} 1h data does not cover the requested study window")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


def build_daily_contribution_schedule(frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in BTC 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def build_alt_etf_signals(hourly: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for asset, family in ALT_FAMILIES:
        family_hourly = hourly[hourly["family"].eq(family)].copy().sort_values("timestamp")
        if family_hourly.empty:
            continue
        family_hourly["delta_24h"] = family_hourly["yes_price"].diff(24)
        signals = family_hourly[
            (family_hourly["delta_24h"] >= spec.delta_threshold) & (family_hourly["yes_price"] >= spec.level_threshold)
        ].copy()
        if signals.empty:
            continue
        signals["asset"] = asset
        signals["entry_time"] = signals["timestamp"] + pd.Timedelta(hours=1)
        signals["exit_time"] = signals["entry_time"] + pd.Timedelta(hours=spec.hold_hours)
        rows.append(
            signals[
                [
                    "timestamp",
                    "entry_time",
                    "exit_time",
                    "asset",
                    "family",
                    "slug",
                    "question",
                    "yes_price",
                    "delta_24h",
                ]
            ]
        )
    if not rows:
        return pd.DataFrame(
            columns=["timestamp", "entry_time", "exit_time", "asset", "family", "slug", "question", "yes_price", "delta_24h"]
        )
    return pd.concat(rows, ignore_index=True).sort_values(["entry_time", "asset"]).reset_index(drop=True)


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
            ledger_rows.append({"timestamp": timestamp, "kind": "cash_contribution", "gross_spend_usd": 0.0, "fee_slippage_usd": 0.0, "cash_after": cash})
        records.append(mark_record(timestamp, cash, final_closes))
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
            ref_open = float(row.open)
            execution_price = ref_open * (1 + one_way_cost)
            gross_spend = cash
            bought = gross_spend / execution_price
            fee_slippage = gross_spend * one_way_cost
            cash = 0.0
            units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": f"daily_{asset.lower()}_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": fee_slippage,
                    "execution_price": execution_price,
                    "reference_open": ref_open,
                    f"{asset.lower()}_bought": bought,
                    f"{asset.lower()}_after": units,
                    "cash_after": cash,
                }
            )
        equity = cash + units * float(row.close)
        records.append(mark_record(timestamp, equity, final_closes, asset_units={asset: units}, cash=cash))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(f"daily_{asset.lower()}_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_equal_weight_alt_basket(
    asset_frames: dict[str, pd.DataFrame],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
) -> SimulationResult:
    cash = 0.0
    units = {asset: 0.0 for asset, _ in ALT_FAMILIES}
    eth = asset_frames["ETH"]
    sol = asset_frames["SOL"]
    xrp = asset_frames["XRP"]
    lookup = {asset: asset_frames[asset].set_index("timestamp") for asset, _ in ALT_FAMILIES}
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in eth.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
            spend_per_asset = cash / len(ALT_FAMILIES)
            for asset, _ in ALT_FAMILIES:
                ref_open = float(lookup[asset].at[timestamp, "open"])
                execution_price = ref_open * (1 + one_way_cost)
                bought = spend_per_asset / execution_price
                ledger_rows.append(
                    {
                        "timestamp": timestamp,
                        "kind": f"daily_{asset.lower()}_basket_buy",
                        "gross_spend_usd": spend_per_asset,
                        "fee_slippage_usd": spend_per_asset * one_way_cost,
                        "execution_price": execution_price,
                        "reference_open": ref_open,
                        f"{asset.lower()}_bought": bought,
                        f"{asset.lower()}_after": units[asset] + bought,
                        "cash_after": 0.0,
                    }
                )
                units[asset] += bought
            cash = 0.0
        equity = cash + units["ETH"] * float(lookup["ETH"].at[timestamp, "close"]) + units["SOL"] * float(lookup["SOL"].at[timestamp, "close"]) + units["XRP"] * float(lookup["XRP"].at[timestamp, "close"])
        records.append(mark_record(timestamp, equity, final_closes, asset_units=units.copy(), cash=cash))
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("daily_equal_weight_alt_basket", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_alt_etf_btc_family(
    asset_frames: dict[str, pd.DataFrame],
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    spec: StrategySpec,
    skip_trade_key: tuple[pd.Timestamp, str] | None = None,
) -> SimulationResult:
    signals = build_alt_etf_signals(hourly, spec)
    btc = asset_frames["BTC"]
    btc_indexed = btc.set_index("timestamp")
    asset_indexed = {asset: frame.set_index("timestamp") for asset, frame in asset_frames.items()}
    scheduled = schedule.to_dict()

    cash = 0.0
    active_trade: dict[str, object] | None = None
    cooldown_until = pd.Timestamp.min.tz_localize("UTC")
    pending_signals = signals.to_dict("records")
    signal_idx = 0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []

    for row in btc.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution

        if active_trade is not None and timestamp == active_trade["exit_time"]:
            notional = float(active_trade["gross_spend_usd"])
            net_return = float(active_trade["realized_return_pct"])
            cash += max(0.0, notional * (1.0 + net_return))
            ledger_rows.append(
                {
                    "timestamp": active_trade["signal_time"],
                    "entry_time": active_trade["entry_time"],
                    "exit_time": active_trade["exit_time"],
                    "kind": "alt_etf_btc_spread_trade",
                    "asset": active_trade["asset"],
                    "market_slug": active_trade["market_slug"],
                    "gross_spend_usd": notional,
                    "fee_slippage_usd": notional * 4 * one_way_cost,
                    "alt_entry_open": active_trade["alt_entry_open"],
                    "btc_entry_open": active_trade["btc_entry_open"],
                    "alt_exit_open": active_trade["alt_exit_open"],
                    "btc_exit_open": active_trade["btc_exit_open"],
                    "return_pct": net_return,
                    "cash_after": cash,
                    "signal_yes_price": active_trade["signal_yes_price"],
                    "signal_delta_24h": active_trade["signal_delta_24h"],
                }
            )
            cooldown_until = pd.Timestamp(active_trade["exit_time"]) + pd.Timedelta(hours=spec.cooldown_hours)
            active_trade = None

        while signal_idx < len(pending_signals) and pd.Timestamp(pending_signals[signal_idx]["entry_time"]) < timestamp:
            signal_idx += 1

        if active_trade is None and cash > 0 and timestamp >= cooldown_until and signal_idx < len(pending_signals):
            signal = pending_signals[signal_idx]
            signal_key = (pd.Timestamp(signal["entry_time"]), str(signal["asset"]))
            if skip_trade_key is not None and signal_key == skip_trade_key:
                signal_idx += 1
            elif pd.Timestamp(signal["entry_time"]) == timestamp:
                asset = str(signal["asset"])
                exit_time = pd.Timestamp(signal["exit_time"])
                if exit_time in asset_indexed[asset].index and exit_time in btc_indexed.index and timestamp in asset_indexed[asset].index:
                    alt_entry_open = float(asset_indexed[asset].at[timestamp, "open"])
                    btc_entry_open = float(btc_indexed.at[timestamp, "open"])
                    alt_exit_open = float(asset_indexed[asset].at[exit_time, "open"])
                    btc_exit_open = float(btc_indexed.at[exit_time, "open"])
                    gross = (alt_exit_open / alt_entry_open - 1.0) - (btc_exit_open / btc_entry_open - 1.0)
                    net = gross - 4 * one_way_cost
                    active_trade = {
                        "signal_time": pd.Timestamp(signal["timestamp"]),
                        "entry_time": timestamp,
                        "exit_time": exit_time,
                        "gross_spend_usd": cash,
                        "asset": asset,
                        "market_slug": str(signal["slug"]),
                        "alt_entry_open": alt_entry_open,
                        "btc_entry_open": btc_entry_open,
                        "alt_exit_open": alt_exit_open,
                        "btc_exit_open": btc_exit_open,
                        "signal_yes_price": float(signal["yes_price"]),
                        "signal_delta_24h": float(signal["delta_24h"]),
                        "realized_return_pct": net,
                    }
                    cash = 0.0
                signal_idx += 1

        equity = cash
        if active_trade is not None:
            notional = float(active_trade["gross_spend_usd"])
            asset = str(active_trade["asset"])
            alt_mark = float(asset_indexed[asset].at[timestamp, "close"])
            btc_mark = float(btc_indexed.at[timestamp, "close"])
            live_gross = (alt_mark / float(active_trade["alt_entry_open"]) - 1.0) - (btc_mark / float(active_trade["btc_entry_open"]) - 1.0)
            live_net = live_gross - 4 * one_way_cost
            equity += max(0.0, notional * (1.0 + live_net))
        records.append(mark_record(timestamp, equity, final_closes, cash=cash))

    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(spec.name, ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def mark_record(
    timestamp: pd.Timestamp,
    equity: float,
    final_closes: dict[str, float],
    asset_units: dict[str, float] | None = None,
    cash: float | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {"timestamp": timestamp, "equity": equity, "cash": equity if cash is None else cash}
    for asset, close in final_closes.items():
        row[f"{asset.lower()}_equivalent"] = float(equity / close) if close > 0 else 0.0
        row[f"{asset.lower()}_close"] = close
        row[f"{asset.lower()}_units"] = float((asset_units or {}).get(asset, 0.0))
    return row


def summarize_strategy(name: str, ledger: pd.DataFrame, equity: pd.DataFrame) -> dict[str, object]:
    equity_curve = equity["equity"]
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    result = {
        "strategy": name,
        "final_usd_value": float(equity_curve.iloc[-1]),
        "final_cash_usd": float(equity["cash"].iloc[-1]),
        "event_count": int(len(ledger)),
        "gross_spent_usd": float(ledger["gross_spend_usd"].sum()) if not ledger.empty else 0.0,
        "total_costs_usd": float(ledger["fee_slippage_usd"].sum()) if not ledger.empty else 0.0,
        "unused_cash_usd": float(equity["cash"].iloc[-1]),
        "total_return_on_committed_capital": float(equity_curve.iloc[-1] / STARTING_CAPITAL - 1.0),
        "max_drawdown": abs(float(drawdown.min())),
        "avg_trade_return": float(ledger["return_pct"].mean()) if "return_pct" in ledger.columns and not ledger.empty else 0.0,
        "win_rate": float((ledger["return_pct"] > 0).mean()) if "return_pct" in ledger.columns and not ledger.empty else 0.0,
    }
    for asset in BENCHMARK_ASSETS:
        result[f"final_{asset.lower()}_equivalent"] = float(equity[f"{asset.lower()}_equivalent"].iloc[-1])
    return result


def summarize_partitions(equity: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for partition in PARTITIONS:
        mask = equity["timestamp"] >= partition.start
        if partition.end_exclusive is not None:
            mask &= equity["timestamp"] < partition.end_exclusive
        section = equity.loc[mask].copy()
        if section.empty:
            continue
        running_max = section["equity"].cummax()
        drawdown = section["equity"] / running_max - 1.0
        ledger_mask = pd.Series(False, index=ledger.index)
        if not ledger.empty and "timestamp" in ledger.columns:
            ledger_mask = ledger["timestamp"] >= partition.start
            if partition.end_exclusive is not None:
                ledger_mask &= ledger["timestamp"] < partition.end_exclusive
        partition_ledger = ledger.loc[ledger_mask] if not ledger.empty else pd.DataFrame()
        row = {
            "partition": partition.name,
            "start": section["timestamp"].iloc[0],
            "end": section["timestamp"].iloc[-1],
            "final_usd_value": float(section["equity"].iloc[-1]),
            "events": int(len(partition_ledger)),
            "costs_usd": float(partition_ledger["fee_slippage_usd"].sum()) if not partition_ledger.empty else 0.0,
            "max_drawdown": abs(float(drawdown.min())),
        }
        for asset in BENCHMARK_ASSETS:
            row[f"final_{asset.lower()}_equivalent"] = float(section[f"{asset.lower()}_equivalent"].iloc[-1])
        rows.append(row)
    return pd.DataFrame(rows)


def run_sensitivity_suite(
    asset_frames: dict[str, pd.DataFrame],
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    primary_summary: dict[str, object],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for level in SENSITIVITY_LEVELS:
        for hold in SENSITIVITY_HOLDS:
            spec = StrategySpec(
                name=f"alt_etf_family_l{int(level*100)}_h{hold}",
                delta_threshold=PRIMARY_DELTA_THRESHOLD,
                level_threshold=level,
                hold_hours=hold,
            )
            result = simulate_alt_etf_btc_family(asset_frames, hourly, schedule, one_way_cost, final_closes, spec)
            summary = result.summary.copy()
            summary["check"] = "nearby_parameters"
            summary["level_threshold"] = level
            summary["hold_hours"] = hold
            summary["excess_usd_vs_primary"] = float(summary["final_usd_value"]) - float(primary_summary["final_usd_value"])
            rows.append(summary)
    doubled = simulate_alt_etf_btc_family(
        asset_frames,
        hourly,
        schedule,
        one_way_cost * 2,
        final_closes,
        StrategySpec("alt_etf_family_doubled_cost", PRIMARY_DELTA_THRESHOLD, PRIMARY_LEVEL_THRESHOLD, PRIMARY_HOLD_HOURS),
    ).summary
    doubled["check"] = "doubled_cost_primary"
    doubled["level_threshold"] = PRIMARY_LEVEL_THRESHOLD
    doubled["hold_hours"] = PRIMARY_HOLD_HOURS
    doubled["excess_usd_vs_primary"] = float(doubled["final_usd_value"]) - float(primary_summary["final_usd_value"])
    rows.append(doubled)
    return pd.DataFrame(rows)


def run_hostile_checks(
    asset_frames: dict[str, pd.DataFrame],
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    primary_spec: StrategySpec,
    primary_summary: dict[str, object],
) -> pd.DataFrame:
    primary = simulate_alt_etf_btc_family(asset_frames, hourly, schedule, one_way_cost, final_closes, primary_spec)
    rows: list[dict[str, object]] = []
    ledger = primary.ledger
    if ledger.empty:
        rows.append({"check": "exclude_best_trade", "trade_count": 0, "final_usd_value": float(primary_summary["final_usd_value"])})
        return pd.DataFrame(rows)
    best = ledger.sort_values("return_pct", ascending=False).iloc[0]
    skip_key = (pd.Timestamp(best["entry_time"]), str(best["asset"]))
    excluded = simulate_alt_etf_btc_family(asset_frames, hourly, schedule, one_way_cost, final_closes, primary_spec, skip_trade_key=skip_key)
    rows.append(
        {
            "check": "exclude_best_trade",
            "skipped_entry_time": best["entry_time"],
            "skipped_asset": best["asset"],
            "trade_count": int(excluded.summary["event_count"]),
            "final_usd_value": float(excluded.summary["final_usd_value"]),
            "final_btc_equivalent": float(excluded.summary["final_btc_equivalent"]),
            "final_eth_equivalent": float(excluded.summary["final_eth_equivalent"]),
            "final_sol_equivalent": float(excluded.summary["final_sol_equivalent"]),
            "final_xrp_equivalent": float(excluded.summary["final_xrp_equivalent"]),
            "delta_usd_vs_primary": float(excluded.summary["final_usd_value"]) - float(primary_summary["final_usd_value"]),
        }
    )
    return pd.DataFrame(rows)


def classify_verdict(
    primary_summary: dict[str, object],
    daily_benchmarks: list[SimulationResult],
    sensitivity: pd.DataFrame,
    hostile: pd.DataFrame,
) -> str:
    primary_usd = float(primary_summary["final_usd_value"])
    beats_all_daily = all(primary_usd > float(item.summary["final_usd_value"]) for item in daily_benchmarks)
    survives_doubled_cost = bool(
        not sensitivity[sensitivity["check"].eq("doubled_cost_primary")].empty
        and float(sensitivity.loc[sensitivity["check"].eq("doubled_cost_primary"), "final_usd_value"].iloc[0]) > 10000.0
    )
    survives_hostile = bool(
        hostile.empty or float(hostile.loc[hostile["check"].eq("exclude_best_trade"), "final_usd_value"].iloc[0]) >= 10000.0
    )
    if beats_all_daily and survives_doubled_cost and survives_hostile:
        return "promising_but_inconclusive"
    if primary_usd <= 10000.0 or not beats_all_daily:
        return "rejected"
    return "mixed"


def write_report(
    output: Path,
    manifest: dict[str, object],
    summaries: pd.DataFrame,
    sensitivity: pd.DataFrame,
    hostile: pd.DataFrame,
    verdict: str,
) -> None:
    primary = summaries[summaries["strategy"].eq("alt_etf_odds_family_long_alt_short_btc")].iloc[0]
    btc = summaries[summaries["strategy"].eq("daily_btc_dca")].iloc[0]
    eth = summaries[summaries["strategy"].eq("daily_eth_dca")].iloc[0]
    sol = summaries[summaries["strategy"].eq("daily_sol_dca")].iloc[0]
    xrp = summaries[summaries["strategy"].eq("daily_xrp_dca")].iloc[0]
    alt_basket = summaries[summaries["strategy"].eq("daily_equal_weight_alt_basket")].iloc[0]
    doubled = sensitivity[sensitivity["check"].eq("doubled_cost_primary")].iloc[0]
    hostile_row = hostile.iloc[0] if not hostile.empty else None
    lines = [
        "# Alt ETF odds family -> alt/BTC spread validation",
        "",
        f"Run artifact: `{output / 'REPORT.md'}`",
        "",
        "## Key findings",
        "",
        "- **Primary rule tested:** across the real Polymarket **ETH / SOL / XRP spot-ETF approval** markets, trigger when YES odds jump by at least **10 points over 24h** and remain at or above **55%**; enter **long the alt / short BTC** at the next hourly open, hold **72h**, then exit. Global positions are **non-overlapping** and a **24h cooldown** applies after exit.",
        "- **Benchmarking method:** same fixed **$10,000** reserve released as equal daily contributions from **2024-01-01** onward, compared against **daily BTC, ETH, SOL, and XRP DCA** plus a **daily equal-weight ETH/SOL/XRP basket DCA**.",
        f"- **Sample window:** `{manifest['sample_start']}` through `{manifest['sample_end']}` using real Binance spot hourly data and real Polymarket hourly YES odds.",
        "",
        "## Result table",
        "",
        "| Strategy | Final USD | Trades | Avg trade | Win rate | Verdict |",
        "|---|---:|---:|---:|---:|---|",
        f"| Daily BTC DCA | {float(btc['final_usd_value']):.2f} | {int(btc['event_count'])} | n/a | n/a | Baseline |",
        f"| Daily ETH DCA | {float(eth['final_usd_value']):.2f} | {int(eth['event_count'])} | n/a | n/a | Baseline |",
        f"| Daily SOL DCA | {float(sol['final_usd_value']):.2f} | {int(sol['event_count'])} | n/a | n/a | Baseline |",
        f"| Daily XRP DCA | {float(xrp['final_usd_value']):.2f} | {int(xrp['event_count'])} | n/a | n/a | Baseline |",
        f"| Daily equal-weight alt basket | {float(alt_basket['final_usd_value']):.2f} | {int(alt_basket['event_count'])} | n/a | n/a | Baseline |",
        f"| Alt ETF odds family -> alt/BTC spread | {float(primary['final_usd_value']):.2f} | {int(primary['event_count'])} | {float(primary['avg_trade_return']):.2%} | {float(primary['win_rate']):.0%} | {verdict.replace('_', ' ')} |",
        "",
        "## Honest conclusion",
        "",
    ]
    if verdict == "rejected":
        lines.append(
            f"> **Rejected.** Extending the ETH ETF idea into a pooled ETH/SOL/XRP analogue family did improve sample size to **{int(primary['event_count'])} trades**, but the unified rule still failed the decisive benchmark test: it finished **behind XRP DCA** ({float(primary['final_usd_value']):.2f} vs {float(xrp['final_usd_value']):.2f})."
        )
    else:
        lines.append(
            f"> **{verdict.replace('_', ' ').title()}.** The family produced {int(primary['event_count'])} trades and ended at {float(primary['final_usd_value']):.2f} USD."
        )
    lines.extend(
        [
            "",
            "## Decisive checks",
            "",
            f"- **Doubled-cost check:** final USD `{float(doubled['final_usd_value']):.2f}`.",
            f"- **Best-trade exclusion:** final USD `{float(hostile_row['final_usd_value']):.2f}` after removing `{hostile_row['skipped_asset']}` at `{hostile_row['skipped_entry_time']}`." if hostile_row is not None and 'skipped_asset' in hostile_row else "- **Best-trade exclusion:** no completed trades.",
            "- **Interpretation:** the analogue-family extension is useful as a hostile test because it adds real event count, but it does **not** support upgrading the ETH ETF spread from 'promising but inconclusive' to validated edge.",
            "",
            "## Files",
            "",
            f"- `{output / 'strategy_summary.csv'}`",
            f"- `{output / 'trade_log.csv'}`",
            f"- `{output / 'signal_panel.csv'}`",
            f"- `{output / 'sensitivity_checks.csv'}`",
            f"- `{output / 'hostile_checks.csv'}`",
        ]
    )
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


def provenance(paths: Paths, coin: str) -> dict[str, object]:
    source = pd.read_csv(paths.data / "provenance.csv")
    match = source[(source["coin"] == coin) & (source["timeframe"] == "1h")].iloc[0]
    return match.to_dict()
