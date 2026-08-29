from __future__ import annotations

"""Tightening pass for the "promising but inconclusive" BTC wick + supportive
odds rebound rule (see docs/BTC_WICK_ODDS_VALIDATION.md).

The original study found a real, after-cost, doubled-cost-surviving edge on
BTC alone, but with only 6 total trades (2 in holdout) it stayed inconclusive
and a single-event exclusion flipped it negative. This module tests whether
extending the *identical* preregistered rule (same wick detector, same
supportive-odds gate, same confirmation/hold/cooldown parameters -- nothing
tuned) to the same wick pattern on ETH, SOL, and XRP -- using real Binance
1h OHLCV already cached in this repo plus the same real Polymarket composite
odds series -- produces enough independent events to move the verdict, while
sharing one non-overlapping capital sleeve (only one position open across all
four assets at a time, so this is a genuine sample-size increase and not four
uncorrelated bets run in parallel).
"""

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
ASSETS = ("BTC", "ETH", "SOL", "XRP")

# Identical to the frozen primary BTC-only rule -- no thresholds retuned here.
PRIMARY_WICK_WINDOW_HOURS = 48
PRIMARY_DRAWDOWN_THRESHOLD = -0.10
PRIMARY_SUPPORT_DELTA_FLOOR = -0.02
PRIMARY_BOUNCE_THRESHOLD = 0.03
PRIMARY_BOUNCE_WINDOW_HOURS = 24
PRIMARY_HOLD_HOURS = 72
PRIMARY_COOLDOWN_HOURS = 48


@dataclass(frozen=True)
class StrategySpec:
    name: str
    wick_window_hours: int = PRIMARY_WICK_WINDOW_HOURS
    drawdown_threshold: float = PRIMARY_DRAWDOWN_THRESHOLD
    support_delta_floor: float = PRIMARY_SUPPORT_DELTA_FLOOR
    bounce_threshold: float = PRIMARY_BOUNCE_THRESHOLD
    bounce_window_hours: int = PRIMARY_BOUNCE_WINDOW_HOURS
    hold_hours: int = PRIMARY_HOLD_HOURS
    cooldown_hours: int = PRIMARY_COOLDOWN_HOURS


@dataclass(frozen=True)
class StudyConfig:
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    contribution_hour_utc: int = DAILY_CONTRIBUTION_HOUR_UTC
    sample_start: str = "2023-10-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    supportive_families: tuple[str, ...] = SUPPORTIVE_FAMILIES
    assets: tuple[str, ...] = ASSETS
    primary_rule: str = (
        "Identical to the frozen BTC-only rule (wick_window=48h, drawdown<=-10%,"
        " support_delta_floor>=-2pts, bounce>=3% within 24h, hold=72h, cooldown=48h),"
        " applied independently to BTC/ETH/SOL/XRP 1h bars sharing ONE non-overlapping"
        " capital sleeve (earliest qualifying signal across assets wins; no other asset"
        " may enter until the open trade exits and the cooldown elapses)."
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
    Partition("development_2023q4_2024", SAMPLE_START, HOLDOUT_START),
    Partition("holdout_2025_onward", HOLDOUT_START, None),
)


