"""Cross-sectional Monte Carlo significance test for the small/mid-cap Amihud
illiquidity CANDIDATE (EXP-2026-08-30-AMIHUD-SMALLCAP-001).

Correct null for a cross-sectional ranking factor: scramble the label
assignment (which coin lands in the long vs short leg at each rebalance),
holding leg sizes/turnover/cost structure identical -- not a generic
time-order shuffle (which is a degenerate/wrong null for this statistic,
per this skill's own documented pitfall).

n_trials=500. Reports p-value = P(random-ranking final capital >= observed
strategy final capital).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from amihud_illiquidity_smallcap import (
    ROOT, ROUND_TRIP_COST, INITIAL_CAPITAL,
    discover_universe, load_field, build_illiquidity_score, rebalance_dates,
    run_ls_backtest, run_random_control, compute_metrics,
)


def main() -> None:
    universe = discover_universe()
    closes = load_field(universe, "close")
    opens = load_field(universe, "open")
    volumes = load_field(universe, "volume")
    score = build_illiquidity_score(closes, volumes)

    observed = run_ls_backtest(score, opens, "observed")
    m_observed = compute_metrics(observed["equity"], observed["trades"])
    observed_final = m_observed["final_capital"]
    observed_sharpe = m_observed["sharpe"]
    print(f"Observed strategy final capital: {observed_final:.2f}, Sharpe: {observed_sharpe:.3f}")

    n_trials = 500
    sim_finals = []
    sim_sharpes = []
    for trial in range(n_trials):
        seed = 90000 + trial
        r = run_random_control(score.index, list(closes.columns), opens, seed)
        m = compute_metrics(r["equity"], r["trades"])
        sim_finals.append(m["final_capital"])
        sim_sharpes.append(m["sharpe"])

    sim_finals = np.array(sim_finals)
    sim_sharpes = np.array([s for s in sim_sharpes if np.isfinite(s)])

    p_value_final = float((sim_finals >= observed_final).mean())
    p_value_sharpe = float((sim_sharpes >= observed_sharpe).mean()) if len(sim_sharpes) else float("nan")

    print(f"\nMonte Carlo (n_trials={n_trials}, label-scramble null):")
    print(f"  Simulated final capital: mean={sim_finals.mean():.2f}, std={sim_finals.std():.2f}, "
          f"p5={np.percentile(sim_finals,5):.2f}, p95={np.percentile(sim_finals,95):.2f}")
    print(f"  p-value (final capital): {p_value_final:.4f}")
    print(f"  Simulated Sharpe: mean={sim_sharpes.mean():.3f}, std={sim_sharpes.std():.3f}")
    print(f"  p-value (Sharpe): {p_value_sharpe:.4f}")

    out_dir = ROOT / "results" / "amihud_illiquidity_smallcap" / "runs"
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"mc_test-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame({"sim_final_capital": sim_finals, "sim_sharpe": pd.Series(sim_sharpes).reindex(range(len(sim_finals)))}).to_csv(
        run_dir / "mc_simulations.csv", index=False)

    with open(run_dir / "mc_verdict.txt", "w") as f:
        f.write(f"observed_final_capital={observed_final}\nobserved_sharpe={observed_sharpe}\n")
        f.write(f"n_trials={n_trials}\np_value_final_capital={p_value_final}\np_value_sharpe={p_value_sharpe}\n")
        f.write(f"significant_at_0.05={p_value_final < 0.05}\n")

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
