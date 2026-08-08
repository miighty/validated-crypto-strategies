"""Strict, reproducible validation for the Crypto Edge PRD.

No result in this module is a trading instruction.  The suite deliberately
fails closed when a required point-in-time dataset is absent, and it records
the exact reason in the ranked report instead of manufacturing a proxy.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths
from .data import load_ohlcv
from .indicators import atr
from .regimes import load_regimes, regimes_known_at

MIN_EVENTS = 20
HORIZONS = (6, 24, 48, 72, 168)
FIXED_CRASHES = (-0.10, -0.15, -0.20, -0.25, -0.30)
FIXED_RALLIES = (0.10, 0.15, 0.20, 0.25, 0.30)
PERCENTILES = (0.01, 0.025, 0.05)
_CONTROL_CONTEXTS: dict[tuple[int, int], tuple[dict[tuple[str, float], np.ndarray], pd.Series, np.ndarray]] = {}


@dataclass(frozen=True)
class EventSpec:
    family: str
    name: str
    side: int
    signal_return: pd.Series
    threshold: float
    horizon_hours: int


def run_validation(paths: Paths, seed: int = 7, bootstrap_samples: int = 2_000) -> pd.DataFrame:
    """Run executable BTC tests and issue explicit data requirements for the rest."""
    paths.create()
    # Never overwrite a prior evidence run. This also avoids macOS provenance
    # locks on artifacts from an interrupted process.
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.edge_results / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    btc = load_ohlcv(paths, "BTC", "1h")
    regimes = regimes_known_at(btc.index, load_regimes(paths, "BTC"))
    results: list[dict[str, object]] = []
    events: list[pd.DataFrame] = []

    dca, dca_ledger = weekly_dca_benchmarks(btc)
    dca.to_csv(output / "dca_benchmarks.csv", index=False, float_format="%.17g")
    dca_ledger.to_csv(output / "dca_purchases.csv", index=False, float_format="%.17g")
    results.extend(dca.assign(family="weekly_btc_dca", decision="benchmark_not_edge_assessment").to_dict("records"))

    for spec in extreme_move_specs(btc):
        trades = build_non_overlapping_events(btc, regimes, spec)
        if not trades.empty:
            trades["family"] = spec.family
            trades["variant"] = spec.name
            events.append(trades)
        results.append(event_result(spec, trades, btc, seed, bootstrap_samples))

    missing = external_data_decisions(paths)
    results.extend(missing)
    result_frame = pd.DataFrame(results)
    result_frame.to_csv(output / "variant_results.csv", index=False, float_format="%.17g")
    event_frame = pd.concat(events, ignore_index=True) if events else pd.DataFrame()
    event_frame.to_csv(output / "event_ledger.csv", index=False, float_format="%.17g")
    write_ranked_report(output, result_frame)
    print(f"Crypto Edge suite: {len(result_frame)} variants written to {output}", flush=True)
    return result_frame


def extreme_move_specs(frame: pd.DataFrame) -> list[EventSpec]:
    r48 = frame["close"].pct_change(48)
    r24 = frame["close"].pct_change(24)
    specs: list[EventSpec] = []
    for threshold in FIXED_CRASHES:
        for hours in HORIZONS:
            specs.append(EventSpec("btc_crash_rebound", f"crash_48h_{abs(threshold):.0%}_{hours}h", 1, r48, threshold, hours))
    for threshold in FIXED_RALLIES:
        for side, label in ((1, "continuation"), (-1, "reversal")):
            for hours in HORIZONS:
                specs.append(EventSpec("btc_rally", f"rally_24h_{threshold:.0%}_{label}_{hours}h", side, r24, threshold, hours))
    # Quantiles and volatility thresholds are calculated from trailing observations only.
    for quantile in PERCENTILES:
        crash_threshold = r48.rolling(24 * 180, min_periods=24 * 60).quantile(quantile)
        rally_threshold = r24.rolling(24 * 180, min_periods=24 * 60).quantile(1 - quantile)
        for hours in HORIZONS:
            specs.extend((
                EventSpec("btc_crash_rebound", f"crash_48h_p{quantile:g}_{hours}h", 1, r48 - crash_threshold, 0.0, hours),
                EventSpec("btc_rally", f"rally_24h_p{quantile:g}_continuation_{hours}h", 1, r24 - rally_threshold, 0.0, hours),
                EventSpec("btc_rally", f"rally_24h_p{quantile:g}_reversal_{hours}h", -1, r24 - rally_threshold, 0.0, hours),
            ))
    daily_atr = atr(frame, 24 * 14) / frame["close"]
    for multiple in (3.0, 4.0, 5.0):
        for hours in HORIZONS:
            specs.extend((
                EventSpec("btc_crash_rebound", f"crash_48h_{multiple:g}x_atr_{hours}h", 1, r48 / daily_atr, -multiple, hours),
                EventSpec("btc_rally", f"rally_24h_{multiple:g}x_atr_continuation_{hours}h", 1, r24 / daily_atr, multiple, hours),
                EventSpec("btc_rally", f"rally_24h_{multiple:g}x_atr_reversal_{hours}h", -1, r24 / daily_atr, multiple, hours),
            ))
    return specs


def build_non_overlapping_events(
    frame: pd.DataFrame, regimes: pd.Series, spec: EventSpec,
) -> pd.DataFrame:
    """Signal on a completed close; enter next open.  A later signal cannot overlap exit."""
    signal = spec.signal_return <= spec.threshold if spec.threshold < 0 else spec.signal_return >= spec.threshold
    rows: list[dict[str, object]] = []
    next_allowed = 0
    for signal_i in np.flatnonzero(signal.fillna(False).to_numpy()):
        entry_i = signal_i + 1
        exit_i = entry_i + spec.horizon_hours
        if entry_i < next_allowed or exit_i >= len(frame):
            continue
        entry = float(frame["open"].iloc[entry_i]) * (1 + ONE_WAY_COST * spec.side)
        exit_price = float(frame["open"].iloc[exit_i]) * (1 - ONE_WAY_COST * spec.side)
        window = frame.iloc[entry_i : exit_i + 1]
        gross = spec.side * (exit_price / entry - 1)
        mae = spec.side * (window["low"].min() / entry - 1) if spec.side > 0 else spec.side * (window["high"].max() / entry - 1)
        mfe = spec.side * (window["high"].max() / entry - 1) if spec.side > 0 else spec.side * (window["low"].min() / entry - 1)
        rows.append({
            "signal_time": frame.index[signal_i], "entry_time": frame.index[entry_i],
            "exit_time": frame.index[exit_i], "side": "long" if spec.side > 0 else "short",
            "signal_return": float(spec.signal_return.iloc[signal_i]), "entry_price": entry,
            "exit_price": exit_price, "net_return": gross, "mae": mae, "mfe": mfe,
            "regime": regimes.iloc[entry_i], "year": frame.index[entry_i].year,
            "realized_volatility": float(frame["close"].pct_change().rolling(24 * 7).std().iloc[signal_i]),
        })
        next_allowed = exit_i + 1
    return pd.DataFrame(rows)


def event_result(spec: EventSpec, trades: pd.DataFrame, frame: pd.DataFrame, seed: int, bootstrap_samples: int) -> dict[str, object]:
    base = {"family": spec.family, "variant": spec.name, "horizon_hours": spec.horizon_hours, "side": "long" if spec.side > 0 else "short", "entry_rule": "completed signal close, next hourly open", "cost_model": f"{ONE_WAY_COST:.2%} per side"}
    if len(trades) < MIN_EVENTS:
        return {**base, "event_count": len(trades), "decision": "insufficient_data", "explanation": f"Only {len(trades)} non-overlapping events; fewer than {MIN_EVENTS} is exploratory."}
    returns = trades["net_return"]
    splits = chronological_splits(trades)
    test = splits["test"]
    control_mean = matched_random_mean(frame, trades, spec.horizon_hours, spec.side, seed)
    boot_low, boot_high = bootstrap_ci(returns, seed, bootstrap_samples)
    metrics = trade_metrics(returns, trades)
    train_mean = float(splits["train"]["net_return"].mean()) if not splits["train"].empty else np.nan
    validation_mean = float(splits["validation"]["net_return"].mean()) if not splits["validation"].empty else np.nan
    test_mean = float(test["net_return"].mean()) if not test.empty else np.nan
    passes = len(test) >= MIN_EVENTS and test_mean > 0 and boot_low > 0 and test_mean > control_mean
    explanation = ("Passes the predeclared event, test-period, bootstrap and random-control gates."
                   if passes else "Fails one or more predeclared gates: untouched test must have 20 events, positive mean return, positive bootstrap lower bound, and beat matched random events.")
    return {**base, **metrics, "train_mean_return": train_mean, "validation_mean_return": validation_mean,
            "test_mean_return": test_mean, "test_event_count": len(test), "matched_random_mean_return": control_mean,
            "bootstrap_mean_ci_low": boot_low, "bootstrap_mean_ci_high": boot_high,
            "decision": "pass" if passes else "fail", "explanation": explanation}


def chronological_splits(trades: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ordered = trades.sort_values("entry_time").reset_index(drop=True)
    n = len(ordered)
    return {"train": ordered.iloc[: int(n * .6)], "validation": ordered.iloc[int(n * .6): int(n * .8)], "test": ordered.iloc[int(n * .8):]}


def trade_metrics(returns: pd.Series, trades: pd.DataFrame) -> dict[str, object]:
    values = returns.dropna()
    wins = values[values > 0].sum(); losses = -values[values < 0].sum()
    curve = (1 + values).cumprod(); drawdown = curve / curve.cummax() - 1
    downside = values[values < 0].std(ddof=1)
    return {"event_count": len(values), "net_return": float(curve.iloc[-1] - 1), "mean_trade_return": float(values.mean()), "median_trade_return": float(values.median()), "win_rate": float((values > 0).mean()), "profit_factor": float(wins / losses) if losses > 0 else np.nan, "sharpe": float(np.sqrt(len(values)) * values.mean() / values.std(ddof=1)) if values.std(ddof=1) > 0 else np.nan, "sortino": float(np.sqrt(len(values)) * values.mean() / downside) if downside and downside > 0 else np.nan, "maximum_drawdown": abs(float(drawdown.min())), "maximum_adverse_excursion": float(trades["mae"].min()), "maximum_favourable_excursion": float(trades["mfe"].max())}


def bootstrap_ci(returns: pd.Series, seed: int, samples: int) -> tuple[float, float]:
    # Cap each resample at 500 events: this is a bootstrap of the empirical event
    # distribution, keeps the full parameter grid rerunnable on a laptop, and is
    # deliberately disclosed rather than silently reducing the number of draws.
    rng = np.random.default_rng(seed)
    values = returns.to_numpy()
    resample_size = min(len(values), 500)
    means = rng.choice(values, size=(samples, resample_size), replace=True).mean(axis=1)
    return float(np.quantile(means, .025)), float(np.quantile(means, .975))


def matched_random_mean(frame: pd.DataFrame, trades: pd.DataFrame, horizon: int, side: int, seed: int) -> float:
    """Random control matched to entry year/month and trailing-volatility quintile; no event reuse."""
    rng = np.random.default_rng(seed)
    cache_key = (id(frame), horizon)
    if cache_key not in _CONTROL_CONTEXTS:
        volatility = frame["close"].pct_change().rolling(24 * 7).std()
        all_candidates = pd.DataFrame({"position": np.arange(len(frame)), "vol": volatility.to_numpy()})
        all_candidates["month"] = frame.index.strftime("%Y-%m")
        all_candidates["bucket"] = pd.qcut(all_candidates["vol"], 5, labels=False, duplicates="drop")
        candidates = all_candidates[all_candidates["position"] + horizon < len(frame)]
        pools = {
            key: group["position"].to_numpy()
            for key, group in candidates.dropna(subset=["bucket"]).groupby(["month", "bucket"])
        }
        _CONTROL_CONTEXTS[cache_key] = (
            pools,
            pd.Series(np.arange(len(frame)), index=frame.index),
            all_candidates["bucket"].to_numpy(),
        )
    pools, entry_positions, buckets = _CONTROL_CONTEXTS[cache_key]
    random_returns = []
    for row in trades.itertuples():
        entry_position = int(entry_positions.loc[row.entry_time])
        bucket = buckets[entry_position]
        if pd.isna(bucket):
            continue
        pool = pools.get((pd.Timestamp(row.entry_time).strftime("%Y-%m"), bucket))
        if pool is None or len(pool) == 0:
            continue
        i = int(rng.choice(pool))
        entry = frame["open"].iloc[i] * (1 + ONE_WAY_COST * side)
        exit_price = frame["open"].iloc[i + horizon] * (1 - ONE_WAY_COST * side)
        random_returns.append(side * (exit_price / entry - 1))
    return float(np.mean(random_returns)) if random_returns else np.nan


def weekly_dca_benchmarks(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    five_years = frame.loc[frame.index >= frame.index.max() - pd.DateOffset(years=5)].copy()
    london = five_years.index.tz_convert("Europe/London")
    schedules: dict[str, pd.DatetimeIndex] = {}
    for weekday in range(7): schedules[f"{['mon','tue','wed','thu','fri','sat','sun'][weekday]}_09_london"] = five_years.index[(london.weekday == weekday) & (london.hour == 9)]
    schedules["daily_equal_capital"] = five_years.index[london.hour == 9]
    schedules["monthly_equal_capital"] = five_years.index[(london.day == 1) & (london.hour == 9)]
    schedules["immediate_weekly_available"] = five_years.index[(london.weekday == 0) & (london.hour == 0)]
    weekly_rows = pd.DataFrame({"timestamp": five_years.index, "week": london.strftime("%G-%V")})
    random_generator = np.random.default_rng(7)
    random_weekly = weekly_rows.groupby("week", sort=True)["timestamp"].apply(
        lambda values: random_generator.choice(values.to_numpy())
    )
    schedules["random_weekly_purchase_time"] = pd.DatetimeIndex(random_weekly.to_numpy())
    # All alternatives receive exactly the Monday strategy's total capital; their per-purchase size changes.
    total = len(schedules["mon_09_london"]) * 100.0
    rows = []; ledger = []
    for name, times in schedules.items():
        if len(times) == 0: continue
        spend = total / len(times); shares = 0.0; cash = 0.0; equity = []
        planned = set(times)
        for timestamp, row in five_years.iterrows():
            if timestamp in planned:
                shares += (spend * (1 - ONE_WAY_COST)) / (row["open"] * (1 + ONE_WAY_COST)); cash -= spend
                ledger.append({"benchmark": name, "timestamp": timestamp, "capital": spend, "execution_price": row["open"] * (1 + ONE_WAY_COST)})
            equity.append(cash + shares * row["close"])
        curve = pd.Series(equity, index=five_years.index); dd = curve / curve.cummax() - 1
        underwater = float((dd < 0).mean()); terminal = float(curve.iloc[-1]); years = (curve.index[-1] - curve.index[0]).days / 365.25
        rows.append({"variant": name, "purchase_count": len(times), "total_capital": total, "terminal_value": terminal, "net_return": terminal / total - 1, "xirr_proxy_annualized": float((terminal / total) ** (1 / years) - 1), "maximum_drawdown": abs(float(dd.min())), "time_underwater": underwater, "day_of_week": name[:3] if name.endswith("london") else "comparison"})
    return pd.DataFrame(rows), pd.DataFrame(ledger)


def external_data_decisions(paths: Paths) -> list[dict[str, object]]:
    requirements = {
        "crypto_stock_overnight_lag": ["equity_bars.csv.gz", "index_futures_bars.csv.gz"],
        "liquidation_conditioned_lag": ["equity_bars.csv.gz", "index_futures_bars.csv.gz", "liquidations.csv.gz", "open_interest.csv.gz", "funding.csv.gz"],
        "strategy_inc_transaction_period": ["strategy_inc_transactions.csv"],
        "strategy_inc_disclosure_event": ["strategy_inc_disclosures.csv", "mstr_bars.csv.gz"],
    }
    output = []
    for family, names in requirements.items():
        absent = [name for name in names if not (paths.edge_data / name).exists()]
        output.append({"family": family, "variant": "all", "event_count": 0, "decision": "insufficient_data", "explanation": "Missing point-in-time inputs: " + ", ".join(absent) if absent else "Input files supplied but this study adapter has not yet been enabled.", "required_inputs": ", ".join(names)})
    return output


def write_ranked_report(output: Path, results: pd.DataFrame) -> None:
    passing = results[results["decision"] == "pass"] if "decision" in results else pd.DataFrame()
    failing = results[results["decision"] == "fail"] if "decision" in results else pd.DataFrame()
    insufficient = results[results["decision"] == "insufficient_data"] if "decision" in results else pd.DataFrame()
    lines = ["# Crypto Edge Validation Suite", "", "This is historical research, not investment advice or an execution signal.", "", "## Ranking", "", f"- Validated edge variants: {len(passing)}", f"- Failed variants: {len(failing)}", f"- Insufficient-data variants: {len(insufficient)}", "", "A passing variant must have at least 20 untouched-test events, positive out-of-sample mean, a positive 95% bootstrap lower bound, and beat volatility/month-matched random controls. Weekly DCA is a benchmark and is never classified as an edge.", "", "See `variant_results.csv`, `event_ledger.csv`, and `dca_benchmarks.csv` for all metrics and inputs."]
    (output / "RANKED_REPORT.md").write_text("\n".join(lines) + "\n")