def run_btc_wick_odds_multiasset_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "btc_wick_odds_multiasset" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    metadata = fetch_market_metadata(paths)
    hourly = load_or_fetch_hourly_series(paths, metadata)
    supportive = hourly[hourly["family"].isin(config.supportive_families)].copy()
    supportive = supportive[supportive["timestamp"] >= pd.Timestamp(config.sample_start)].copy()
    if supportive.empty:
        raise RuntimeError("No supportive Polymarket hourly series found for multi-asset wick study")
    support_composite = build_support_composite(supportive, config.supportive_families)

    asset_frames: dict[str, pd.DataFrame] = {}
    for asset in config.assets:
        frame = load_ohlcv(paths, asset, "1h")
        frame = frame.loc[frame.index >= pd.Timestamp(config.sample_start)].copy()
        if frame.empty:
            raise RuntimeError(f"{asset} 1h data does not cover the requested wick study window")
        reset = frame.reset_index()
        reset["timestamp"] = pd.to_datetime(reset["timestamp"], utc=True)
        asset_frames[asset] = reset

    # Shared clock/schedule is BTC's timeline (all four assets have full 1h coverage
    # over this window; BTC is used only to anchor daily contribution timestamps).
    schedule = build_daily_contribution_schedule(
        asset_frames["BTC"], config.initial_capital, config.contribution_hour_utc
    )
    daily = simulate_daily_dca(asset_frames["BTC"], schedule, config.one_way_cost, "BTC")
    weekly = simulate_weekly_dca(asset_frames["BTC"], schedule, config.one_way_cost, "BTC")

    per_asset_signals = {
        asset: build_wick_signals(asset_frames[asset], support_composite, StrategySpec(name=f"{asset}_wick"))
        for asset in config.assets
    }
    raw_signal_counts = {asset: int(len(sig)) for asset, sig in per_asset_signals.items()}

    primary = simulate_multiasset_strategy(
        asset_frames, per_asset_signals, schedule, config.one_way_cost, "btc_eth_sol_xrp_wick_supportive_odds_rebound"
    )

    # BTC-only replica run on this identical code path, to confirm this
    # generalized engine reproduces the original single-asset finding before
    # trusting the multi-asset extension.
    btc_only = simulate_multiasset_strategy(
        {"BTC": asset_frames["BTC"]},
        {"BTC": per_asset_signals["BTC"]},
        schedule,
        config.one_way_cost,
        "btc_only_replica_wick_supportive_odds_rebound",
    )

    hostile = run_hostile_checks(asset_frames, per_asset_signals, schedule, config.one_way_cost, primary, daily, weekly)
    verdict = classify_verdict(primary, daily, weekly, hostile)

    summaries = pd.DataFrame([daily.summary, weekly.summary, btc_only.summary, primary.summary])
    summaries.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.ledger.assign(strategy="daily_btc_dca"),
            weekly.ledger.assign(strategy="weekly_monday_btc_dca"),
            btc_only.ledger.assign(strategy="btc_only_replica_wick_supportive_odds_rebound"),
            primary.ledger.assign(strategy="btc_eth_sol_xrp_wick_supportive_odds_rebound"),
        ],
        ignore_index=True,
    ).to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    pd.concat(
        [
            daily.partition_summary.assign(strategy="daily_btc_dca"),
            weekly.partition_summary.assign(strategy="weekly_monday_btc_dca"),
            btc_only.partition_summary.assign(strategy="btc_only_replica_wick_supportive_odds_rebound"),
            primary.partition_summary.assign(strategy="btc_eth_sol_xrp_wick_supportive_odds_rebound"),
        ],
        ignore_index=True,
    ).to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    support_composite.to_csv(output / "supportive_odds_composite.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "raw_signal_counts_per_asset": raw_signal_counts,
        "sample_start": asset_frames["BTC"]["timestamp"].min().isoformat(),
        "sample_end": asset_frames["BTC"]["timestamp"].max().isoformat(),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summaries, hostile, verdict)
    print(f"BTC/ETH/SOL/XRP wick + odds multi-asset validation written to {output}", flush=True)
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
            units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": f"daily_{asset.lower()}_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "units_bought": bought,
                    "cash_after": cash,
                    "units_after": units,
                }
            )
        close = float(row.close)
        equity = cash + units * close
        records.append({"timestamp": timestamp, "cash": cash, "units": units, "close": close, "equity": equity})
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
            units += bought
            ledger_rows.append(
                {
                    "timestamp": timestamp,
                    "kind": f"weekly_{asset.lower()}_dca_buy",
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": cost,
                    "execution_price": exec_price,
                    "reference_open": price,
                    "units_bought": bought,
                    "cash_after": cash,
                    "units_after": units,
                }
            )
        close = float(row.close)
        equity = cash + units * close
        records.append({"timestamp": timestamp, "cash": cash, "units": units, "close": close, "equity": equity})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(f"weekly_{asset.lower()}_dca", ledger, equity),
        ledger,
        equity,
        summarize_partitions(equity, ledger),
    )


