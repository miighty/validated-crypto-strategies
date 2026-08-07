from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .cross_asset import expanding_wild_events
from .cross_asset_studies import StudyInputs, _bootstrap_mean_interval, _lead_lag_panel

RULES = (
    "btc_continuation",
    "btc_reversal",
    "residual_continuation",
    "residual_reversion",
)


def strategy_family_returns(
    inputs: StudyInputs,
    quantile: float = 0.95,
    minimum_prior_observations: int = 60,
    beta_lookback: int = 60,
    beta_minimum: int = 40,
    round_trip_cost_bps: float = 20,
    liquid_minutes: int | None = None,
    long_only: bool = False,
) -> pd.DataFrame:
    """Build event-level returns for four frozen, mutually opposing strategy rules."""
    equity = inputs.equity_daily.reset_index()
    events = inputs.btc_events.copy()
    events["wild_primary"] = False
    lead_panel = _lead_lag_panel(equity, events, beta_lookback, beta_minimum)
    lead_panel = lead_panel.merge(
        equity[["session", "symbol", "minutes"]], on=["session", "symbol"], how="left"
    )
    return _strategy_returns_from_panel(
        lead_panel,
        events,
        quantile,
        minimum_prior_observations,
        round_trip_cost_bps,
        liquid_minutes,
        long_only,
    )


def _strategy_returns_from_panel(
    lead_panel: pd.DataFrame,
    events: pd.DataFrame,
    quantile: float,
    minimum_prior_observations: int,
    round_trip_cost_bps: float,
    liquid_minutes: int | None,
    long_only: bool,
) -> pd.DataFrame:
    if liquid_minutes is not None:
        lead_panel = lead_panel.loc[lead_panel["minutes"].ge(liquid_minutes)]
    events = events.copy()
    events["wild_primary"] = expanding_wild_events(
        events["btc_event_return"], quantile, minimum_prior_observations
    )["is_wild"]
    wild_sessions = events.index[events["wild_primary"]]
    lead_panel = lead_panel.loc[lead_panel["session"].isin(wild_sessions)].copy()
    btc_side = np.sign(lead_panel["btc_event_return"])
    residual_side = np.sign(lead_panel["residual_gap"])
    sides = {
        "btc_continuation": btc_side,
        "btc_reversal": -btc_side,
        "residual_continuation": residual_side,
        "residual_reversion": -residual_side,
    }
    cost = round_trip_cost_bps / 10_000
    event_returns = {}
    for rule, side in sides.items():
        position = side.clip(lower=0) if long_only else side
        asset_net = position * lead_panel["intraday"] - position.ne(0).astype(float) * cost
        event_returns[rule] = asset_net.groupby(lead_panel["session"]).mean()
    return pd.DataFrame(event_returns).sort_index()


def strategy_metrics(returns: pd.Series, initial_capital: float = 10_000) -> dict[str, Any]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return {
            "events": 0,
            "mean_net_return": None,
            "total_return": None,
            "ending_equity": initial_capital,
            "net_profit": 0.0,
            "win_rate": None,
            "maximum_drawdown": None,
            "bootstrap_mean_95": None,
        }
    equity = initial_capital * (1 + clean).cumprod()
    drawdown = equity / equity.cummax() - 1
    positive_profit = clean.clip(lower=0).sum()
    maximum_event_profit_share = (
        float(clean.max() / positive_profit) if positive_profit > 0 else None
    )
    return {
        "events": len(clean),
        "mean_net_return": float(clean.mean()),
        "median_net_return": float(clean.median()),
        "total_return": float(equity.iloc[-1] / initial_capital - 1),
        "ending_equity": float(equity.iloc[-1]),
        "net_profit": float(equity.iloc[-1] - initial_capital),
        "win_rate": float(clean.gt(0).mean()),
        "maximum_drawdown": float(drawdown.min()),
        "maximum_event_profit_share": maximum_event_profit_share,
        "bootstrap_mean_95": _bootstrap_mean_interval(clean),
    }


def validate_strategy_family(
    inputs: StudyInputs,
    development_end: str = "2024-01-01",
    validation_end: str = "2025-01-01",
    initial_capital: float = 10_000,
    **return_kwargs: Any,
) -> dict[str, Any]:
    """Select on development only, then report locked validation and forward results."""
    returns = strategy_family_returns(inputs, **return_kwargs)
    return _validate_return_frame(
        returns, development_end, validation_end, initial_capital
    )


def _validate_return_frame(
    returns: pd.DataFrame,
    development_end: str,
    validation_end: str,
    initial_capital: float,
) -> dict[str, Any]:
    development_cutoff = pd.Timestamp(development_end)
    validation_cutoff = pd.Timestamp(validation_end)
    development = returns.loc[returns.index < development_cutoff]
    validation = returns.loc[
        (returns.index >= development_cutoff) & (returns.index < validation_cutoff)
    ]
    forward = returns.loc[returns.index >= validation_cutoff]
    development_metrics = {
        rule: strategy_metrics(development[rule], initial_capital) for rule in RULES
    }
    ranked = sorted(
        RULES,
        key=lambda rule: development_metrics[rule]["mean_net_return"] or -np.inf,
        reverse=True,
    )
    selected = ranked[0]
    selected_mean = development_metrics[selected]["mean_net_return"]
    if selected_mean is None or selected_mean <= 0:
        selected = None
    periods = {
        "development": {
            rule: development_metrics[rule] for rule in RULES
        },
        "validation": {
            rule: strategy_metrics(validation[rule], initial_capital) for rule in RULES
        },
        "forward": {
            rule: strategy_metrics(forward[rule], initial_capital) for rule in RULES
        },
        "full_five_year": {
            rule: strategy_metrics(returns[rule], initial_capital) for rule in RULES
        },
    }
    selected_results = (
        {period: metrics[selected] for period, metrics in periods.items()} if selected else None
    )
    return {
        "selection_policy": "highest positive development mean; no selection if all are non-positive",
        "selected_rule": selected,
        "periods": periods,
        "selected_results": selected_results,
    }


