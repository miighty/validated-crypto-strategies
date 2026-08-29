"""EXP-2026-08-29-FUNDCARRY-001: Cross-sectional funding-rate carry (market-neutral).

Hypothesis (preregistered, NEW mechanism -- not tested in prior funding studies,
which only tested single-asset LONG-SPOT persistence timing on extreme funding
prints). This test is a dollar-neutral cross-sectional carry trade: go long the
tercile of assets with the most NEGATIVE funding (shorts pay longs -> favorable
to be long) and short the tercile with the most POSITIVE funding (longs pay
shorts -> favorable to be short), rebalanced every real Binance funding
interval (8h). This isolates the carry (funding) return from directional beta,
which is the standard "funding rate carry" trade structure used by real perp
desks -- distinct from the already-REJECTED single-asset directional funding
persistence studies (FUNDING_POSITIVE_PANEL_VALIDATION.md,
FUNDING_NEGATIVE_PANEL_VALIDATION.md).

Design (frozen before any result was inspected):
  - Universe: 10 coins with real Binance USD-M funding history already cached
    in data/funding/*.csv.gz: BTC, ETH, SOL, XRP, BNB, ADA, DOGE, AVAX, LINK, POL.
  - Funding rate is realized/known the instant it prints (every 8h, UTC 00/08/16)
    -- using it to rank at that same timestamp is NOT lookahead, since the print
    itself carries no forward information, it is a already-settled cash flow.
  - Price return for the holding period is computed on real Binance SPOT hourly
    closes (mark_price is >50% missing in the cached data) as a proxy for perp
    price action -- this is standard practice since perp/spot basis for majors
    is small; funding itself already captures the perp-specific carry.
  - At each funding timestamp with >=6 coins having a valid funding print,
    rank all valid assets by funding_rate ascending.
  - Long bottom tercile (most negative funding), short top tercial (most
    positive funding), equal-weighted within each leg, legs equal in gross
    dollar size (dollar-neutral, net market exposure ~0).
  - Holding period = 1 funding interval (8h). Position return per interval =
    0.5 * (avg long-leg price return) - 0.5 * (avg short-leg price return)
    + funding carry captured: longs RECEIVE the negative funding rate they
    were long (shorts pay them), shorts RECEIVE the positive funding rate on
    what they are short (longs pay them) -- i.e. carry_pnl = 0.5*mean(-funding_long_leg)
    + 0.5*mean(funding_short_leg), which is strictly the real funding cash flow
    swapped at each 8h settlement, applied to notional at that leg's weight.
  - Rebalance every interval; cost = repo-standard round-trip 30bps
    (FEE_RATE=0.001 + SLIPPAGE_RATE=0.0005, doubled) charged on the fraction of
    gross notional that changes membership between rebalances (both legs).
  - Benchmarks: cash (0%), BTC/ETH/SOL/XRP buy-and-hold, equal-weight-10
    buy-and-hold, and a seeded-random long/short matched-turnover control that
    reshuffles which assets are long/short each interval (same leg sizes, same
    turnover, same cost model) to test whether the FUNDING-BASED ranking adds
    value over a structurally identical but randomly-ranked L/S carry sleeve.

Fastest rejection criterion: funding-carry sleeve does not beat BOTH (a) the
random-ranking L/S control on Sharpe/net-return AND (b) cash, after costs.
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

UNIVERSE = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "LINK", "POL"]
INITIAL_CAPITAL = 10_000.0
START_ANALYSIS = pd.Timestamp("2021-01-01", tz="UTC")  # after all 10 coins have funding history
SEED = 20260829


def load_funding() -> dict[str, pd.Series]:
    out = {}
    for coin in UNIVERSE:
        path = ROOT / "data" / "funding" / f"{coin}_funding.csv.gz"
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="ISO8601").dt.floor("h")
        df = df.drop_duplicates(subset="timestamp").set_index("timestamp").sort_index()
        out[coin] = df["funding_rate"]
    return out


def load_hourly_close() -> dict[str, pd.Series]:
    out = {}
    for coin in UNIVERSE:
        path = PATHS.raw / f"{coin}_1h.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        out[coin] = df["close"]
    return out


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    funding_map = load_funding()
    close_map = load_hourly_close()
    funding_df = pd.concat(funding_map, axis=1)
    funding_df = funding_df[funding_df.index >= START_ANALYSIS]
    funding_df = funding_df.sort_index()
    close_df = pd.concat(close_map, axis=1)
    close_df = close_df.sort_index()
    return funding_df, close_df


def price_return(close_df: pd.DataFrame, coin: str, t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    try:
        p0 = close_df[coin].asof(t0)
        p1 = close_df[coin].asof(t1)
    except KeyError:
        return np.nan
    if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        return np.nan
    return p1 / p0 - 1.0


def run_carry_backtest(funding_df: pd.DataFrame, close_df: pd.DataFrame, randomize: bool,
                        seed: int, label: str, stride: int = 1) -> dict:
    rng = np.random.default_rng(seed)
    timestamps = funding_df.index[::stride]
    capital = INITIAL_CAPITAL
    prev_long: set[str] = set()
    prev_short: set[str] = set()
    equity_curve = []
    trade_log = []

    for i, ts in enumerate(timestamps):
        row = funding_df.loc[ts].dropna()
        if len(row) < 6:
            continue
        n = len(row)
        top_n = max(1, n // 3)
        sorted_row = row.sort_values(ascending=True)  # ascending: most negative first
        if not randomize:
            long_names = sorted_row.head(top_n).index.tolist()  # most negative funding
            short_names = sorted_row.tail(top_n).index.tolist()  # most positive funding
        else:
            shuffled = list(row.index)
            rng.shuffle(shuffled)
            long_names = shuffled[:top_n]
            short_names = shuffled[top_n:2 * top_n] if len(shuffled) >= 2 * top_n else shuffled[top_n:]
        if not short_names:
            continue

        if i + 1 >= len(timestamps):
            break
        t1 = timestamps[i + 1]

        # turnover cost: fraction of gross notional (each leg = 0.5 of gross) that changes membership
        new_long, new_short = set(long_names), set(short_names)
        long_turnover = len(new_long.symmetric_difference(prev_long)) / (2 * max(len(new_long), 1))
        short_turnover = len(new_short.symmetric_difference(prev_short)) / (2 * max(len(new_short), 1))
        turnover_frac = 0.5 * long_turnover + 0.5 * short_turnover
        cost = capital * turnover_frac * ROUND_TRIP_COST

        # price return per leg (equal-weighted)
        long_rets = [price_return(close_df, c, ts, t1) for c in long_names]
        short_rets = [price_return(close_df, c, ts, t1) for c in short_names]
        long_rets = [r for r in long_rets if not pd.isna(r)]
        short_rets = [r for r in short_rets if not pd.isna(r)]
        if not long_rets or not short_rets:
            continue
        price_pnl = 0.5 * np.mean(long_rets) - 0.5 * np.mean(short_rets)

        # funding carry: accumulate real funding cash flow over every settlement
        # actually held during [ts, t1) -- receive -funding on long leg, +funding on short leg
        held_prints = funding_df.loc[ts:t1].iloc[:-1]  # exclude t1 itself (that belongs to next period)
        if held_prints.empty:
            held_prints = funding_df.loc[[ts]]
        long_funding_total = held_prints[long_names].mean(axis=1).sum()
        short_funding_total = held_prints[short_names].mean(axis=1).sum()
        carry_pnl = 0.5 * (-long_funding_total) + 0.5 * (short_funding_total)

        gross_ret = price_pnl + carry_pnl
        capital_before = capital
        capital = capital * (1.0 + gross_ret) - cost
        equity_curve.append({"date": t1, "equity": capital})
        trade_log.append({
            "timestamp": ts, "n_long": len(long_names), "n_short": len(short_names),
            "long_names": ",".join(long_names), "short_names": ",".join(short_names),
            "price_pnl": price_pnl, "carry_pnl": carry_pnl, "gross_return": gross_ret,
            "turnover_frac": turnover_frac, "cost": cost,
            "capital_before": capital_before, "capital_after": capital,
        })
        prev_long, prev_short = new_long, new_short

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": label, "equity": equity_df, "trades": trades_df, "final_capital": capital}


def compute_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame, bars_per_day: float = 3.0) -> dict:
    if equity_df.empty or trades_df.empty:
        return {"n_trades": 0, "final_capital": INITIAL_CAPITAL, "total_return": 0.0,
                "sharpe": float("nan"), "sortino": float("nan"), "max_drawdown": float("nan"),
                "win_rate": float("nan"), "profit_factor": float("nan")}
    equity = equity_df["equity"]
    period_returns = trades_df["gross_return"] - trades_df["turnover_frac"] * ROUND_TRIP_COST
    bars_per_year = 365.25 * bars_per_day
    mean_r = period_returns.mean()
    std_r = period_returns.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(bars_per_year) if std_r > 0 else float("nan")
    downside = period_returns.clip(upper=0.0)
    downside_dev = np.sqrt((downside ** 2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(bars_per_year) if downside_dev > 0 else float("nan")
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min()
    win_rate = (period_returns > 0).mean()
    gains = period_returns[period_returns > 0].sum()
    losses = -period_returns[period_returns < 0].sum()
    profit_factor = gains / losses if losses > 0 else float("nan")
    total_return = equity.iloc[-1] / INITIAL_CAPITAL - 1.0
    return {
        "n_trades": len(trades_df), "final_capital": equity.iloc[-1],
        "total_return": total_return, "sharpe": sharpe, "sortino": sortino,
        "max_drawdown": max_dd, "win_rate": win_rate, "profit_factor": profit_factor,
    }


def buy_and_hold(close_df: pd.DataFrame, coin: str, start: pd.Timestamp) -> dict:
    series = close_df[coin][close_df[coin].index >= start].dropna()
    start_price = series.iloc[0]
    end_price = series.iloc[-1]
    total_return = end_price / start_price - 1.0
    final_capital = INITIAL_CAPITAL * (1 + total_return)
    hourly_ret = series.pct_change().dropna()
    sharpe = (hourly_ret.mean() / hourly_ret.std(ddof=1)) * np.sqrt(365.25 * 24) if hourly_ret.std() > 0 else float("nan")
    running_max = series.cummax()
    dd = ((series - running_max) / running_max).min()
    return {"final_capital": final_capital, "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


def equal_weight_bh(close_df: pd.DataFrame, start: pd.Timestamp) -> dict:
    sub = close_df[close_df.index >= start]
    norm = sub / sub.iloc[0]
    basket = norm.mean(axis=1) * INITIAL_CAPITAL
    total_return = basket.iloc[-1] / INITIAL_CAPITAL - 1.0
    hourly_ret = basket.pct_change().dropna()
    sharpe = (hourly_ret.mean() / hourly_ret.std(ddof=1)) * np.sqrt(365.25 * 24) if hourly_ret.std() > 0 else float("nan")
    running_max = basket.cummax()
    dd = ((basket - running_max) / running_max).min()
    return {"final_capital": basket.iloc[-1], "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


def main() -> None:
    funding_df, close_df = build_panel()
    print(f"Universe: {len(UNIVERSE)} coins, {len(funding_df)} funding timestamps, "
          f"{funding_df.index.min()} -> {funding_df.index.max()}")
    print(f"Valid funding coverage per timestamp (median): {funding_df.notna().sum(axis=1).median()}")

    result_carry = run_carry_backtest(funding_df, close_df, randomize=False, seed=SEED, label="funding_carry_ls_8h")
    result_random = run_carry_backtest(funding_df, close_df, randomize=True, seed=SEED, label="random_ls_control_8h")
    result_carry_daily = run_carry_backtest(funding_df, close_df, randomize=False, seed=SEED,
                                             label="funding_carry_ls_daily", stride=3)
    result_random_daily = run_carry_backtest(funding_df, close_df, randomize=True, seed=SEED,
                                              label="random_ls_control_daily", stride=3)

    metrics_carry = compute_metrics(result_carry["equity"], result_carry["trades"], bars_per_day=3.0)
    metrics_random = compute_metrics(result_random["equity"], result_random["trades"], bars_per_day=3.0)
    metrics_carry_daily = compute_metrics(result_carry_daily["equity"], result_carry_daily["trades"], bars_per_day=1.0)
    metrics_random_daily = compute_metrics(result_random_daily["equity"], result_random_daily["trades"], bars_per_day=1.0)

    ew_bh = equal_weight_bh(close_df, START_ANALYSIS)
    btc_bh = buy_and_hold(close_df, "BTC", START_ANALYSIS)
    eth_bh = buy_and_hold(close_df, "ETH", START_ANALYSIS)
    sol_bh = buy_and_hold(close_df, "SOL", START_ANALYSIS)
    xrp_bh = buy_and_hold(close_df, "XRP", START_ANALYSIS)

    out_dir = ROOT / "results" / "funding_carry_cross_sectional" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result_carry["trades"].to_csv(run_dir / "carry_trades_8h.csv", index=False)
    result_random["trades"].to_csv(run_dir / "random_control_trades_8h.csv", index=False)
    result_carry["equity"].to_csv(run_dir / "carry_equity_8h.csv")
    result_random["equity"].to_csv(run_dir / "random_control_equity_8h.csv")
    result_carry_daily["trades"].to_csv(run_dir / "carry_trades_daily.csv", index=False)
    result_random_daily["trades"].to_csv(run_dir / "random_control_trades_daily.csv", index=False)
    result_carry_daily["equity"].to_csv(run_dir / "carry_equity_daily.csv")
    result_random_daily["equity"].to_csv(run_dir / "random_control_equity_daily.csv")

    summary_rows = [
        {"strategy": "Funding-carry L/S 8h rebalance", **metrics_carry},
        {"strategy": "Random-ranking L/S control 8h rebalance", **metrics_random},
        {"strategy": "Funding-carry L/S daily rebalance", **metrics_carry_daily},
        {"strategy": "Random-ranking L/S control daily rebalance", **metrics_random_daily},
        {"strategy": "Cash (0% exposure)", "n_trades": 0, "final_capital": INITIAL_CAPITAL,
         "total_return": 0.0, "sharpe": float("nan"), "sortino": float("nan"),
         "max_drawdown": 0.0, "win_rate": float("nan"), "profit_factor": float("nan")},
        {"strategy": "Equal-weight 10-asset buy-and-hold", **ew_bh, "n_trades": 1,
         "sortino": float("nan"), "win_rate": float("nan"), "profit_factor": float("nan")},
        {"strategy": "BTC buy-and-hold", **btc_bh, "n_trades": 1, "sortino": float("nan"),
         "win_rate": float("nan"), "profit_factor": float("nan")},
        {"strategy": "ETH buy-and-hold", **eth_bh, "n_trades": 1, "sortino": float("nan"),
         "win_rate": float("nan"), "profit_factor": float("nan")},
        {"strategy": "SOL buy-and-hold", **sol_bh, "n_trades": 1, "sortino": float("nan"),
         "win_rate": float("nan"), "profit_factor": float("nan")},
        {"strategy": "XRP buy-and-hold", **xrp_bh, "n_trades": 1, "sortino": float("nan"),
         "win_rate": float("nan"), "profit_factor": float("nan")},
    ]
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print(f"\nArtifacts written to {run_dir}")

    beats_random_8h = metrics_carry["final_capital"] > metrics_random["final_capital"]
    beats_cash_8h = metrics_carry["final_capital"] > INITIAL_CAPITAL
    beats_random_daily = metrics_carry_daily["final_capital"] > metrics_random_daily["final_capital"]
    beats_cash_daily = metrics_carry_daily["final_capital"] > INITIAL_CAPITAL
    verdict = "CANDIDATE" if ((beats_random_8h and beats_cash_8h) or (beats_random_daily and beats_cash_daily)) else "REJECTED"
    print(f"\n8h: beats random={beats_random_8h}, beats cash={beats_cash_8h}")
    print(f"daily: beats random={beats_random_daily}, beats cash={beats_cash_daily}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"beats_random_control_8h={beats_random_8h}\nbeats_cash_8h={beats_cash_8h}\n"
                 f"beats_random_control_daily={beats_random_daily}\nbeats_cash_daily={beats_cash_daily}\n"
                 f"verdict={verdict}\n")


if __name__ == "__main__":
    main()
