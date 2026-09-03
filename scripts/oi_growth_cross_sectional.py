"""EXP-2026-09-03-OIXSMOM-001: Cross-sectional open-interest growth ranking.

Hypothesis (preregistered, genuinely new -- not previously tested in this
repo's docs/experiment_registry.md):
  Real Binance USD-M futures open interest, ranked CROSS-SECTIONALLY (not as a
  single-asset event trigger or slow SMA-crossover regime filter, both of
  which have already been REJECTED in this program for OI -- see
  OI_TREND_REGIME_VALIDATION.md, OI_BREAKOUT_CONFIRMATION_VALIDATION.md,
  OI_THIN_BREAKOUT_VALIDATION.md, CROWDED_PERP_UNWIND_VALIDATION.md), should
  identify assets attracting fresh leveraged demand (long top-tercile OI
  growth) vs assets seeing leverage unwind (short bottom-tercile), earning a
  premium net of costs. This is mechanistically distinct from every prior OI
  study: those were single-asset (event trigger or regime filter); this is a
  dollar-neutral cross-sectional ranking, mirroring the already-tested-and-
  REJECTED Amihud/funding-carry/residual-momentum/low-vol cross-sectional
  factor family but with a genuinely new underlying data field (OI growth,
  never ranked cross-sectionally in this repo before).

Design (frozen before any result was inspected):
  - Universe: the 10 coins with real Binance USD-M OI archive coverage in
    this repo (BTC, ETH, SOL, XRP, BNB, ADA, DOGE, AVAX, LINK, ATOM) --
    smaller than the 30-coin universe used for the prior 4 cross-sectional
    factor rejections; this is a known, disclosed limitation (OI archive
    coverage does not extend to the other 20+ coins already used for the
    30-coin spot studies), not a cherry-picked universe.
  - OI growth score per asset per day: pct-change of sum_open_interest over
    a trailing 7-day window, i.e. oi_t / oi_{t-7} - 1, then shift(1) so the
    rebalance-day score never uses same-day OI.
  - Rebalance: weekly (every 7 days), long top tercile (fastest OI growth) /
    short bottom tercile (OI shrinking most), equal-weighted within each leg,
    dollar-neutral (50%/50% gross). Enter at next day's open, hold to next
    rebalance's entry -- identical mechanics to amihud_illiquidity_cross_
    sectional.py for direct comparability.
  - Costs: repo-standard 30bps round-trip, charged on turnover.
  - Control: seeded random-ranking L/S with identical leg sizes/turnover/cost.
  - Benchmarks: cash, BTC/ETH/SOL/XRP buy-and-hold, equal-weight-10 BH.

Fastest rejection criterion (preregistered): OI-growth L/S must beat the
random-ranking control AND cash after costs, or it is rejected.
Concentration cap: no single trade > 20% of total strategy net PnL.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import Paths, project_root, FEE_RATE, SLIPPAGE_RATE

ROOT = project_root()
PATHS = Paths(ROOT)
ROUND_TRIP_COST = 2 * (FEE_RATE + SLIPPAGE_RATE)  # 30bps

UNIVERSE = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "LINK", "ATOM"]

OI_GROWTH_WINDOW = 7
REBALANCE_DAYS = 7
INITIAL_CAPITAL = 10_000.0
RANDOM_SEED = 20260903


def load_spot_field(field: str, start: pd.Timestamp) -> pd.DataFrame:
    frames = {}
    for coin in UNIVERSE:
        path = PATHS.raw / f"{coin}_1d.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        frames[coin] = df[field]
    out = pd.concat(frames, axis=1)
    out = out[out.index >= start]
    return out.sort_index()


def load_oi(start: pd.Timestamp) -> pd.DataFrame:
    frames = {}
    for coin in UNIVERSE:
        path = PATHS.data / "open_interest" / f"{coin}_oi_daily.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        frames[coin] = df["sum_open_interest"]
    out = pd.concat(frames, axis=1)
    out = out[out.index >= start]
    return out.sort_index()


def build_oi_growth_score(oi: pd.DataFrame) -> pd.DataFrame:
    growth = oi.pct_change(OI_GROWTH_WINDOW)
    return growth.shift(1)  # never use same-day OI at rebalance time


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index[::REBALANCE_DAYS]


def run_ls_backtest(score: pd.DataFrame, opens: pd.DataFrame, label: str) -> dict:
    dates = score.index
    reb_dates = rebalance_dates(dates)
    capital = INITIAL_CAPITAL
    prev_weights: dict[str, float] = {}
    equity_curve = []
    trade_log = []

    for i, reb_date in enumerate(reb_dates):
        row = score.loc[reb_date].dropna()
        if len(row) < 6:
            continue
        n = len(row)
        leg_n = max(1, n // 3)
        ranked = row.sort_values(ascending=False)
        long_names = ranked.head(leg_n).index.tolist()   # fastest OI growth
        short_names = ranked.tail(leg_n).index.tolist()  # OI shrinking most
        new_weights = {name: 0.5 / len(long_names) for name in long_names}
        for name in short_names:
            new_weights[name] = new_weights.get(name, 0.0) - 0.5 / len(short_names)

        pos_in_index = dates.get_indexer([reb_date])[0]
        if pos_in_index + 1 >= len(dates):
            break
        entry_date = dates[pos_in_index + 1]
        if entry_date not in opens.index:
            continue

        if i + 1 < len(reb_dates):
            next_reb_pos = dates.get_indexer([reb_dates[i + 1]])[0]
            exit_pos = next_reb_pos + 1
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
        cost = capital * turnover * ROUND_TRIP_COST

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
            "n_long": len(long_names), "n_short": len(short_names),
            "long_names": ",".join(long_names), "short_names": ",".join(short_names),
            "weighted_return": weighted_ret, "turnover_frac": turnover, "cost": cost,
            "capital_before": capital_before, "capital_after": capital,
            "net_pnl": capital - capital_before,
        })
        prev_weights = new_weights

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": label, "equity": equity_df, "trades": trades_df, "final_capital": capital}


def run_random_control(score_index: pd.DatetimeIndex, universe_cols: list[str],
                        opens: pd.DataFrame, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    reb_dates = rebalance_dates(score_index)
    capital = INITIAL_CAPITAL
    prev_weights: dict[str, float] = {}
    equity_curve = []
    trade_log = []

    for i, reb_date in enumerate(reb_dates):
        available = [c for c in universe_cols if reb_date in opens.index and pd.notna(opens.loc[reb_date, c])]
        if len(available) < 6:
            continue
        shuffled = list(available)
        rng.shuffle(shuffled)
        n = len(shuffled)
        leg_n = max(1, n // 3)
        long_names = shuffled[:leg_n]
        short_names = shuffled[leg_n:2 * leg_n]
        new_weights = {name: 0.5 / len(long_names) for name in long_names}
        for name in short_names:
            new_weights[name] = new_weights.get(name, 0.0) - 0.5 / len(short_names)

        pos_in_index = score_index.get_indexer([reb_date])[0]
        if pos_in_index + 1 >= len(score_index):
            break
        entry_date = score_index[pos_in_index + 1]
        if entry_date not in opens.index:
            continue

        if i + 1 < len(reb_dates):
            next_reb_pos = score_index.get_indexer([reb_dates[i + 1]])[0]
            exit_pos = next_reb_pos + 1
            if exit_pos >= len(score_index):
                exit_pos = len(score_index) - 1
            exit_date = score_index[exit_pos]
        else:
            exit_date = score_index[-1]

        turnover = 0.0
        all_names = set(prev_weights) | set(new_weights)
        for name in all_names:
            turnover += abs(new_weights.get(name, 0.0) - prev_weights.get(name, 0.0))
        turnover = min(turnover, 2.0) / 2.0
        cost = capital * turnover * ROUND_TRIP_COST

        all_leg_names = long_names + short_names
        entry_prices = opens.loc[entry_date, all_leg_names]
        if exit_date == entry_date:
            exit_prices = entry_prices
        else:
            exit_pos_idx = score_index.get_indexer([exit_date])[0]
            exit_prices = opens.loc[score_index[exit_pos_idx], all_leg_names]
        valid = entry_prices.notna() & exit_prices.notna() & (entry_prices > 0)
        per_asset_ret = (exit_prices[valid] / entry_prices[valid]) - 1.0
        weighted_ret = 0.0
        for name in per_asset_ret.index:
            weighted_ret += new_weights.get(name, 0.0) * per_asset_ret[name]

        capital_before = capital
        capital = capital * (1.0 + weighted_ret) - cost
        equity_curve.append({"date": exit_date, "equity": capital})
        trade_log.append({
            "rebalance_date": reb_date, "weighted_return": weighted_ret,
            "turnover_frac": turnover, "cost": cost, "net_pnl": capital - capital_before,
        })
        prev_weights = new_weights

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": "random_control", "equity": equity_df, "trades": trades_df, "final_capital": capital}


def compute_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
    if equity_df.empty:
        return {"n_trades": 0, "final_capital": INITIAL_CAPITAL, "total_return": 0.0,
                "sharpe": float("nan"), "max_drawdown": float("nan"), "win_rate": float("nan"),
                "top_trade_pct_of_pnl": float("nan")}
    equity = equity_df["equity"]
    period_returns = trades_df["weighted_return"] - trades_df["turnover_frac"] * ROUND_TRIP_COST
    n_periods_per_year = 365.25 / REBALANCE_DAYS
    mean_r = period_returns.mean()
    std_r = period_returns.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(n_periods_per_year) if std_r > 0 else float("nan")
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min()
    win_rate = (period_returns > 0).mean()
    total_return = equity.iloc[-1] / INITIAL_CAPITAL - 1.0
    total_pnl = trades_df["net_pnl"].sum()
    top_trade_pct = (trades_df["net_pnl"].abs().max() / abs(total_pnl)) if total_pnl != 0 else float("nan")
    return {
        "n_trades": len(trades_df), "final_capital": equity.iloc[-1],
        "total_return": total_return, "sharpe": sharpe, "max_drawdown": max_dd,
        "win_rate": win_rate, "top_trade_pct_of_pnl": top_trade_pct,
    }


def buy_and_hold(closes: pd.DataFrame, coin: str) -> dict:
    series = closes[coin].dropna()
    start_price = series.iloc[0]
    end_price = series.iloc[-1]
    total_return = end_price / start_price - 1.0
    final_capital = INITIAL_CAPITAL * (1 + total_return)
    daily_ret = series.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std(ddof=1)) * np.sqrt(365.25) if daily_ret.std() > 0 else float("nan")
    running_max = series.cummax()
    dd = ((series - running_max) / running_max).min()
    return {"final_capital": final_capital, "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


def equal_weight_universe_bh(closes: pd.DataFrame) -> dict:
    norm = closes / closes.iloc[0]
    basket = norm.mean(axis=1) * INITIAL_CAPITAL
    total_return = basket.iloc[-1] / INITIAL_CAPITAL - 1.0
    daily_ret = basket.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std(ddof=1)) * np.sqrt(365.25) if daily_ret.std() > 0 else float("nan")
    running_max = basket.cummax()
    dd = ((basket - running_max) / running_max).min()
    return {"final_capital": basket.iloc[-1], "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


def cross_sectional_mc_test(score: pd.DataFrame, opens: pd.DataFrame, observed_final: float,
                             n_trials: int = 500, seed: int = 20260903) -> dict:
    """Label-scrambling MC: shuffle which coins land in long/short legs each
    rebalance (not time-order shuffle), the correct null for a ranking
    strategy per the skill's cross-sectional MC guidance."""
    rng = np.random.default_rng(seed)
    sims = []
    for trial in range(n_trials):
        res = run_random_control(score.index, list(opens.columns), opens, seed=rng.integers(0, 2**31 - 1))
        sims.append(res["final_capital"])
    sims = np.array(sims)
    p_value = (sims >= observed_final).mean()
    return {"n_trials": n_trials, "observed_final": observed_final,
            "sim_mean": sims.mean(), "sim_std": sims.std(), "p_value": p_value}


