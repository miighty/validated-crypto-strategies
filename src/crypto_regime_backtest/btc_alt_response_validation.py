from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv

SAMPLE_START = pd.Timestamp("2021-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")
CONTRIBUTION_HOUR_UTC = 9
PRIMARY_BTC_LOOKBACK_HOURS = 4
PRIMARY_BTC_SHOCK_THRESHOLD = 0.03
PRIMARY_LAG_RATIO_MAX = 0.60
PRIMARY_HOLD_HOURS = 72
PRIMARY_COOLDOWN_HOURS = 24
BOOTSTRAP_SAMPLES = 2_000
MIN_HOLDOUT_TRADES = 20
TARGET_ASSETS = ("ETH", "SOL", "XRP")
BENCHMARK_ASSETS = ("BTC", "ETH", "SOL", "XRP")


@dataclass(frozen=True)
class StrategySpec:
    name: str
    btc_lookback_hours: int
    btc_shock_threshold: float
    lag_ratio_max: float
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
    btc_lookback_hours: int = PRIMARY_BTC_LOOKBACK_HOURS
    btc_shock_threshold: float = PRIMARY_BTC_SHOCK_THRESHOLD
    lag_ratio_max: float = PRIMARY_LAG_RATIO_MAX
    hold_hours: int = PRIMARY_HOLD_HOURS
    cooldown_hours: int = PRIMARY_COOLDOWN_HOURS
    primary_rule: str = (
        "If BTC rises at least 3% close-to-close over the prior 4 completed hourly bars and the target alt"
        " gained at most 60% of that BTC move over the same completed 4-hour window, deploy the full"
        " accrued reserve long the alt at the next hourly open, hold 72 hours, then return to cash."
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


def run_btc_alt_response_validation(paths: Paths, seed: int = 29) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "btc_alt_response" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    spec = StrategySpec(
        name="btc_shock_alt_underreaction",
        btc_lookback_hours=config.btc_lookback_hours,
        btc_shock_threshold=config.btc_shock_threshold,
        lag_ratio_max=config.lag_ratio_max,
        hold_hours=config.hold_hours,
        cooldown_hours=config.cooldown_hours,
    )

    market = {
        asset: load_ohlcv(paths, asset, "1h").loc[lambda df: df.index >= SAMPLE_START].copy()
        for asset in ("BTC", *TARGET_ASSETS)
    }
    for asset, frame in market.items():
        if frame.empty:
            raise RuntimeError(f"{asset} 1h data does not cover the requested study window")

    summaries: list[dict[str, object]] = []
    ledgers: list[pd.DataFrame] = []
    equities: list[pd.DataFrame] = []
    partitions: list[pd.DataFrame] = []
    hostile_rows: list[dict[str, object]] = []

    passive = passive_benchmarks(paths, config)
    passive.to_csv(output / "benchmark_summary.csv", index=False, float_format="%.17g")

    for asset in TARGET_ASSETS:
        frame = market[asset].reset_index()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        btc = market["BTC"].reset_index()
        btc["timestamp"] = pd.to_datetime(btc["timestamp"], utc=True)
        schedule = build_daily_contribution_schedule(frame, config.initial_capital, config.contribution_hour_utc)
        daily = simulate_daily_dca(frame, schedule, config.one_way_cost, asset)
        weekly = simulate_weekly_dca(frame, schedule, config.one_way_cost, asset)
        primary = simulate_btc_alt_strategy(frame, btc, schedule, config.one_way_cost, asset, spec)
        hostile = hostile_checks(frame, btc, primary.ledger, asset, spec, seed)
        verdict = classify_verdict(primary, daily, weekly, hostile)

        asset_summaries = pd.DataFrame([
            daily.summary,
            weekly.summary,
            {**primary.summary, "verdict": verdict},
        ])
        asset_summaries["asset"] = asset
        summaries.extend(asset_summaries.to_dict("records"))

        ledgers.extend([
            daily.ledger.assign(asset=asset, strategy=f"daily_{asset.lower()}_dca"),
            weekly.ledger.assign(asset=asset, strategy=f"weekly_{asset.lower()}_dca"),
            primary.ledger.assign(asset=asset, strategy=spec.name),
        ])
        equities.extend([
            daily.equity.assign(asset=asset, strategy=f"daily_{asset.lower()}_dca"),
            weekly.equity.assign(asset=asset, strategy=f"weekly_{asset.lower()}_dca"),
            primary.equity.assign(asset=asset, strategy=spec.name),
        ])
        partitions.extend([
            daily.partition_summary.assign(asset=asset, strategy=f"daily_{asset.lower()}_dca"),
            weekly.partition_summary.assign(asset=asset, strategy=f"weekly_{asset.lower()}_dca"),
            primary.partition_summary.assign(asset=asset, strategy=spec.name),
        ])
        hostile_rows.extend([{**row, "asset": asset} for row in hostile])

    summary_frame = pd.DataFrame(summaries)
    trade_log = pd.concat(ledgers, ignore_index=True)
    equity_curve = pd.concat(equities, ignore_index=True)
    partition_frame = pd.concat(partitions, ignore_index=True)
    hostile_frame = pd.DataFrame(hostile_rows)

    summary_frame.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    trade_log.to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    equity_curve.to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    partition_frame.to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    hostile_frame.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "spec": asdict(spec),
        "btc_data": provenance(paths, "BTC"),
        "assets": {asset: provenance(paths, asset) for asset in TARGET_ASSETS},
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summary_frame, passive, hostile_frame)
    print(f"BTC shock -> alt underreaction validation written to {output}", flush=True)
    return summary_frame


