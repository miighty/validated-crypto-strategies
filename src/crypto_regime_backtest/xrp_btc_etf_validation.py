from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv
from .polymarket_crypto_validation import fetch_market_metadata, load_or_fetch_hourly_series

SAMPLE_START = pd.Timestamp("2025-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-05-01T00:00:00Z")
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
    sample_start: str = "2025-01-01T00:00:00Z"
    holdout_start: str = "2025-05-01T00:00:00Z"
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
    Partition("development_2025q1", SAMPLE_START, HOLDOUT_START),
    Partition("holdout_2025q2_onward", HOLDOUT_START, None),
)


def run_xrp_btc_etf_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "xrp_btc_etf" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    xrp = load_ohlcv(paths, "XRP", "1h")
    btc = load_ohlcv(paths, "BTC", "1h")
    xrp = xrp.loc[xrp.index >= pd.Timestamp(config.sample_start)].copy()
    btc = btc.loc[btc.index >= pd.Timestamp(config.sample_start)].copy()
    if xrp.empty or btc.empty:
        raise RuntimeError("XRP/BTC 1h data does not cover the requested study window")

    xrp_reset = xrp.reset_index()
    btc_reset = btc.reset_index()
    xrp_reset["timestamp"] = pd.to_datetime(xrp_reset["timestamp"], utc=True)
    btc_reset["timestamp"] = pd.to_datetime(btc_reset["timestamp"], utc=True)

    metadata = fetch_market_metadata(paths)
    hourly = load_or_fetch_hourly_series(paths, metadata)
    xrp_etf = hourly[hourly["family"].eq("xrp_etf")].copy().sort_values("timestamp")
    xrp_etf = xrp_etf[xrp_etf["timestamp"] >= pd.Timestamp(config.sample_start)].copy()
    if xrp_etf.empty:
        raise RuntimeError("No XRP ETF Polymarket hourly series found")

    schedule = build_daily_contribution_schedule(xrp_reset, config.initial_capital, config.contribution_hour_utc)
    daily = simulate_daily_xrp_dca(xrp_reset, schedule, config.one_way_cost)
    weekly = simulate_weekly_xrp_dca(xrp_reset, schedule, config.one_way_cost)
    primary_spec = StrategySpec(
        name="xrp_etf_odds_xrp_btc_spread",
        delta_threshold=PRIMARY_DELTA_THRESHOLD,
        level_threshold=PRIMARY_LEVEL_THRESHOLD,
        hold_hours=PRIMARY_HOLD_HOURS,
    )
    primary = simulate_xrp_btc_spread(xrp_reset, btc_reset, xrp_etf, schedule, config.one_way_cost, primary_spec)

    sensitivity = run_sensitivity_suite(
        xrp_reset,
        btc_reset,
        xrp_etf,
        schedule,
        config.one_way_cost,
        baseline_daily_xrp=float(daily.summary["final_xrp_equivalent"]),
        baseline_weekly_xrp=float(weekly.summary["final_xrp_equivalent"]),
    )
    hostile = run_hostile_checks(primary, daily, weekly)
    verdict = classify_verdict(primary, daily, weekly, sensitivity, hostile)

    summaries = pd.DataFrame([daily.summary, weekly.summary, primary.summary])
    summaries.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.ledger.assign(strategy="daily_xrp_dca"),
            weekly.ledger.assign(strategy="weekly_monday_xrp_dca"),
            primary.ledger.assign(strategy="xrp_etf_odds_xrp_btc_spread"),
        ],
        ignore_index=True,
    ).to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.equity.assign(strategy="daily_xrp_dca"),
            weekly.equity.assign(strategy="weekly_monday_xrp_dca"),
            primary.equity.assign(strategy="xrp_etf_odds_xrp_btc_spread"),
        ],
        ignore_index=True,
    ).to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.partition_summary.assign(strategy="daily_xrp_dca"),
            weekly.partition_summary.assign(strategy="weekly_monday_xrp_dca"),
            primary.partition_summary.assign(strategy="xrp_etf_odds_xrp_btc_spread"),
        ],
        ignore_index=True,
    ).to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    xrp_etf[["timestamp", "slug", "yes_price", "trade_count", "traded_notional"]].to_csv(
        output / "xrp_etf_hourly_odds.csv", index=False, float_format="%.17g"
    )

    manifest = {
        "config": asdict(config),
        "xrp_data": provenance(paths, "XRP"),
        "btc_data": provenance(paths, "BTC"),
        "sample_rows": int(len(xrp_reset)),
        "sample_start": xrp_reset["timestamp"].min().isoformat(),
        "sample_end": xrp_reset["timestamp"].max().isoformat(),
        "market_slug": str(xrp_etf["slug"].iloc[0]),
        "market_question": str(xrp_etf["question"].iloc[0]),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summaries, sensitivity, hostile, verdict)
    print(f"XRP/BTC ETF-odds validation written to {output}", flush=True)
    return summaries


