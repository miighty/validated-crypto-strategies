"""Deflated Sharpe Ratio (Bailey/Lopez de Prado) for the small/mid-cap Amihud
illiquidity CANDIDATE, using the program's true search size (84 prior
backtest run directories in results/ as of this test, a conservative proxy
for the total number of strategy variants tried in this repo).

Correctly converts the annualized Sharpe to per-rebalance-period units before
computing the standard error (per this skill's own documented DSR annualization
bug pitfall), then converts back to annualized terms.
"""
from __future__ import annotations

import sys
from pathlib import Path

import math

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from amihud_illiquidity_smallcap import (
    ROOT, ROUND_TRIP_COST, REBALANCE_DAYS,
    discover_universe, load_field, build_illiquidity_score,
    run_ls_backtest,
)

N_STRATEGY_VARIANTS = 84  # conservative proxy: count of results/*/runs/* dirs in this repo


def deflated_sharpe_ratio(trade_returns: np.ndarray, bars_per_year: float,
                           n_trials: int) -> dict:
    n_obs = len(trade_returns)
    sr_per_bar = trade_returns.mean() / trade_returns.std(ddof=1)
    sr_annualized = sr_per_bar * np.sqrt(bars_per_year)

    mean_r = trade_returns.mean()
    std_r = trade_returns.std(ddof=1)
    skew = np.mean(((trade_returns - mean_r) / std_r) ** 3)
    kurt = np.mean(((trade_returns - mean_r) / std_r) ** 4)  # normal = 3

    # SE formula operates on the PER-BAR Sharpe and per-bar n_obs -- consistent units.
    se_per_bar = np.sqrt(
        (1 + 0.5 * sr_per_bar**2 - skew * sr_per_bar + (kurt - 3) / 4 * sr_per_bar**2) / n_obs
    )

    def norm_ppf(p: float) -> float:
        # Acklam's rational approximation to the inverse standard normal CDF.
        a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
             1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
             6.680131188771972e+01, -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
             -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
             3.754408661907416e+00]
        p_low = 0.02425
        p_high = 1 - p_low
        if p <= 0:
            return -np.inf
        if p >= 1:
            return np.inf
        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
                   (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
        else:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                    ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

    def norm_cdf(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    # Expected max Sharpe under n_trials independent trials (approx, per-bar units)
    # using the standard extreme-value approximation.
    if n_trials > 1:
        euler_gamma = 0.5772156649
        expected_max_sr_per_bar = se_per_bar * (
            (1 - euler_gamma) * norm_ppf(1 - 1.0 / n_trials)
            + euler_gamma * norm_ppf(1 - 1.0 / (n_trials * math.e))
        )
    else:
        expected_max_sr_per_bar = 0.0

    dsr_stat = (sr_per_bar - expected_max_sr_per_bar) / se_per_bar
    p_value = 1 - norm_cdf(dsr_stat)

    return {
        "sr_annualized": float(sr_annualized),
        "sr_per_bar": float(sr_per_bar),
        "se_per_bar": float(se_per_bar),
        "skew": float(skew),
        "kurtosis": float(kurt),
        "n_obs": int(n_obs),
        "n_trials": int(n_trials),
        "expected_max_sr_per_bar": float(expected_max_sr_per_bar),
        "dsr_stat": float(dsr_stat),
        "dsr_p_value": float(p_value),
        "passes_at_0.05": bool(p_value < 0.05),
    }


def main() -> None:
    universe = discover_universe()
    closes = load_field(universe, "close")
    opens = load_field(universe, "open")
    volumes = load_field(universe, "volume")
    score = build_illiquidity_score(closes, volumes)

    result = run_ls_backtest(score, opens, "observed")
    trades = result["trades"]
    trade_returns = (trades["weighted_return"] - trades["turnover_frac"] * ROUND_TRIP_COST).values

    bars_per_year = 365.25 / REBALANCE_DAYS
    dsr = deflated_sharpe_ratio(trade_returns, bars_per_year, N_STRATEGY_VARIANTS)

    print("Deflated Sharpe Ratio test:")
    for k, v in dsr.items():
        print(f"  {k}: {v}")

    out_dir = ROOT / "results" / "amihud_illiquidity_smallcap" / "runs"
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"dsr-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "dsr_result.txt", "w") as f:
        for k, v in dsr.items():
            f.write(f"{k}={v}\n")
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
