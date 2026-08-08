"""Fail-closed BTC-dominance and ETF-flow validation workflow.

The source data is deliberately supplied by the researcher because publication
timestamps and point-in-time tradable universes are core evidence, not details
that can safely be reconstructed after the fact.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths
from .data import load_ohlcv
from .regimes import load_regimes, regimes_known_at

MIN_EVENTS = 20
HOLDING_DAYS = (1, 3, 7, 14, 30)
DOMINANCE_COLUMNS = {
    "timestamp", "available_at", "btc_dominance", "alt_market_cap_ex_btc", "total3_market_cap", "source_url"
}
ALT_COLUMNS = {
    "timestamp", "symbol", "close", "market_cap", "tradeable", "stablecoin", "perpetual_tradeable"
}
ETF_COLUMNS = {"flow_date", "published_at", "asset", "fund", "net_flow_usd", "total_assets_usd", "source_url"}


def run_dominance_etf_validation(paths: Paths, seed: int = 17) -> pd.DataFrame:
    """Create visual review artifacts before executing predeclared event tests."""
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.dominance_etf_results / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    missing = missing_inputs(paths)
    if missing:
        results = pd.DataFrame([{
            "study": "btc_dominance_and_etf_flows", "variant": "all", "decision": "insufficient_data",
            "event_count": 0, "explanation": "Missing required point-in-time files: " + ", ".join(missing),
        }])
        results.to_csv(output / "results.csv", index=False)
        write_report(output, results, missing)
        return results

    dominance = read_csv(paths.dominance_etf_data / "dominance.csv", DOMINANCE_COLUMNS, "timestamp")
    alt = read_csv(paths.dominance_etf_data / "alt_universe.csv.gz", ALT_COLUMNS, "timestamp")
    etf = read_csv(paths.dominance_etf_data / "etf_flows.csv", ETF_COLUMNS, "published_at")
    btc = load_ohlcv(paths, "BTC", "1h")
    eth = load_ohlcv(paths, "ETH", "1h")
    validate_availability(dominance, "timestamp", "available_at", "dominance")
    validate_availability(etf, "flow_date", "published_at", "etf_flows")
    basket = point_in_time_alt_baskets(alt)
    visual_review(output, dominance, basket, etf, btc, eth)
    regimes = regimes_known_at(btc.index, load_regimes(paths, "BTC"))
    results = [*dominance_tests(dominance, basket, btc, regimes, seed), *etf_tests(etf, btc, eth, regimes, seed)]
    result_frame = pd.DataFrame(results)
    result_frame.to_csv(output / "results.csv", index=False, float_format="%.17g")
    write_report(output, result_frame, [])
    return result_frame


def missing_inputs(paths: Paths) -> list[str]:
    required = ("dominance.csv", "alt_universe.csv.gz", "etf_flows.csv")
    return [name for name in required if not (paths.dominance_etf_data / name).exists()]


def read_csv(path: Path, required: set[str], time_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    absent = sorted(required - set(frame.columns))
    if absent:
        raise ValueError(f"{path.name} missing required columns: {', '.join(absent)}")
    for column in {time_column, "timestamp", "available_at", "published_at", "flow_date"} & set(frame.columns):
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="raise")
    if frame[time_column].duplicated().any() and path.name == "dominance.csv":
        raise ValueError("dominance.csv has duplicate timestamps")
    return frame.sort_values(time_column)


def validate_availability(frame: pd.DataFrame, observation: str, available: str, label: str) -> None:
    if (frame[available] < frame[observation]).any():
        raise ValueError(f"{label} has availability before the observed period")
    if frame[available].duplicated().any() and label == "dominance":
        raise ValueError("dominance has duplicate publication timestamps")


def point_in_time_alt_baskets(alt: pd.DataFrame) -> pd.DataFrame:
    clean = alt[(alt["tradeable"].astype(bool)) & (~alt["stablecoin"].astype(bool)) & (alt["close"] > 0)].copy()
    clean["weight"] = clean.groupby("timestamp")["market_cap"].transform(lambda x: x / x.sum())
    return clean


def dominance_signals(frame: pd.DataFrame) -> dict[str, pd.Series]:
    value = frame.set_index("available_at")["btc_dominance"].sort_index()
    change = value.diff()
    return {
        "cross_above_29pct": (value >= .29) & (value.shift(1) < .29),
        "cross_below_29pct": (value < .29) & (value.shift(1) >= .29),
        "local_low_rising": (value.shift(1) < value.shift(2)) & (value.shift(1) < value) & (change > 0),
        "rise_2pp": change.rolling(5).sum() >= .02,
        "rise_3pp": change.rolling(5).sum() >= .03,
        "rise_5pp": change.rolling(5).sum() >= .05,
        "break_30d_high": value >= value.shift(1).rolling(30).max(),
        "break_60d_high": value >= value.shift(1).rolling(60).max(),
        "break_90d_high": value >= value.shift(1).rolling(90).max(),
        "ma_trend_positive": value.rolling(20).mean() > value.rolling(60).mean(),
        "top_5pct": value >= value.shift(1).rolling(365, min_periods=90).quantile(.95),
    }


def dominance_tests(dominance: pd.DataFrame, basket: pd.DataFrame, btc: pd.DataFrame, regimes: pd.Series, seed: int) -> list[dict[str, object]]:
    returns = basket_returns(basket)
    btc_returns = btc["close"].pct_change().resample("1D").apply(lambda x: (1 + x).prod() - 1)
    outputs = []
    for name, signals in dominance_signals(dominance).items():
        for basket_name, basket_return in returns.items():
            for days in HOLDING_DAYS:
                outputs.append(decide("btc_dominance", f"{name}:{basket_name}:short_alt:{days}d", forward_events(signals, basket_return, days, -1, regimes), seed))
                relative = btc_returns.sub(basket_return, fill_value=np.nan)
                outputs.append(decide("btc_dominance", f"{name}:{basket_name}:long_btc_short_alt:{days}d", forward_events(signals, relative, days, 1, regimes), seed))
        eth_btc = returns["eth"].sub(btc_returns, fill_value=np.nan)
        for days in HOLDING_DAYS:
            outputs.append(decide("btc_dominance", f"{name}:short_eth_btc:{days}d", forward_events(signals, eth_btc, days, -1, regimes), seed))
    return outputs


def basket_returns(basket: pd.DataFrame) -> dict[str, pd.Series]:
    """Every constituent is selected from the contemporaneously tradeable universe."""
    work = basket.copy()
    work["rank"] = work.groupby("timestamp")["market_cap"].rank(ascending=False, method="first")
    work["ret"] = work.groupby("symbol")["close"].pct_change()

    def equal(mask: pd.Series) -> pd.Series:
        return work[mask].groupby("timestamp")["ret"].mean()

    def weighted(mask: pd.Series) -> pd.Series:
        selected = work[mask]
        return selected.groupby("timestamp").apply(
            lambda rows: np.average(rows["ret"].fillna(0), weights=rows["market_cap"]), include_groups=False
        )

    top = lambda n: work["rank"] <= n
    outputs = {
        "equal_weight_top10": equal(top(10)), "equal_weight_top20": equal(top(20)),
        "equal_weight_top50": equal(top(50)), "market_cap_weighted": weighted(work["rank"] > 0),
        "large_cap": equal(top(20)), "mid_cap": equal((work["rank"] > 20) & (work["rank"] <= 100)),
        "perpetual_top20": equal(top(20) & work["perpetual_tradeable"].astype(bool)),
        "eth": equal(work["symbol"].str.upper() == "ETH"),
    }
    # High beta is defined before each date from trailing 30 available daily returns.
    beta_proxy = work.groupby("symbol")["ret"].transform(lambda x: x.rolling(30).std())
    outputs["high_beta"] = equal(beta_proxy >= beta_proxy.groupby(work["timestamp"]).transform("quantile", .75))
    return outputs


def etf_tests(etf: pd.DataFrame, btc: pd.DataFrame, eth: pd.DataFrame, regimes: pd.Series, seed: int) -> list[dict[str, object]]:
    outputs = []
    for asset, price in {"BTC": btc, "ETH": eth}.items():
        flows = etf[etf["asset"].str.upper() == asset].groupby("published_at", as_index=True).agg(net_flow_usd=("net_flow_usd", "sum"), total_assets_usd=("total_assets_usd", "sum"))
        if flows.empty: continue
        flow_pct = flows["net_flow_usd"] / flows["total_assets_usd"].replace(0, np.nan)
        signals = {
            "any_outflow": flows["net_flow_usd"] < 0,
            "outflow_over_100m": flows["net_flow_usd"] <= -100_000_000,
            "outflow_over_250m": flows["net_flow_usd"] <= -250_000_000,
            "outflow_over_500m": flows["net_flow_usd"] <= -500_000_000,
            "outflow_025pct_assets": flow_pct <= -.0025,
            "outflow_050pct_assets": flow_pct <= -.005,
            "outflow_100pct_assets": flow_pct <= -.01,
            "worst_5pct": flows["net_flow_usd"] <= flows["net_flow_usd"].shift(1).rolling(252, min_periods=60).quantile(.05),
        }
        returns = price["close"].pct_change().resample("1D").apply(lambda x: (1 + x).prod() - 1)
        for name, signal in signals.items():
            for days in (1, 3, 7):
                for side, label in ((-1, "continuation_short"), (1, "contrarian_long")):
                    events = forward_events(signal, returns, days, side, regimes)
                    outputs.append(decide("etf_outflows", f"{asset}:{name}:{label}:{days}d", events, seed))
    return outputs


def forward_events(signals: pd.Series, returns: pd.Series, days: int, side: int, regimes: pd.Series) -> pd.DataFrame:
    returns = returns.sort_index(); signal_times = pd.DatetimeIndex(signals[signals.fillna(False)].index)
    rows = []; next_time = pd.Timestamp.min.tz_localize("UTC")
    for time in signal_times:
        entry_candidates = returns.index[returns.index > time]
        if not len(entry_candidates): continue
        entry = entry_candidates[0]; exit_index = returns.index.get_indexer([entry])[0] + days
        if entry < next_time or exit_index >= len(returns): continue
        exit_time = returns.index[exit_index]; trade_return = side * ((1 + returns.iloc[returns.index.get_indexer([entry])[0]:exit_index]).prod() - 1) - 2 * ONE_WAY_COST
        known_regime = regimes.asof(entry) if not regimes.empty else "Unavailable"
        rows.append({"entry_time": entry, "exit_time": exit_time, "return": trade_return, "regime": known_regime})
        next_time = exit_time
    return pd.DataFrame(rows)


def decide(study: str, variant: str, events: pd.DataFrame, seed: int) -> dict[str, object]:
    if len(events) < MIN_EVENTS:
        return {"study": study, "variant": variant, "event_count": len(events), "decision": "insufficient_data", "explanation": f"Only {len(events)} independent events; fewer than {MIN_EVENTS} is exploratory."}
    values = events["return"]; split = int(len(values) * .8); test = values.iloc[split:]
    rng = np.random.default_rng(seed); sample_size = min(len(values), 500)
    ci_low = float(np.quantile(rng.choice(values, size=(1000, sample_size)).mean(axis=1), .025))
    curve = (1 + values).cumprod(); max_dd = abs(float((curve / curve.cummax() - 1).min()))
    regime_means = events.groupby("regime")["return"].mean()
    passed = len(test) >= MIN_EVENTS and test.mean() > 0 and ci_low > 0 and (regime_means > 0).sum() >= 2
    return {"study": study, "variant": variant, "event_count": len(events), "net_return": float(curve.iloc[-1] - 1), "mean_return": float(values.mean()), "median_return": float(values.median()), "win_rate": float((values > 0).mean()), "max_drawdown": max_dd, "test_event_count": len(test), "test_mean_return": float(test.mean()), "bootstrap_ci_low": ci_low, "positive_regime_count": int((regime_means > 0).sum()), "decision": "pass" if passed else "fail", "explanation": "Passes predeclared OOS, bootstrap and multi-regime gates." if passed else "Does not clear the OOS, bootstrap or multi-regime decision gates."}


def visual_review(output: Path, dominance: pd.DataFrame, basket: pd.DataFrame, etf: pd.DataFrame, btc: pd.DataFrame, eth: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 16), sharex=False)
    axes[0].plot(dominance["timestamp"], dominance["btc_dominance"], label="BTC dominance"); axes[0].axhline(.29, color="red", ls="--", label="29% threshold"); axes[0].legend()
    axes[1].plot(btc.index, btc["close"], label="BTC"); axes[1].plot(eth.index, eth["close"], label="ETH"); axes[1].set_yscale("log"); axes[1].legend()
    basket_value = basket.groupby("timestamp")["market_cap"].sum(); axes[2].plot(basket_value.index, basket_value, label="Alt market cap (tradeable universe)"); axes[2].legend()
    daily_flow = etf.groupby("published_at")["net_flow_usd"].sum(); axes[3].bar(daily_flow.index, daily_flow, width=1, label="Published ETF net flow"); axes[3].legend()
    fig.suptitle("Visual review: dominance, crypto prices, alt universe, and published ETF flows")
    fig.tight_layout(); fig.savefig(output / "visual_review.png", dpi=150); plt.close(fig)


def write_report(output: Path, results: pd.DataFrame, missing: list[str]) -> None:
    decisions = results["decision"].value_counts().to_dict()
    lines = ["# BTC Dominance and ETF Flow Validation", "", "Charts are generated before event studies whenever all point-in-time inputs are available.", "", "## Decision summary", ""]
    lines.extend(f"- {key}: {value}" for key, value in sorted(decisions.items()))
    if missing: lines.extend(["", "## Missing evidence", "", "- " + "\n- ".join(missing)])
    lines.extend(["", "No result is trading advice. A pass requires 20 independent observations, positive untouched-test expectancy, positive bootstrap lower bound, and positive performance in at least two regimes."])
    (output / "RANKED_REPORT.md").write_text("\n".join(lines) + "\n")