def run_validation_suite(inputs: StudyInputs, initial_capital: float = 10_000) -> dict[str, Any]:
    """Run the primary frozen specification and locked-rule hostile sensitivities."""
    equity = inputs.equity_daily.reset_index()
    events = inputs.btc_events.copy()
    events["wild_primary"] = False
    lead_panel = _lead_lag_panel(equity, events, lookback=60, minimum=40)
    lead_panel = lead_panel.merge(
        equity[["session", "symbol", "minutes"]], on=["session", "symbol"], how="left"
    )

    def run_returns(**kwargs: Any) -> dict[str, Any]:
        returns = _strategy_returns_from_panel(
            lead_panel,
            events,
            quantile=kwargs.get("quantile", 0.95),
            minimum_prior_observations=60,
            round_trip_cost_bps=kwargs.get("round_trip_cost_bps", 20),
            liquid_minutes=kwargs.get("liquid_minutes"),
            long_only=kwargs.get("long_only", False),
        )
        return _validate_return_frame(returns, "2024-01-01", "2025-01-01", initial_capital)

    primary = run_returns()
    variants = {
        "liquid_sessions": run_returns(liquid_minutes=300),
        "cost_50bps": run_returns(round_trip_cost_bps=50),
        "wild_90th_percentile": run_returns(quantile=0.90),
        "long_only": run_returns(long_only=True),
        "long_only_liquid_sessions": run_returns(long_only=True, liquid_minutes=300),
        "long_only_cost_50bps": run_returns(long_only=True, round_trip_cost_bps=50),
        "long_only_wild_90th_percentile": run_returns(long_only=True, quantile=0.90),
    }
    locked_rule = primary["selected_rule"]
    candidate_rule = "residual_continuation"
    candidate_primary = variants["long_only"]["periods"]
    candidate_reasons = []
    if locked_rule != candidate_rule:
        candidate_reasons.append("Residual continuation was not selected by the frozen development rule.")
    candidate_forward = candidate_primary["forward"][candidate_rule]
    candidate_interval = candidate_forward["bootstrap_mean_95"]
    if candidate_interval is None or candidate_interval[0] <= 0:
        candidate_reasons.append("Long-only forward event-return uncertainty includes zero.")
    candidate_concentration = candidate_forward["maximum_event_profit_share"]
    if candidate_concentration is None or candidate_concentration > 0.25:
        candidate_reasons.append("One event supplied more than 25% of long-only forward profits.")
    if (
        variants["long_only_wild_90th_percentile"]["periods"]["development"][candidate_rule][
            "total_return"
        ]
        <= 0
    ):
        candidate_reasons.append("The 90th-percentile threshold lost money in development.")
    research_candidate = {
        "rule": candidate_rule,
        "implementation": "long_only",
        "historically_profitable": candidate_primary["full_five_year"][candidate_rule][
            "total_return"
        ]
        > 0,
        "validation_passed": not candidate_reasons,
        "failure_reasons": candidate_reasons,
        "periods": {
            period: candidate_primary[period][candidate_rule]
            for period in ("development", "validation", "forward", "full_five_year")
        },
        "sensitivities": {
            name: {
                period: variants[name]["periods"][period][candidate_rule]
                for period in ("development", "validation", "forward", "full_five_year")
            }
            for name in (
                "long_only_liquid_sessions",
                "long_only_cost_50bps",
                "long_only_wild_90th_percentile",
            )
        },
    }
    if locked_rule is None:
        return {
            "primary": primary,
            "variants": variants,
            "locked_rule": None,
            "locked_variant_results": None,
            "validation_passed": False,
            "failure_reasons": ["No candidate had a positive development mean return."],
            "research_candidate": research_candidate,
        }
    locked_variants = {
        name: {
            period: result["periods"][period][locked_rule]
            for period in ("development", "validation", "forward", "full_five_year")
        }
        for name, result in variants.items()
    }
    selected = primary["selected_results"]
    reasons = []
    if selected["validation"]["total_return"] <= 0:
        reasons.append("Locked rule lost money in validation.")
    if selected["forward"]["total_return"] <= 0:
        reasons.append("Locked rule lost money in the untouched forward window.")
    forward_interval = selected["forward"]["bootstrap_mean_95"]
    if forward_interval is None or forward_interval[0] <= 0:
        reasons.append("Forward event-return uncertainty includes zero.")
    if locked_variants["liquid_sessions"]["forward"]["total_return"] <= 0:
        reasons.append("Locked rule failed the liquid-session forward sensitivity.")
    if locked_variants["cost_50bps"]["forward"]["total_return"] <= 0:
        reasons.append("Locked rule failed the 50 bps cost forward sensitivity.")
    concentration = selected["forward"]["maximum_event_profit_share"]
    if concentration is None or concentration > 0.25:
        reasons.append("One event supplied more than 25% of forward gross profits.")
    return {
        "primary": primary,
        "variants": variants,
        "locked_rule": locked_rule,
        "locked_variant_results": locked_variants,
        "validation_passed": not reasons,
        "failure_reasons": reasons,
        "research_candidate": research_candidate,
    }
