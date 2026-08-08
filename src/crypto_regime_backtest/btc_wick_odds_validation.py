from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv
from .polymarket_crypto_validation import fetch_market_metadata, load_or_fetch_hourly_series

SAMPLE_START = pd.Timestamp("2023-10-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")
DAILY_CONTRIBUTION_HOUR_UTC = 9
SUPPORTIVE_FAMILIES = ("btc_etf", "eth_etf", "trump_election", "bitcoin_reserve")
PRIMARY_WICK_WINDOW_HOURS = 48
PRIMARY_DRAWDOWN_THRESHOLD = -0.10
PRIMARY_SUPPORT_DELTA_FLOOR = -0.02
PRIMARY_BOUNCE_THRESHOLD = 0.03
PRIMARY_BOUNCE_WINDOW_HOURS = 24
PRIMARY_HOLD_HOURS = 72
PRIMARY_COOLDOWN_HOURS = 48
SENSITIVITY_WICK_WINDOWS = (48, 72)
SENSITIVITY_DRAWDOWNS = (-0.10, -0.12)
SENSITIVITY_SUPPORT_FLOORS = (-0.02, 0.0)
SENSITIVITY_BOUNCES = (0.03, 0.05)
SENSITIVITY_HOLDS = (48, 72, 96)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    wick_window_hours: int
    drawdown_threshold: float
    support_delta_floor: float
    bounce_threshold: float
    bounce_window_hours: int
    hold_hours: int
    cooldown_hours: int = PRIMARY_COOLDOWN_HOURS


@dataclass(frozen=True)
class StudyConfig:
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    contribution_hour_utc: int = DAILY_CONTRIBUTION_HOUR_UTC
    sample_start: str = "2023-10-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    supportive_families: tuple[str, ...] = SUPPORTIVE_FAMILIES
    primary_wick_window_hours: int = PRIMARY_WICK_WINDOW_HOURS
    primary_drawdown_threshold: float = PRIMARY_DRAWDOWN_THRESHOLD
    primary_support_delta_floor: float = PRIMARY_SUPPORT_DELTA_FLOOR
    primary_bounce_threshold: float = PRIMARY_BOUNCE_THRESHOLD
    primary_bounce_window_hours: int = PRIMARY_BOUNCE_WINDOW_HOURS
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
    Partition("development_2023q4_2024", SAMPLE_START, HOLDOUT_START),
    Partition("holdout_2025_onward", HOLDOUT_START, None),
)


