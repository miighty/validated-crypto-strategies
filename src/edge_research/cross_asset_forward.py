from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .cross_asset import expanding_wild_events
from .cross_asset_strategy import strategy_metrics
from .cross_asset_studies import (
    StudyInputs,
    _lead_lag_panel,
    btc_event_returns,
    combine_daily_panels,
    load_databento_daily,
)

FROZEN_STRATEGY = {
    "rule": "residual_continuation",
    "direction": "long_only",
    "btc_signal_time": "09:25",
    "wild_event_quantile": 0.95,
    "minimum_prior_observations": 60,
    "factor_lookback_sessions": 60,
    "factor_minimum_sessions": 40,
    "factors": ["BTC", "SPY", "QQQ"],
    "observation_window": ["09:35", "09:40"],
    "entry_window": ["09:40", "09:45"],
    "exit_window": ["15:55", "16:00"],
    "round_trip_cost_bps": 20,
    "stress_round_trip_cost_bps": 50,
    "weighting": "equal_slots_with_non_signals_in_cash",
    "initial_paper_capital_usd": 10_000,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def load_forward_config(path: str | Path) -> dict[str, Any]:
    config = yaml.safe_load(Path(path).read_text())
    if config.get("strategy") != FROZEN_STRATEGY:
        raise ValueError("Forward strategy parameters differ from the frozen specification")
    if config.get("safety", {}).get("order_submission") != "prohibited":
        raise ValueError("Forward testing must prohibit order submission")
    return config


def semantic_lock_id(config: dict[str, Any]) -> str:
    """Hash the meaningful pre-registration rather than YAML formatting."""
    return _hash(config)


def _iso_date(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def build_forward_observations(
    inputs: StudyInputs,
    config: dict[str, Any],
    through_session: str | pd.Timestamp,
    observed_at: str | None = None,
) -> list[dict[str, Any]]:
    """Calculate deterministic, finalized-session paper observations."""
    strategy = config["strategy"]
    start = pd.Timestamp(config["first_eligible_session"])
    through = pd.Timestamp(through_session).normalize()
    if through < start:
        raise ValueError("Cannot observe a session before the pre-registered forward start")

    equity = inputs.equity_daily.reset_index().copy()
    equity["session"] = pd.to_datetime(equity["session"]).dt.tz_localize(None).dt.normalize()
    available = pd.DatetimeIndex(equity["session"].unique()).sort_values()
    if through not in available:
        last = available.max().date().isoformat() if len(available) else "none"
        raise ValueError(f"Session {through.date()} is not finalized in the equity panel (last={last})")

    events = inputs.btc_events.copy()
    events.index = pd.to_datetime(events.index).tz_localize(None).normalize()
    flags = expanding_wild_events(
        events["btc_event_return"],
        quantile=float(strategy["wild_event_quantile"]),
        minimum_prior_observations=int(strategy["minimum_prior_observations"]),
    )
    events["wild_primary"] = flags["is_wild"]
    lead = _lead_lag_panel(
        equity,
        events,
        lookback=int(strategy["factor_lookback_sessions"]),
        minimum=int(strategy["factor_minimum_sessions"]),
    )
    detail_columns = [
        "session", "symbol", "entry", "trade_entry", "close", "minutes"
    ]
    lead = lead.merge(equity[detail_columns], on=["session", "symbol"], how="left")
    allowed = set(config["universe"]["equities"])
    lead = lead.loc[lead["symbol"].isin(allowed)]

    timestamp = observed_at or datetime.now(UTC).isoformat()
    records: list[dict[str, Any]] = []
    sessions = available[(available >= start) & (available <= through)]
    for session in sessions:
        event = events.loc[session] if session in events.index else None
        threshold = flags.loc[session, "threshold"] if session in flags.index else np.nan
        btc_return = event["btc_event_return"] if event is not None else np.nan
        if pd.isna(btc_return) or pd.isna(threshold):
            classification = "data_ineligible"
            is_wild = False
        else:
            is_wild = bool(event["wild_primary"])
            classification = "wild_event" if is_wild else "no_event"

        day = lead.loc[lead["session"].eq(session)].copy() if is_wild else lead.iloc[0:0]
        trades: list[dict[str, Any]] = []
        primary_assets: list[float] = []
        stress_assets: list[float] = []
        liquid_assets: list[float] = []
        for row in day.sort_values("symbol").itertuples():
            traded = bool(row.residual_gap > 0)
            gross = float(row.intraday) if traded else 0.0
            primary_net = gross - 0.002 if traded else 0.0
            stress_net = gross - 0.005 if traded else 0.0
            primary_assets.append(primary_net)
            stress_assets.append(stress_net)
            if row.minutes >= int(config["promotion_gate"]["liquid_session_minimum_minutes"]):
                liquid_assets.append(primary_net)
            trades.append(
                {
                    "symbol": row.symbol,
                    "expected_gap": float(row.expected_gap),
                    "observed_gap": float(row.observed_gap),
                    "residual_gap": float(row.residual_gap),
                    "traded": traded,
                    "observation_price": float(row.entry),
                    "paper_entry_price": float(row.trade_entry) if traded else None,
                    "paper_exit_price": float(row.close) if traded else None,
                    "gross_return": gross,
                    "net_return_20bps": primary_net,
                    "net_return_50bps": stress_net,
                    "observed_minutes": int(row.minutes),
                }
            )

        record = {
            "experiment_id": config["experiment_id"],
            "lock_id": semantic_lock_id(config),
            "session": session.date().isoformat(),
            "recorded_at_utc": timestamp,
            "classification": classification,
            "btc_event_return": None if pd.isna(btc_return) else float(btc_return),
            "wild_threshold": None if pd.isna(threshold) else float(threshold),
            "eligible_asset_slots": len(day),
            "positions_opened": int(sum(item["traded"] for item in trades)),
            "portfolio_return_20bps": float(np.mean(primary_assets)) if primary_assets else 0.0,
            "portfolio_return_50bps": float(np.mean(stress_assets)) if stress_assets else 0.0,
            "liquid_portfolio_return_20bps": (
                float(np.mean(liquid_assets)) if liquid_assets else 0.0
            ),
            "trades": trades,
        }
        records.append(record)
    return records


def read_ledger(path: str | Path) -> list[dict[str, Any]]:
    ledger = Path(path)
    if not ledger.exists():
        return []
    records = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    previous = None
    last_session = None
    for record in records:
        claimed = record.get("record_hash")
        payload = {key: value for key, value in record.items() if key != "record_hash"}
        if payload.get("previous_record_hash") != previous or _hash(payload) != claimed:
            raise ValueError("Forward ledger hash chain is invalid")
        if last_session is not None and record["session"] <= last_session:
            raise ValueError("Forward ledger sessions are not strictly increasing")
        previous = claimed
        last_session = record["session"]
    return records


def append_observations(path: str | Path, observations: list[dict[str, Any]]) -> int:
    """Append only sessions newer than the verified ledger tail."""
    ledger = Path(path)
    existing = read_ledger(ledger)
    previous = existing[-1]["record_hash"] if existing else None
    last_session = existing[-1]["session"] if existing else None
    fresh = [item for item in observations if last_session is None or item["session"] > last_session]
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as handle:
        for item in fresh:
            payload = {**item, "previous_record_hash": previous}
            record = {**payload, "record_hash": _hash(payload)}
            handle.write(_canonical(record) + "\n")
            previous = record["record_hash"]
    return len(fresh)


def forward_status(records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    lock_id = semantic_lock_id(config)
    if any(record.get("lock_id") != lock_id for record in records):
        raise ValueError("Ledger contains an observation from a different strategy lock")
    event_records = [record for record in records if record["classification"] == "wild_event"]
    primary = pd.Series([record["portfolio_return_20bps"] for record in event_records], dtype=float)
    stress = pd.Series([record["portfolio_return_50bps"] for record in event_records], dtype=float)
    liquid = pd.Series(
        [record["liquid_portfolio_return_20bps"] for record in event_records], dtype=float
    )
    primary_metrics = strategy_metrics(primary)
    stress_metrics = strategy_metrics(stress)
    liquid_metrics = strategy_metrics(liquid)
    gate = config["promotion_gate"]
    interval = primary_metrics.get("bootstrap_mean_95")
    checks = {
        "minimum_event_count": len(event_records) >= int(gate["minimum_new_event_sessions"]),
        "positive_total_return": (primary_metrics["total_return"] or 0) > 0,
        "bootstrap_lower_bound_above_zero": interval is not None and interval[0] > 0,
        "positive_50bps_stress_return": (stress_metrics["total_return"] or 0) > 0,
        "positive_liquid_session_return": (liquid_metrics["total_return"] or 0) > 0,
        "maximum_event_profit_share": (
            primary_metrics.get("maximum_event_profit_share") is not None
            and primary_metrics["maximum_event_profit_share"]
            <= float(gate["maximum_single_event_profit_share"])
        ),
    }
    return {
        "experiment_id": config["experiment_id"],
        "lock_id": lock_id,
        "first_eligible_session": config["first_eligible_session"],
        "last_recorded_session": records[-1]["session"] if records else None,
        "sessions_recorded": len(records),
        "new_event_sessions": len(event_records),
        "minimum_required_event_sessions": int(gate["minimum_new_event_sessions"]),
        "primary": primary_metrics,
        "stress_50bps": stress_metrics,
        "liquid_sessions": liquid_metrics,
        "promotion_checks": checks,
        "ready_for_independent_review": all(checks.values()),
        "live_trading_approved": False,
    }


def run_forward_update(
    config_path: str | Path,
    equity_path: str | Path,
    btc_path: str | Path,
    ledger_path: str | Path,
    status_path: str | Path,
    through_session: str,
) -> tuple[int, dict[str, Any]]:
    config = load_forward_config(config_path)
    equity = pd.read_parquet(equity_path)
    btc = pd.read_parquet(btc_path)
    events = btc_event_returns(btc, equity.index.get_level_values("session"))
    observations = build_forward_observations(
        StudyInputs(equity, events), config, through_session
    )
    appended = append_observations(ledger_path, observations)
    status = forward_status(read_ledger(ledger_path), config)
    destination = Path(status_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(status, indent=2) + "\n")
    return appended, status


def prepare_forward_equity_panel(
    base_path: str | Path,
    forward_roots: list[str | Path],
    output_path: str | Path,
) -> Path:
    """Combine the fixed research history with newly licensed daily DBN files."""
    base = pd.read_parquet(base_path)
    additions = [
        load_databento_daily(root, adjust_corporate_actions=False)
        for root in forward_roots
    ]
    combined = combine_daily_panels(base, *additions) if additions else base
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(destination, compression="zstd")
    return destination