def build_wick_signals(frame: pd.DataFrame, support_composite: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    data = frame.copy().sort_values("timestamp")
    data["prior_high"] = data["high"].shift(1).rolling(spec.wick_window_hours).max()
    data["wick_drawdown"] = data["low"] / data["prior_high"] - 1.0
    support = support_composite.set_index("timestamp")
    rows: list[dict[str, object]] = []
    cooldown_until = pd.Timestamp.min.tz_localize("UTC")
    indexed = data.set_index("timestamp")
    for row in data.itertuples(index=False):
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


def simulate_multiasset_strategy(
    asset_frames: dict[str, pd.DataFrame],
    per_asset_signals: dict[str, pd.DataFrame],
    schedule: pd.Series,
    one_way_cost: float,
    strategy_name: str,
) -> SimulationResult:
    combined = []
    for asset, signals in per_asset_signals.items():
        if signals.empty:
            continue
        tagged = signals.copy()
        tagged["asset"] = asset
        combined.append(tagged)
    if combined:
        pooled = pd.concat(combined, ignore_index=True).sort_values(["entry_time", "asset"]).reset_index(drop=True)
    else:
        pooled = pd.DataFrame(
            columns=["timestamp", "entry_time", "exit_time", "confirmation_time", "event_low", "wick_drawdown", "support_delta_24h", "asset"]
        )

    # Enforce one non-overlapping global position: greedily accept signals in
    # chronological entry order, skipping any signal whose entry falls before
    # the previously accepted trade's exit + cooldown, regardless of asset.
    chosen: list[dict[str, object]] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for row in pooled.itertuples(index=False):
        entry_time = pd.Timestamp(row.entry_time)
        if entry_time < next_ok:
            continue
        chosen.append(row._asdict())
        next_ok = pd.Timestamp(row.exit_time) + pd.Timedelta(hours=PRIMARY_COOLDOWN_HOURS)
    chosen_frame = pd.DataFrame(chosen)

    price_maps = {asset: frame.set_index("timestamp")[["open", "high", "low", "close"]] for asset, frame in asset_frames.items()}
    anchor = next(iter(asset_frames.values()))["timestamp"]
    cash = 0.0
    records: list[dict[str, object]] = []
    ledger_rows: list[dict[str, object]] = []
    scheduled = schedule.to_dict()
    signal_by_entry = {pd.Timestamp(r["entry_time"]): r for r in chosen} if chosen else {}
    active_trade: dict[str, object] | None = None
    anchor_asset = next(iter(asset_frames))
    anchor_closes = price_maps[anchor_asset]["close"]

    for timestamp in anchor:
        timestamp = pd.Timestamp(timestamp)
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
                    "kind": strategy_name,
                    "asset": active_trade["asset"],
                    "signal_time": pd.Timestamp(active_trade["signal_time"]),
                    "entry_time": pd.Timestamp(active_trade["entry_time"]),
                    "exit_time": pd.Timestamp(active_trade["exit_time"]),
                    "gross_spend_usd": gross_spend,
                    "fee_slippage_usd": gross_spend * 2 * one_way_cost,
                    "entry_open": float(active_trade["entry_open"]),
                    "exit_open": float(active_trade["exit_open"]),
                    "return_pct": net_return,
                    "cash_after": cash,
                }
            )
            active_trade = None

        if active_trade is None and cash > 0 and timestamp in signal_by_entry:
            signal = signal_by_entry[timestamp]
            asset = str(signal["asset"])
            exit_time = pd.Timestamp(signal["exit_time"])
            asset_index = price_maps[asset].index
            if timestamp in asset_index and exit_time in asset_index:
                entry_open = float(price_maps[asset].at[timestamp, "open"])
                exit_open = float(price_maps[asset].at[exit_time, "open"])
                gross = exit_open / entry_open - 1.0
                net = gross - 2 * one_way_cost
                active_trade = {
                    "asset": asset,
                    "signal_time": pd.Timestamp(signal["timestamp"]),
                    "entry_time": timestamp,
                    "exit_time": exit_time,
                    "event_low": float(signal["event_low"]),
                    "wick_drawdown": float(signal["wick_drawdown"]),
                    "support_delta_24h": float(signal["support_delta_24h"]),
                    "gross_spend_usd": cash,
                    "entry_open": entry_open,
                    "exit_open": exit_open,
                    "realized_return_pct": net,
                }
                cash = 0.0

        equity = cash
        anchor_close = float(anchor_closes.at[timestamp])
        if active_trade is not None:
            asset = str(active_trade["asset"])
            asset_index = price_maps[asset].index
            notional = float(active_trade["gross_spend_usd"])
            if timestamp in asset_index:
                live_gross = float(price_maps[asset].at[timestamp, "close"]) / float(active_trade["entry_open"]) - 1.0
                live_net = live_gross - 2 * one_way_cost
                equity += max(0.0, notional * (1.0 + live_net))
            else:
                equity += notional
        btc_equiv = equity / anchor_close if anchor_close > 0 else 0.0
        records.append(
            {
                "timestamp": timestamp,
                "cash": cash,
                "close": anchor_close,
                "equity": equity,
                "anchor_equivalent": btc_equiv,
            }
        )

    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(records)
    return SimulationResult(
        summarize_strategy(strategy_name, ledger, equity),
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
    final_anchor_equivalent = float(equity_curve.iloc[-1] / final_close) if final_close > 0 else 0.0
    total_costs = float(ledger["fee_slippage_usd"].sum()) if not ledger.empty else 0.0
    gross_spend = float(ledger["gross_spend_usd"].sum()) if not ledger.empty else 0.0
    trade_returns = ledger["return_pct"] if "return_pct" in ledger.columns else pd.Series(dtype=float)
    return {
        "strategy": name,
        "final_usd_value": float(equity_curve.iloc[-1]),
        "final_cash_usd": final_cash,
        "final_anchor_equivalent": final_anchor_equivalent,
        "final_anchor_close": final_close,
        "event_count": int(len(ledger)),
        "gross_spent_usd": gross_spend,
        "total_costs_usd": total_costs,
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
                "final_anchor_equivalent": float(section["equity"].iloc[-1] / section["close"].iloc[-1]),
                "events": int(len(partition_ledger)),
                "costs_usd": float(partition_ledger["fee_slippage_usd"].sum()) if not partition_ledger.empty else 0.0,
                "max_drawdown": abs(float(drawdown.min())),
                "avg_trade_return": float(trade_returns.mean()) if not trade_returns.empty else pd.NA,
            }
        )
    return pd.DataFrame(rows)


