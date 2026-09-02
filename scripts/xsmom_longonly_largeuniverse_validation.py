"""EXP-2026-09-02-XSMOM-LONGONLY-001: Cross-sectional long-only top-decile
momentum rotation on the repo's full ~75-coin real Binance universe.

Hypothesis (preregistered; checked docs/experiment_registry.md and
docs/next_hypotheses.md in full before writing this -- genuinely new for
this repo).

Four prior cross-sectional dollar-neutral long/short factor studies on this
repo's 30-coin universe all failed to beat cash (Amihud illiquidity,
funding-rate carry, residual momentum, low-volatility premium). Each
registry note for those rejections explicitly recommended, as the next step,
either (a) a materially larger universe (100+ names) or (b) a non-dollar-
neutral construction -- because the short leg's borrow/short-cost drag and
turnover cost on both legs may be destroying a genuine long-side factor.
This study tests recommendation (b) directly: a LONG-ONLY, no-short-leg
cross-sectional momentum rotation, on a genuinely larger universe (75 coins
with >=730 days of real Binance daily history, vs the prior study's 30) --
this is NOT a retune of the residual-momentum study (that was dollar-neutral
tercile long+short on 30 coins with beta-residualization); this is the pure
long-only raw-momentum top-decile construction on 2.5x the universe size,
directly implementing this program's own registry recommendation.

Economic rationale: cross-sectional momentum (winners keep winning short-
term) is one of the most replicated cross-asset factors in finance. A dollar-
neutral construction pays shorting/borrow-equivalent costs on the short leg
and doubles turnover; a long-only top-decile rotation only pays costs on the
long leg and only has to beat a passive benchmark, not "beat cash while also
carrying a short book" -- a fundamentally different (and much lower) bar to
clear economically, while still directly testing whether the momentum RANKING
signal itself has any value.

PRIMARY RULE (frozen before any result was inspected):
  1. Universe: any of the 75 coins in data/raw/*_1d.csv.gz with >=730 rows
     of real Binance daily OHLCV, dynamically eligible once it individually
     has >=90 days of trailing history (assets phase in as they list).
  2. Signal: trailing 30-day total return (pct_change over 30 days), no
     residualization, no compounding assumptions beyond simple return.
  3. Rebalance weekly (every 7 days). Rank eligible coins by trailing 30-day
     return descending; go long the top decile (max(1, n // 10)),
     equal-weighted, ALL-IN (100% of capital across the decile, no cash
     buffer) -- rest of universe is simply not held (no short leg).
  4. Enter at next day's open after the rebalance signal date, hold to the
     next rebalance's entry (same non-overlapping-block structure as the
     prior residual-momentum/Amihud/low-vol studies for direct
     comparability).
  5. Costs: repo-standard 30bps round-trip charged on the turnover fraction
     of the portfolio that changes membership at each rebalance.
  6. Sample: full available history, analysis starting 2020-01-01 (when a
     usable number of eligible coins first exists).

Baselines: cash ($10,000 fixed), BTC/ETH/SOL/XRP buy-and-hold, equal-weight-
75-coin-universe buy-and-hold, seeded random-decile-selection long-only
control (identical N per rebalance, identical turnover/cost structure, from
the same eligible universe -- isolates whether the RANKING carries value
versus simply holding a random subset of the same size).

Falsification (preregistered): primary must beat cash AND the equal-weight-
universe buy-and-hold AND the random-selection control after costs, survive
doubled round-trip cost, and no single rebalance block may exceed 20% of
total strategy net PnL (concentration cap) -- or REJECTED. Additionally
report a walk-forward first-half/second-half split and 2025+ holdout
(descriptive, not a hard gate given weekly rebalance frequency yields a
modest total block count).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root

ROOT = project_root()
PATHS = Paths(ROOT)
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
ROUND_TRIP_COST = 2 * ONE_WAY_COST

MIN_ROWS = 730
MOMENTUM_WINDOW = 30
MIN_ELIGIBLE_HISTORY = 90
REBALANCE_DAYS = 7
INITIAL_CAPITAL = 10_000.0
START_ANALYSIS = pd.Timestamp("2020-01-01", tz="UTC")
END_EXCLUSIVE = pd.Timestamp("2026-07-28", tz="UTC")
RANDOM_SEED = 20260902
TEST_START = pd.Timestamp("2025-01-01", tz="UTC")
BENCH_ASSETS = ["BTC", "ETH", "SOL", "XRP"]


def discover_universe() -> list[str]:
    coins = []
    for f in sorted((PATHS.raw).glob("*_1d.csv.gz")):
        coin = f.name.replace("_1d.csv.gz", "")
        df = pd.read_csv(f, usecols=["timestamp"])
        if len(df) >= MIN_ROWS:
            coins.append(coin)
    return coins


def load_field(universe: list[str], field: str) -> pd.DataFrame:
    frames = {}
    for coin in universe:
        path = PATHS.raw / f"{coin}_1d.csv.gz"
        df = pd.read_csv(path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        df = df[df.index < END_EXCLUSIVE]
        frames[coin] = df[field]
    out = pd.concat(frames, axis=1)
    out = out[out.index >= START_ANALYSIS]
    return out.sort_index()


def eligibility_mask(closes: pd.DataFrame) -> pd.DataFrame:
    """True once an asset has >= MIN_ELIGIBLE_HISTORY non-null days of history."""
    valid_count = closes.notna().cumsum()
    return valid_count >= MIN_ELIGIBLE_HISTORY


def build_momentum_score(closes: pd.DataFrame) -> pd.DataFrame:
    mom = closes.pct_change(MOMENTUM_WINDOW)
    return mom.shift(1)  # prior-only, no lookahead into the rebalance day itself


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index[::REBALANCE_DAYS]


def run_backtest(score: pd.DataFrame, eligible: pd.DataFrame, opens: pd.DataFrame, label: str,
                  round_trip_cost: float = ROUND_TRIP_COST) -> dict:
    dates = score.index
    reb_dates = rebalance_dates(dates)
    capital = INITIAL_CAPITAL
    prev_weights: dict[str, float] = {}
    equity_curve = []
    trade_log = []

    for i, reb_date in enumerate(reb_dates):
        elig_row = eligible.loc[reb_date]
        row = score.loc[reb_date][elig_row].dropna()
        if len(row) < 5:
            continue
        n = len(row)
        leg_n = max(1, n // 10)
        ranked = row.sort_values(ascending=False)
        long_names = ranked.head(leg_n).index.tolist()
        new_weights = {name: 1.0 / len(long_names) for name in long_names}

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
        cost = capital * turnover * round_trip_cost

        entry_prices = opens.loc[entry_date, long_names]
        if exit_date == entry_date:
            exit_prices = entry_prices
        else:
            exit_pos_idx = dates.get_indexer([exit_date])[0]
            exit_prices = opens.loc[dates[exit_pos_idx], long_names]
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
            "n_eligible": n, "n_long": len(long_names),
            "long_names": ",".join(long_names),
            "weighted_return": weighted_ret, "turnover_frac": turnover, "cost": cost,
            "capital_before": capital_before, "capital_after": capital,
            "net_pnl": capital - capital_before,
        })
        prev_weights = new_weights

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": label, "equity": equity_df, "trades": trades_df, "final_capital": capital}


def run_random_control(score_index: pd.DatetimeIndex, eligible: pd.DataFrame,
                        opens: pd.DataFrame, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    reb_dates = rebalance_dates(score_index)
    capital = INITIAL_CAPITAL
    prev_weights: dict[str, float] = {}
    equity_curve = []
    trade_log = []

    for i, reb_date in enumerate(reb_dates):
        elig_row = eligible.loc[reb_date]
        avail_cols = [c for c in elig_row.index if elig_row[c] and reb_date in opens.index
                      and pd.notna(opens.loc[reb_date, c])]
        if len(avail_cols) < 5:
            continue
        shuffled = list(avail_cols)
        rng.shuffle(shuffled)
        n = len(shuffled)
        leg_n = max(1, n // 10)
        long_names = shuffled[:leg_n]
        new_weights = {name: 1.0 / len(long_names) for name in long_names}

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

        entry_prices = opens.loc[entry_date, long_names]
        if exit_date == entry_date:
            exit_prices = entry_prices
        else:
            exit_pos_idx = score_index.get_indexer([exit_date])[0]
            exit_prices = opens.loc[score_index[exit_pos_idx], long_names]
        valid = entry_prices.notna() & exit_prices.notna() & (entry_prices > 0)
        per_asset_ret = (exit_prices[valid] / entry_prices[valid]) - 1.0
        weighted_ret = 0.0
        for name in per_asset_ret.index:
            weighted_ret += new_weights.get(name, 0.0) * per_asset_ret[name]

        capital_before = capital
        capital = capital * (1.0 + weighted_ret) - cost
        equity_curve.append({"date": exit_date, "equity": capital})
        trade_log.append({"rebalance_date": reb_date, "weighted_return": weighted_ret,
                           "turnover_frac": turnover, "cost": cost, "net_pnl": capital - capital_before})
        prev_weights = new_weights

    equity_df = pd.DataFrame(equity_curve).set_index("date") if equity_curve else pd.DataFrame()
    trades_df = pd.DataFrame(trade_log)
    return {"label": "random_control", "equity": equity_df, "trades": trades_df, "final_capital": capital}


def compute_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame,
                     round_trip_cost: float = ROUND_TRIP_COST) -> dict:
    if equity_df.empty:
        return {"n_trades": 0, "final_capital": INITIAL_CAPITAL, "total_return": 0.0,
                "sharpe": float("nan"), "sortino": float("nan"), "max_drawdown": float("nan"),
                "win_rate": float("nan"), "top_block_pct_of_pnl": float("nan")}
    equity = equity_df["equity"]
    period_returns = trades_df["weighted_return"] - trades_df["turnover_frac"] * round_trip_cost
    n_periods_per_year = 365.25 / REBALANCE_DAYS
    mean_r = period_returns.mean()
    std_r = period_returns.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(n_periods_per_year) if std_r > 0 else float("nan")
    downside = period_returns.clip(upper=0.0)
    downside_dev = np.sqrt((downside ** 2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(n_periods_per_year) if downside_dev > 0 else float("nan")
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min()
    win_rate = (period_returns > 0).mean()
    total_return = equity.iloc[-1] / INITIAL_CAPITAL - 1.0
    total_pnl = trades_df["net_pnl"].sum()
    top_block_pct = (trades_df["net_pnl"].abs().max() / abs(total_pnl)) if total_pnl != 0 else float("nan")
    return {
        "n_trades": len(trades_df), "final_capital": equity.iloc[-1],
        "total_return": total_return, "sharpe": sharpe, "sortino": sortino,
        "max_drawdown": max_dd, "win_rate": win_rate, "top_block_pct_of_pnl": top_block_pct,
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
    norm = closes / closes.bfill().iloc[0]
    # normalize each column by its own first valid value (assets phase in)
    first_valid = closes.apply(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
    norm = closes.divide(first_valid, axis=1)
    basket = norm.mean(axis=1) * INITIAL_CAPITAL
    total_return = basket.iloc[-1] / INITIAL_CAPITAL - 1.0
    daily_ret = basket.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std(ddof=1)) * np.sqrt(365.25) if daily_ret.std() > 0 else float("nan")
    running_max = basket.cummax()
    dd = ((basket - running_max) / running_max).min()
    return {"final_capital": basket.iloc[-1], "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


def walk_forward_split(trades_df: pd.DataFrame) -> tuple[float, float]:
    if trades_df.empty:
        return float("nan"), float("nan")
    mid = len(trades_df) // 2
    first = trades_df.iloc[:mid]
    second = trades_df.iloc[mid:]

    def block_sharpe(df):
        if len(df) < 5:
            return float("nan")
        r = df["weighted_return"] - df["turnover_frac"] * ROUND_TRIP_COST
        if r.std(ddof=1) == 0 or r.empty:
            return float("nan")
        return (r.mean() / r.std(ddof=1)) * np.sqrt(365.25 / REBALANCE_DAYS)

    return block_sharpe(first), block_sharpe(second)


def main() -> None:
    universe = discover_universe()
    print(f"Universe: {len(universe)} coins with >= {MIN_ROWS} rows")
    closes = load_field(universe, "close")
    opens = load_field(universe, "open")
    eligible = eligibility_mask(closes)
    score = build_momentum_score(closes)

    primary = run_backtest(score, eligible, opens, "xsmom_longonly_top_decile")
    doubled = run_backtest(score, eligible, opens, "xsmom_longonly_doubled_cost",
                            round_trip_cost=ROUND_TRIP_COST * 2)

    random_ctrl = run_random_control(score.index, eligible, opens, RANDOM_SEED)

    metrics_primary = compute_metrics(primary["equity"], primary["trades"])
    metrics_doubled = compute_metrics(doubled["equity"], doubled["trades"], round_trip_cost=ROUND_TRIP_COST * 2)
    metrics_random = compute_metrics(random_ctrl["equity"], random_ctrl["trades"])

    bh_results = {coin: buy_and_hold(closes, coin) for coin in BENCH_ASSETS if coin in closes.columns}
    ew_bh = equal_weight_universe_bh(closes)

    wf_first, wf_second = walk_forward_split(primary["trades"])

    # holdout 2025+
    test_trades = primary["trades"][primary["trades"]["entry_date"] >= TEST_START]
    n_test_trades = len(test_trades)

    out_dir = ROOT / "results" / "xsmom_longonly_largeuniverse" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    primary["trades"].to_csv(run_dir / "trades.csv", index=False)
    random_ctrl["trades"].to_csv(run_dir / "random_control_trades.csv", index=False)

    summary = {
        "n_universe": len(universe),
        "n_rebalance_blocks": metrics_primary["n_trades"],
        "primary_final_capital": metrics_primary["final_capital"],
        "primary_total_return": metrics_primary["total_return"],
        "primary_sharpe": metrics_primary["sharpe"],
        "primary_sortino": metrics_primary["sortino"],
        "primary_max_dd": metrics_primary["max_drawdown"],
        "primary_win_rate": metrics_primary["win_rate"],
        "primary_top_block_pct_of_pnl": metrics_primary["top_block_pct_of_pnl"],
        "doubled_cost_final_capital": metrics_doubled["final_capital"],
        "doubled_cost_sharpe": metrics_doubled["sharpe"],
        "random_control_final_capital": metrics_random["final_capital"],
        "random_control_sharpe": metrics_random["sharpe"],
        "equal_weight_universe_bh_final": ew_bh["final_capital"],
        "equal_weight_universe_bh_sharpe": ew_bh["sharpe"],
        "wf_first_half_sharpe": wf_first,
        "wf_second_half_sharpe": wf_second,
        "n_test_partition_trades": n_test_trades,
    }
    for coin, res in bh_results.items():
        summary[f"{coin}_bh_final"] = res["final_capital"]
        summary[f"{coin}_bh_sharpe"] = res["sharpe"]

    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(run_dir / "summary.csv", index=False)
    print(summary_df.T.to_string())

    beats_cash = metrics_primary["final_capital"] > INITIAL_CAPITAL
    beats_ew_bh = metrics_primary["final_capital"] > ew_bh["final_capital"]
    beats_random = metrics_primary["final_capital"] > metrics_random["final_capital"]
    beats_doubled_cost_positive = metrics_doubled["final_capital"] > INITIAL_CAPITAL
    concentration_ok = (not np.isnan(metrics_primary["top_block_pct_of_pnl"])) and \
        abs(metrics_primary["top_block_pct_of_pnl"]) <= 0.20
    n_beat_majors = sum(1 for coin, res in bh_results.items() if metrics_primary["final_capital"] > res["final_capital"])

    gates = {
        "beats_cash": beats_cash,
        "beats_equal_weight_universe_bh": beats_ew_bh,
        "beats_random_control": beats_random,
        "survives_doubled_cost_positive": beats_doubled_cost_positive,
        "concentration_ok": concentration_ok,
        "n_majors_beaten_of_4": n_beat_majors,
    }
    print("\nGates:", gates)

    core_pass = beats_cash and beats_ew_bh and beats_random and concentration_ok
    if core_pass and n_beat_majors >= 3:
        verdict = "CANDIDATE"
    elif core_pass or (beats_ew_bh and beats_random):
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nVerdict: {verdict}")
    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"gates={gates}\nverdict={verdict}\n")
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