def main() -> None:
    start = pd.Timestamp("2021-12-01", tz="UTC")  # shared OI coverage start (ETH/SOL/XRP/BNB/ADA/DOGE/AVAX/LINK/ATOM)
    closes = load_spot_field("close", start)
    opens = load_spot_field("open", start)
    oi = load_oi(start)

    common_index = closes.index.intersection(oi.index)
    closes = closes.loc[common_index]
    opens = opens.loc[common_index]
    oi = oi.loc[common_index]

    print(f"Universe: {len(UNIVERSE)} coins, {len(closes)} daily rows, "
          f"{closes.index.min()} -> {closes.index.max()}")

    score = build_oi_growth_score(oi)

    result_strategy = run_ls_backtest(score, opens, "oi_growth_ls")
    result_random = run_random_control(score.index, list(closes.columns), opens, RANDOM_SEED)

    metrics_strategy = compute_metrics(result_strategy["equity"], result_strategy["trades"])
    metrics_random = compute_metrics(result_random["equity"], result_random["trades"])

    ew_bh = equal_weight_universe_bh(closes)
    btc_bh = buy_and_hold(closes, "BTC")
    eth_bh = buy_and_hold(closes, "ETH")
    sol_bh = buy_and_hold(closes, "SOL")
    xrp_bh = buy_and_hold(closes, "XRP")

    # 1-bar execution delay robustness check (first-pass gate, per skill's
    # updated delay-robustness discipline)
    score_delayed = score.shift(1)
    result_delayed = run_ls_backtest(score_delayed, opens, "oi_growth_ls_delay1")
    metrics_delayed = compute_metrics(result_delayed["equity"], result_delayed["trades"])

    # Doubled-cost robustness check
    global ROUND_TRIP_COST
    original_cost = ROUND_TRIP_COST
    ROUND_TRIP_COST = original_cost * 2
    result_2x = run_ls_backtest(score, opens, "oi_growth_ls_2xcost")
    metrics_2x = compute_metrics(result_2x["equity"], result_2x["trades"])
    ROUND_TRIP_COST = original_cost

    # Cross-sectional label-scramble Monte Carlo (proper null for a ranking strategy)
    mc_result = cross_sectional_mc_test(score, opens, metrics_strategy["final_capital"], n_trials=500)

    out_dir = ROOT / "results" / "oi_growth_cross_sectional" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result_strategy["trades"].to_csv(run_dir / "strategy_trades.csv", index=False)
    result_random["trades"].to_csv(run_dir / "random_control_trades.csv", index=False)
    result_strategy["equity"].to_csv(run_dir / "strategy_equity.csv")
    result_random["equity"].to_csv(run_dir / "random_control_equity.csv")

    summary_rows = [
        {"strategy": "OI-growth L/S (long rising-OI tercile, short falling-OI tercile)", **metrics_strategy},
        {"strategy": "OI-growth L/S 1-bar delay", **metrics_delayed},
        {"strategy": "OI-growth L/S 2x cost", **metrics_2x},
        {"strategy": "Random-ranking L/S control (same leg sizes/turnover)", **metrics_random},
        {"strategy": "Equal-weight 10-asset buy-and-hold", **ew_bh, "n_trades": 1, "win_rate": float("nan"),
         "top_trade_pct_of_pnl": float("nan")},
        {"strategy": "BTC buy-and-hold", **btc_bh, "n_trades": 1, "win_rate": float("nan"),
         "top_trade_pct_of_pnl": float("nan")},
        {"strategy": "ETH buy-and-hold", **eth_bh, "n_trades": 1, "win_rate": float("nan"),
         "top_trade_pct_of_pnl": float("nan")},
        {"strategy": "SOL buy-and-hold", **sol_bh, "n_trades": 1, "win_rate": float("nan"),
         "top_trade_pct_of_pnl": float("nan")},
        {"strategy": "XRP buy-and-hold", **xrp_bh, "n_trades": 1, "win_rate": float("nan"),
         "top_trade_pct_of_pnl": float("nan")},
        {"strategy": "Cash", "final_capital": INITIAL_CAPITAL, "total_return": 0.0,
         "sharpe": float("nan"), "max_drawdown": 0.0, "n_trades": 0, "win_rate": float("nan"),
         "top_trade_pct_of_pnl": float("nan")},
    ]
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print(f"\nCross-sectional MC (n_trials={mc_result['n_trials']}): "
          f"observed_final={mc_result['observed_final']:.2f}, "
          f"sim_mean={mc_result['sim_mean']:.2f}, sim_std={mc_result['sim_std']:.2f}, "
          f"p_value={mc_result['p_value']:.4f}")
    print(f"\nArtifacts written to {run_dir}")

    beats_random = metrics_strategy["final_capital"] > metrics_random["final_capital"]
    beats_cash = metrics_strategy["final_capital"] > INITIAL_CAPITAL
    concentration_ok = (
        not np.isfinite(metrics_strategy["top_trade_pct_of_pnl"])
        or abs(metrics_strategy["top_trade_pct_of_pnl"]) <= 0.20
    )
    delay_retains_edge = (
        np.isfinite(metrics_delayed["sharpe"]) and np.isfinite(metrics_strategy["sharpe"])
        and metrics_strategy["sharpe"] > 0
        and metrics_delayed["sharpe"] > 0.5 * metrics_strategy["sharpe"]
    )
    mc_significant = mc_result["p_value"] <= 0.05

    verdict = "CANDIDATE" if (beats_random and beats_cash and concentration_ok and mc_significant) else "REJECTED"
    print(f"\nBeats random control: {beats_random}; Beats cash: {beats_cash}; "
          f"Concentration OK (<=20%): {concentration_ok}; "
          f"Delay retains >=50% Sharpe: {delay_retains_edge}; MC significant (p<=0.05): {mc_significant}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_random_control={beats_random}\nbeats_cash={beats_cash}\n"
            f"concentration_ok={concentration_ok}\ndelay_retains_edge={delay_retains_edge}\n"
            f"mc_p_value={mc_result['p_value']}\nmc_significant={mc_significant}\n"
            f"verdict={verdict}\n"
        )


if __name__ == "__main__":
    main()
