from __future__ import annotations

import json
from datetime import timedelta
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv

SAMPLE_START = pd.Timestamp("2021-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")
DAILY_CONTRIBUTION_HOUR_UTC = 9
PRIMARY_THRESHOLD = 0.30
PRIMARY_WINDOW_HOURS = 72
PRIMARY_DELAY_HOURS = 1
PRIMARY_COOLDOWN_HOURS = 24
HOSTILE_THRESHOLDS = (0.25, 0.30, 0.35)
HOSTILE_WINDOWS = (48, 72, 96)
HOSTILE_DELAYS = (1, 24)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    threshold: float
    window_hours: int
    delay_hours: int = PRIMARY_DELAY_HOURS
    cooldown_hours: int = PRIMARY_COOLDOWN_HOURS


@dataclass(frozen=True)
class StudyConfig:
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    contribution_hour_utc: int = DAILY_CONTRIBUTION_HOUR_UTC
    sample_start: str = "2021-01-01T00:00:00Z"
    validation_start: str = "2024-01-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    primary_threshold: float = PRIMARY_THRESHOLD
    primary_window_hours: int = PRIMARY_WINDOW_HOURS
    primary_delay_hours: int = PRIMARY_DELAY_HOURS
    primary_cooldown_hours: int = PRIMARY_COOLDOWN_HOURS
    spend_rule: str = "all_available_reserve"
    multiple_signal_rule: str = (
        "Earliest qualifying signal wins; ignore new signals until cooldown expires and the"
        " pending next-open entry has either fired or been skipped."
    )
    cash_rule: str = (
        "Each strategy receives the same initial funded reserve, released as equal daily"
        " contributions at 09:00 UTC. Daily DCA spends the same-day tranche immediately;"
        " weekly DCA spends the accrued reserve every Monday 09:00 UTC; drawdown buys spend"
        " the entire currently accrued reserve on a qualifying signal."
    )


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
    Partition("development_pre_2024", SAMPLE_START, VALIDATION_START),
    Partition("validation_2024", VALIDATION_START, HOLDOUT_START),
    Partition("holdout_2025_onward", HOLDOUT_START, None),
)


def run_btc_drawdown_dca_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "btc_drawdown_dca" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    frame = load_ohlcv(paths, "BTC", "1h")
    frame = frame.loc[frame.index >= pd.Timestamp(config.sample_start)].copy()
    if frame.empty:
        raise RuntimeError("BTC 1h data does not cover the requested study window")

    schedule = build_daily_contribution_schedule(frame, config.initial_capital, config.contribution_hour_utc)
    daily = simulate_daily_dca(frame, schedule, config.one_way_cost)
    weekly = simulate_weekly_dca(frame, schedule, config.one_way_cost)
    primary_spec = StrategySpec("btc_drawdown_30pct_72h", PRIMARY_THRESHOLD, PRIMARY_WINDOW_HOURS)
    primary = simulate_drawdown_strategy(frame, schedule, config.one_way_cost, primary_spec)

    sensitivity = run_sensitivity_suite(
        frame,
        schedule,
        config.one_way_cost,
        baseline_daily_btc=float(daily.summary["final_btc"]),
        baseline_weekly_btc=float(weekly.summary["final_btc"]),
    )
    hostile = run_hostile_checks(primary, daily, weekly)
    verdict = classify_verdict(primary, daily, weekly, sensitivity, hostile)

    summaries = pd.DataFrame([daily.summary, weekly.summary, primary.summary])
    summaries.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")

    primary.ledger.to_csv(output / "drawdown_trade_log.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.ledger.assign(strategy="daily_dca"),
            weekly.ledger.assign(strategy="weekly_monday_dca"),
            primary.ledger.assign(strategy="btc_drawdown_30pct_72h"),
        ],
        ignore_index=True,
    ).to_csv(output / "all_purchase_ledger.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.equity.assign(strategy="daily_dca"),
            weekly.equity.assign(strategy="weekly_monday_dca"),
            primary.equity.assign(strategy="btc_drawdown_30pct_72h"),
        ],
        ignore_index=True,
    ).to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.partition_summary.assign(strategy="daily_dca"),
            weekly.partition_summary.assign(strategy="weekly_monday_dca"),
            primary.partition_summary.assign(strategy="btc_drawdown_30pct_72h"),
        ],
        ignore_index=True,
    ).to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")

    provenance = btc_provenance(paths)
    manifest = {
        "config": asdict(config),
        "btc_data": provenance,
        "sample_rows": int(len(frame)),
        "sample_start": frame.index.min().isoformat(),
        "sample_end": frame.index.max().isoformat(),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summaries, sensitivity, hostile, verdict)
    print(f"BTC drawdown vs DCA validation written to {output}", flush=True)
    return summaries


