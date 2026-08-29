"""EXP-2026-08-30-VOLPREM-001: Cross-sectional low-volatility (betting-against-
volatility) premium.

Hypothesis (preregistered, genuinely new -- not previously tested in this
repo's docs/experiment_registry.md; distinct mechanism from the already-
rejected Amihud illiquidity, funding-carry, and residual-momentum studies):
  Leverage-constrained crypto traders (spot-only investors who want more
  upside exposure, or perp traders capped by exchange margin limits) bid up
  high-realized-volatility / high-beta assets to embed extra leverage,
  analogous to the Frazzini-Pedersen "betting against beta/volatility"
  mechanism documented in equities. This should make high-vol assets
  systematically *overpriced* relative to low-vol assets, producing a return
  premium for a dollar-neutral long-low-vol / short-high-vol cross-sectional
  portfolio, net of realistic round-trip costs, on this repo's real Binance
  30-coin universe.

Design (frozen before any result was inspected):
  - Universe: identical 30-coin real Binance spot USDT daily universe already
    cached in data/raw/*_1d.csv.gz, 2020-01-01 through repo cutoff (same
    universe used by the Amihud/momentum/funding-carry studies, for direct
    comparability).
  - Realized volatility score per asset per day: rolling 21-day standard
    deviation of daily simple returns, computed through day t-1 (shift(1)
    applied) so the rebalance-day score never uses same-day data. Minimum 15
    observations required.
  - Rebalance: weekly (every 7 days), long bottom tercile (lowest realized
    vol) / short top tercile (highest realized vol) by score, equal-weighted
    within each leg, dollar-neutral (each leg at 50% of gross capital, net
    market exposure ~0). Enter at next day's open, hold to next rebalance's
    entry -- identical mechanics to the Amihud L/S engine for direct
    comparability.
  - Costs: repo-standard 30bps round-trip (10bps fee + 5bps slippage per
    side), charged on turnover fraction of gross notional that changes
    membership between rebalances (both legs).
  - Control: seeded random-ranking L/S with identical leg sizes/turnover/cost
    structure, to isolate whether the volatility ranking itself adds value.
  - Benchmarks: cash, BTC/ETH/SOL/XRP buy-and-hold, equal-weight-30
    buy-and-hold.

Fastest rejection criterion (preregistered): the low-vol L/S must beat the
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
ROUND_TRIP_COST = 2 * (FEE_RATE + SLIPPAGE_RATE)  # 0.003 = 30 bps

UNIVERSE = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK", "POL",
    "LTC", "BCH", "XLM", "ETC", "VET", "ZEC", "DASH", "THETA", "ENJ", "ZIL",
    "BAT", "IOST", "ICX", "ONT", "NEO", "QTUM", "IOTA", "TRX", "ATOM", "ALGO",
]

VOL_WINDOW = 21
VOL_MIN_OBS = 15
REBALANCE_DAYS = 7
INITIAL_CAPITAL = 10_000.0
START_ANALYSIS = pd.Timestamp("2020-01-01", tz="UTC")
RANDOM_SEED = 20260830


def load_field(field: str) -> pd.DataFrame:
    frames = {}
    for coin in UNIVERSE:
        path = PATHS.raw / f"{coin}_1d.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        frames[coin] = df[field]
    out = pd.concat(frames, axis=1)
    out = out[out.index >= START_ANALYSIS]
    return out.sort_index()


def build_vol_score(closes: pd.DataFrame) -> pd.DataFrame:
    returns = closes.pct_change()
    vol = returns.rolling(VOL_WINDOW, min_periods=VOL_MIN_OBS).std(ddof=1)
    # score available at day t must only use data through t-1 -> shift by 1 day
    return vol.shift(1)


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
        if len(row) < 9:
            continue
        n = len(row)
        leg_n = max(1, n // 3)
        ranked = row.sort_values(ascending=True)  # ascending: lowest vol first
        long_names = ranked.head(leg_n).index.tolist()   # lowest volatility
        short_names = ranked.tail(leg_n).index.tolist()  # highest volatility
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


def main() -> None:
    closes = load_field("close")
    opens = load_field("open")
    print(f"Universe: {len(UNIVERSE)} coins, {len(closes)} daily rows, "
          f"{closes.index.min()} -> {closes.index.max()}")

    score = build_vol_score(closes)

    result_strategy = run_ls_backtest(score, opens, "lowvol_highvol_ls")
    result_random = run_random_control(score.index, list(closes.columns), opens, RANDOM_SEED)

    metrics_strategy = compute_metrics(result_strategy["equity"], result_strategy["trades"])
    metrics_random = compute_metrics(result_random["equity"], result_random["trades"])

    ew_bh = equal_weight_universe_bh(closes)
    btc_bh = buy_and_hold(closes, "BTC")
    eth_bh = buy_and_hold(closes, "ETH")
    sol_bh = buy_and_hold(closes, "SOL")
    xrp_bh = buy_and_hold(closes, "XRP")

    out_dir = ROOT / "results" / "volatility_premium_cross_sectional" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result_strategy["trades"].to_csv(run_dir / "strategy_trades.csv", index=False)
    result_random["trades"].to_csv(run_dir / "random_control_trades.csv", index=False)
    result_strategy["equity"].to_csv(run_dir / "strategy_equity.csv")
    result_random["equity"].to_csv(run_dir / "random_control_equity.csv")

    summary_rows = [
        {"strategy": "Low-vol/High-vol L/S (long low-vol, short high-vol)", **metrics_strategy},
        {"strategy": "Random-ranking L/S control (same leg sizes/turnover)", **metrics_random},
        {"strategy": "Equal-weight 30-asset buy-and-hold", **ew_bh, "n_trades": 1, "win_rate": float("nan"),
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
    print(f"\nArtifacts written to {run_dir}")

    beats_random = metrics_strategy["final_capital"] > metrics_random["final_capital"]
    beats_cash = metrics_strategy["final_capital"] > INITIAL_CAPITAL
    concentration_ok = (
        not np.isfinite(metrics_strategy["top_trade_pct_of_pnl"])
        or metrics_strategy["top_trade_pct_of_pnl"] <= 0.20
    )
    verdict = "CANDIDATE" if (beats_random and beats_cash and concentration_ok) else "REJECTED"
    print(f"\nBeats random control: {beats_random}; Beats cash: {beats_cash}; "
          f"Concentration OK (<=20%): {concentration_ok}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_random_control={beats_random}\nbeats_cash={beats_cash}\n"
            f"concentration_ok={concentration_ok}\nverdict={verdict}\n"
        )


if __name__ == "__main__":
    main()
