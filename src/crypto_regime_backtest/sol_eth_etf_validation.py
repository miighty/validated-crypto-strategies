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
SENSITIVITY_DELTAS = (0.08, 0.10, 0.12)
SENSITIVITY_LEVELS = (0.50, 0.55, 0.60)
SENSITIVITY_HOLDS = (48, 72, 96)


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


def run_sol_eth_etf_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "sol_eth_etf" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    sol = load_ohlcv(paths, "SOL", "1h")
    eth = load_ohlcv(paths, "ETH", "1h")
    sol = sol.loc[sol.index >= pd.Timestamp(config.sample_start)].copy()
    eth = eth.loc[eth.index >= pd.Timestamp(config.sample_start)].copy()
    if sol.empty or eth.empty:
        raise RuntimeError("SOL/ETH 1h data does not cover the requested study window")

    sol_reset = sol.reset_index()
    eth_reset = eth.reset_index()
    sol_reset["timestamp"] = pd.to_datetime(sol_reset["timestamp"], utc=True)
    eth_reset["timestamp"] = pd.to_datetime(eth_reset["timestamp"], utc=True)

    metadata = fetch_market_metadata(paths)
    hourly = load_or_fetch_hourly_series(paths, metadata)
    sol_etf = hourly[hourly["family"].eq("sol_etf")].copy().sort_values("timestamp")
    sol_etf = sol_etf[sol_etf["timestamp"] >= pd.Timestamp(config.sample_start)].copy()
    if sol_etf.empty:
        raise RuntimeError("No SOL ETF Polymarket hourly series found")

    schedule = build_daily_contribution_schedule(sol_reset, config.initial_capital, config.contribution_hour_utc)
    daily = simulate_daily_sol_dca(sol_reset, schedule, config.one_way_cost)
    weekly = simulate_weekly_sol_dca(sol_reset, schedule, config.one_way_cost)
    primary_spec = StrategySpec(
        name="sol_etf_odds_sol_eth_spread",
        delta_threshold=PRIMARY_DELTA_THRESHOLD,
        level_threshold=PRIMARY_LEVEL_THRESHOLD,
        hold_hours=PRIMARY_HOLD_HOURS,
    )
    primary = simulate_sol_eth_spread(sol_reset, eth_reset, sol_etf, schedule, config.one_way_cost, primary_spec)

    sensitivity = run_sensitivity_suite(
        sol_reset,
        eth_reset,
        sol_etf,
        schedule,
        config.one_way_cost,
        baseline_daily_sol=float(daily.summary["final_sol_equivalent"]),
        baseline_weekly_sol=float(weekly.summary["final_sol_equivalent"]),
    )
    hostile = run_hostile_checks(primary, daily, weekly)
    verdict = classify_verdict(primary, daily, weekly, sensitivity, hostile)

    summaries = pd.DataFrame([daily.summary, weekly.summary, primary.summary])
    summaries.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.ledger.assign(strategy="daily_sol_dca"),
            weekly.ledger.assign(strategy="weekly_monday_sol_dca"),
            primary.ledger.assign(strategy="sol_etf_odds_sol_eth_spread"),
        ],
        ignore_index=True,
    ).to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.equity.assign(strategy="daily_sol_dca"),
            weekly.equity.assign(strategy="weekly_monday_sol_dca"),
            primary.equity.assign(strategy="sol_etf_odds_sol_eth_spread"),
        ],
        ignore_index=True,
    ).to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.partition_summary.assign(strategy="daily_sol_dca"),
            weekly.partition_summary.assign(strategy="weekly_monday_sol_dca"),
            primary.partition_summary.assign(strategy="sol_etf_odds_sol_eth_spread"),
        ],
        ignore_index=True,
    ).to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    sol_etf[["timestamp", "slug", "yes_price", "trade_count", "traded_notional"]].to_csv(
        output / "sol_etf_hourly_odds.csv", index=False, float_format="%.17g"
    )

    manifest = {
        "config": asdict(config),
        "sol_data": provenance(paths, "SOL"),
        "eth_data": provenance(paths, "ETH"),
        "sample_rows": int(len(sol_reset)),
        "sample_start": sol_reset["timestamp"].min().isoformat(),
        "sample_end": sol_reset["timestamp"].max().isoformat(),
        "market_slug": str(sol_etf["slug"].iloc[0]),
        "market_question": str(sol_etf["question"].iloc[0]),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summaries, sensitivity, hostile, verdict)
    print(f"SOL/ETH ETF-odds validation written to {output}", flush=True)
    return summaries


