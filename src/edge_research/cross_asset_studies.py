from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import databento as db
import numpy as np
import pandas as pd

from .cross_asset import expanding_wild_events

NEW_YORK = "America/New_York"
BENCHMARKS = ("SPY", "QQQ")
SPLIT_RATIOS = np.array([0.1, 0.2, 0.25, 1 / 3, 0.5, 2.0, 3.0, 4.0, 5.0, 10.0])


@dataclass(frozen=True)
class StudyInputs:
    equity_daily: pd.DataFrame
    btc_events: pd.DataFrame


def volume_weighted_typical_price(frame: pd.DataFrame) -> float:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    volume = frame["volume"].astype(float)
    if volume.sum() <= 0:
        return float(typical.mean())
    return float((typical * volume).sum() / volume.sum())


def intraday_to_daily(
    frame: pd.DataFrame, adjust_corporate_actions: bool = True
) -> pd.DataFrame:
    """Collapse minute OHLCV into executable daily study features."""
    local = frame.copy()
    local.index = pd.to_datetime(local.index, utc=True).tz_convert(NEW_YORK)
    local = local.between_time("09:30", "15:59", inclusive="both")
    rows: list[dict[str, Any]] = []
    for session, day in local.groupby(local.index.date):
        entry_window = day.between_time("09:35", "09:39", inclusive="both")
        trade_window = day.between_time("09:40", "09:44", inclusive="both")
        close_window = day.between_time("15:55", "15:59", inclusive="both")
        if entry_window.empty or trade_window.empty or close_window.empty:
            continue
        rows.append(
            {
                "session": pd.Timestamp(session),
                "open": float(day.iloc[0]["open"]),
                "entry": volume_weighted_typical_price(entry_window),
                "trade_entry": volume_weighted_typical_price(trade_window),
                "close": volume_weighted_typical_price(close_window),
                "minutes": len(day),
            }
        )
    result = pd.DataFrame(rows).set_index("session").sort_index()
    if adjust_corporate_actions:
        result = adjust_splits(result)
    else:
        result["split_event"] = False
    return calculate_daily_returns(result)


def adjust_splits(daily: pd.DataFrame, tolerance: float = 0.08) -> pd.DataFrame:
    """Put raw prices on the latest split basis when an overnight ratio is near a split."""
    result = daily.copy()
    result["split_event"] = False
    raw_ratio = result["open"] / result["close"].shift(1)
    for position in range(1, len(result)):
        ratio = float(raw_ratio.iloc[position])
        nearest = float(SPLIT_RATIOS[np.argmin(np.abs(SPLIT_RATIOS - ratio))])
        relative_error = abs(ratio - nearest) / nearest
        if relative_error <= tolerance and (nearest <= 0.5 or nearest >= 2.0):
            price_columns = [
                column for column in ("open", "entry", "trade_entry", "close")
                if column in result
            ]
            result.iloc[:position, result.columns.get_indexer(price_columns)] *= nearest
            result.iloc[position, result.columns.get_loc("split_event")] = True
    return result


def calculate_daily_returns(result: pd.DataFrame) -> pd.DataFrame:
    result = result.copy()
    result["previous_close"] = result["close"].shift(1)
    result["gap"] = result["entry"] / result["previous_close"] - 1
    result["intraday"] = result["close"] / result["entry"] - 1
    if "trade_entry" in result:
        result["strategy_intraday"] = result["close"] / result["trade_entry"] - 1
    result["close_return"] = result["close"] / result["previous_close"] - 1
    result["next_close"] = result["close"].shift(-1) / result["entry"] - 1
    result["three_close"] = result["close"].shift(-3) / result["entry"] - 1
    return result


