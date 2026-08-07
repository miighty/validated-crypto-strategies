"""Pre-registered MSTR opening-fade study after adverse BTC overnight events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import databento as db
import numpy as np
import pandas as pd

from .cross_asset import expanding_wild_events
from .cross_asset_strategy import strategy_metrics

NEW_YORK = "America/New_York"
HORIZONS = (5, 10, 15)


def load_symbol_minutes(root: str | Path, symbol: str) -> pd.DataFrame:
    """Load licensed one-minute history for one symbol, preserving opening-bar OHLC."""
    files = sorted(Path(root).rglob(f"*.{symbol}.dbn.zst"))
    if not files:
        raise FileNotFoundError(f"No {symbol} one-minute DBN files below {root}")
    parts = [db.DBNStore.from_file(path).to_df() for path in files]
    minute = pd.concat(parts).sort_index()
    minute = minute.loc[~minute.index.duplicated(keep="last")]
    minute.index = pd.to_datetime(minute.index, utc=True).tz_convert(NEW_YORK)
    return minute.between_time("09:30", "15:59", inclusive="both")


def load_mstr_minutes(root: str | Path) -> pd.DataFrame:
    return load_symbol_minutes(root, "MSTR")


def opening_fade_returns(
    minute: pd.DataFrame,
    btc_events: pd.DataFrame,
    *,
    quantile: float = 0.95,
    minimum_prior_observations: int = 60,
    round_trip_cost_bps: float = 20,
) -> pd.DataFrame:
    """Buy MSTR at the opening print after an adverse BTC signal; exit at each horizon.

    A completed 09:25 ET BTC signal is available before the 09:30 opening auction.
    An N-minute exit uses the close of the 09:(29 + N) one-minute bar: 09:34,
    09:39, or 09:44 respectively.  Costs are deducted once per executed round trip.
    """
    flags = expanding_wild_events(
        btc_events["btc_event_return"], quantile, minimum_prior_observations
    )
    events = btc_events.join(flags.add_prefix("signal_"), how="left")
    rows: list[dict[str, Any]] = []
    cost = round_trip_cost_bps / 10_000
    for session, day in minute.groupby(minute.index.normalize().tz_localize(None)):
        if session not in events.index:
            continue
        event = events.loc[session]
        # The user hypothesis is long-only: BTC fell unusually hard before the open.
        if not bool(event["signal_is_wild"]) or event["btc_event_return"] >= 0:
            continue
        opening = day.iloc[0]
        if opening.name.strftime("%H:%M") != "09:30":
            continue
        entry = float(opening["open"])
        if not np.isfinite(entry) or entry <= 0:
            continue
        row: dict[str, Any] = {
            "session": session,
            "btc_event_return": float(event["btc_event_return"]),
            "btc_threshold": float(event["signal_threshold"]),
            "entry": entry,
        }
        for horizon in HORIZONS:
            exit_time = f"09:{29 + horizon:02d}"
            exit_bar = day.loc[day.index.strftime("%H:%M") == exit_time]
            if exit_bar.empty:
                row[f"h{horizon}"] = np.nan
                continue
            exit_price = float(exit_bar.iloc[-1]["close"])
            row[f"h{horizon}"] = exit_price / entry - 1 - cost
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=[f"h{horizon}" for horizon in HORIZONS])
    return pd.DataFrame(rows).set_index("session").sort_index()


def _period_metrics(returns: pd.DataFrame, start: str | None, end: str | None) -> dict[str, Any]:
    selected = returns
    if start:
        selected = selected.loc[selected.index >= pd.Timestamp(start)]
    if end:
        selected = selected.loc[selected.index < pd.Timestamp(end)]
    return {column: strategy_metrics(selected[column]) for column in selected.columns if column.startswith("h")}


def run_mstr_open_fade_validation(
    minute: pd.DataFrame, btc_events: pd.DataFrame, *, round_trip_cost_bps: float = 20
) -> dict[str, Any]:
    """Choose one horizon using 2021--23 only, then leave later periods unchanged."""
    returns = opening_fade_returns(minute, btc_events, round_trip_cost_bps=round_trip_cost_bps)
    development = _period_metrics(returns, None, "2024-01-01")
    ranked = sorted(
        development,
        key=lambda horizon: development[horizon]["mean_net_return"] or -np.inf,
        reverse=True,
    )
    selected = ranked[0] if ranked and development[ranked[0]]["mean_net_return"] > 0 else None
    periods = {
        "development_2021_2023": development,
        "validation_2024": _period_metrics(returns, "2024-01-01", "2025-01-01"),
        "observed_2025_2026": _period_metrics(returns, "2025-01-01", None),
        "full_observed": _period_metrics(returns, None, None),
    }
    selected_results = {name: data[selected] for name, data in periods.items()} if selected else None
    reasons: list[str] = []
    if selected is None:
        reasons.append("No 5/10/15-minute horizon had a positive 2021-2023 mean return.")
    else:
        validation = selected_results["validation_2024"]
        later = selected_results["observed_2025_2026"]
        if validation["total_return"] is None or validation["total_return"] <= 0:
            reasons.append("The development-selected horizon lost money in the locked 2024 validation year.")
        if later["bootstrap_mean_95"] is None or later["bootstrap_mean_95"][0] <= 0:
            reasons.append("Observed 2025-2026 event-return uncertainty includes zero.")
        if later["maximum_event_profit_share"] is None or later["maximum_event_profit_share"] > 0.25:
            reasons.append("One event supplied more than 25% of observed later positive profits.")
    return {
        "specification": {
            "instrument": "MSTR common stock, Nasdaq one-minute OHLCV",
            "signal": "BTC prior US close to completed 09:25 ET return below its expanding 95th percentile absolute threshold; long only when BTC return is negative",
            "entry": "09:30 ET opening print",
            "exits_tested": {"h5": "09:34 close", "h10": "09:39 close", "h15": "09:44 close"},
            "cost_model": f"{round_trip_cost_bps:g} bps per executed round trip",
            "selection": "highest positive mean return in 2021-2023 among exactly h5, h10, h15",
        },
        "selected_horizon": selected,
        "periods": periods,
        "selected_results": selected_results,
        "validation_passed": not reasons,
        "failure_reasons": reasons,
        "event_returns": returns.reset_index().to_dict(orient="records"),
    }


def write_mstr_open_fade_results(result: dict[str, Any], output: str | Path) -> Path:
    import json

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return path
