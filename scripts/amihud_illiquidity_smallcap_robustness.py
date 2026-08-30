"""Robustness checks for the small/mid-cap Amihud illiquidity CANDIDATE
(EXP-2026-08-30-AMIHUD-SMALLCAP-001) before upgrading from CANDIDATE to PASS.

Checks (frozen, standard for this repo):
  1. Doubled round-trip cost (60bps) -- still beat cash?
  2. 1-day execution delay (enter one day later than signal) -- still beat cash?
  3. Walk-forward split: first half (2020-2023) vs second half (2023-2026) --
     does the edge persist out-of-sample or was it concentrated in one era?
  4. Best-trade exclusion -- drop the single best-PnL trade, still profitable?
  5. Seeded block-bootstrap 95% CI on mean trade return.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from amihud_illiquidity_smallcap import (
    ROOT, PATHS, ROUND_TRIP_COST, ILLIQ_WINDOW, ILLIQ_MIN_OBS, REBALANCE_DAYS,
    INITIAL_CAPITAL, START_ANALYSIS, RANDOM_SEED,
    discover_universe, load_field, build_illiquidity_score, rebalance_dates,
    compute_metrics,
)


def run_ls_backtest_generic(score: pd.DataFrame, opens: pd.DataFrame, cost_rate: float,
                             delay_days: int, label: str,
                             restrict_start: pd.Timestamp | None = None,
                             restrict_end: pd.Timestamp | None = None) -> dict:
    dates = score.index
    reb_dates = rebalance_dates(dates)
    if restrict_start is not None or restrict_end is not None:
        mask = pd.Series(True, index=reb_dates)
        if restrict_start is not None:
            mask &= reb_dates >= restrict_start
        if restrict_end is not None:
            mask &= reb_dates < restrict_end
        reb_dates = reb_dates[mask]
    capital = INITIAL_CAPITAL
    prev_weights: dict[str, float] = {}
    equity_curve = []
    trade_log = []

    for i, reb_date in enumerate(reb_dates):
        row = score.loc[reb_date].dropna()
        if len(row) < 9:
            continue
        n = len(row)
        leg_n = max(1, n // 3)
        ranked = row.sort_values(ascending=False)
        long_names = ranked.head(leg_n).index.tolist()
        short_names = ranked.tail(leg_n).index.tolist()
        new_weights = {name: 0.5 / len(long_names) for name in long_names}
        for name in short_names:
            new_weights[name] = new_weights.get(name, 0.0) - 0.5 / len(short_names)

        pos_in_index = dates.get_indexer([reb_date])[0]
        entry_pos = pos_in_index + 1 + delay_days
        if entry_pos >= len(dates):
            break
        entry_date = dates[entry_pos]
        if entry_date not in opens.index:
            continue

        if i + 1 < len(reb_dates):
            next_reb_pos = dates.get_indexer([reb_dates[i + 1]])[0]
            exit_pos = next_reb_pos + 1 + delay_days
            if exit_pos >= len(dates):
                exit_pos = len(dates) - 1
            exit_date = dates[exit_pos]
        else:
            exit_date = dates[-1]

        turnover = 0.0
        all_names = set(prev_weights) | set(new_weights)
        for name in all_names:
            turnover += abs(new_weights.get(name, 0.0) - prev_weights.get(name, 0.0))
        turnover = min(turnover, 2.0) / 2.0
        cost = capital * turnover * cost_rate

        all_leg_names = long_names + short_names
        entry_prices = opens.loc[entry_date, all_leg_names]
        if exit_date == entry_date:
            exit_prices = entry_prices
        else:
            exit_pos_idx = dates.get_indexer([exit_date])[0]
            exit_prices = opens.loc[dates[exit_pos_idx], all_leg_names]
        valid = entry_prices.notna() & exit_prices.notna() & (entry_prices > 0)

        per_asset_ret = (exit_prices[valid] / entry_prices[valid]) - 1.0
        weighted_ret = 0.0
        for name in per_asset_ret.index:
            weighted_ret += new_weights.get(name, 0.0) * per_asset_ret[name]

        capital_before = capital
        capital = capital * (1.0 + weighted_ret) - cost
        equity_curve.append({"date": exit_date, "equity": capital})
        trade_log.append({
            "rebalance_date": reb_date, "entry_date": entry_date, "exit_date": exit_date,
            "weighted_return": weighted_ret, "turnover_frac": turnover, "cost": cost,
            "capital_before": capital_before, "capital_after": capital,
            "net_pnl": capital - capital_before,
        })
        prev_weights = new_weights

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": label, "equity": equity_df, "trades": trades_df, "final_capital": capital}


def block_bootstrap_ci(trade_returns: np.ndarray, n_boot: int = 5000, block: int = 8,
                        seed: int = 20260830) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(trade_returns)
    if n < block * 2:
        return (float("nan"), float("nan"), float("nan"))
    means = []
    n_blocks = int(np.ceil(n / block))
    for _ in range(n_boot):
        idx = []
        for _ in range(n_blocks):
            start = rng.integers(0, n - block + 1)
            idx.extend(range(start, start + block))
        idx = idx[:n]
        means.append(trade_returns[idx].mean())
    means = np.array(means)
    return (float(np.mean(trade_returns)), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def main() -> None:
    universe = discover_universe()
    closes = load_field(universe, "close")
    opens = load_field(universe, "open")
    volumes = load_field(universe, "volume")
    score = build_illiquidity_score(closes, volumes)

    print("=== 1. Baseline (30bps, no delay) ===")
    base = run_ls_backtest_generic(score, opens, ROUND_TRIP_COST, 0, "baseline")
    m_base = compute_metrics(base["equity"], base["trades"])
    print(m_base)

    print("\n=== 2. Doubled cost (60bps) ===")
    doubled = run_ls_backtest_generic(score, opens, 2 * ROUND_TRIP_COST, 0, "doubled_cost")
    m_doubled = compute_metrics(doubled["equity"], doubled["trades"])
    print(m_doubled)

    print("\n=== 3. 1-day execution delay ===")
    delayed = run_ls_backtest_generic(score, opens, ROUND_TRIP_COST, 1, "delayed_1d")
    m_delayed = compute_metrics(delayed["equity"], delayed["trades"])
    print(m_delayed)

    print("\n=== 4. Walk-forward split ===")
    mid = pd.Timestamp("2023-04-01", tz="UTC")
    first_half = run_ls_backtest_generic(score, opens, ROUND_TRIP_COST, 0, "first_half",
                                          restrict_end=mid)
    second_half = run_ls_backtest_generic(score, opens, ROUND_TRIP_COST, 0, "second_half",
                                           restrict_start=mid)
    m_first = compute_metrics(first_half["equity"], first_half["trades"])
    m_second = compute_metrics(second_half["equity"], second_half["trades"])
    print("First half (2020-01 to 2023-04):", m_first)
    print("Second half (2023-04 to 2026-07):", m_second)

    print("\n=== 5. Best-trade exclusion ===")
    trades = base["trades"].copy()
    if not trades.empty:
        best_idx = trades["net_pnl"].idxmax()
        excl_pnl = trades.drop(index=best_idx)["net_pnl"].sum()
        total_pnl = trades["net_pnl"].sum()
        print(f"Total net PnL: {total_pnl:.2f}; excluding best trade: {excl_pnl:.2f}; "
              f"still positive: {excl_pnl > 0}")

    print("\n=== 6. Block-bootstrap 95% CI on mean trade return (net of costs) ===")
    trade_rets = (trades["weighted_return"] - trades["turnover_frac"] * ROUND_TRIP_COST).values
    mean_r, lo, hi = block_bootstrap_ci(trade_rets)
    print(f"Mean trade return: {mean_r:.5f}, 95% CI: [{lo:.5f}, {hi:.5f}]")
    ci_excludes_zero = (lo > 0) or (hi < 0)
    print(f"CI excludes zero: {ci_excludes_zero}")

    out_dir = ROOT / "results" / "amihud_illiquidity_smallcap" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"robustness-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = pd.DataFrame([
        {"check": "baseline_30bps", **m_base},
        {"check": "doubled_cost_60bps", **m_doubled},
        {"check": "delayed_1d", **m_delayed},
        {"check": "first_half_2020_2023", **m_first},
        {"check": "second_half_2023_2026", **m_second},
    ])
    summary.to_csv(run_dir / "robustness_summary.csv", index=False)

    with open(run_dir / "robustness_verdict.txt", "w") as f:
        f.write(f"doubled_cost_beats_cash={m_doubled['final_capital'] > INITIAL_CAPITAL}\n")
        f.write(f"delayed_1d_beats_cash={m_delayed['final_capital'] > INITIAL_CAPITAL}\n")
        f.write(f"first_half_beats_cash={m_first['final_capital'] > INITIAL_CAPITAL}\n")
        f.write(f"second_half_beats_cash={m_second['final_capital'] > INITIAL_CAPITAL}\n")
        f.write(f"best_trade_exclusion_still_positive={excl_pnl > 0 if not trades.empty else 'N/A'}\n")
        f.write(f"bootstrap_mean_trade_return={mean_r}\n")
        f.write(f"bootstrap_ci_lo={lo}\nbootstrap_ci_hi={hi}\n")
        f.write(f"bootstrap_ci_excludes_zero={ci_excludes_zero}\n")

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