def run_btc_wick_odds_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "btc_wick_odds" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    metadata = fetch_market_metadata(paths)
    hourly = load_or_fetch_hourly_series(paths, metadata)
    supportive = hourly[hourly["family"].isin(config.supportive_families)].copy()
    supportive = supportive[supportive["timestamp"] >= pd.Timestamp(config.sample_start)].copy()
    if supportive.empty:
        raise RuntimeError("No supportive Polymarket hourly series found for BTC wick study")

    btc = load_ohlcv(paths, "BTC", "1h")
    btc = btc.loc[btc.index >= pd.Timestamp(config.sample_start)].copy()
    if btc.empty:
        raise RuntimeError("BTC 1h data does not cover the requested BTC wick study window")
    btc_reset = btc.reset_index()
    btc_reset["timestamp"] = pd.to_datetime(btc_reset["timestamp"], utc=True)

    support_composite = build_support_composite(supportive, config.supportive_families)
    schedule = build_daily_contribution_schedule(btc_reset, config.initial_capital, config.contribution_hour_utc)
    daily = simulate_daily_btc_dca(btc_reset, schedule, config.one_way_cost)
    weekly = simulate_weekly_btc_dca(btc_reset, schedule, config.one_way_cost)
    primary_spec = StrategySpec(
        name="btc_wick_supportive_odds_rebound",
        wick_window_hours=PRIMARY_WICK_WINDOW_HOURS,
        drawdown_threshold=PRIMARY_DRAWDOWN_THRESHOLD,
        support_delta_floor=PRIMARY_SUPPORT_DELTA_FLOOR,
        bounce_threshold=PRIMARY_BOUNCE_THRESHOLD,
        bounce_window_hours=PRIMARY_BOUNCE_WINDOW_HOURS,
        hold_hours=PRIMARY_HOLD_HOURS,
    )
    primary = simulate_btc_wick_strategy(btc_reset, support_composite, schedule, config.one_way_cost, primary_spec)

    sensitivity = run_sensitivity_suite(
        btc_reset,
        support_composite,
        schedule,
        config.one_way_cost,
        baseline_daily_btc=float(daily.summary["final_btc_equivalent"]),
        baseline_weekly_btc=float(weekly.summary["final_btc_equivalent"]),
    )
    hostile = run_hostile_checks(primary, daily, weekly)
    verdict = classify_verdict(primary, daily, weekly, sensitivity, hostile)

    summaries = pd.DataFrame([daily.summary, weekly.summary, primary.summary])
    summaries.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.ledger.assign(strategy="daily_btc_dca"),
            weekly.ledger.assign(strategy="weekly_monday_btc_dca"),
            primary.ledger.assign(strategy="btc_wick_supportive_odds_rebound"),
        ],
        ignore_index=True,
    ).to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.equity.assign(strategy="daily_btc_dca"),
            weekly.equity.assign(strategy="weekly_monday_btc_dca"),
            primary.equity.assign(strategy="btc_wick_supportive_odds_rebound"),
        ],
        ignore_index=True,
    ).to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.partition_summary.assign(strategy="daily_btc_dca"),
            weekly.partition_summary.assign(strategy="weekly_monday_btc_dca"),
            primary.partition_summary.assign(strategy="btc_wick_supportive_odds_rebound"),
        ],
        ignore_index=True,
    ).to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    support_composite.to_csv(output / "supportive_odds_composite.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "btc_data": provenance(paths, "BTC"),
        "sample_rows": int(len(btc_reset)),
        "sample_start": btc_reset["timestamp"].min().isoformat(),
        "sample_end": btc_reset["timestamp"].max().isoformat(),
        "supportive_families": list(config.supportive_families),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summaries, sensitivity, hostile, verdict)
    print(f"BTC wick + odds validation written to {output}", flush=True)
    return summaries


def build_support_composite(hourly: pd.DataFrame, families: tuple[str, ...]) -> pd.DataFrame:
    grouped = hourly.groupby(["timestamp", "family"], as_index=False)["yes_price"].mean()
    pivot = grouped.pivot(index="timestamp", columns="family", values="yes_price").sort_index().ffill()
    for family in families:
        if family not in pivot.columns:
            pivot[family] = pd.NA
    pivot = pivot[list(families)]
    composite = pivot.mean(axis=1, skipna=True).to_frame("support_mean").reset_index()
    composite["support_delta_24h"] = composite["support_mean"].diff(24)
    return composite


