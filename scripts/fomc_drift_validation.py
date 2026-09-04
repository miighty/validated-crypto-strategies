"""EXP-2026-09-04-FOMCDRIFT-001: Pre-FOMC-announcement drift in crypto.

Hypothesis (preregistered; checked docs/experiment_registry.md and
docs/next_hypotheses.md in full first -- genuinely new for this repo: no
prior study has used the FOMC's own SCHEDULED meeting calendar as a signal.
The closest prior studies are FED_HAWKISH_BTC_VALIDATION (Polymarket
rate-cut-odds MOMENTUM signal, a continuous market-derived series) and
DXY_TREND_REGIME_VALIDATION (a continuous FRED SMA-crossover regime state).
This study uses neither: it is a pure calendar/event-scheduling effect --
the well-documented TradFi "pre-FOMC announcement drift" (Lucca & Moench,
2015, Journal of Finance): equity/risk-asset returns are disproportionately
realized in the ~24h window immediately preceding a SCHEDULED FOMC rate
decision, independent of whether the decision itself is hawkish or dovish
-- attributed to a pre-announcement risk/uncertainty-resolution premium,
not to the decision content. This is the first test of whether that
documented TradFi calendar effect also holds in crypto.

Data:
  - Real FOMC scheduled decision dates, 2018-01-31 through 2026-07-29 (72
    meetings), manually transcribed from the Federal Reserve's own public
    calendar pages (federalreserve.gov/monetarypolicy/fomccalendars.htm and
    fomchistorical{2018,2019,2020}.htm), cached to
    data/macro_fomc/fomc_decision_dates.csv. These are the actual last day
    of each two-day (or one-day) FOMC meeting, i.e. the day the policy
    statement is released. No proxy -- these are the Fed's own published
    dates, not inferred or estimated.
  - Real Binance spot hourly OHLCV, BTC/ETH/SOL/XRP (data/raw/*_1h.csv.gz,
    already cached).

Design (frozen before any result was inspected):
  - Decision time approximated as 18:00 UTC on the decision date (2:00pm
    Eastern Time, the Fed's standard post-2011 statement release time,
    accounting for the ET/UTC offset by using a fixed 18:00 UTC across the
    whole sample -- a deliberate simplification that introduces at most a
    1-hour timing error during EDT vs EST, immaterial at a 24h holding
    horizon).
  - Entry: 24h BEFORE the decision timestamp (t_decision - 24h), at that
    hour's open. Exit: 24h AFTER the decision timestamp (t_decision + 24h),
    at that hour's open. Non-overlapping by construction (FOMC meetings are
    >=5 weeks apart, holding window is 48h).
  - This captures the FULL pre-announcement drift + announcement reaction
    window (48h total), the standard construction in the TradFi literature
    (drift window ends at the announcement; here we also hold through the
    reaction since crypto trades continuously and a hard cutoff exactly at
    the drift boundary is not meaningfully testable at 1h granularity
    without inventing a sub-hour execution assumption).
  - Long-only, same fixed entry/exit rule applied independently per asset.
  - Costs: repo-standard 30bps round trip (15bps/side).
  - Partitions: development (start -> 2020-01-01), validation
    (2020-01-01 -> 2023-01-01), test (2023-01-01 -> end). Each asset's
    trades are additionally clipped to that asset's real listing history.
  - Baselines: cash, buy-and-hold, DCA (daily), always-long-random-schedule
    control (same trade count/hold length, seeded random start times,
    matched cost model) to isolate whether FOMC timing itself adds value
    over the same trade structure at arbitrary calendar dates.

Fastest rejection criterion: primary rule does not beat BOTH buy-and-hold
and the seeded random-timing control (same n_trades, same 48h hold, same
cost) on a majority (>=3/4) of assets, or fails the untouched 2023+ test
partition, or fails doubled costs, or a single trade exceeds the 20%
concentration cap.
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

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VALIDATION_START = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2023-01-01T00:00:00Z")

DECISION_HOUR_UTC = 18  # 2:00pm ET approximated as 18:00 UTC year-round
PRE_WINDOW_H = 24
POST_WINDOW_H = 24
BASE_SEED = 20260904
INITIAL_CAPITAL = 10_000.0

FOMC_DATES_PATH = ROOT / "data" / "macro_fomc" / "fomc_decision_dates.csv"


def load_fomc_dates() -> list[pd.Timestamp]:
    df = pd.read_csv(FOMC_DATES_PATH, parse_dates=["decision_date"])
    ts = [
        pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=DECISION_HOUR_UTC)
        for d in df["decision_date"]
    ]
    ts = sorted(t for t in ts if t < END_EXCLUSIVE)
    return ts


def load_asset_hourly(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def price_at_or_after(price: pd.Series, ts: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    idx = price.index.searchsorted(ts)
    if idx >= len(price):
        return None
    return price.index[idx], float(price.iloc[idx])


def build_trades(price: pd.Series, decision_times: list[pd.Timestamp],
                  pre_h: int, post_h: int, one_way_cost: float) -> pd.DataFrame:
    rows = []
    for dt in decision_times:
        entry_target = dt - pd.Timedelta(hours=pre_h)
        exit_target = dt + pd.Timedelta(hours=post_h)
        entry = price_at_or_after(price, entry_target)
        exit_ = price_at_or_after(price, exit_target)
        if entry is None or exit_ is None:
            continue
        entry_ts, entry_price_raw = entry
        exit_ts, exit_price_raw = exit_
        if entry_ts >= exit_ts:
            continue
        entry_price = entry_price_raw * (1 + one_way_cost)
        exit_price = exit_price_raw * (1 - one_way_cost)
        gross_return = exit_price / entry_price - 1.0
        rows.append({
            "decision_time": dt, "entry_time": entry_ts, "exit_time": exit_ts,
            "entry_price": entry_price, "exit_price": exit_price,
            "gross_return": gross_return,
        })
    return pd.DataFrame(rows)


def compound_equity(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series([INITIAL_CAPITAL], index=[pd.Timestamp("1970-01-01", tz="UTC")])
    capital = INITIAL_CAPITAL
    vals, idx = [], []
    for _, row in trades.iterrows():
        capital *= (1.0 + row["gross_return"])
        vals.append(capital)
        idx.append(row["exit_time"])
    return pd.Series(vals, index=idx)


def compute_metrics(trades: pd.DataFrame, equity: pd.Series, holding_hours: float) -> dict:
    if trades.empty:
        return {"n_trades": 0, "final_capital": INITIAL_CAPITAL, "total_return": 0.0,
                "sharpe": float("nan"), "sortino": float("nan"), "max_drawdown": float("nan"),
                "win_rate": float("nan"), "top_trade_pnl_share": float("nan")}
    rets = trades["gross_return"]
    bars_per_year = 365.25 * 24.0 / holding_hours
    mean_r, std_r = rets.mean(), rets.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(bars_per_year) if std_r > 0 else float("nan")
    downside = rets.clip(upper=0.0)
    downside_dev = np.sqrt((downside**2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(bars_per_year) if downside_dev > 0 else float("nan")
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    total_return = equity.iloc[-1] / INITIAL_CAPITAL - 1.0
    win_rate = (rets > 0).mean()
    total_pnl = rets.sum()
    top_share = float(rets.abs().max() / abs(total_pnl)) if total_pnl != 0 else float("nan")
    return {"n_trades": len(trades), "final_capital": float(equity.iloc[-1]),
            "total_return": total_return, "sharpe": sharpe, "sortino": sortino,
            "max_drawdown": float(dd.min()), "win_rate": float(win_rate),
            "top_trade_pnl_share": top_share}


def buy_and_hold(price: pd.Series) -> dict:
    start_price, end_price = float(price.iloc[0]), float(price.iloc[-1])
    total_return = end_price / start_price - 1.0
    final_capital = INITIAL_CAPITAL * (1 + total_return)
    rets = price.pct_change().dropna()
    sharpe = (rets.mean() / rets.std(ddof=1)) * np.sqrt(365.25 * 24) if rets.std() > 0 else float("nan")
    running_max = price.cummax()
    dd = ((price - running_max) / running_max).min()
    return {"final_capital": final_capital, "total_return": total_return, "sharpe": sharpe, "max_drawdown": dd}


def dca(price: pd.Series) -> dict:
    daily = price.resample("1D").first().dropna()
    n = len(daily)
    if n == 0:
        return {"final_capital": INITIAL_CAPITAL, "total_return": 0.0}
    contrib = INITIAL_CAPITAL / n
    units = (contrib / daily).sum()
    final_capital = units * float(daily.iloc[-1])
    return {"final_capital": final_capital, "total_return": final_capital / INITIAL_CAPITAL - 1.0}


def random_timing_control(price: pd.Series, n_trades: int, pre_h: int, post_h: int,
                           one_way_cost: float, seed: int, exclude_times: list[pd.Timestamp]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    hold_hours = pre_h + post_h
    idx = price.index
    valid_start = idx.min() + pd.Timedelta(hours=pre_h)
    valid_end = idx.max() - pd.Timedelta(hours=post_h)
    candidates = idx[(idx >= valid_start) & (idx <= valid_end)]
    if len(candidates) == 0 or n_trades == 0:
        return pd.DataFrame()
    chosen_decisions = []
    used_ranges = []
    attempts = 0
    while len(chosen_decisions) < n_trades and attempts < n_trades * 200:
        attempts += 1
        cand = candidates[rng.integers(0, len(candidates))]
        window = (cand - pd.Timedelta(hours=pre_h), cand + pd.Timedelta(hours=post_h))
        overlap = any(not (window[1] < u[0] or window[0] > u[1]) for u in used_ranges)
        if overlap:
            continue
        chosen_decisions.append(cand)
        used_ranges.append(window)
    return build_trades(price, chosen_decisions, pre_h, post_h, one_way_cost)


def partition_trades(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    if trades.empty:
        return trades
    mask = trades["entry_time"] >= start
    if end is not None:
        mask &= trades["entry_time"] < end
    return trades.loc[mask]


def exclude_best_trade_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return INITIAL_CAPITAL
    best_idx = trades["gross_return"].idxmax()
    remaining = trades.drop(index=best_idx)
    equity = compound_equity(remaining)
    return float(equity.iloc[-1])


def run_for_asset(coin: str, decision_times: list[pd.Timestamp]) -> dict:
    asset_df = load_asset_hourly(coin)
    price = asset_df["close"]
    listing_start = price.index.min()
    valid_decisions = [d for d in decision_times if d - pd.Timedelta(hours=PRE_WINDOW_H) >= listing_start]

    trades = build_trades(price, valid_decisions, PRE_WINDOW_H, POST_WINDOW_H, ONE_WAY_COST)
    equity = compound_equity(trades)
    holding_hours = PRE_WINDOW_H + POST_WINDOW_H
    metrics = compute_metrics(trades, equity, holding_hours)

    trades_doubled = build_trades(price, valid_decisions, PRE_WINDOW_H, POST_WINDOW_H, ONE_WAY_COST * 2)
    equity_doubled = compound_equity(trades_doubled)
    doubled_final = float(equity_doubled.iloc[-1])

    excl_best_final = exclude_best_trade_final(trades)

    bh = buy_and_hold(price)
    dca_result = dca(price)

    seed = BASE_SEED + (hash(coin) % 10_000)
    rand_trades = random_timing_control(price, len(trades), PRE_WINDOW_H, POST_WINDOW_H,
                                         ONE_WAY_COST, seed, valid_decisions)
    rand_equity = compound_equity(rand_trades)
    rand_metrics = compute_metrics(rand_trades, rand_equity, holding_hours)

    partitions = {
        "development": (listing_start, VALIDATION_START),
        "validation": (VALIDATION_START, TEST_START),
        "test": (TEST_START, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        ptrades = partition_trades(trades, pstart, pend)
        if ptrades.empty:
            partition_rows.append({"partition": pname, "n_trades": 0, "final_capital_rel": 1.0})
            continue
        pequity = compound_equity(ptrades)
        p_bh_price = price[(price.index >= pstart) & (price.index < (pend or price.index.max() + pd.Timedelta(days=1)))]
        p_bh = buy_and_hold(p_bh_price) if len(p_bh_price) > 2 else {"total_return": float("nan")}
        partition_rows.append({
            "partition": pname, "n_trades": len(ptrades),
            "final_capital_rel": float(pequity.iloc[-1]) / INITIAL_CAPITAL,
            "bh_total_return_plus1": 1.0 + p_bh["total_return"],
        })

    return {
        "coin": coin, "trades": trades, "equity": equity, "metrics": metrics,
        "doubled_final": doubled_final, "excl_best_final": excl_best_final,
        "bh": bh, "dca": dca_result, "rand_metrics": rand_metrics, "rand_trades": rand_trades,
        "partitions": pd.DataFrame(partition_rows), "n_decision_events": len(valid_decisions),
    }


def main() -> None:
    decision_times = load_fomc_dates()
    print(f"Loaded {len(decision_times)} real FOMC decision dates "
          f"({decision_times[0].date()} -> {decision_times[-1].date()})")

    out_dir = ROOT / "results" / "fomc_drift" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts_str}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    gate_rows = []
    for coin in ASSETS:
        res = run_for_asset(coin, decision_times)
        m = res["metrics"]
        rm = res["rand_metrics"]
        beats_bh = m["final_capital"] > res["bh"]["final_capital"]
        beats_dca = m["final_capital"] > res["dca"]["final_capital"]
        beats_random = m["final_capital"] > rm["final_capital"]
        survives_doubled = res["doubled_final"] > INITIAL_CAPITAL
        survives_excl_best = res["excl_best_final"] > INITIAL_CAPITAL
        clears_concentration = (not np.isnan(m["top_trade_pnl_share"])) and m["top_trade_pnl_share"] <= 0.20
        test_part = res["partitions"][res["partitions"]["partition"] == "test"]
        test_n = int(test_part["n_trades"].iloc[0]) if not test_part.empty else 0
        test_final_rel = float(test_part["final_capital_rel"].iloc[0]) if not test_part.empty else float("nan")
        test_bh_rel = float(test_part["bh_total_return_plus1"].iloc[0]) if (not test_part.empty and "bh_total_return_plus1" in test_part.columns) else float("nan")
        passes_test_partition = (test_n == 0) or (test_final_rel >= test_bh_rel)

        summary_rows.append({
            "asset": coin, "n_events": res["n_decision_events"], "n_trades": m["n_trades"],
            "final_capital": m["final_capital"], "total_return_pct": m["total_return"] * 100,
            "sharpe": m["sharpe"], "sortino": m["sortino"], "win_rate": m["win_rate"],
            "top_trade_pnl_share_pct": m["top_trade_pnl_share"] * 100 if not np.isnan(m["top_trade_pnl_share"]) else float("nan"),
            "bh_final": res["bh"]["final_capital"], "dca_final": res["dca"]["final_capital"],
            "random_control_final": rm["final_capital"], "doubled_cost_final": res["doubled_final"],
            "excl_best_trade_final": res["excl_best_final"],
            "test_partition_n_trades": test_n, "test_partition_final_rel": test_final_rel,
            "test_partition_bh_rel": test_bh_rel,
        })
        gate_rows.append({
            "asset": coin, "beats_bh": beats_bh, "beats_dca": beats_dca, "beats_random": beats_random,
            "survives_doubled_cost": survives_doubled, "survives_best_trade_exclusion": survives_excl_best,
            "clears_concentration_cap": clears_concentration, "passes_test_partition": passes_test_partition,
        })
        res["trades"].to_csv(run_dir / f"{coin}_trades.csv", index=False)
        res["partitions"].to_csv(run_dir / f"{coin}_partitions.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    gates_df = pd.DataFrame(gate_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    gates_df.to_csv(run_dir / "gates.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(gates_df.to_string(index=False))

    n_pass_majority = sum(
        r["beats_bh"] and r["beats_random"] and r["survives_doubled_cost"]
        and r["clears_concentration_cap"] and r["passes_test_partition"]
        for r in gate_rows
    )
    verdict = "CANDIDATE" if n_pass_majority >= 3 else "REJECTED"
    print(f"\nAssets clearing ALL gates: {n_pass_majority}/4")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"n_pass_all_gates={n_pass_majority}/4\nverdict={verdict}\n")
        f.write(gates_df.to_string(index=False) + "\n")

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