def build_daily_contribution_schedule(
    frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int
) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in SOL 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def simulate_daily_sol_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    cash = 0.0
    sol_units = 0.0
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
            sol_units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "daily_sol_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "sol_bought": bought,
                    "cash_after": cash,
                    "sol_after": sol_units,
                }
            )
        close = float(row.close)
        equity = cash + sol_units * close
        records.append(
            {"timestamp": timestamp, "cash": cash, "sol_units": sol_units, "close": close, "equity": equity}
        )
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("daily_sol_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_weekly_sol_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    cash = 0.0
    sol_units = 0.0
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
            sol_units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "weekly_monday_sol_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "sol_bought": bought,
                    "cash_after": cash,
                    "sol_after": sol_units,
                }
            )
        close = float(row.close)
        equity = cash + sol_units * close
        records.append(
            {"timestamp": timestamp, "cash": cash, "sol_units": sol_units, "close": close, "equity": equity}
        )
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("weekly_monday_sol_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def build_sol_etf_signals(hourly: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    frame = hourly.copy().sort_values("timestamp")
    frame["delta_24h"] = frame["yes_price"].diff(24)
    frame = frame.dropna(subset=["delta_24h", "yes_price"]).copy()
    frame = frame[
        (frame["delta_24h"] >= spec.delta_threshold) & (frame["yes_price"] >= spec.level_threshold)
    ].copy()
    frame["entry_time"] = frame["timestamp"] + pd.Timedelta(hours=1)
    frame["exit_time"] = frame["entry_time"] + pd.Timedelta(hours=spec.hold_hours)
    return frame.reset_index(drop=True)


def simulate_sol_eth_spread(
    sol: pd.DataFrame,
    eth: pd.DataFrame,
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    spec: StrategySpec,
) -> SimulationResult:
    signals = build_sol_etf_signals(hourly, spec)
    sol_indexed = sol.set_index("timestamp")
    eth_indexed = eth.set_index("timestamp")
    scheduled = schedule.to_dict()

    cash = 0.0
    active_trade: dict[str, object] | None = None
    cooldown_until = pd.Timestamp.min.tz_localize("UTC")
    pending_signals = signals.to_dict("records")
    signal_idx = 0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []

    for row in sol.itertuples(index=False):
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
                    "kind": "sol_eth_spread_trade",
                    "gross_spend_usd": notional,
                    "fee_slippage_usd": notional * 4 * one_way_cost,
                    "sol_entry_open": active_trade["sol_entry_open"],
                    "eth_entry_open": active_trade["eth_entry_open"],
                    "sol_exit_open": active_trade["sol_exit_open"],
                    "eth_exit_open": active_trade["eth_exit_open"],
                    "soleth_entry_ratio": active_trade["sol_entry_open"] / active_trade["eth_entry_open"],
                    "soleth_exit_ratio": active_trade["sol_exit_open"] / active_trade["eth_exit_open"],
                    "return_pct": net_return,
                    "cash_after": cash,
                }
            )
            cooldown_until = pd.Timestamp(active_trade["exit_time"]) + pd.Timedelta(hours=spec.cooldown_hours)
            active_trade = None

        while signal_idx < len(pending_signals) and pd.Timestamp(pending_signals[signal_idx]["entry_time"]) < timestamp:
            signal_idx += 1

        if active_trade is None and cash > 0 and timestamp >= cooldown_until and signal_idx < len(pending_signals):
            signal = pending_signals[signal_idx]
            if pd.Timestamp(signal["entry_time"]) == timestamp:
                exit_time = pd.Timestamp(signal["exit_time"])
                if exit_time in sol_indexed.index and exit_time in eth_indexed.index:
                    sol_entry_open = float(sol_indexed.at[timestamp, "open"])
                    eth_entry_open = float(eth_indexed.at[timestamp, "open"])
                    sol_exit_open = float(sol_indexed.at[exit_time, "open"])
                    eth_exit_open = float(eth_indexed.at[exit_time, "open"])
                    gross = (sol_exit_open / sol_entry_open - 1.0) - (eth_exit_open / eth_entry_open - 1.0)
                    net = gross - 4 * one_way_cost
                    active_trade = {
                        "signal_time": pd.Timestamp(signal["timestamp"]),
                        "entry_time": timestamp,
                        "exit_time": exit_time,
                        "gross_spend_usd": cash,
                        "sol_entry_open": sol_entry_open,
                        "eth_entry_open": eth_entry_open,
                        "sol_exit_open": sol_exit_open,
                        "eth_exit_open": eth_exit_open,
                        "realized_return_pct": net,
                    }
                    cash = 0.0
                signal_idx += 1

        close = float(row.close)
        equity = cash
        if active_trade is not None:
            notional = float(active_trade["gross_spend_usd"])
            sol_mark = float(sol_indexed.at[timestamp, "close"])
            eth_mark = float(eth_indexed.at[timestamp, "close"])
            live_gross = (sol_mark / float(active_trade["sol_entry_open"]) - 1.0) - (
                eth_mark / float(active_trade["eth_entry_open"]) - 1.0
            )
            live_net = live_gross - 4 * one_way_cost
            equity += max(0.0, notional * (1.0 + live_net))
        sol_equiv = equity / close if close > 0 else 0.0
        records.append(
            {
                "timestamp": timestamp,
                "cash": cash,
                "sol_units": 0.0,
                "close": close,
                "equity": equity,
                "sol_equivalent": sol_equiv,
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
    final_sol_equivalent = float(equity_curve.iloc[-1] / final_close) if final_close > 0 else 0.0
    total_costs = float(ledger["fee_slippage_usd"].sum()) if not ledger.empty else 0.0
    gross_spend = float(ledger["gross_spend_usd"].sum()) if not ledger.empty else 0.0
    if "sol_after" in ledger.columns and not ledger.empty:
        final_sol_units = float(ledger["sol_after"].iloc[-1])
    else:
        final_sol_units = 0.0
    return {
        "strategy": name,
        "final_usd_value": float(equity_curve.iloc[-1]),
        "final_cash_usd": final_cash,
        "final_sol_units": final_sol_units,
        "final_sol_equivalent": final_sol_equivalent,
        "final_sol_close": final_close,
        "event_count": int(len(ledger)),
        "gross_spent_usd": gross_spend,
        "total_costs_usd": total_costs,
        "unused_cash_usd": final_cash,
        "total_return_on_committed_capital": float(equity_curve.iloc[-1] / STARTING_CAPITAL - 1.0),
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
        drawdown = section["equity"] / running_max - 1.0
        ledger_mask = pd.Series(False, index=ledger.index)
        if not ledger.empty and "timestamp" in ledger.columns:
            ledger_mask = ledger["timestamp"] >= partition.start
            if partition.end_exclusive is not None:
                ledger_mask &= ledger["timestamp"] < partition.end_exclusive
        partition_ledger = ledger.loc[ledger_mask] if not ledger.empty else pd.DataFrame()
        rows.append(
            {
                "partition": partition.name,
                "start": section["timestamp"].iloc[0],
                "end": section["timestamp"].iloc[-1],
                "final_usd_value": float(section["equity"].iloc[-1]),
                "final_sol_equivalent": float(section["equity"].iloc[-1] / section["close"].iloc[-1]),
                "events": int(len(partition_ledger)),
                "costs_usd": float(partition_ledger["fee_slippage_usd"].sum()) if not partition_ledger.empty else 0.0,
                "max_drawdown": abs(float(drawdown.min())),
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity_suite(
    sol: pd.DataFrame,
    eth: pd.DataFrame,
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    baseline_daily_sol: float,
    baseline_weekly_sol: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for delta in SENSITIVITY_DELTAS:
        for level in SENSITIVITY_LEVELS:
            for hold in SENSITIVITY_HOLDS:
                spec = StrategySpec(
                    name=f"sol_etf_spread_d{int(delta*1000)}_l{int(level*100)}_h{hold}",
                    delta_threshold=delta,
                    level_threshold=level,
                    hold_hours=hold,
                )
                result = simulate_sol_eth_spread(sol, eth, hourly, schedule, one_way_cost, spec)
                summary = result.summary.copy()
                summary["excess_sol_vs_daily"] = float(summary["final_sol_equivalent"]) - baseline_daily_sol
                summary["excess_sol_vs_weekly"] = float(summary["final_sol_equivalent"]) - baseline_weekly_sol
                summary["check"] = "nearby_parameters"
                rows.append(summary)
    doubled = simulate_sol_eth_spread(
        sol,
        eth,
        hourly,
        schedule,
        one_way_cost * 2,
        StrategySpec("sol_etf_spread_doubled_cost", PRIMARY_DELTA_THRESHOLD, PRIMARY_LEVEL_THRESHOLD, PRIMARY_HOLD_HOURS),
    ).summary
    doubled["check"] = "doubled_cost_primary"
    doubled["excess_sol_vs_daily"] = float(doubled["final_sol_equivalent"]) - baseline_daily_sol
    doubled["excess_sol_vs_weekly"] = float(doubled["final_sol_equivalent"]) - baseline_weekly_sol
    rows.append(doubled)
    return pd.DataFrame(rows)


def run_hostile_checks(primary: SimulationResult, daily: SimulationResult, weekly: SimulationResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary_edge_daily = float(primary.summary["final_sol_equivalent"]) - float(daily.summary["final_sol_equivalent"])
    primary_edge_weekly = float(primary.summary["final_sol_equivalent"]) - float(weekly.summary["final_sol_equivalent"])
    rows.append(
        {
            "check": "primary_edge_vs_dca",
            "value": primary_edge_daily,
            "secondary_value": primary_edge_weekly,
            "passes": primary_edge_daily > 0 and primary_edge_weekly > 0,
        }
    )
    if not primary.ledger.empty:
        contrib = primary.ledger.copy()
        contrib["terminal_sol_equivalent"] = contrib["gross_spend_usd"] * (1.0 + contrib["return_pct"]) / float(
            primary.equity["close"].iloc[-1]
        )
        best_event = contrib.loc[contrib["terminal_sol_equivalent"].idxmax()]
        rows.append(
            {
                "check": "exclude_best_event",
                "value": float(primary.summary["final_sol_equivalent"]) - float(best_event["terminal_sol_equivalent"]) - float(daily.summary["final_sol_equivalent"]),
                "secondary_value": float(primary.summary["final_sol_equivalent"]) - float(best_event["terminal_sol_equivalent"]) - float(weekly.summary["final_sol_equivalent"]),
                "passes": (
                    float(primary.summary["final_sol_equivalent"]) - float(best_event["terminal_sol_equivalent"]) > float(daily.summary["final_sol_equivalent"])
                    and float(primary.summary["final_sol_equivalent"]) - float(best_event["terminal_sol_equivalent"]) > float(weekly.summary["final_sol_equivalent"])
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
        float(primary.summary["final_sol_equivalent"]) > float(daily.summary["final_sol_equivalent"])
        and float(primary.summary["final_sol_equivalent"]) > float(weekly.summary["final_sol_equivalent"])
    )
    holdout = extract_partition(primary.partition_summary, "holdout_2025_onward")
    holdout_weekly = extract_partition(weekly.partition_summary, "holdout_2025_onward")
    nearby = sensitivity[sensitivity["check"].eq("nearby_parameters")].copy() if "check" in sensitivity else pd.DataFrame()
    nearby_pass_rate = float(((nearby["excess_sol_vs_weekly"] > 0) & (nearby["excess_sol_vs_daily"] > 0)).mean()) if not nearby.empty else 0.0
    doubled = sensitivity[sensitivity["check"].eq("doubled_cost_primary")].copy() if "check" in sensitivity else pd.DataFrame()
    doubled_pass = bool(
        not doubled.empty
        and float(doubled.iloc[0]["excess_sol_vs_daily"]) > 0
        and float(doubled.iloc[0]["excess_sol_vs_weekly"]) > 0
    )
    hostile_pass = bool(hostile["passes"].all()) if not hostile.empty else False
    holdout_pass = bool(holdout and holdout_weekly and holdout["final_sol_equivalent"] > holdout_weekly["final_sol_equivalent"])

    if primary.summary["event_count"] == 0:
        label = "rejected"
        reason = "Primary SOL ETF spread rule never triggered in the full sample."
    elif primary.summary["event_count"] < 3:
        label = "inconclusive"
        reason = "Positive signal exists, but fewer than 3 trades is not enough to validate against DCA."
    elif primary_beats_both and holdout_pass and nearby_pass_rate >= 0.5 and hostile_pass and doubled_pass:
        label = "paper-trading candidate"
        reason = "Primary spread rule beat both DCA baselines and cleared the main robustness gates."
    else:
        label = "rejected"
        reason = "The edge does not survive enough of the DCA, robustness, holdout, or cost checks."
    return {
        "verdict": label,
        "reason": reason,
        "primary_beats_both_dca": primary_beats_both,
        "holdout_pass": holdout_pass,
        "nearby_parameter_pass_rate": nearby_pass_rate,
        "hostile_pass": hostile_pass,
        "doubled_cost_pass": doubled_pass,
    }


def extract_partition(frame: pd.DataFrame, name: str) -> dict[str, object] | None:
    if frame.empty:
        return None
    match = frame.loc[frame["partition"] == name]
    return match.iloc[0].to_dict() if not match.empty else None


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
    daily = summaries.loc[summaries["strategy"] == "daily_sol_dca"].iloc[0]
    weekly = summaries.loc[summaries["strategy"] == "weekly_monday_sol_dca"].iloc[0]
    primary = summaries.loc[summaries["strategy"] == "sol_etf_odds_sol_eth_spread"].iloc[0]
    lines = [
        "# SOL ETF Odds → SOL/ETH Spread Validation",
        "",
        "Historical research only. This is not a live-trading instruction.",
        "",
        "## Data",
        "",
        f"- SOL source: {manifest['sol_data']['source']} spot ({manifest['sol_data']['source_symbols']})",
        f"- ETH source: {manifest['eth_data']['source']} spot ({manifest['eth_data']['source_symbols']})",
        f"- Polymarket market: {manifest['market_slug']} — {manifest['market_question']}",
        f"- Study sample: {manifest['sample_start']} to {manifest['sample_end']}",
        f"- Coverage rows: {manifest['sample_rows']}",
        f"- SOL SHA-256: {manifest['sol_data']['sha256']}",
        f"- ETH SHA-256: {manifest['eth_data']['sha256']}",
        "",
        "## Primary rule frozen for this run",
        "",
        "- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC.",
        "- Daily SOL DCA spends each daily tranche immediately.",
        "- Weekly SOL DCA spends the accumulated reserve every Monday 09:00 UTC.",
        "- Spread strategy waits for the SOL ETF Polymarket YES probability to jump by at least 10 points over 24 hours and remain at or above 55%.",
        "- Entry: next hourly open after the completed signal bar.",
        "- Position: long SOL / short ETH spread for 72 hours, using the full currently accrued reserve as margin capital.",
        "- Cooldown: 24 hours after exit.",
        f"- Cost model: {manifest['config']['one_way_cost']:.2%} one-way per leg; spread round-trip cost = {4 * manifest['config']['one_way_cost']:.2%}.",
        "",
        "## Summary",
        "",
        "| Strategy | Final USD | Final SOL-equivalent | Costs USD | Events | Max DD | SOL edge vs daily | SOL edge vs weekly |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Daily SOL DCA | {daily['final_usd_value']:.2f} | {daily['final_sol_equivalent']:.8f} | {daily['total_costs_usd']:.2f} | {int(daily['event_count'])} | {daily['max_drawdown']:.2%} | 0.00000000 | {daily['final_sol_equivalent'] - weekly['final_sol_equivalent']:.8f} |",
        f"| Weekly SOL DCA | {weekly['final_usd_value']:.2f} | {weekly['final_sol_equivalent']:.8f} | {weekly['total_costs_usd']:.2f} | {int(weekly['event_count'])} | {weekly['max_drawdown']:.2%} | {weekly['final_sol_equivalent'] - daily['final_sol_equivalent']:.8f} | 0.00000000 |",
        f"| SOL ETF odds → SOL/ETH spread | {primary['final_usd_value']:.2f} | {primary['final_sol_equivalent']:.8f} | {primary['total_costs_usd']:.2f} | {int(primary['event_count'])} | {primary['max_drawdown']:.2%} | {primary['final_sol_equivalent'] - daily['final_sol_equivalent']:.8f} | {primary['final_sol_equivalent'] - weekly['final_sol_equivalent']:.8f} |",
        "",
        "## Verdict",
        "",
        f"- Verdict: **{verdict['verdict']}**",
        f"- Reason: {verdict['reason']}",
        f"- Beats both DCA baselines: **{verdict['primary_beats_both_dca']}**",
        f"- Holdout 2025+ pass: **{verdict['holdout_pass']}**",
        f"- Nearby-parameter pass rate: **{verdict['nearby_parameter_pass_rate']:.2%}**",
        f"- Doubled-cost pass: **{verdict['doubled_cost_pass']}**",
        f"- Hostile checks pass: **{verdict['hostile_pass']}**",
        "",
        "## Files",
        "",
        "- `strategy_summary.csv`",
        "- `trade_log.csv`",
        "- `equity_curves.csv`",
        "- `partition_summary.csv`",
        "- `sensitivity_checks.csv`",
        "- `hostile_checks.csv`",
        "- `sol_etf_hourly_odds.csv`",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