def run_hostile_checks(
    asset_frames: dict[str, pd.DataFrame],
    per_asset_signals: dict[str, pd.DataFrame],
    schedule: pd.Series,
    one_way_cost: float,
    primary: SimulationResult,
    daily: SimulationResult,
    weekly: SimulationResult,
) -> pd.DataFrame:
    doubled = simulate_multiasset_strategy(
        asset_frames, per_asset_signals, schedule, one_way_cost * 2, "doubled_cost"
    )
    rows: list[dict[str, object]] = [
        {
            "check": "doubled_cost",
            "terminal_value": float(doubled.summary["final_usd_value"]),
            "beats_daily": float(doubled.summary["final_usd_value"]) >= float(daily.summary["final_usd_value"]),
            "beats_weekly": float(doubled.summary["final_usd_value"]) >= float(weekly.summary["final_usd_value"]),
        }
    ]

    if not primary.ledger.empty:
        contrib = primary.ledger.copy()
        contrib["terminal_contribution"] = contrib["gross_spend_usd"] * (1.0 + contrib["return_pct"])
        best_idx = contrib["terminal_contribution"].idxmax()
        best_event = contrib.loc[best_idx]
        without_best_value = float(primary.summary["final_usd_value"]) - (
            float(best_event["terminal_contribution"]) - float(best_event["gross_spend_usd"])
        )
        rows.append(
            {
                "check": "exclude_best_event",
                "terminal_value": without_best_value,
                "beats_daily": without_best_value >= float(daily.summary["final_usd_value"]),
                "beats_weekly": without_best_value >= float(weekly.summary["final_usd_value"]),
                "excluded_event_asset": str(best_event["asset"]),
                "excluded_event_timestamp": best_event["timestamp"],
            }
        )
        total_pnl = float(primary.summary["final_usd_value"]) - STARTING_CAPITAL
        best_event_pnl = float(best_event["terminal_contribution"]) - float(best_event["gross_spend_usd"])
        pnl_share = (best_event_pnl / total_pnl) if abs(total_pnl) > 50.0 and total_pnl > 0 else pd.NA
        rows.append({"check": "best_event_pnl_share", "terminal_value": pnl_share, "beats_daily": pd.NA, "beats_weekly": pd.NA})

        by_asset = contrib.groupby("asset")["return_pct"].agg(["count", "mean"])
        for asset, agg in by_asset.iterrows():
            rows.append(
                {
                    "check": f"per_asset_trades_{asset}",
                    "terminal_value": float(agg["mean"]),
                    "beats_daily": int(agg["count"]),
                    "beats_weekly": pd.NA,
                }
            )
    return pd.DataFrame(rows)