def build_daily_contribution_schedule(
    frame: pd.DataFrame,
    initial_capital: float,
    contribution_hour_utc: int,
) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in BTC 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def simulate_daily_btc_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    cash = 0.0
    btc_units = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
            price = float(row.open)
            gross_spend = contribution
            cost = gross_spend * one_way_cost
            exec_price = price * (1 + one_way_cost)
            bought = gross_spend / exec_price
            cash -= gross_spend
            btc_units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "daily_btc_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "btc_bought": bought,
                    "cash_after": cash,
                    "btc_after": btc_units,
                }
            )
        close = float(row.close)
        equity = cash + btc_units * close
        records.append({"timestamp": timestamp, "cash": cash, "btc_units": btc_units, "close": close, "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("daily_btc_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_weekly_btc_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    cash = 0.0
    btc_units = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
        if timestamp.hour == DAILY_CONTRIBUTION_HOUR_UTC and timestamp.dayofweek == 0 and cash > 0:
            price = float(row.open)
            gross_spend = cash
            cost = gross_spend * one_way_cost
            exec_price = price * (1 + one_way_cost)
            bought = gross_spend / exec_price
            cash = 0.0
            btc_units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "weekly_btc_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "btc_bought": bought,
                    "cash_after": cash,
                    "btc_after": btc_units,
                }
            )
        close = float(row.close)
        equity = cash + btc_units * close
        records.append({"timestamp": timestamp, "cash": cash, "btc_units": btc_units, "close": close, "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("weekly_monday_btc_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def build_btc_wick_signals(btc: pd.DataFrame, support_composite: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    frame = btc.copy().sort_values("timestamp")
    frame["prior_high"] = frame["high"].shift(1).rolling(spec.wick_window_hours).max()
    frame["wick_drawdown"] = frame["low"] / frame["prior_high"] - 1.0
    support = support_composite.set_index("timestamp")
    rows: list[dict[str, object]] = []
    cooldown_until = pd.Timestamp.min.tz_localize("UTC")
    indexed = frame.set_index("timestamp")
    for row in frame.itertuples(index=False):
        signal_time = pd.Timestamp(row.timestamp)
        if signal_time <= cooldown_until:
            continue
        if pd.isna(row.wick_drawdown) or float(row.wick_drawdown) > spec.drawdown_threshold:
            continue
        support_delta = support["support_delta_24h"].get(signal_time, pd.NA)
        if pd.isna(support_delta) or float(support_delta) < spec.support_delta_floor:
            continue
        event_low = float(row.low)
        confirm_deadline = signal_time + pd.Timedelta(hours=int(spec.bounce_window_hours))
        confirmation_window = indexed.loc[(indexed.index > signal_time) & (indexed.index <= confirm_deadline)]
        reclaim = confirmation_window[confirmation_window["close"] >= event_low * (1 + spec.bounce_threshold)]
        if reclaim.empty:
            continue
        confirmation_time = pd.Timestamp(reclaim.index[0])
        entry_time = confirmation_time + pd.Timedelta(hours=1)
        exit_time = entry_time + pd.Timedelta(hours=int(spec.hold_hours))
        if entry_time not in indexed.index or exit_time not in indexed.index:
            continue
        rows.append(
            {
                "timestamp": signal_time,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "confirmation_time": confirmation_time,
                "event_low": event_low,
                "wick_drawdown": float(row.wick_drawdown),
                "support_delta_24h": float(support_delta),
            }
        )
        cooldown_until = exit_time + pd.Timedelta(hours=int(spec.cooldown_hours))
    return pd.DataFrame(rows)


def simulate_btc_wick_strategy(
    btc: pd.DataFrame,
    support_composite: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    spec: StrategySpec,
) -> SimulationResult:
    signals = build_btc_wick_signals(btc, support_composite, spec)
    cash = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    btc_indexed = btc.set_index("timestamp")
    pending_signals = signals.to_dict("records")
    signal_idx = 0
    active_trade: dict[str, object] | None = None

    for row in btc.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution

        if active_trade is not None and timestamp == pd.Timestamp(active_trade["exit_time"]):
            gross_spend = float(active_trade["gross_spend_usd"])
            net_return = float(active_trade["realized_return_pct"])
            proceeds = gross_spend * (1.0 + net_return)
            cash += max(0.0, proceeds)
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": spec.name,
                    "signal_time": pd.Timestamp(active_trade["signal_time"]),
                    "entry_time": pd.Timestamp(active_trade["entry_time"]),
                    "exit_time": pd.Timestamp(active_trade["exit_time"]),
                    "confirmation_time": pd.Timestamp(active_trade["confirmation_time"]),
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": gross_spend * 2 * one_way_cost,
                    "entry_open": float(active_trade["entry_open"]),
                    "exit_open": float(active_trade["exit_open"]),
                    "event_low": float(active_trade["event_low"]),
                    "wick_drawdown": float(active_trade["wick_drawdown"]),
                    "support_delta_24h": float(active_trade["support_delta_24h"]),
                    "return_pct": net_return,
                    "cash_after": cash,
                }
            )
            active_trade = None

        while signal_idx < len(pending_signals) and pd.Timestamp(pending_signals[signal_idx]["entry_time"]) < timestamp:
            signal_idx += 1

        if active_trade is None and cash > 0 and signal_idx < len(pending_signals):
            signal = pending_signals[signal_idx]
            if pd.Timestamp(signal["entry_time"]) == timestamp:
                exit_time = pd.Timestamp(signal["exit_time"])
                if exit_time in btc_indexed.index:
                    entry_open = float(btc_indexed.at[timestamp, "open"])
                    exit_open = float(btc_indexed.at[exit_time, "open"])
                    gross = exit_open / entry_open - 1.0
                    net = gross - 2 * one_way_cost
                    active_trade = {
                        "signal_time": pd.Timestamp(signal["timestamp"]),
                        "entry_time": timestamp,
                        "exit_time": exit_time,
                        "confirmation_time": pd.Timestamp(signal["confirmation_time"]),
                        "event_low": float(signal["event_low"]),
                        "wick_drawdown": float(signal["wick_drawdown"]),
                        "support_delta_24h": float(signal["support_delta_24h"]),
                        "gross_spend_usd": cash,
                        "entry_open": entry_open,
                        "exit_open": exit_open,
                        "realized_return_pct": net,
                    }
                    cash = 0.0
                signal_idx += 1

        close = float(row.close)
        equity = cash
        if active_trade is not None:
            notional = float(active_trade["gross_spend_usd"])
            live_gross = float(btc_indexed.at[timestamp, "close"]) / float(active_trade["entry_open"]) - 1.0
            live_net = live_gross - 2 * one_way_cost
            equity += max(0.0, notional * (1.0 + live_net))
        btc_equiv = equity / close if close > 0 else 0.0
        records.append(
            {
                "timestamp": timestamp,
                "cash": cash,
                "btc_units": 0.0,
                "close": close,
                "equity": equity,
                "btc_equivalent": btc_equiv,
            }
        )

    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(spec.name, ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def summarize_strategy(name: str, ledger: pd.DataFrame, equity: pd.DataFrame) -> dict[str, object]:
    equity_curve = equity["equity"]
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    final_close = float(equity["close"].iloc[-1])
    final_cash = float(equity["cash"].iloc[-1])
    final_btc_equivalent = float(equity_curve.iloc[-1] / final_close) if final_close > 0 else 0.0
    total_costs = float(ledger["fee_slippage_usd"].sum()) if not ledger.empty else 0.0
    gross_spend = float(ledger["gross_spend_usd"].sum()) if not ledger.empty else 0.0
    trade_returns = ledger["return_pct"] if "return_pct" in ledger.columns else pd.Series(dtype=float)
    return {
        "strategy": name,
        "final_usd_value": float(equity_curve.iloc[-1]),
        "final_cash_usd": final_cash,
        "final_btc_units": 0.0,
        "final_btc_equivalent": final_btc_equivalent,
        "final_btc_close": final_close,
        "event_count": int(len(ledger)),
        "gross_spent_usd": gross_spend,
        "total_costs_usd": total_costs,
        "unused_cash_usd": final_cash,
        "total_return_on_committed_capital": float(equity_curve.iloc[-1] / STARTING_CAPITAL - 1.0),
        "max_drawdown": abs(float(drawdown.min())),
        "avg_trade_return": float(trade_returns.mean()) if not trade_returns.empty else pd.NA,
        "win_rate": float(trade_returns.gt(0).mean()) if not trade_returns.empty else pd.NA,
    }


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
        if not ledger.empty and "entry_time" in ledger.columns:
            ledger_mask = ledger["entry_time"] >= partition.start
            if partition.end_exclusive is not None:
                ledger_mask &= ledger["entry_time"] < partition.end_exclusive
        partition_ledger = ledger.loc[ledger_mask] if not ledger.empty else pd.DataFrame()
        trade_returns = partition_ledger["return_pct"] if "return_pct" in partition_ledger.columns else pd.Series(dtype=float)
        rows.append(
            {
                "partition": partition.name,
                "start": section["timestamp"].iloc[0],
                "end": section["timestamp"].iloc[-1],
                "final_usd_value": float(section["equity"].iloc[-1]),
                "final_btc_equivalent": float(section["equity"].iloc[-1] / section["close"].iloc[-1]),
                "events": int(len(partition_ledger)),
                "costs_usd": float(partition_ledger["fee_slippage_usd"].sum()) if not partition_ledger.empty else 0.0,
                "max_drawdown": abs(float(drawdown.min())),
                "avg_trade_return": float(trade_returns.mean()) if not trade_returns.empty else pd.NA,
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity_suite(
    btc: pd.DataFrame,
    support_composite: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    baseline_daily_btc: float,
    baseline_weekly_btc: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for wick_window in SENSITIVITY_WICK_WINDOWS:
        for drawdown in SENSITIVITY_DRAWDOWNS:
            for support_floor in SENSITIVITY_SUPPORT_FLOORS:
                for bounce in SENSITIVITY_BOUNCES:
                    for hold in SENSITIVITY_HOLDS:
                        spec = StrategySpec(
                            name=(
                                f"btc_wick_w{wick_window}_dd{int(abs(drawdown)*100)}"
                                f"_sf{int((support_floor + 0.1) * 100)}_b{int(bounce*100)}_h{hold}"
                            ),
                            wick_window_hours=wick_window,
                            drawdown_threshold=drawdown,
                            support_delta_floor=support_floor,
                            bounce_threshold=bounce,
                            bounce_window_hours=PRIMARY_BOUNCE_WINDOW_HOURS,
                            hold_hours=hold,
                        )
                        result = simulate_btc_wick_strategy(btc, support_composite, schedule, one_way_cost, spec)
                        summary = result.summary.copy()
                        summary["excess_btc_vs_daily"] = float(summary["final_btc_equivalent"]) - baseline_daily_btc
                        summary["excess_btc_vs_weekly"] = float(summary["final_btc_equivalent"]) - baseline_weekly_btc
                        summary["check"] = "nearby_parameters"
                        rows.append(summary)
    doubled = simulate_btc_wick_strategy(
        btc,
        support_composite,
        schedule,
        one_way_cost * 2,
        StrategySpec(
            name="btc_wick_doubled_cost",
            wick_window_hours=PRIMARY_WICK_WINDOW_HOURS,
            drawdown_threshold=PRIMARY_DRAWDOWN_THRESHOLD,
            support_delta_floor=PRIMARY_SUPPORT_DELTA_FLOOR,
            bounce_threshold=PRIMARY_BOUNCE_THRESHOLD,
            bounce_window_hours=PRIMARY_BOUNCE_WINDOW_HOURS,
            hold_hours=PRIMARY_HOLD_HOURS,
        ),
    ).summary
    doubled["check"] = "doubled_cost_primary"
    doubled["excess_btc_vs_daily"] = float(doubled["final_btc_equivalent"]) - baseline_daily_btc
    doubled["excess_btc_vs_weekly"] = float(doubled["final_btc_equivalent"]) - baseline_weekly_btc
    rows.append(doubled)
    return pd.DataFrame(rows)


def run_hostile_checks(primary: SimulationResult, daily: SimulationResult, weekly: SimulationResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary_edge_daily = float(primary.summary["final_btc_equivalent"]) - float(daily.summary["final_btc_equivalent"])
    primary_edge_weekly = float(primary.summary["final_btc_equivalent"]) - float(weekly.summary["final_btc_equivalent"])
    rows.append(
        {
            "check": "primary_edge_vs_dca",
            "value": primary_edge_daily,
            "secondary_value": primary_edge_weekly,
            "passes": primary_edge_daily > 0 and primary_edge_weekly > 0,
        }
    )
    holdout = primary.partition_summary[primary.partition_summary["partition"].eq("holdout_2025_onward")]
    rows.append(
        {
            "check": "holdout_positive",
            "value": float(holdout.iloc[0]["avg_trade_return"]) if not holdout.empty and pd.notna(holdout.iloc[0]["avg_trade_return"]) else pd.NA,
            "secondary_value": float(holdout.iloc[0]["events"]) if not holdout.empty else 0,
            "passes": bool(not holdout.empty and float(holdout.iloc[0]["events"]) >= 1 and float(holdout.iloc[0]["avg_trade_return"]) > 0),
        }
    )
    if not primary.ledger.empty:
        contrib = primary.ledger.copy()
        contrib["terminal_btc_equivalent"] = contrib["gross_spend_usd"] * (1.0 + contrib["return_pct"]) / float(primary.equity["close"].iloc[-1])
        best_event = contrib.loc[contrib["terminal_btc_equivalent"].idxmax()]
        rows.append(
            {
                "check": "exclude_best_event",
                "value": float(primary.summary["final_btc_equivalent"]) - float(best_event["terminal_btc_equivalent"]) - float(daily.summary["final_btc_equivalent"]),
                "secondary_value": float(primary.summary["final_btc_equivalent"]) - float(best_event["terminal_btc_equivalent"]) - float(weekly.summary["final_btc_equivalent"]),
                "passes": (
                    float(primary.summary["final_btc_equivalent"]) - float(best_event["terminal_btc_equivalent"]) > float(daily.summary["final_btc_equivalent"])
                    and float(primary.summary["final_btc_equivalent"]) - float(best_event["terminal_btc_equivalent"]) > float(weekly.summary["final_btc_equivalent"])
                ),
                "event_timestamp": best_event["timestamp"],
            }
        )
    return pd.DataFrame(rows)


def classify_verdict(
    primary: SimulationResult,
    daily: SimulationResult,
    weekly: SimulationResult,
    sensitivity: pd.DataFrame,
    hostile: pd.DataFrame,
) -> dict[str, object]:
    primary_beats_both = (
        float(primary.summary["final_btc_equivalent"]) > float(daily.summary["final_btc_equivalent"])
        and float(primary.summary["final_btc_equivalent"]) > float(weekly.summary["final_btc_equivalent"])
    )
    nearby = sensitivity[sensitivity["check"].eq("nearby_parameters")].copy() if "check" in sensitivity else pd.DataFrame()
    nearby_pass_rate = float(((nearby["excess_btc_vs_weekly"] > 0) & (nearby["excess_btc_vs_daily"] > 0)).mean()) if not nearby.empty else 0.0
    doubled = sensitivity[sensitivity["check"].eq("doubled_cost_primary")].copy() if "check" in sensitivity else pd.DataFrame()
    doubled_pass = bool(
        not doubled.empty
        and float(doubled.iloc[0]["excess_btc_vs_daily"]) > 0
        and float(doubled.iloc[0]["excess_btc_vs_weekly"]) > 0
    )
    holdout = primary.partition_summary[primary.partition_summary["partition"].eq("holdout_2025_onward")]
    holdout_events = int(holdout.iloc[0]["events"]) if not holdout.empty else 0
    holdout_avg = float(holdout.iloc[0]["avg_trade_return"]) if not holdout.empty and pd.notna(holdout.iloc[0]["avg_trade_return"]) else 0.0
    hostile_pass = bool(hostile[hostile["check"].eq("primary_edge_vs_dca")]["passes"].all()) if not hostile.empty else False

    if primary.summary["event_count"] == 0:
        label = "rejected"
        reason = "No qualifying trades under the preregistered wick + odds rule."
    elif primary_beats_both and doubled_pass and nearby_pass_rate >= 0.5 and holdout_events >= 2 and holdout_avg > 0:
        label = "promising_but_inconclusive"
        reason = "Positive after-cost edge vs both DCA baselines survived nearby parameters and doubled costs, but the untouched holdout still has only a few events."
    elif primary_beats_both and hostile_pass:
        label = "promising_but_inconclusive"
        reason = "The rule beat both DCA baselines, but evidence is still sparse and fragile to concentration checks."
    else:
        label = "rejected"
        reason = "The wick + odds rebound rule failed the baseline or robustness gates."

    return {
        "label": label,
        "reason": reason,
        "primary_beats_both_dca": primary_beats_both,
        "nearby_parameter_pass_rate": nearby_pass_rate,
        "doubled_cost_pass": doubled_pass,
        "holdout_events": holdout_events,
        "holdout_avg_trade_return": holdout_avg,
    }


def provenance(paths: Paths, coin: str) -> dict[str, object]:
    source = pd.read_csv(paths.data / "provenance.csv")
    match = source[(source["coin"] == coin) & (source["timeframe"] == "1h")].iloc[0]
    return match.to_dict()


def write_report(
    output: Path,
    manifest: dict[str, object],
    summaries: pd.DataFrame,
    sensitivity: pd.DataFrame,
    hostile: pd.DataFrame,
    verdict: dict[str, object],
) -> None:
    primary = summaries[summaries["strategy"].eq("btc_wick_supportive_odds_rebound")].iloc[0]
    daily = summaries[summaries["strategy"].eq("daily_btc_dca")].iloc[0]
    weekly = summaries[summaries["strategy"].eq("weekly_monday_btc_dca")].iloc[0]
    lines = [
        "# BTC wick flush + supportive odds validation",
        "",
        "## Primary preregistered rule",
        "",
        "- Timeframe: `1h` BTC spot bars from Binance.",
        "- Wick detector: `low / rolling_max(high.shift(1), 48h) - 1 <= -10%`.",
        "- Rolling peak excludes the current bar via `shift(1)` to avoid lookahead.",
        "- Support filter: mean YES odds across BTC ETF, ETH ETF, Trump election, and Bitcoin reserve markets must have a 24h delta of at least `-2` points.",
        "- Confirmation: first close within the next `24h` that is at least `3%` above the event low.",
        "- Entry: next hourly open after confirmation; exit `72h` later at the next hourly open.",
        "- Cooldown: no overlapping positions; wait until `48h` after exit before accepting a new event.",
        "",
        "## Result table",
        "",
        summaries.to_string(index=False),
        "",
        "## Partition summary",
        "",
        pd.read_csv(output / "partition_summary.csv").to_string(index=False),
        "",
        "## Sensitivity checks",
        "",
        sensitivity.to_string(index=False),
        "",
        "## Hostile checks",
        "",
        hostile.to_string(index=False),
        "",
        "## Verdict",
        "",
        json.dumps(verdict, indent=2),
        "",
        "## Key takeaways",
        "",
        f"- Primary final BTC-equivalent: {float(primary['final_btc_equivalent']):.8f} vs daily DCA {float(daily['final_btc_equivalent']):.8f} and weekly DCA {float(weekly['final_btc_equivalent']):.8f}.",
        f"- Trade count: {int(primary['event_count'])}; average realized trade return: {float(primary['avg_trade_return']):.2%}.",
        f"- User-facing label: {verdict['label']}. {verdict['reason']}",
        "",
        "## Manifest",
        "",
        json.dumps(manifest, indent=2),
        "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