def load_databento_daily(
    root: str | Path, adjust_corporate_actions: bool = True
) -> pd.DataFrame:
    """Read split DBN files and return a symbol/session feature panel."""
    files = sorted(Path(root).rglob("*.dbn.zst"))
    if not files:
        raise FileNotFoundError(f"No Databento DBN files found under {root}")
    by_symbol: dict[str, list[pd.DataFrame]] = {}
    for path in files:
        frame = db.DBNStore.from_file(path).to_df()
        if frame.empty:
            continue
        for symbol, part in frame.groupby("symbol"):
            by_symbol.setdefault(str(symbol), []).append(part)
    panels = []
    for symbol, parts in sorted(by_symbol.items()):
        minute = pd.concat(parts).sort_index()
        minute = minute.loc[~minute.index.duplicated(keep="last")]
        daily = intraday_to_daily(minute, adjust_corporate_actions)
        daily["symbol"] = symbol
        panels.append(daily.reset_index().set_index(["session", "symbol"]))
    if not panels:
        raise ValueError("Databento files contained no usable minute bars")
    return pd.concat(panels).sort_index()


def btc_event_returns(btc_5m: pd.DataFrame, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Create prior-close-to-09:25 BTC returns using only completed five-minute bars."""
    btc = btc_5m.copy().sort_index()
    btc.index = pd.to_datetime(btc.index, utc=True)
    session_index = pd.DatetimeIndex(pd.to_datetime(sessions).normalize().unique()).sort_values()
    closes = btc["close"].astype(float)
    rows = []
    prior_session: pd.Timestamp | None = None
    for raw_session in session_index:
        session = pd.Timestamp(raw_session)
        if prior_session is None:
            prior_session = session
            continue
        signal_local = pd.Timestamp(f"{session.date()} 09:25", tz=NEW_YORK)
        signal_completed = signal_local.tz_convert("UTC") - pd.offsets.Minute(5)
        signal_price = _exact_or_nan(closes, signal_completed)
        prior_close_local = pd.Timestamp(f"{prior_session.date()} 16:00", tz=NEW_YORK)
        prior_completed = prior_close_local.tz_convert("UTC") - pd.offsets.Minute(5)
        prior_price = _exact_or_nan(closes, prior_completed)
        rows.append(
            {
                "session": session,
                "btc_event_return": signal_price / prior_price - 1,
                "is_weekend": session.weekday() == 0 and prior_session.weekday() == 4,
                "prior_session": prior_session,
            }
        )
        prior_session = session
    result = pd.DataFrame(rows).set_index("session")
    result["btc_close_return"] = _btc_session_close_returns(closes, session_index)
    return result


def _exact_or_nan(series: pd.Series, timestamp: pd.Timestamp) -> float:
    value = series.get(timestamp, np.nan)
    return float(value)


def _btc_session_close_returns(closes: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    prices = {}
    for session in sessions:
        close_local = pd.Timestamp(f"{session.date()} 16:00", tz=NEW_YORK)
        prices[session] = _exact_or_nan(
            closes, close_local.tz_convert("UTC") - pd.offsets.Minute(5)
        )
    return pd.Series(prices).pct_change(fill_method=None)


def prepare_inputs(equity_root: str | Path, btc_path: str | Path) -> StudyInputs:
    equity = load_databento_daily(equity_root)
    btc = pd.read_parquet(btc_path)
    sessions = equity.index.get_level_values("session")
    events = btc_event_returns(btc, sessions)
    return StudyInputs(equity, events)


def combine_daily_panels(*panels: pd.DataFrame) -> pd.DataFrame:
    """Combine separately downloaded windows and recalculate cross-boundary returns."""
    combined = pd.concat(panels).reset_index()
    output = []
    for symbol, part in combined.groupby("symbol"):
        daily = (
            part.sort_values("session")
            .drop_duplicates("session", keep="last")
            .set_index("session")[["open", "entry", "trade_entry", "close", "minutes"]]
        )
        daily = calculate_daily_returns(adjust_splits(daily))
        daily["symbol"] = symbol
        output.append(daily.reset_index().set_index(["session", "symbol"]))
    return pd.concat(output).sort_index()


def run_studies(
    inputs: StudyInputs,
    primary_quantile: float = 0.95,
    sensitivity_quantile: float = 0.90,
    minimum_prior_events: int = 60,
    beta_lookback: int = 60,
    beta_minimum: int = 40,
    round_trip_cost_bps: float = 20,
) -> dict[str, Any]:
    panel = inputs.equity_daily.reset_index()
    events = inputs.btc_events.copy()
    event_flags = expanding_wild_events(
        events["btc_event_return"], primary_quantile, minimum_prior_events
    )
    sensitivity = expanding_wild_events(
        events["btc_event_return"], sensitivity_quantile, minimum_prior_events
    )
    events["wild_primary"] = event_flags["is_wild"]
    events["wild_sensitivity"] = sensitivity["is_wild"]
    weekends = events.loc[events["is_weekend"], "btc_event_return"]
    weekend_primary = expanding_wild_events(
        weekends, primary_quantile, minimum_prior_events
    )["is_wild"]
    weekend_sensitivity = expanding_wild_events(
        weekends, sensitivity_quantile, minimum_prior_events
    )["is_wild"]
    events["weekend_wild_primary"] = weekend_primary.reindex(events.index, fill_value=False)
    events["weekend_wild_sensitivity"] = weekend_sensitivity.reindex(
        events.index, fill_value=False
    )
    panel = panel.merge(events.reset_index(), on="session", how="inner")
    study_6 = {
        "overnight_primary": _directional_event_summary(panel.loc[panel["wild_primary"]]),
        "overnight_sensitivity": _directional_event_summary(
            panel.loc[panel["wild_sensitivity"]]
        ),
        "weekend_primary": _directional_event_summary(
            panel.loc[panel["weekend_wild_primary"]]
        ),
        "weekend_sensitivity": _directional_event_summary(
            panel.loc[panel["weekend_wild_sensitivity"]]
        ),
    }
    lead_lag_panel = _lead_lag_panel(panel, events, beta_lookback, beta_minimum)
    study_7 = _lead_lag_summary(lead_lag_panel, round_trip_cost_bps / 10_000)
    coverage = _coverage(panel)
    return {"coverage": coverage, "study_6": study_6, "study_7": study_7}


def _directional_event_summary(panel: pd.DataFrame) -> dict[str, Any]:
    return {
        "all": _event_summary(panel),
        "btc_up": _event_summary(panel.loc[panel["btc_event_return"].gt(0)]),
        "btc_down": _event_summary(panel.loc[panel["btc_event_return"].lt(0)]),
    }


def _event_summary(panel: pd.DataFrame) -> dict[str, Any]:
    if panel.empty:
        return {"event_count": 0, "asset_observations": 0, "returns": {}}
    event_level = panel.groupby("session")[["gap", "intraday", "next_close", "three_close"]].mean()
    returns = {}
    for column in event_level:
        values = event_level[column].dropna()
        returns[column] = {
            "mean": float(values.mean()) if len(values) else None,
            "median": float(values.median()) if len(values) else None,
            "positive_share": float(values.gt(0).mean()) if len(values) else None,
            "observations": len(values),
            "bootstrap_95": _bootstrap_mean_interval(values),
        }
    return {
        "event_count": int(event_level.index.nunique()),
        "asset_observations": len(panel),
        "returns": returns,
    }


def _bootstrap_mean_interval(values: pd.Series, samples: int = 2000) -> list[float] | None:
    array = values.dropna().to_numpy(float)
    if len(array) < 2:
        return None
    rng = np.random.default_rng(20260804)
    means = rng.choice(array, size=(samples, len(array)), replace=True).mean(axis=1)
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def _lead_lag_panel(
    panel: pd.DataFrame, events: pd.DataFrame, lookback: int, minimum: int
) -> pd.DataFrame:
    daily = panel.pivot(index="session", columns="symbol", values="close_return")
    gaps = panel.pivot(index="session", columns="symbol", values="gap")
    outcome = "strategy_intraday" if "strategy_intraday" in panel else "intraday"
    intraday = panel.pivot(index="session", columns="symbol", values=outcome)
    btc_daily = events["btc_close_return"].reindex(daily.index)
    factor_symbols = [symbol for symbol in BENCHMARKS if symbol in daily]
    factors = pd.concat(
        [btc_daily.rename("BTC"), daily[factor_symbols]], axis=1
    )
    factor_gaps = pd.concat(
        [events["btc_event_return"].reindex(daily.index).rename("BTC"), gaps[factor_symbols]],
        axis=1,
    )
    rows = []
    for symbol in daily.columns:
        if symbol in BENCHMARKS:
            continue
        betas = _rolling_factor_betas(daily[symbol], factors, lookback, minimum)
        expected = (betas * factor_gaps).sum(axis=1, min_count=1)
        beta = betas["BTC"]
        residual = gaps[symbol] - expected
        part = pd.DataFrame(
            {
                "session": daily.index,
                "symbol": symbol,
                "beta": beta,
                "expected_gap": expected,
                "observed_gap": gaps[symbol],
                "residual_gap": residual,
                "intraday": intraday[symbol],
                "btc_event_return": events["btc_event_return"].reindex(daily.index),
                "wild_primary": events["wild_primary"].reindex(daily.index),
            }
        )
        rows.append(part)
    return pd.concat(rows, ignore_index=True).dropna(subset=["residual_gap", "intraday"])


def _rolling_factor_betas(
    target: pd.Series, factors: pd.DataFrame, lookback: int, minimum: int
) -> pd.DataFrame:
    """Estimate zero-intercept factor sensitivities using only prior sessions."""
    output = pd.DataFrame(np.nan, index=target.index, columns=factors.columns)
    for position in range(1, len(target)):
        start = max(0, position - lookback)
        joined = pd.concat(
            [target.iloc[start:position].rename("target"), factors.iloc[start:position]], axis=1
        ).dropna()
        if len(joined) < minimum:
            continue
        coefficients, *_ = np.linalg.lstsq(
            joined[factors.columns].to_numpy(float), joined["target"].to_numpy(float), rcond=None
        )
        output.iloc[position] = coefficients
    return output


def _lead_lag_summary(panel: pd.DataFrame, cost: float) -> dict[str, Any]:
    def summarize(frame: pd.DataFrame) -> dict[str, Any]:
        if frame.empty:
            return {"sessions": 0, "asset_observations": 0}
        event = frame.groupby("session")[
            ["btc_event_return", "observed_gap", "residual_gap", "intraday"]
        ].mean()
        correlation = event["residual_gap"].corr(event["intraday"])
        btc_gap_correlation = event["btc_event_return"].corr(event["observed_gap"])
        btc_variance = event["btc_event_return"].var()
        btc_gap_slope = (
            event["btc_event_return"].cov(event["observed_gap"]) / btc_variance
            if btc_variance > 0
            else np.nan
        )
        direction_match = np.sign(event["btc_event_return"]) == np.sign(event["observed_gap"])
        reversion_gross = -np.sign(event["residual_gap"]) * event["intraday"]
        continuation_gross = np.sign(event["residual_gap"]) * event["intraday"]
        return {
            "sessions": int(event.index.nunique()),
            "asset_observations": len(frame),
            "btc_to_open_gap_correlation": float(btc_gap_correlation),
            "btc_to_open_gap_slope": float(btc_gap_slope),
            "btc_open_gap_direction_match": float(direction_match.mean()),
            "residual_to_intraday_correlation": float(correlation),
            "reversion": _strategy_summary(reversion_gross - cost),
            "continuation": _strategy_summary(continuation_gross - cost),
        }
    return {
        "all_sessions": summarize(panel),
        "wild_sessions": summarize(panel.loc[panel["wild_primary"].fillna(False)]),
    }


def _strategy_summary(returns: pd.Series) -> dict[str, Any]:
    clean = returns.dropna()
    if clean.empty:
        return {"mean_net_return": None, "win_rate": None, "observations": 0}
    return {
        "mean_net_return": float(clean.mean()),
        "median_net_return": float(clean.median()),
        "win_rate": float(clean.gt(0).mean()),
        "observations": len(clean),
        "bootstrap_95": _bootstrap_mean_interval(clean),
    }


def _coverage(panel: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for symbol, part in panel.groupby("symbol"):
        rows.append(
            {
                "symbol": symbol,
                "sessions": int(part["session"].nunique()),
                "first_session": str(part["session"].min().date()),
                "last_session": str(part["session"].max().date()),
                "short_sessions": int(part["minutes"].lt(300).sum()),
                "split_events_adjusted": int(part["split_event"].sum()),
            }
        )
    return {"symbols": rows, "total_asset_sessions": len(panel)}


def write_results(results: dict[str, Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2) + "\n")
    return path
