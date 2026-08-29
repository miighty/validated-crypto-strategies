"""EXP-2026-08-29-XSMOM-001: Cross-sectional residual momentum backtest.

Hypothesis (preregistered, from docs/next_hypotheses.md rank #4):
  Asset-specific demand may persist after removing the common crypto (BTC-beta)
  factor from an asset's trailing return. Ranking residual 7-day returns
  (raw return minus rolling-beta-implied BTC contribution) and going long the
  top tercile should outperform raw (non-residualized) momentum ranking and
  passive benchmarks after realistic costs.

Design (frozen before any result was inspected):
  - Universe: 30 real Binance spot USDT daily coins already cached in
    data/raw/*_1d.csv.gz (10 core + 20 fetched this run for breadth).
  - Rolling BTC beta: OLS slope of asset's daily log return on BTC's daily log
    return over the trailing 60 completed days (min 40 obs), shifted so beta
    at day t uses only data through t-1 (no lookahead).
  - Trailing 7-day return r_asset, r_btc computed from completed daily closes
    ending at the rebalance day's close (available at that day's close).
  - Residual momentum score = r_asset - beta_t * r_btc.
  - Rebalance every 7 days (weekly), long-only top tercile of assets with a
    valid score that week, equal-weighted, entering at NEXT day's open,
    holding until next rebalance.
  - Costs: repo standard 15bps one-way / 30bps round trip (FEE_RATE=0.001 +
    SLIPPAGE_RATE=0.0005), charged on the delta between two rebalances'
    equal-weight holdings (only turnover is costed, not full portfolio value).
  - Baselines: (1) raw-momentum top tercile (same ranking, no beta residualization),
    (2) equal-weight all-30-asset buy-and-hold, (3) BTC/ETH/SOL/XRP daily DCA
    on the same $10,000 capital schedule (lump-sum buy-and-hold, since this is
    not a DCA-style entry strategy -- reported as straight buy-and-hold for
    those four assets over the same window for reference).

Fastest rejection criterion: residual-momentum tercile does not beat BOTH the
raw-momentum tercile AND the equal-weight-30 benchmark after costs.
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
ROUND_TRIP_COST = 2 * (FEE_RATE + SLIPPAGE_RATE)  # 0.003 = 30 bps

UNIVERSE = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "POL",
    "LTC", "BCH", "XLM", "ETC", "VET", "ZEC", "DASH", "THETA", "ENJ", "ZIL",
    "BAT", "IOST", "ICX", "ONT", "NEO", "QTUM", "IOTA", "TRX", "ATOM", "ALGO",
]

BETA_WINDOW = 60
BETA_MIN_OBS = 40
MOM_WINDOW = 7
REBALANCE_DAYS = 7
INITIAL_CAPITAL = 10_000.0
START_ANALYSIS = pd.Timestamp("2020-01-01", tz="UTC")


def load_closes() -> pd.DataFrame:
    frames = {}
    for coin in UNIVERSE:
        path = PATHS.raw / f"{coin}_1d.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        frames[coin] = df["close"]
    closes = pd.concat(frames, axis=1)
    closes = closes[closes.index >= START_ANALYSIS]
    closes = closes.sort_index()
    return closes


def load_opens() -> pd.DataFrame:
    frames = {}
    for coin in UNIVERSE:
        path = PATHS.raw / f"{coin}_1d.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        frames[coin] = df["open"]
    opens = pd.concat(frames, axis=1)
    opens = opens[opens.index >= START_ANALYSIS]
    return opens.sort_index()


def compute_rolling_beta(log_returns: pd.DataFrame, btc_col: str = "BTC") -> pd.DataFrame:
    """Rolling OLS beta of each asset's daily log return on BTC's, using only
    the trailing BETA_WINDOW completed days strictly before the current day
    (shift(1) applied by the caller's alignment)."""
    btc = log_returns[btc_col]
    betas = pd.DataFrame(index=log_returns.index, columns=log_returns.columns, dtype=float)
    btc_var = btc.rolling(BETA_WINDOW, min_periods=BETA_MIN_OBS).var()
    for coin in log_returns.columns:
        cov = log_returns[coin].rolling(BETA_WINDOW, min_periods=BETA_MIN_OBS).cov(btc)
        betas[coin] = cov / btc_var
    return betas


def build_scores(closes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    log_returns = np.log(closes / closes.shift(1))
    betas_raw = compute_rolling_beta(log_returns)
    # Beta available at day t must only use data through t-1 -> shift by 1 day
    betas = betas_raw.shift(1)

    mom = closes.pct_change(MOM_WINDOW)  # trailing 7-day simple return, ends at day t (available at close of t)
    btc_mom = mom["BTC"]

    raw_mom_score = mom.copy()
    residual_score = mom.sub(betas.mul(btc_mom, axis=0))
    return raw_mom_score, residual_score


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index[::REBALANCE_DAYS]


def run_tercile_backtest(score: pd.DataFrame, opens: pd.DataFrame, closes: pd.DataFrame,
                          label: str) -> dict:
    dates = score.index
    reb_dates = rebalance_dates(dates)
    capital = INITIAL_CAPITAL
    prev_weights: dict[str, float] = {}
    equity_curve = []
    trade_log = []

    for i, reb_date in enumerate(reb_dates):
        row = score.loc[reb_date].dropna()
        # need at least 9 valid names for a meaningful tercile (>=3 per tercile)
        if len(row) < 9:
            continue
        n = len(row)
        top_n = max(1, n // 3)
        top_names = row.sort_values(ascending=False).head(top_n).index.tolist()
        new_weights = {name: 1.0 / len(top_names) for name in top_names}

        # entry at next available day's open (entry_delay = 1 day)
        pos_in_index = dates.get_indexer([reb_date])[0]
        if pos_in_index + 1 >= len(dates):
            break
        entry_date = dates[pos_in_index + 1]
        if entry_date not in opens.index:
            continue

        # determine holding period: until next rebalance's entry date (or end)
        if i + 1 < len(reb_dates):
            next_reb_pos = dates.get_indexer([reb_dates[i + 1]])[0]
            exit_pos = next_reb_pos + 1
            if exit_pos >= len(dates):
                exit_pos = len(dates) - 1
            exit_date = dates[exit_pos]
        else:
            exit_date = dates[-1]

        # turnover cost: charge round-trip cost on the fraction of capital that
        # changes name membership between prev_weights and new_weights
        turnover = 0.0
        all_names = set(prev_weights) | set(new_weights)
        for name in all_names:
            turnover += abs(new_weights.get(name, 0.0) - prev_weights.get(name, 0.0))
        turnover = min(turnover, 2.0) / 2.0  # normalize: 2.0 = full flip -> 1.0 turnover fraction
        cost = capital * turnover * ROUND_TRIP_COST

        # compute period gross return: equal-weight basket of top_names entry->exit at OPEN prices
        entry_prices = opens.loc[entry_date, top_names]
        if exit_date == entry_date:
            exit_prices = entry_prices
        else:
            exit_pos_idx = dates.get_indexer([exit_date])[0]
            exit_date_for_open = dates[exit_pos_idx]
            exit_prices = opens.loc[exit_date_for_open, top_names]
        valid = entry_prices.notna() & exit_prices.notna() & (entry_prices > 0)
        if valid.sum() == 0:
            gross_ret = 0.0
        else:
            per_asset_ret = (exit_prices[valid] / entry_prices[valid]) - 1.0
            gross_ret = per_asset_ret.mean()

        capital_before = capital
        capital = capital * (1.0 + gross_ret) - cost
        equity_curve.append({"date": exit_date, "equity": capital})
        trade_log.append({
            "rebalance_date": reb_date, "entry_date": entry_date, "exit_date": exit_date,
            "n_names": len(top_names), "names": ",".join(top_names),
            "gross_return": gross_ret, "turnover_frac": turnover, "cost": cost,
            "capital_before": capital_before, "capital_after": capital,
        })
        prev_weights = new_weights

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": label, "equity": equity_df, "trades": trades_df, "final_capital": capital}


def compute_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
    if equity_df.empty:
        return {"n_trades": 0, "final_capital": INITIAL_CAPITAL, "total_return": 0.0,
                "sharpe": float("nan"), "max_drawdown": float("nan"), "win_rate": float("nan")}
    equity = equity_df["equity"]
    period_returns = trades_df["gross_return"] - trades_df["turnover_frac"] * ROUND_TRIP_COST
    n_periods_per_year = 365.25 / REBALANCE_DAYS
    mean_r = period_returns.mean()
    std_r = period_returns.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(n_periods_per_year) if std_r > 0 else float("nan")
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min()
    win_rate = (period_returns > 0).mean()
    total_return = equity.iloc[-1] / INITIAL_CAPITAL - 1.0
    return {
        "n_trades": len(trades_df), "final_capital": equity.iloc[-1],
        "total_return": total_return, "sharpe": sharpe, "max_drawdown": max_dd,
        "win_rate": win_rate,
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


def main() -> None:
    closes = load_closes()
    opens = load_opens()
    print(f"Universe: {len(UNIVERSE)} coins, {len(closes)} daily rows, "
          f"{closes.index.min()} -> {closes.index.max()}")

    raw_mom_score, residual_score = build_scores(closes)

    result_residual = run_tercile_backtest(residual_score, opens, closes, "residual_momentum_tercile")
    result_raw = run_tercile_backtest(raw_mom_score, opens, closes, "raw_momentum_tercile")

    metrics_residual = compute_metrics(result_residual["equity"], result_residual["trades"])
    metrics_raw = compute_metrics(result_raw["equity"], result_raw["trades"])

    ew_bh = equal_weight_universe_bh(closes)
    btc_bh = buy_and_hold(closes, "BTC")
    eth_bh = buy_and_hold(closes, "ETH")
    sol_bh = buy_and_hold(closes, "SOL")
    xrp_bh = buy_and_hold(closes, "XRP")

    out_dir = ROOT / "results" / "cross_sectional_residual_momentum" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result_residual["trades"].to_csv(run_dir / "residual_trades.csv", index=False)
    result_raw["trades"].to_csv(run_dir / "raw_momentum_trades.csv", index=False)
    result_residual["equity"].to_csv(run_dir / "residual_equity.csv")
    result_raw["equity"].to_csv(run_dir / "raw_momentum_equity.csv")

    summary_rows = [
        {"strategy": "Residual momentum tercile (long top 1/3)", **metrics_residual},
        {"strategy": "Raw momentum tercile (long top 1/3, no beta-adjust)", **metrics_raw},
        {"strategy": "Equal-weight 30-asset buy-and-hold", **ew_bh, "n_trades": 1, "win_rate": float("nan")},
        {"strategy": "BTC buy-and-hold", **btc_bh, "n_trades": 1, "win_rate": float("nan")},
        {"strategy": "ETH buy-and-hold", **eth_bh, "n_trades": 1, "win_rate": float("nan")},
        {"strategy": "SOL buy-and-hold", **sol_bh, "n_trades": 1, "win_rate": float("nan")},
        {"strategy": "XRP buy-and-hold", **xrp_bh, "n_trades": 1, "win_rate": float("nan")},
    ]
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print(f"\nArtifacts written to {run_dir}")

    # Decisive check outputs
    beats_raw = metrics_residual["final_capital"] > metrics_raw["final_capital"]
    beats_ew = metrics_residual["final_capital"] > ew_bh["final_capital"]
    verdict = "CANDIDATE" if (beats_raw and beats_ew) else "REJECTED"
    print(f"\nBeats raw momentum: {beats_raw}; Beats equal-weight-30 BH: {beats_ew}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"beats_raw_momentum={beats_raw}\nbeats_equal_weight_bh={beats_ew}\nverdict={verdict}\n")


if __name__ == "__main__":
    main()
