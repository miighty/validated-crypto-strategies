"""Cross-exchange replication of EXP-2026-08-30-AMIHUD-SMALLCAP-001 on Bybit
spot daily OHLCV (independently-sourced data), per the skill's near-miss
follow-up discipline: does the small/mid-cap Amihud illiquidity premium
survive on a second venue?

Universe: the 42/54 coins from the original Binance small/mid-cap universe
that are actually listed on Bybit spot USDT markets (12 missing: CFX, CVX,
DCR, GLM, GNO, IOTA, NEO, PROM, RAY, SFP, SYRUP, XEC -- not silently padded
back with substitute tickers).

Identical mechanism/parameters to the original study:
  - Illiquidity ratio: mean(|daily return| / dollar_volume) over rolling
    14-day window (min 10 obs), shifted 1 day (no lookahead).
  - Rebalance every 7 days, long top tercile (illiquid) / short bottom
    tercile (liquid), equal-weighted, 50/50 dollar-neutral gross split.
  - 30bps round-trip costs on turnover.

Runs baseline + doubled-cost + 1-day-delay + walk-forward split + best-trade
exclusion + block-bootstrap + cross-sectional label-scramble Monte Carlo
(n_trials=500) + Deflated Sharpe (using the program's current true search
size) in one pass.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crypto_regime_backtest.config import Paths, project_root, FEE_RATE, SLIPPAGE_RATE

ROOT = project_root()
PATHS = Paths(ROOT)
BYBIT_DIR = ROOT / "data" / "bybit_raw"
ROUND_TRIP_COST = 2 * (FEE_RATE + SLIPPAGE_RATE)  # 30bps

ILLIQ_WINDOW = 14
ILLIQ_MIN_OBS = 10
REBALANCE_DAYS = 7
INITIAL_CAPITAL = 10_000.0
START_ANALYSIS = pd.Timestamp("2020-01-01", tz="UTC")
RANDOM_SEED = 20260830
N_STRATEGY_VARIANTS_AT_RUN_TIME = 90  # bumped from 84 (prior program search count) + this study


def discover_universe() -> list[str]:
    return sorted(p.name.replace("_1d.csv.gz", "") for p in BYBIT_DIR.glob("*_1d.csv.gz"))


def load_field(universe: list[str], field: str) -> pd.DataFrame:
    frames = {}
    for coin in universe:
        path = BYBIT_DIR / f"{coin}_1d.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        frames[coin] = df[field]
    out = pd.concat(frames, axis=1)
    out = out[out.index >= START_ANALYSIS]
    return out.sort_index()


def build_illiquidity_score(closes: pd.DataFrame, volumes: pd.DataFrame) -> pd.DataFrame:
    returns = closes.pct_change()
    dollar_volume = closes * volumes
    ratio = returns.abs() / dollar_volume.replace(0, np.nan)
    illiq = ratio.rolling(ILLIQ_WINDOW, min_periods=ILLIQ_MIN_OBS).mean()
    return illiq.shift(1)


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index[::REBALANCE_DAYS]


def _leg_split(row: pd.Series) -> tuple[list[str], list[str]]:
    n = len(row)
    leg_n = max(1, n // 3)
    ranked = row.sort_values(ascending=False)
    return ranked.head(leg_n).index.tolist(), ranked.tail(leg_n).index.tolist()


def run_ls_backtest(score: pd.DataFrame, opens: pd.DataFrame, cost_rate: float,
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
    equity_curve, trade_log = [], []

    for i, reb_date in enumerate(reb_dates):
        row = score.loc[reb_date].dropna()
        if len(row) < 9:
            continue
        long_names, short_names = _leg_split(row)
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
        weighted_ret = sum(new_weights.get(n, 0.0) * per_asset_ret[n] for n in per_asset_ret.index)

        capital_before = capital
        capital = capital * (1.0 + weighted_ret) - cost
        equity_curve.append({"date": exit_date, "equity": capital})
        trade_log.append({
            "rebalance_date": reb_date, "entry_date": entry_date, "exit_date": exit_date,
            "n_long": len(long_names), "n_short": len(short_names),
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
    equity_curve, trade_log = [], []

    for i, reb_date in enumerate(reb_dates):
        available = [c for c in universe_cols if reb_date in opens.index and pd.notna(opens.loc[reb_date, c])]
        if len(available) < 9:
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
        weighted_ret = sum(new_weights.get(n, 0.0) * per_asset_ret[n] for n in per_asset_ret.index)

        capital_before = capital
        capital = capital * (1.0 + weighted_ret) - cost
        equity_curve.append({"date": exit_date, "equity": capital})
        trade_log.append({"rebalance_date": reb_date, "weighted_return": weighted_ret,
                           "turnover_frac": turnover, "cost": cost, "net_pnl": capital - capital_before})
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
    return {"n_trades": len(trades_df), "final_capital": equity.iloc[-1], "total_return": total_return,
            "sharpe": sharpe, "max_drawdown": max_dd, "win_rate": win_rate,
            "top_trade_pct_of_pnl": top_trade_pct}


def buy_and_hold(closes: pd.DataFrame, coin: str) -> dict:
    series = closes[coin].dropna()
    start_price, end_price = series.iloc[0], series.iloc[-1]
    total_return = end_price / start_price - 1.0
    final_capital = INITIAL_CAPITAL * (1 + total_return)
    daily_ret = series.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std(ddof=1)) * np.sqrt(365.25) if daily_ret.std() > 0 else float("nan")
    running_max = series.cummax()
    dd = ((series - running_max) / running_max).min()
    return {"final_capital": final_capital, "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


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


def norm_ppf(p: float) -> float:
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1 - p_low
    if p <= 0:
        return -np.inf
    if p >= 1:
        return np.inf
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def deflated_sharpe_ratio(trade_returns: np.ndarray, bars_per_year: float, n_trials: int) -> dict:
    n_obs = len(trade_returns)
    mean_r, std_r = trade_returns.mean(), trade_returns.std(ddof=1)
    sr_per_bar = mean_r / std_r
    sr_annualized = sr_per_bar * np.sqrt(bars_per_year)
    skew = np.mean(((trade_returns - mean_r) / std_r) ** 3)
    kurt = np.mean(((trade_returns - mean_r) / std_r) ** 4)
    se_per_bar = np.sqrt((1 + 0.5 * sr_per_bar**2 - skew * sr_per_bar + (kurt - 3) / 4 * sr_per_bar**2) / n_obs)
    if n_trials > 1:
        euler_gamma = 0.5772156649
        expected_max_sr_per_bar = se_per_bar * (
            (1 - euler_gamma) * norm_ppf(1 - 1.0 / n_trials) + euler_gamma * norm_ppf(1 - 1.0 / (n_trials * math.e))
        )
    else:
        expected_max_sr_per_bar = 0.0
    dsr_stat = (sr_per_bar - expected_max_sr_per_bar) / se_per_bar
    p_value = 1 - norm_cdf(dsr_stat)
    return {"sr_annualized": float(sr_annualized), "sr_per_bar": float(sr_per_bar),
            "se_per_bar": float(se_per_bar), "skew": float(skew), "kurtosis": float(kurt),
            "n_obs": int(n_obs), "n_trials": int(n_trials),
            "expected_max_sr_per_bar": float(expected_max_sr_per_bar),
            "dsr_stat": float(dsr_stat), "dsr_p_value": float(p_value),
            "passes_at_0.05": bool(p_value < 0.05)}


def main() -> None:
    universe = discover_universe()
    print(f"Bybit universe ({len(universe)} coins): {universe}")
    if len(universe) < 15:
        print("ERROR: universe too small. Aborting.")
        sys.exit(1)

    closes = load_field(universe, "close")
    opens = load_field(universe, "open")
    volumes = load_field(universe, "volume")
    print(f"{len(closes)} daily rows, {closes.index.min()} -> {closes.index.max()}")

    score = build_illiquidity_score(closes, volumes)

    print("\n=== 1. Baseline (30bps, no delay) ===")
    base = run_ls_backtest(score, opens, ROUND_TRIP_COST, 0, "baseline")
    m_base = compute_metrics(base["equity"], base["trades"])
    print(m_base)

    random_ctrl = run_random_control(score.index, list(closes.columns), opens, RANDOM_SEED)
    m_random = compute_metrics(random_ctrl["equity"], random_ctrl["trades"])
    print("Random control:", m_random)

    print("\n=== 2. Doubled cost (60bps) ===")
    doubled = run_ls_backtest(score, opens, 2 * ROUND_TRIP_COST, 0, "doubled_cost")
    m_doubled = compute_metrics(doubled["equity"], doubled["trades"])
    print(m_doubled)

    print("\n=== 3. 1-day execution delay ===")
    delayed = run_ls_backtest(score, opens, ROUND_TRIP_COST, 1, "delayed_1d")
    m_delayed = compute_metrics(delayed["equity"], delayed["trades"])
    print(m_delayed)

    print("\n=== 4. Walk-forward split ===")
    mid_point = score.index[len(score.index) // 2]
    first_half = run_ls_backtest(score, opens, ROUND_TRIP_COST, 0, "first_half", restrict_end=mid_point)
    second_half = run_ls_backtest(score, opens, ROUND_TRIP_COST, 0, "second_half", restrict_start=mid_point)
    m_first = compute_metrics(first_half["equity"], first_half["trades"])
    m_second = compute_metrics(second_half["equity"], second_half["trades"])
    print(f"First half (start -> {mid_point.date()}):", m_first)
    print(f"Second half ({mid_point.date()} -> end):", m_second)

    print("\n=== 5. Best-trade exclusion ===")
    trades = base["trades"].copy()
    excl_pnl = float("nan")
    if not trades.empty:
        best_idx = trades["net_pnl"].idxmax()
        excl_pnl = trades.drop(index=best_idx)["net_pnl"].sum()
        total_pnl = trades["net_pnl"].sum()
        print(f"Total net PnL: {total_pnl:.2f}; excluding best trade: {excl_pnl:.2f}")

    print("\n=== 6. Block-bootstrap 95% CI ===")
    trade_rets = (trades["weighted_return"] - trades["turnover_frac"] * ROUND_TRIP_COST).values
    mean_r, lo, hi = block_bootstrap_ci(trade_rets)
    print(f"Mean trade return: {mean_r:.5f}, 95% CI: [{lo:.5f}, {hi:.5f}]")

    print("\n=== 7. Cross-sectional label-scramble Monte Carlo (n_trials=500) ===")
    n_trials = 500
    sim_finals, sim_sharpes = [], []
    for trial in range(n_trials):
        seed = 90000 + trial
        r = run_random_control(score.index, list(closes.columns), opens, seed)
        m = compute_metrics(r["equity"], r["trades"])
        sim_finals.append(m["final_capital"])
        sim_sharpes.append(m["sharpe"])
    sim_finals = np.array(sim_finals)
    sim_sharpes = np.array([s for s in sim_sharpes if np.isfinite(s)])
    p_value_final = float((sim_finals >= m_base["final_capital"]).mean())
    p_value_sharpe = float((sim_sharpes >= m_base["sharpe"]).mean()) if len(sim_sharpes) else float("nan")
    print(f"p-value (final capital): {p_value_final:.4f}; p-value (Sharpe): {p_value_sharpe:.4f}")

    print("\n=== 8. Deflated Sharpe Ratio ===")
    bars_per_year = 365.25 / REBALANCE_DAYS
    dsr = deflated_sharpe_ratio(trade_rets, bars_per_year, N_STRATEGY_VARIANTS_AT_RUN_TIME)
    for k, v in dsr.items():
        print(f"  {k}: {v}")

    # Benchmarks: standard repo core universe from existing Binance cache (data/raw),
    # benchmarks don't need to be Bybit-sourced -- this is the standard BTC/ETH/SOL/XRP
    # buy-and-hold comparison used across this repo's studies.
    core_bh = {}
    for c in ["BTC", "ETH", "SOL", "XRP"]:
        p = PATHS.raw / f"{c}_1d.csv.gz"
        if p.exists():
            df = pd.read_csv(p, parse_dates=["timestamp"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp").sort_index()
            df = df[df.index >= START_ANALYSIS]
            core_bh[c] = buy_and_hold(df.rename(columns={"close": c})[[c]], c)

    out_dir = ROOT / "results" / "amihud_illiquidity_smallcap" / "runs"
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"bybit-crosscheck-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    base["trades"].to_csv(run_dir / "strategy_trades.csv", index=False)
    with open(run_dir / "universe.txt", "w") as f:
        f.write("\n".join(universe))

    summary = pd.DataFrame([
        {"check": "baseline_30bps", **m_base},
        {"check": "random_control", **m_random},
        {"check": "doubled_cost_60bps", **m_doubled},
        {"check": "delayed_1d", **m_delayed},
        {"check": "first_half", **m_first},
        {"check": "second_half", **m_second},
    ])
    summary.to_csv(run_dir / "robustness_summary.csv", index=False)

    beats_random = m_base["final_capital"] > m_random["final_capital"]
    beats_cash = m_base["final_capital"] > INITIAL_CAPITAL
    concentration_ok = not np.isfinite(m_base["top_trade_pct_of_pnl"]) or m_base["top_trade_pct_of_pnl"] <= 0.20

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"universe_size={len(universe)}\n")
        f.write(f"beats_random_control={beats_random}\nbeats_cash={beats_cash}\n")
        f.write(f"concentration_ok={concentration_ok}\n")
        f.write(f"mc_p_value_final={p_value_final}\nmc_p_value_sharpe={p_value_sharpe}\n")
        f.write(f"dsr_p_value={dsr['dsr_p_value']}\ndsr_passes={dsr['passes_at_0.05']}\n")
        f.write(f"top_trade_pct_of_pnl={m_base['top_trade_pct_of_pnl']}\n")
        f.write(f"sharpe_baseline={m_base['sharpe']}\nsharpe_delayed_1d={m_delayed['sharpe']}\n")
        f.write(f"sharpe_doubled_cost={m_doubled['sharpe']}\n")
        f.write(f"sharpe_first_half={m_first['sharpe']}\nsharpe_second_half={m_second['sharpe']}\n")
        for c, bh in core_bh.items():
            f.write(f"benchmark_{c}_total_return={bh['total_return']}\n")

    print(f"\nArtifacts written to {run_dir}")
    print(f"\nVerdict inputs: beats_random={beats_random}, beats_cash={beats_cash}, "
          f"concentration_ok={concentration_ok}, mc_p={p_value_final:.4f}, dsr_p={dsr['dsr_p_value']:.4f}")


if __name__ == "__main__":
    main()