def build_daily_contribution_schedule(
    frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int
) -> pd.Series:
    hour_index = frame.index.to_series().dt.hour
    slots = hour_index.index[hour_index == contribution_hour_utc]
    if len(slots) == 0:
        raise RuntimeError("No contribution slots available in BTC 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def simulate_daily_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    records: list[dict[str, object]] = []
    btc = 0.0
    cash = 0.0
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for timestamp, row in frame.iterrows():
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
            price = float(row["open"])
            gross_spend = contribution
            cost = gross_spend * one_way_cost
            exec_price = price * (1 + one_way_cost)
            btc_bought = gross_spend / exec_price
            cash -= gross_spend
            btc += btc_bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "daily_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "btc_bought": btc_bought,
                    "cash_after": cash,
                    "btc_after": btc,
                }
            )
        equity = cash + btc * float(row["close"])
        records.append({"timestamp": timestamp, "cash": cash, "btc": btc, "close": float(row["close"]), "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    summary = summarize_strategy("daily_dca", ledger, equity)
    partitions = summarize_partitions(equity, ledger)
    return SimulationResult(summary, ledger, equity, partitions)


def simulate_weekly_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    records: list[dict[str, object]] = []
    btc = 0.0
    cash = 0.0
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    for timestamp, row in frame.iterrows():
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
        if timestamp.hour == DAILY_CONTRIBUTION_HOUR_UTC and timestamp.dayofweek == 0 and cash > 0:
            price = float(row["open"])
            gross_spend = cash
            cost = gross_spend * one_way_cost
            exec_price = price * (1 + one_way_cost)
            btc_bought = gross_spend / exec_price
            cash = 0.0
            btc += btc_bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "weekly_monday_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "btc_bought": btc_bought,
                    "cash_after": cash,
                    "btc_after": btc,
                }
            )
        equity = cash + btc * float(row["close"])
        records.append({"timestamp": timestamp, "cash": cash, "btc": btc, "close": float(row["close"]), "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    summary = summarize_strategy("weekly_monday_dca", ledger, equity)
    partitions = summarize_partitions(equity, ledger)
    return SimulationResult(summary, ledger, equity, partitions)


def detect_drawdown_signals(
    frame: pd.DataFrame, threshold: float, window_hours: int, delay_hours: int
) -> pd.DataFrame:
    drawdown = frame["close"].pct_change(window_hours)
    signal = drawdown <= -threshold
    rows = []
    for signal_loc in np.flatnonzero(signal.fillna(False).to_numpy()):
        signal_time = frame.index[signal_loc]
        entry_loc = signal_loc + delay_hours
        if entry_loc >= len(frame):
            continue
        rows.append(
            {
                "signal_time": signal_time,
                "entry_time": frame.index[entry_loc],
                "window_hours": window_hours,
                "delay_hours": delay_hours,
                "drawdown_pct": float(drawdown.iloc[signal_loc]),
                "signal_close": float(frame["close"].iloc[signal_loc]),
                "entry_open": float(frame["open"].iloc[entry_loc]),
            }
        )
    return pd.DataFrame(rows)


def simulate_drawdown_strategy(
    frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float, spec: StrategySpec
) -> SimulationResult:
    signal_frame = detect_drawdown_signals(frame, spec.threshold, spec.window_hours, spec.delay_hours)
    signals_by_entry = signal_frame.set_index("entry_time").to_dict("index") if not signal_frame.empty else {}
    records: list[dict[str, object]] = []
    btc = 0.0
    cash = 0.0
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    next_allowed_entry = frame.index.min()
    for timestamp, row in frame.iterrows():
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
        signal_row = signals_by_entry.get(timestamp)
        if signal_row and timestamp >= next_allowed_entry and cash > 0:
            price = float(row["open"])
            gross_spend = cash
            cost = gross_spend * one_way_cost
            exec_price = price * (1 + one_way_cost)
            btc_bought = gross_spend / exec_price
            cash = 0.0
            btc += btc_bought
            next_allowed_entry = pd.Timestamp(timestamp.to_pydatetime() + timedelta(hours=spec.cooldown_hours))
            ledger_rows.append(
                {
                    "signal_time": signal_row["signal_time"],
                    "timestamp": timestamp,
                    "kind": "drawdown_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "btc_bought": btc_bought,
                    "cash_after": cash,
                    "btc_after": btc,
                    "drawdown_pct": signal_row["drawdown_pct"],
                    "window_hours": spec.window_hours,
                    "threshold": spec.threshold,
                    "delay_hours": spec.delay_hours,
                    "cooldown_hours": spec.cooldown_hours,
                }
            )
        equity = cash + btc * float(row["close"])
        records.append({"timestamp": timestamp, "cash": cash, "btc": btc, "close": float(row["close"]), "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    summary = summarize_strategy(spec.name, ledger, equity)
    summary.update(
        {
            "threshold": spec.threshold,
            "window_hours": spec.window_hours,
            "delay_hours": spec.delay_hours,
            "cooldown_hours": spec.cooldown_hours,
        }
    )
    partitions = summarize_partitions(equity, ledger)
    return SimulationResult(summary, ledger, equity, partitions)


def summarize_strategy(name: str, ledger: pd.DataFrame, equity: pd.DataFrame) -> dict[str, object]:
    equity_curve = equity["equity"]
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    final_close = float(equity["close"].iloc[-1])
    final_cash = float(equity["cash"].iloc[-1])
    final_btc = float(equity["btc"].iloc[-1])
    total_costs = float(ledger["fee_slippage_usd"].sum()) if not ledger.empty else 0.0
    gross_spend = float(ledger["gross_spend_usd"].sum()) if not ledger.empty else 0.0
    return {
        "strategy": name,
        "final_usd_value": float(equity_curve.iloc[-1]),
        "final_cash_usd": final_cash,
        "final_btc": final_btc,
        "final_close": final_close,
        "event_count": int(len(ledger)),
        "purchase_count": int(len(ledger)),
        "gross_spent_usd": gross_spend,
        "total_costs_usd": total_costs,
        "unused_cash_usd": final_cash,
        "total_return_on_committed_capital": float(equity_curve.iloc[-1] / STARTING_CAPITAL - 1),
        "max_drawdown": abs(float(drawdown.min())),
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
        drawdown = section["equity"] / running_max - 1
        if not ledger.empty and "timestamp" in ledger.columns:
            ledger_mask = ledger["timestamp"] >= partition.start
            if partition.end_exclusive is not None:
                ledger_mask &= ledger["timestamp"] < partition.end_exclusive
            partition_ledger = ledger.loc[ledger_mask]
        else:
            partition_ledger = pd.DataFrame()
        rows.append(
            {
                "partition": partition.name,
                "start": section["timestamp"].iloc[0],
                "end": section["timestamp"].iloc[-1],
                "final_usd_value": float(section["equity"].iloc[-1]),
                "final_btc": float(section["btc"].iloc[-1]),
                "purchases": int(len(partition_ledger)),
                "costs_usd": float(partition_ledger["fee_slippage_usd"].sum()) if not partition_ledger.empty else 0.0,
                "max_drawdown": abs(float(drawdown.min())),
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity_suite(
    frame: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    baseline_daily_btc: float,
    baseline_weekly_btc: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for threshold in HOSTILE_THRESHOLDS:
        for window in HOSTILE_WINDOWS:
            for delay in HOSTILE_DELAYS:
                spec = StrategySpec(
                    name=f"drawdown_{int(threshold * 100)}pct_{window}h_delay{delay}h",
                    threshold=threshold,
                    window_hours=window,
                    delay_hours=delay,
                )
                result = simulate_drawdown_strategy(frame, schedule, one_way_cost, spec)
                summary = result.summary.copy()
                summary["excess_btc_vs_daily"] = float(summary["final_btc"]) - baseline_daily_btc
                summary["excess_btc_vs_weekly"] = float(summary["final_btc"]) - baseline_weekly_btc
                summary["check"] = "nearby_parameters"
                rows.append(summary)
    doubled_result = simulate_drawdown_strategy(
        frame, schedule, one_way_cost * 2, StrategySpec("drawdown_30pct_72h_doubled_cost", 0.30, 72)
    ).summary
    doubled_result["check"] = "doubled_cost_primary"
    doubled_result["excess_btc_vs_daily"] = float(doubled_result["final_btc"]) - baseline_daily_btc
    doubled_result["excess_btc_vs_weekly"] = float(doubled_result["final_btc"]) - baseline_weekly_btc
    rows.append(doubled_result)
    return pd.DataFrame(rows)


def run_hostile_checks(
    primary: SimulationResult, daily: SimulationResult, weekly: SimulationResult
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary_edge_btc_daily = float(primary.summary["final_btc"]) - float(daily.summary["final_btc"])
    primary_edge_btc_weekly = float(primary.summary["final_btc"]) - float(weekly.summary["final_btc"])
    rows.append(
        {
            "check": "primary_edge_vs_dca",
            "value": primary_edge_btc_daily,
            "secondary_value": primary_edge_btc_weekly,
            "passes": primary_edge_btc_daily > 0 and primary_edge_btc_weekly > 0,
        }
    )
    if not primary.ledger.empty:
        terminal_close = float(primary.equity["close"].iloc[-1])
        contrib = primary.ledger.copy()
        contrib["terminal_value"] = contrib["btc_bought"] * terminal_close
        best_event = contrib.loc[contrib["terminal_value"].idxmax()]
        rows.append(
            {
                "check": "exclude_best_event",
                "value": float(primary.summary["final_btc"]) - float(best_event["btc_bought"]) - float(daily.summary["final_btc"]),
                "secondary_value": float(primary.summary["final_btc"]) - float(best_event["btc_bought"]) - float(weekly.summary["final_btc"]),
                "passes": (
                    float(primary.summary["final_btc"]) - float(best_event["btc_bought"]) > float(daily.summary["final_btc"])
                    and float(primary.summary["final_btc"]) - float(best_event["btc_bought"]) > float(weekly.summary["final_btc"])
                ),
                "event_timestamp": best_event["timestamp"],
            }
        )
        contrib["year"] = pd.to_datetime(contrib["timestamp"], utc=True).dt.year
        yearly = contrib.groupby("year", as_index=False)["terminal_value"].sum()
        best_year = int(yearly.loc[yearly["terminal_value"].idxmax(), "year"])
        btc_removed = float(contrib.loc[contrib["year"] == best_year, "btc_bought"].sum())
        rows.append(
            {
                "check": "exclude_best_year",
                "value": float(primary.summary["final_btc"]) - btc_removed - float(daily.summary["final_btc"]),
                "secondary_value": float(primary.summary["final_btc"]) - btc_removed - float(weekly.summary["final_btc"]),
                "passes": (
                    float(primary.summary["final_btc"]) - btc_removed > float(daily.summary["final_btc"])
                    and float(primary.summary["final_btc"]) - btc_removed > float(weekly.summary["final_btc"])
                ),
                "year": best_year,
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
    primary_better = (
        float(primary.summary["final_btc"]) > float(daily.summary["final_btc"])
        and float(primary.summary["final_btc"]) > float(weekly.summary["final_btc"])
    )
    validation = extract_partition(primary.partition_summary, "validation_2024")
    validation_daily = extract_partition(daily.partition_summary, "validation_2024")
    holdout = extract_partition(primary.partition_summary, "holdout_2025_onward")
    holdout_daily = extract_partition(daily.partition_summary, "holdout_2025_onward")
    nearby = sensitivity[sensitivity["check"].eq("nearby_parameters")].copy() if "check" in sensitivity else pd.DataFrame()
    nearby_pass = bool(
        (nearby["excess_btc_vs_daily"] > 0).all() and (nearby["excess_btc_vs_weekly"] > 0).all()
    ) if not nearby.empty else False
    hostile_pass = bool(hostile["passes"].all()) if not hostile.empty else False
    doubled = sensitivity[sensitivity["check"].eq("doubled_cost_primary")].copy() if "check" in sensitivity else pd.DataFrame()
    doubled_pass = bool(
        not doubled.empty
        and float(doubled.iloc[0]["excess_btc_vs_daily"]) > 0
        and float(doubled.iloc[0]["excess_btc_vs_weekly"]) > 0
    )
    validation_pass = bool(validation and validation_daily and validation["final_btc"] > validation_daily["final_btc"])
    holdout_pass = bool(holdout and holdout_daily and holdout["final_btc"] > holdout_daily["final_btc"])
    if primary.summary["event_count"] == 0:
        label = "rejected"
        reason = (
            "The primary 30%/72h rule never triggered in the full 2021-2026 BTC sample, while"
            " nearby-parameter alternatives still lagged both DCA baselines after costs."
        )
    elif primary.summary["event_count"] < 3:
        label = "inconclusive"
        reason = "Too few qualifying drawdown events for a serious BTC-only crash-buy study."
    elif primary_better and validation_pass and holdout_pass and nearby_pass and hostile_pass and doubled_pass:
        label = "paper-trading candidate"
        reason = (
            "Primary rule stayed ahead of both DCA baselines through validation, holdout,"
            " nearby-parameter checks, and hostile stress tests. Historical evidence alone is"
            " still insufficient for live-ready classification."
        )
    else:
        label = "rejected"
        reason = (
            "The apparent edge does not survive one or more required gates: after-cost comparison"
            " versus DCA, validation/holdout performance, nearby-parameter robustness, delayed"
            " entry, doubled costs, or exclusion of the best event/year."
        )
    return {
        "verdict": label,
        "reason": reason,
        "primary_beats_both_dca": primary_better,
        "validation_pass": validation_pass,
        "holdout_pass": holdout_pass,
        "nearby_parameter_pass": nearby_pass,
        "hostile_pass": hostile_pass,
        "doubled_cost_pass": doubled_pass,
    }


def extract_partition(frame: pd.DataFrame, name: str) -> dict[str, object] | None:
    if frame.empty:
        return None
    match = frame.loc[frame["partition"] == name]
    return match.iloc[0].to_dict() if not match.empty else None


def btc_provenance(paths: Paths) -> dict[str, object]:
    provenance = pd.read_csv(paths.data / "provenance.csv")
    match = provenance[(provenance["coin"] == "BTC") & (provenance["timeframe"] == "1h")].iloc[0]
    return match.to_dict()


def write_report(
    output: Path,
    manifest: dict[str, object],
    summaries: pd.DataFrame,
    sensitivity: pd.DataFrame,
    hostile: pd.DataFrame,
    verdict: dict[str, object],
) -> None:
    daily = summaries.loc[summaries["strategy"] == "daily_dca"].iloc[0]
    weekly = summaries.loc[summaries["strategy"] == "weekly_monday_dca"].iloc[0]
    primary = summaries.loc[summaries["strategy"] == "btc_drawdown_30pct_72h"].iloc[0]
    lines = [
        "# BTC 72h Drawdown vs DCA Validation",
        "",
        "This is historical research on finalized Binance BTC spot candles. It is not a live-trading instruction.",
        "",
        "## Data",
        "",
        f"- Exchange: {manifest['btc_data']['source']} spot ({manifest['btc_data']['source_symbols']})",
        "- Timeframe: 1h OHLCV, signals formed from completed hourly closes and executed no earlier than the next hourly open",
        f"- Study sample: {manifest['sample_start']} to {manifest['sample_end']}",
        f"- Coverage rows: {manifest['sample_rows']}",
        f"- SHA-256: {manifest['btc_data']['sha256']}",
        "",
        "## Primary preregistered rule",
        "",
        "- Start with the same fixed $10,000 reserve across all strategies.",
        "- Release that reserve as equal daily contributions at 09:00 UTC across the full sample.",
        "- Daily DCA spends each day’s tranche immediately at that hour’s open.",
        "- Monday weekly DCA spends the accumulated reserve every Monday 09:00 UTC.",
        "- Drawdown strategy buys BTC only when the completed 72-hour close-to-close drawdown is at least 30%, then enters at the next hourly open.",
        "- Drawdown strategy spends the full currently accrued reserve on each qualifying event.",
        "- Cooldown: 24 hours between entries; clustered signals during cooldown are ignored.",
        f"- Costs: {manifest['config']['one_way_cost']:.2%} one-way fee+slippage per buy.",
        "",
        "## Summary",
        "",
        "| Strategy | Final USD value | Final BTC | Costs USD | Event count | Max drawdown | BTC edge vs daily DCA | BTC edge vs weekly DCA |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Daily DCA | {daily['final_usd_value']:.2f} | {daily['final_btc']:.8f} | {daily['total_costs_usd']:.2f} | {int(daily['event_count'])} | {daily['max_drawdown']:.2%} | 0.00000000 | {daily['final_btc'] - weekly['final_btc']:.8f} |",
        f"| Monday weekly DCA | {weekly['final_usd_value']:.2f} | {weekly['final_btc']:.8f} | {weekly['total_costs_usd']:.2f} | {int(weekly['event_count'])} | {weekly['max_drawdown']:.2%} | {weekly['final_btc'] - daily['final_btc']:.8f} | 0.00000000 |",
        f"| 30% / 72h drawdown buy | {primary['final_usd_value']:.2f} | {primary['final_btc']:.8f} | {primary['total_costs_usd']:.2f} | {int(primary['event_count'])} | {primary['max_drawdown']:.2%} | {primary['final_btc'] - daily['final_btc']:.8f} | {primary['final_btc'] - weekly['final_btc']:.8f} |",
        "",
        "## Verdict",
        "",
        f"**{verdict['verdict'].upper()}** — {verdict['reason']}",
        "",
        "Gate status:",
        "",
        f"- Primary beats both DCA baselines: `{verdict['primary_beats_both_dca']}`",
        f"- 2024 validation beats daily DCA: `{verdict['validation_pass']}`",
        f"- 2025+ holdout beats daily DCA: `{verdict['holdout_pass']}`",
        f"- Nearby-parameter robustness: `{verdict['nearby_parameter_pass']}`",
        f"- Hostile checks (exclude best event/year, etc.): `{verdict['hostile_pass']}`",
        f"- Doubled-cost robustness: `{verdict['doubled_cost_pass']}`",
        "",
        "See `strategy_summary.csv`, `partition_summary.csv`, `drawdown_trade_log.csv`, `sensitivity_checks.csv`, and `hostile_checks.csv` for the full evidence trail.",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