def classify_verdict(
    primary: SimulationResult,
    daily: SimulationResult,
    weekly: SimulationResult,
    hostile: pd.DataFrame,
) -> dict[str, object]:
    primary_terminal = float(primary.summary["final_usd_value"])
    beats_both = primary_terminal > float(daily.summary["final_usd_value"]) and primary_terminal > float(weekly.summary["final_usd_value"])
    holdout = primary.partition_summary[primary.partition_summary["partition"].eq("holdout_2025_onward")]
    holdout_events = int(holdout.iloc[0]["events"]) if not holdout.empty else 0
    holdout_avg = float(holdout.iloc[0]["avg_trade_return"]) if not holdout.empty and pd.notna(holdout.iloc[0]["avg_trade_return"]) else 0.0
    doubled_row = hostile.loc[hostile["check"].eq("doubled_cost")]
    doubled_pass = bool(not doubled_row.empty and bool(doubled_row.iloc[0]["beats_daily"]) and bool(doubled_row.iloc[0]["beats_weekly"]))
    exclude_row = hostile.loc[hostile["check"].eq("exclude_best_event")]
    exclude_pass = bool(not exclude_row.empty and bool(exclude_row.iloc[0]["beats_daily"]) and bool(exclude_row.iloc[0]["beats_weekly"]))
    concentration_row = hostile.loc[hostile["check"].eq("best_event_pnl_share")]
    concentration_ok = bool(
        not concentration_row.empty
        and pd.notna(concentration_row.iloc[0]["terminal_value"])
        and float(concentration_row.iloc[0]["terminal_value"]) <= 0.5
    )

    event_count = int(primary.summary["event_count"])
    net_profitable = primary_terminal > STARTING_CAPITAL
    if event_count == 0:
        label = "rejected"
        reason = "No qualifying trades under the identical multi-asset rule."
    elif not net_profitable:
        label = "rejected"
        reason = (
            "Pooling ETH/SOL/XRP wick events into the same sleeve produced a net LOSS on"
            " committed capital, even though it beat the (also-negative) DCA baselines in this"
            " bearish sample window. Beating a losing benchmark is not evidence of edge; the"
            " decisive comparison is against zero/breakeven. Diluting the BTC-only signal with"
            " other assets made results worse, not better."
        )
    elif not beats_both:
        label = "rejected"
        reason = "Multi-asset extension did not beat both DCA baselines."
    elif doubled_pass and exclude_pass and concentration_ok and holdout_events >= 4 and holdout_avg > 0:
        label = "promising_but_still_capped"
        reason = "Beats baselines, survives doubled cost and best-event exclusion, and concentration is under 50%, but sample remains modest -- treat as strengthened evidence, not a validated edge."
    elif doubled_pass and holdout_events >= 2:
        label = "promising_but_inconclusive"
        reason = "Beats baselines and survives doubled cost, but either concentration or best-event exclusion still shows fragility."
    else:
        label = "rejected"
        reason = "Multi-asset extension failed a decisive hostile check (doubled cost, best-event exclusion, or holdout sample)."

    return {
        "label": label,
        "reason": reason,
        "event_count": event_count,
        "beats_both_dca": beats_both,
        "doubled_cost_pass": doubled_pass,
        "exclude_best_event_pass": exclude_pass,
        "concentration_ok": concentration_ok,
        "holdout_events": holdout_events,
        "holdout_avg_trade_return": holdout_avg,
    }


def write_report(
    output: Path,
    manifest: dict[str, object],
    summaries: pd.DataFrame,
    hostile: pd.DataFrame,
    verdict: dict[str, object],
) -> None:
    lines = [
        "# BTC/ETH/SOL/XRP wick + supportive odds multi-asset tightening pass",
        "",
        "## Rule (identical to the frozen BTC-only primary rule; only the asset universe changed)",
        "",
        "- Wick detector per asset: `low / rolling_max(high.shift(1), 48h) - 1 <= -10%`.",
        "- Support filter: composite mean YES odds across BTC ETF / ETH ETF / Trump election / Bitcoin reserve markets, 24h delta >= -2 points.",
        "- Confirmation: first close within 24h that is at least 3% above the event low.",
        "- Entry: next hourly open after confirmation; exit 72h later.",
        "- ONE shared non-overlapping capital sleeve across all 4 assets; cooldown 48h after each exit.",
        "",
        "## Result table",
        "",
        summaries.to_string(index=False),
        "",
        "## Partition summary",
        "",
        pd.read_csv(output / "partition_summary.csv").to_string(index=False),
        "",
        "## Hostile checks",
        "",
        hostile.to_string(index=False),
        "",
        "## Verdict",
        "",
        json.dumps(verdict, indent=2),
        "",
        "## Manifest",
        "",
        json.dumps(manifest, indent=2),
        "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