def build_daily_contribution_schedule(frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def simulate_daily_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float, asset: str) -> SimulationResult:
    cash = 0.0
    units = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    unit_label = f"{asset.lower()}_bought"
    held_label = f"{asset.lower()}_after"
    units_field = f"{asset.lower()}_units"
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
            reference_open = float(row.open)
            execution_price = reference_open * (1 + one_way_cost)
            bought = contribution / execution_price
            cash -= contribution
            units += bought
            ledger_rows.append({
                "timestamp": timestamp,
                "kind": "daily_dca_buy",
                "gross_spend_usd": contribution,
                "fee_slippage_usd": contribution * one_way_cost,
                "execution_price": execution_price,
                "reference_open": reference_open,
                unit_label: bought,
                "cash_after": cash,
                held_label: units,
            })
        close = float(row.close)
        equity = cash + units * close
        records.append({"timestamp": timestamp, "cash": cash, units_field: units, "close": close, "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(f"daily_{asset.lower()}_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_weekly_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float, asset: str) -> SimulationResult:
    cash = 0.0
    units = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    daily_schedule = schedule.to_dict()
    unit_label = f"{asset.lower()}_bought"
    held_label = f"{asset.lower()}_after"
    units_field = f"{asset.lower()}_units"
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(daily_schedule.get(timestamp, 0.0))
        if contribution:
            cash += contribution
        if timestamp.weekday() == 0 and timestamp.hour == CONTRIBUTION_HOUR_UTC and cash > 0:
            gross_spend = cash
            reference_open = float(row.open)
            execution_price = reference_open * (1 + one_way_cost)
            bought = gross_spend / execution_price
            cash = 0.0
            units += bought
            ledger_rows.append({
                "timestamp": timestamp,
                "kind": "weekly_dca_buy",
                "gross_spend_usd": gross_spend,
                "fee_slippage_usd": gross_spend * one_way_cost,
                "execution_price": execution_price,
                "reference_open": reference_open,
                unit_label: bought,
                "cash_after": cash,
                held_label: units,
            })
        close = float(row.close)
        equity = cash + units * close
        records.append({"timestamp": timestamp, "cash": cash, units_field: units, "close": close, "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(f"weekly_{asset.lower()}_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_btc_alt_strategy(
    frame: pd.DataFrame,
    btc: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    asset: str,
    spec: StrategySpec,
) -> SimulationResult:
    merged = frame[["timestamp", "open", "close"]].merge(
        btc[["timestamp", "close"]].rename(columns={"close": "btc_close"}), on="timestamp", how="inner"
    )
    merged["asset_lookback_return"] = merged["close"].pct_change(spec.btc_lookback_hours)
    merged["btc_lookback_return"] = merged["btc_close"].pct_change(spec.btc_lookback_hours)
    merged["lag_ratio"] = merged["asset_lookback_return"] / merged["btc_lookback_return"]
    merged["signal"] = np.logical_and(
        merged["btc_lookback_return"] >= spec.btc_shock_threshold,
        merged["lag_ratio"] <= spec.lag_ratio_max,
    )

    cash = 0.0
    units = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    last_exit_time = pd.Timestamp.min.tz_localize("UTC")
    active_exit_time: pd.Timestamp | None = None
    pending_exit_row: dict[str, object] | None = None

    for index, row in merged.iterrows():
        timestamp = pd.Timestamp(row["timestamp"])
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution

        if pending_exit_row is not None and timestamp == active_exit_time:
            reference_open = float(row["open"])
            execution_price = reference_open * (1 - one_way_cost)
            gross_sale = units * execution_price
            fee_slippage = units * reference_open * one_way_cost
            cash += gross_sale
            pending_exit_row.update({
                "exit_time": timestamp,
                "exit_reference_open": reference_open,
                "exit_execution_price": execution_price,
                "gross_sale_usd": gross_sale,
                "exit_fee_slippage_usd": fee_slippage,
                "cash_after_exit": cash,
                "net_trade_return": gross_sale / pending_exit_row["gross_spend_usd"] - 1,
            })
            ledger_rows.append(pending_exit_row)
            units = 0.0
            last_exit_time = timestamp + pd.Timedelta(hours=spec.cooldown_hours)
            active_exit_time = None
            pending_exit_row = None

        if units == 0.0 and bool(row["signal"]) and cash > 0 and timestamp >= last_exit_time:
            entry_idx = index + 1
            exit_idx = entry_idx + spec.hold_hours
            if exit_idx >= len(merged):
                close = float(row["close"])
                records.append({"timestamp": timestamp, "cash": cash, f"{asset.lower()}_units": units, "close": close, "equity": cash})
                continue
            entry_time = pd.Timestamp(merged.iloc[entry_idx]["timestamp"])
            exit_time = pd.Timestamp(merged.iloc[exit_idx]["timestamp"])
            reference_open = float(merged.iloc[entry_idx]["open"])
            execution_price = reference_open * (1 + one_way_cost)
            gross_spend = cash
            bought = gross_spend / execution_price
            units = bought
            cash = 0.0
            pending_exit_row = {
                "signal_time": timestamp,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "kind": "btc_shock_alt_underreaction_trade",
                "gross_spend_usd": gross_spend,
                "entry_fee_slippage_usd": gross_spend * one_way_cost,
                "entry_reference_open": reference_open,
                "entry_execution_price": execution_price,
                f"{asset.lower()}_bought": bought,
                "btc_lookback_return": float(row["btc_lookback_return"]),
                "asset_lookback_return": float(row["asset_lookback_return"]),
                "lag_ratio": float(row["lag_ratio"]),
                "hold_hours": spec.hold_hours,
            }
            active_exit_time = exit_time

        close = float(row["close"])
        equity = cash + units * close
        records.append({"timestamp": timestamp, "cash": cash, f"{asset.lower()}_units": units, "close": close, "equity": equity})

    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(spec.name, ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def summarize_strategy(name: str, ledger: pd.DataFrame, equity: pd.DataFrame) -> dict[str, object]:
    if equity.empty:
        raise RuntimeError(f"No equity rows for {name}")
    terminal_value = float(equity["equity"].iloc[-1])
    drawdown = equity["equity"] / equity["equity"].cummax() - 1
    summary: dict[str, object] = {
        "strategy": name,
        "terminal_value": terminal_value,
        "net_return": terminal_value / STARTING_CAPITAL - 1,
        "trade_count": int(len(ledger)),
        "max_drawdown": abs(float(drawdown.min())),
    }
    if "net_trade_return" in ledger.columns and not ledger.empty:
        trades = ledger["net_trade_return"].dropna()
        summary.update({
            "mean_trade_return": float(trades.mean()),
            "median_trade_return": float(trades.median()),
            "win_rate": float((trades > 0).mean()),
            "profit_factor": profit_factor(trades),
            "bootstrap_ci_low": bootstrap_mean_ci(trades, 29)[0],
            "bootstrap_ci_high": bootstrap_mean_ci(trades, 29)[1],
        })
    return summary


def summarize_partitions(equity: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for partition in PARTITIONS:
        mask = equity["timestamp"] >= partition.start
        if partition.end_exclusive is not None:
            mask = np.logical_and(mask, equity["timestamp"] < partition.end_exclusive)
        part = equity.loc[mask].copy()
        if part.empty:
            continue
        entry_mask = ledger.get("entry_time")
        if entry_mask is None:
            trades = ledger[(ledger["timestamp"] >= partition.start)] if not ledger.empty else ledger
            if partition.end_exclusive is not None and not trades.empty:
                trades = trades[trades["timestamp"] < partition.end_exclusive]
        else:
            trades = ledger[(ledger["entry_time"] >= partition.start)] if not ledger.empty else ledger
            if partition.end_exclusive is not None and not trades.empty:
                trades = trades[trades["entry_time"] < partition.end_exclusive]
        start_equity = float(part["equity"].iloc[0])
        end_equity = float(part["equity"].iloc[-1])
        rows.append({
            "partition": partition.name,
            "start": part["timestamp"].iloc[0],
            "end": part["timestamp"].iloc[-1],
            "trade_count": int(len(trades)),
            "net_return": end_equity / start_equity - 1 if start_equity > 0 else np.nan,
            "mean_trade_return": float(trades["net_trade_return"].mean()) if "net_trade_return" in trades.columns and not trades.empty else np.nan,
        })
    return pd.DataFrame(rows)


def passive_benchmarks(paths: Paths, config: StudyConfig) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for asset in BENCHMARK_ASSETS:
        frame = load_ohlcv(paths, asset, "1h").loc[lambda df: df.index >= SAMPLE_START].reset_index()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        schedule = build_daily_contribution_schedule(frame, config.initial_capital, config.contribution_hour_utc)
        daily = simulate_daily_dca(frame, schedule, config.one_way_cost, asset)
        weekly = simulate_weekly_dca(frame, schedule, config.one_way_cost, asset)
        rows.extend([
            {"asset": asset, **daily.summary},
            {"asset": asset, **weekly.summary},
        ])
    return pd.DataFrame(rows)


def hostile_checks(
    frame: pd.DataFrame,
    btc: pd.DataFrame,
    primary_ledger: pd.DataFrame,
    asset: str,
    spec: StrategySpec,
    seed: int,
) -> list[dict[str, object]]:
    if primary_ledger.empty:
        return [
            {"check": "btc_shock_without_lag_filter", "trade_count": 0, "mean_trade_return": np.nan},
            {"check": "same_asset_momentum", "trade_count": 0, "mean_trade_return": np.nan},
            {"check": "matched_random", "trade_count": 0, "mean_trade_return": np.nan},
        ]

    merged = frame[["timestamp", "open", "close"]].merge(
        btc[["timestamp", "close"]].rename(columns={"close": "btc_close"}), on="timestamp", how="inner"
    )
    merged["asset_lookback_return"] = merged["close"].pct_change(spec.btc_lookback_hours)
    merged["btc_lookback_return"] = merged["btc_close"].pct_change(spec.btc_lookback_hours)
    merged["lag_ratio"] = merged["asset_lookback_return"] / merged["btc_lookback_return"]
    raw_signal = pd.Series(merged["btc_lookback_return"] >= spec.btc_shock_threshold, index=merged.index)
    asset_signal = pd.Series(merged["asset_lookback_return"] >= spec.btc_shock_threshold, index=merged.index)
    raw_trades = event_returns_from_signal(merged, raw_signal, spec.hold_hours, spec.cooldown_hours)
    asset_trades = event_returns_from_signal(merged, asset_signal, spec.hold_hours, spec.cooldown_hours)
    random_trades = matched_random_returns(merged, len(primary_ledger), spec.hold_hours, spec.cooldown_hours, seed)
    return [
        {"check": "btc_shock_without_lag_filter", "trade_count": len(raw_trades), "mean_trade_return": float(raw_trades.mean()) if not raw_trades.empty else np.nan},
        {"check": "same_asset_momentum", "trade_count": len(asset_trades), "mean_trade_return": float(asset_trades.mean()) if not asset_trades.empty else np.nan},
        {"check": "matched_random", "trade_count": len(random_trades), "mean_trade_return": float(random_trades.mean()) if not random_trades.empty else np.nan},
    ]


def event_returns_from_signal(merged: pd.DataFrame, signal: pd.Series, hold_hours: int, cooldown_hours: int) -> pd.Series:
    returns: list[float] = []
    next_allowed = pd.Timestamp.min.tz_localize("UTC")
    for signal_idx in np.flatnonzero(signal.fillna(False).to_numpy()):
        entry_idx = signal_idx + 1
        exit_idx = entry_idx + hold_hours
        if exit_idx >= len(merged):
            continue
        signal_time = pd.to_datetime(merged.iloc[signal_idx]["timestamp"], utc=True)
        if signal_time < next_allowed:
            continue
        buy = float(merged.iloc[entry_idx]["open"]) * (1 + ONE_WAY_COST)
        sell = float(merged.iloc[exit_idx]["open"]) * (1 - ONE_WAY_COST)
        returns.append(sell / buy - 1)
        next_allowed = pd.to_datetime(merged.iloc[exit_idx]["timestamp"], utc=True) + pd.Timedelta(hours=int(cooldown_hours))
    return pd.Series(returns, dtype=float)


def matched_random_returns(merged: pd.DataFrame, count: int, hold_hours: int, cooldown_hours: int, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    if count == 0 or len(merged) <= hold_hours + 1:
        return pd.Series(dtype=float)
    positions = np.arange(1, len(merged) - hold_hours)
    rng.shuffle(positions)
    returns: list[float] = []
    next_allowed = pd.Timestamp.min.tz_localize("UTC")
    for entry_idx in positions:
        signal_time = pd.to_datetime(merged.iloc[entry_idx - 1]["timestamp"], utc=True)
        if signal_time < next_allowed:
            continue
        exit_idx = entry_idx + hold_hours
        buy = float(merged.iloc[entry_idx]["open"]) * (1 + ONE_WAY_COST)
        sell = float(merged.iloc[exit_idx]["open"]) * (1 - ONE_WAY_COST)
        returns.append(sell / buy - 1)
        next_allowed = pd.to_datetime(merged.iloc[exit_idx]["timestamp"], utc=True) + pd.Timedelta(hours=int(cooldown_hours))
        if len(returns) >= count:
            break
    return pd.Series(returns, dtype=float)


def classify_verdict(primary: SimulationResult, daily: SimulationResult, weekly: SimulationResult, hostile: list[dict[str, object]]) -> str:
    if primary.ledger.empty:
        return "Rejected"
    holdout = primary.partition_summary[primary.partition_summary["partition"] == "holdout_2025_onward"]
    holdout_trade_count = int(holdout["trade_count"].iloc[0]) if not holdout.empty else 0
    holdout_mean = float(holdout["mean_trade_return"].iloc[0]) if not holdout.empty and pd.notna(holdout["mean_trade_return"].iloc[0]) else np.nan
    trades = primary.ledger["net_trade_return"].dropna()
    bootstrap_low = bootstrap_mean_ci(trades, 29)[0] if len(trades) else np.nan
    hostile_map = {row["check"]: row["mean_trade_return"] for row in hostile}
    beats_hostile = all(
        pd.isna(hostile_map.get(name)) or primary.summary.get("mean_trade_return", np.nan) > hostile_map.get(name)
        for name in ("btc_shock_without_lag_filter", "same_asset_momentum", "matched_random")
    )
    beats_dca = primary.summary["terminal_value"] > max(daily.summary["terminal_value"], weekly.summary["terminal_value"])
    if holdout_trade_count >= MIN_HOLDOUT_TRADES and holdout_mean > 0 and bootstrap_low > 0 and beats_dca and beats_hostile:
        return "Pass"
    if primary.summary["trade_count"] < MIN_HOLDOUT_TRADES:
        return "Insufficient sample"
    return "Rejected"


def bootstrap_mean_ci(values: pd.Series, seed: int) -> tuple[float, float]:
    if values.empty:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    sample = values.to_numpy()
    means = rng.choice(sample, size=(BOOTSTRAP_SAMPLES, len(sample)), replace=True).mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def profit_factor(values: pd.Series) -> float:
    wins = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return wins / losses if losses > 0 else np.nan


def provenance(paths: Paths, coin: str) -> dict[str, object]:
    manifest = json.loads((paths.data / "manifest.json").read_text())
    files = [row for row in manifest["files"] if row["coin"] == coin and row["timeframe"] == "1h"]
    if not files:
        raise RuntimeError(f"No manifest record found for {coin} 1h data")
    return files[0]


def write_report(
    output: Path,
    manifest: dict[str, object],
    summary: pd.DataFrame,
    passive: pd.DataFrame,
    hostile: pd.DataFrame,
) -> None:
    strategy_rows = summary[summary["strategy"] == "btc_shock_alt_underreaction"].copy()
    best = strategy_rows.sort_values("terminal_value", ascending=False).iloc[0]
    holdout = strategy_rows[["asset", "trade_count", "terminal_value", "net_return", "verdict"]]
    passive_best = passive.sort_values("terminal_value", ascending=False).head(4)
    hostile_best = hostile.sort_values(["asset", "mean_trade_return"], ascending=[True, False])

    def render_table(frame: pd.DataFrame) -> str:
        return frame.to_string(index=False)

    lines = [
        "# BTC Shock -> Alt Underreaction Validation",
        "",
        "## Primary rule",
        "",
        f"- {manifest['config']['primary_rule']}",
        f"- Costs: {manifest['config']['one_way_cost']:.2%} per side.",
        f"- Sample: {manifest['config']['sample_start']} through pinned Binance cutoff.",
        "",
        "## Best strategy row",
        "",
        f"- Asset: {best['asset']}",
        f"- Terminal value: ${best['terminal_value']:.2f}",
        f"- Net return: {best['net_return']:.2%}",
        f"- Trades: {int(best['trade_count'])}",
        f"- Verdict: {best['verdict']}",
        "",
        "## Strategy table",
        "",
        render_table(holdout),
        "",
        "## Strongest passive DCA comparators",
        "",
        render_table(passive_best[["asset", "strategy", "terminal_value", "net_return"]]),
        "",
        "## Hostile checks",
        "",
        render_table(hostile_best[["asset", "check", "trade_count", "mean_trade_return"]]),
        "",
        "No result is trading advice. This report uses only finalized Binance spot candles and predeclared execution timing.",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