def build_daily_contribution_schedule(
    frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int
) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in XRP 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def simulate_daily_xrp_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    cash = 0.0
    xrp_units = 0.0
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
            xrp_units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "daily_xrp_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "xrp_bought": bought,
                    "cash_after": cash,
                    "xrp_after": xrp_units,
                }
            )
        close = float(row.close)
        equity = cash + xrp_units * close
        records.append(
            {"timestamp": timestamp, "cash": cash, "xrp_units": xrp_units, "close": close, "equity": equity}
        )
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("daily_xrp_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def simulate_weekly_xrp_dca(frame: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> SimulationResult:
    cash = 0.0
    xrp_units = 0.0
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
            xrp_units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": "weekly_monday_xrp_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "xrp_bought": bought,
                    "cash_after": cash,
                    "xrp_after": xrp_units,
                }
            )
        close = float(row.close)
        equity = cash + xrp_units * close
        records.append(
            {"timestamp": timestamp, "cash": cash, "xrp_units": xrp_units, "close": close, "equity": equity}
        )
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy("weekly_monday_xrp_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def build_xrp_etf_signals(hourly: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    frame = hourly.copy().sort_values("timestamp")
    frame["delta_24h"] = frame["yes_price"].diff(24)
    frame = frame.dropna(subset=["delta_24h", "yes_price"]).copy()
    frame = frame[
        (frame["delta_24h"] >= spec.delta_threshold) & (frame["yes_price"] >= spec.level_threshold)
    ].copy()
    frame["entry_time"] = frame["timestamp"] + pd.Timedelta(hours=1)
    frame["exit_time"] = frame["entry_time"] + pd.Timedelta(hours=spec.hold_hours)
    return frame.reset_index(drop=True)


def simulate_xrp_btc_spread(
    xrp: pd.DataFrame,
    btc: pd.DataFrame,
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    spec: StrategySpec,
) -> SimulationResult:
    signals = build_xrp_etf_signals(hourly, spec)
    xrp_indexed = xrp.set_index("timestamp")
    btc_indexed = btc.set_index("timestamp")
    scheduled = schedule.to_dict()

    cash = 0.0
    active_trade: dict[str, object] | None = None
    cooldown_until = pd.Timestamp.min.tz_localize("UTC")
    pending_signals = signals.to_dict("records")
    signal_idx = 0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []

    for row in xrp.itertuples(index=False):
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
                    "kind": "xrp_btc_spread_trade",
                    "gross_spend_usd": notional,
                    "fee_slippage_usd": notional * 4 * one_way_cost,
                    "xrp_entry_open": active_trade["xrp_entry_open"],
                    "btc_entry_open": active_trade["btc_entry_open"],
                    "xrp_exit_open": active_trade["xrp_exit_open"],
                    "btc_exit_open": active_trade["btc_exit_open"],
                    "xrpbtc_entry_ratio": active_trade["xrp_entry_open"] / active_trade["btc_entry_open"],
                    "xrpbtc_exit_ratio": active_trade["xrp_exit_open"] / active_trade["btc_exit_open"],
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
                if exit_time in xrp_indexed.index and exit_time in btc_indexed.index:
                    xrp_entry_open = float(xrp_indexed.at[timestamp, "open"])
                    btc_entry_open = float(btc_indexed.at[timestamp, "open"])
                    xrp_exit_open = float(xrp_indexed.at[exit_time, "open"])
                    btc_exit_open = float(btc_indexed.at[exit_time, "open"])
                    gross = (xrp_exit_open / xrp_entry_open - 1.0) - (btc_exit_open / btc_entry_open - 1.0)
                    net = gross - 4 * one_way_cost
                    active_trade = {
                        "signal_time": pd.Timestamp(signal["timestamp"]),
                        "entry_time": timestamp,
                        "exit_time": exit_time,
                        "gross_spend_usd": cash,
                        "xrp_entry_open": xrp_entry_open,
                        "btc_entry_open": btc_entry_open,
                        "xrp_exit_open": xrp_exit_open,
                        "btc_exit_open": btc_exit_open,
                        "realized_return_pct": net,
                    }
                    cash = 0.0
                signal_idx += 1

        close = float(row.close)
        equity = cash
        if active_trade is not None:
            notional = float(active_trade["gross_spend_usd"])
            xrp_mark = float(xrp_indexed.at[timestamp, "close"])
            btc_mark = float(btc_indexed.at[timestamp, "close"])
            live_gross = (xrp_mark / float(active_trade["xrp_entry_open"]) - 1.0) - (
                btc_mark / float(active_trade["btc_entry_open"]) - 1.0
            )
            live_net = live_gross - 4 * one_way_cost
            equity += max(0.0, notional * (1.0 + live_net))
        xrp_equiv = equity / close if close > 0 else 0.0
        records.append(
            {
                "timestamp": timestamp,
                "cash": cash,
                "xrp_units": 0.0,
                "close": close,
                "equity": equity,
                "xrp_equivalent": xrp_equiv,
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
    final_xrp_equivalent = float(equity_curve.iloc[-1] / final_close) if final_close > 0 else 0.0
    total_costs = float(ledger["fee_slippage_usd"].sum()) if not ledger.empty else 0.0
    gross_spend = float(ledger["gross_spend_usd"].sum()) if not ledger.empty else 0.0
    avg_trade_return_pct = float(ledger["return_pct"].mean()) if "return_pct" in ledger.columns and not ledger.empty else 0.0
    win_rate = float((ledger["return_pct"] > 0).mean()) if "return_pct" in ledger.columns and not ledger.empty else 0.0
    if "xrp_after" in ledger.columns and not ledger.empty:
        final_xrp_units = float(ledger["xrp_after"].iloc[-1])
    else:
        final_xrp_units = 0.0
    return {
        "strategy": name,
        "final_usd_value": float(equity_curve.iloc[-1]),
        "final_cash_usd": final_cash,
        "final_xrp_units": final_xrp_units,
        "final_xrp_equivalent": final_xrp_equivalent,
        "final_xrp_close": final_close,
        "event_count": int(len(ledger)),
        "gross_spent_usd": gross_spend,
        "total_costs_usd": total_costs,
        "avg_trade_return_pct": avg_trade_return_pct,
        "win_rate": win_rate,
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
                "final_xrp_equivalent": float(section["equity"].iloc[-1] / section["close"].iloc[-1]),
                "events": int(len(partition_ledger)),
                "costs_usd": float(partition_ledger["fee_slippage_usd"].sum()) if not partition_ledger.empty else 0.0,
                "max_drawdown": abs(float(drawdown.min())),
            }
        )
    return pd.DataFrame(rows)


def run_sensitivity_suite(
    xrp: pd.DataFrame,
    btc: pd.DataFrame,
    hourly: pd.DataFrame,
    schedule: pd.Series,
    one_way_cost: float,
    baseline_daily_xrp: float,
    baseline_weekly_xrp: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for delta in SENSITIVITY_DELTAS:
        for level in SENSITIVITY_LEVELS:
            for hold in SENSITIVITY_HOLDS:
                spec = StrategySpec(
                    name=f"xrp_etf_spread_d{int(delta*1000)}_l{int(level*100)}_h{hold}",
                    delta_threshold=delta,
                    level_threshold=level,
                    hold_hours=hold,
                )
                result = simulate_xrp_btc_spread(xrp, btc, hourly, schedule, one_way_cost, spec)
                summary = result.summary.copy()
                summary["excess_xrp_vs_daily"] = float(summary["final_xrp_equivalent"]) - baseline_daily_xrp
                summary["excess_xrp_vs_weekly"] = float(summary["final_xrp_equivalent"]) - baseline_weekly_xrp
                summary["check"] = "nearby_parameters"
                rows.append(summary)
    doubled = simulate_xrp_btc_spread(
        xrp,
        btc,
        hourly,
        schedule,
        one_way_cost * 2,
        StrategySpec("xrp_etf_spread_doubled_cost", PRIMARY_DELTA_THRESHOLD, PRIMARY_LEVEL_THRESHOLD, PRIMARY_HOLD_HOURS),
    ).summary
    doubled["check"] = "doubled_cost_primary"
    doubled["excess_xrp_vs_daily"] = float(doubled["final_xrp_equivalent"]) - baseline_daily_xrp
    doubled["excess_xrp_vs_weekly"] = float(doubled["final_xrp_equivalent"]) - baseline_weekly_xrp
    rows.append(doubled)
    return pd.DataFrame(rows)


def run_hostile_checks(primary: SimulationResult, daily: SimulationResult, weekly: SimulationResult) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    primary_edge_daily = float(primary.summary["final_xrp_equivalent"]) - float(daily.summary["final_xrp_equivalent"])
    primary_edge_weekly = float(primary.summary["final_xrp_equivalent"]) - float(weekly.summary["final_xrp_equivalent"])
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
        contrib["terminal_xrp_equivalent"] = contrib["gross_spend_usd"] * (1.0 + contrib["return_pct"]) / float(
            primary.equity["close"].iloc[-1]
        )
        best_event = contrib.loc[contrib["terminal_xrp_equivalent"].idxmax()]
        rows.append(
            {
                "check": "exclude_best_event",
                "value": float(primary.summary["final_xrp_equivalent"]) - float(best_event["terminal_xrp_equivalent"]) - float(daily.summary["final_xrp_equivalent"]),
                "secondary_value": float(primary.summary["final_xrp_equivalent"]) - float(best_event["terminal_xrp_equivalent"]) - float(weekly.summary["final_xrp_equivalent"]),
                "passes": (
                    float(primary.summary["final_xrp_equivalent"]) - float(best_event["terminal_xrp_equivalent"]) > float(daily.summary["final_xrp_equivalent"])
                    and float(primary.summary["final_xrp_equivalent"]) - float(best_event["terminal_xrp_equivalent"]) > float(weekly.summary["final_xrp_equivalent"])
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
        float(primary.summary["final_xrp_equivalent"]) > float(daily.summary["final_xrp_equivalent"])
        and float(primary.summary["final_xrp_equivalent"]) > float(weekly.summary["final_xrp_equivalent"])
    )
    holdout = extract_partition(primary.partition_summary, "holdout_2025q2_onward")
    holdout_weekly = extract_partition(weekly.partition_summary, "holdout_2025q2_onward")
    nearby = sensitivity[sensitivity["check"].eq("nearby_parameters")].copy() if "check" in sensitivity else pd.DataFrame()
    nearby_pass_rate = float(((nearby["excess_xrp_vs_weekly"] > 0) & (nearby["excess_xrp_vs_daily"] > 0)).mean()) if not nearby.empty else 0.0
    doubled = sensitivity[sensitivity["check"].eq("doubled_cost_primary")].copy() if "check" in sensitivity else pd.DataFrame()
    doubled_pass = bool(
        not doubled.empty
        and float(doubled.iloc[0]["excess_xrp_vs_daily"]) > 0
        and float(doubled.iloc[0]["excess_xrp_vs_weekly"]) > 0
    )
    hostile_pass = bool(hostile["passes"].all()) if not hostile.empty else False
    holdout_pass = bool(holdout and holdout_weekly and holdout["final_xrp_equivalent"] > holdout_weekly["final_xrp_equivalent"])

    if primary.summary["event_count"] == 0:
        label = "rejected"
        reason = "Primary XRP ETF spread rule never triggered in the full sample."
    elif float(primary.summary.get("avg_trade_return_pct", 0.0)) <= 0:
        label = "rejected"
        reason = "All realized XRP/BTC spread trades were negative after costs; apparent outperformance came from holding cash, not from a profitable signal."
    elif primary.summary["event_count"] < 5:
        label = "inconclusive"
        reason = "Positive signal exists, but fewer than 5 trades is still too small to validate against DCA."
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
    daily = summaries.loc[summaries["strategy"] == "daily_xrp_dca"].iloc[0]
    weekly = summaries.loc[summaries["strategy"] == "weekly_monday_xrp_dca"].iloc[0]
    primary = summaries.loc[summaries["strategy"] == "xrp_etf_odds_xrp_btc_spread"].iloc[0]
    lines = [
        "# XRP ETF Odds → XRP/BTC Spread Validation",
        "",
        "Historical research only. This is not a live-trading instruction.",
        "",
        "## Data",
        "",
        f"- XRP source: {manifest['xrp_data']['source']} spot ({manifest['xrp_data']['source_symbols']})",
        f"- BTC source: {manifest['btc_data']['source']} spot ({manifest['btc_data']['source_symbols']})",
        f"- Polymarket market: {manifest['market_slug']} — {manifest['market_question']}",
        f"- Study sample: {manifest['sample_start']} to {manifest['sample_end']}",
        f"- Coverage rows: {manifest['sample_rows']}",
        f"- XRP SHA-256: {manifest['xrp_data']['sha256']}",
        f"- BTC SHA-256: {manifest['btc_data']['sha256']}",
        "",
        "## Primary rule frozen for this run",
        "",
        "- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC.",
        "- Daily XRP DCA spends each daily tranche immediately.",
        "- Weekly XRP DCA spends the accumulated reserve every Monday 09:00 UTC.",
        "- Spread strategy waits for the XRP ETF Polymarket YES probability to jump by at least 10 points over 24 completed hours and remain at or above 55%.",
        "- Entry: next hourly open after the completed signal bar.",
        "- Position: long XRP / short BTC spread for 72 hours, using the full currently accrued reserve as margin capital.",
        "- Cooldown: 24 hours after exit.",
        f"- Cost model: {manifest['config']['one_way_cost']:.2%} one-way per leg; spread round-trip cost = {4 * manifest['config']['one_way_cost']:.2%}.",
        "",
        "## Summary",
        "",
        "| Strategy | Final USD | Final XRP-equivalent | Costs USD | Events | Avg trade | Win rate | Max DD | XRP edge vs daily | XRP edge vs weekly |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Daily XRP DCA | {daily['final_usd_value']:.2f} | {daily['final_xrp_equivalent']:.8f} | {daily['total_costs_usd']:.2f} | {int(daily['event_count'])} | n/a | n/a | {daily['max_drawdown']:.2%} | 0.00000000 | {daily['final_xrp_equivalent'] - weekly['final_xrp_equivalent']:.8f} |",
        f"| Weekly XRP DCA | {weekly['final_usd_value']:.2f} | {weekly['final_xrp_equivalent']:.8f} | {weekly['total_costs_usd']:.2f} | {int(weekly['event_count'])} | n/a | n/a | {weekly['max_drawdown']:.2%} | {weekly['final_xrp_equivalent'] - daily['final_xrp_equivalent']:.8f} | 0.00000000 |",
        f"| XRP ETF odds → XRP/BTC spread | {primary['final_usd_value']:.2f} | {primary['final_xrp_equivalent']:.8f} | {primary['total_costs_usd']:.2f} | {int(primary['event_count'])} | {primary['avg_trade_return_pct']:.2%} | {primary['win_rate']:.0%} | {primary['max_drawdown']:.2%} | {primary['final_xrp_equivalent'] - daily['final_xrp_equivalent']:.8f} | {primary['final_xrp_equivalent'] - weekly['final_xrp_equivalent']:.8f} |",
        "",
        "## Verdict",
        "",
        f"- Verdict: **{verdict['verdict']}**",
        f"- Reason: {verdict['reason']}",
        f"- Beats both DCA baselines: **{verdict['primary_beats_both_dca']}**",
        f"- Holdout Q2 2025+ pass: **{verdict['holdout_pass']}**",
        f"- Nearby-parameter pass rate: **{verdict['nearby_parameter_pass_rate']:.2%}**",
        f"- Doubled-cost pass: **{verdict['doubled_cost_pass']}**",
        f"- Hostile checks pass: **{verdict['hostile_pass']}**",
        f"- Mean realized spread trade: **{primary['avg_trade_return_pct']:.2%}** across **{int(primary['event_count'])}** trades",
        f"- Spread win rate: **{primary['win_rate']:.0%}**",
        "",
        "## Files",
        "",
        "- `strategy_summary.csv`",
        "- `trade_log.csv`",
        "- `equity_curves.csv`",
        "- `partition_summary.csv`",
        "- `sensitivity_checks.csv`",
        "- `hostile_checks.csv`",
        "- `xrp_etf_hourly_odds.csv`",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
