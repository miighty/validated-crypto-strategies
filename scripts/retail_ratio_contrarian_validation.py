"""EXP-2026-09-02-RETAILRATIO-001: Retail account long/short ratio extreme-short
contrarian rebound.

Hypothesis (preregistered, genuinely new for this repo -- checked
docs/experiment_registry.md and docs/next_hypotheses.md in full before
writing this).

Every prior use of real Binance USD-M positioning data in this repo used
either:
  - `sum_open_interest` (aggregate leveraged notional) as a fast event
    trigger (crowded_perp_unwind, oi_breakout_confirmation, oi_thin_breakout)
    or a slow SMA-crossover structural regime (oi_trend_regime) -- all
    REJECTED.
  - `sum_toptrader_long_short_ratio` (largest-account/"smart money"
    positioning) as a slow SMA10/SMA30 structural trend-following regime
    (toptrader_positioning_trend) -- REJECTED.
  - CFTC's CME "Leveraged Funds" institutional futures positioning as a
    contrarian 52-week z-score extreme trigger (cftc_cot_positioning_extreme)
    -- REJECTED.

This study is both a genuinely new DATA FIELD (Binance's
`count_long_short_ratio` -- the GLOBAL RETAIL account long/short ratio,
i.e. number of accounts net-long divided by number of accounts net-short,
which is a fundamentally different population than the top-trader ratio:
top-trader is the largest few hundred accounts by size, retail-count is
literally every account on the exchange, dominated by small/unsophisticated
positions) and a genuinely new MECHANISM COMBINATION for this repo: a
CONTRARIAN z-score extreme trigger (like CFTC-COT) applied to RETAIL
(unsophisticated crowd) positioning (like toptrader-trend's data category,
but the opposite population and the opposite construction -- event trigger,
not SMA trend).

Economic rationale: retail traders are classically the "dumb money" in
crowded-positioning theory -- when the aggregate retail account base is
extremely skewed towards SHORT (low count_long_short_ratio, z-score deeply
negative vs its own trailing history), this reflects retail capitulation
into a decline; if retail is systematically wrongfooted (as the classic
contrarian-crowd thesis holds), price should rebound as those short
positions get squeezed/close out. This repo is long-only spot (no shorts),
so only the "retail extremely short -> buy" half of the thesis is testable.

PRIMARY RULE (frozen before any result was inspected):
  1. z = (ratio_t - rolling_mean_90d(ratio_{t-1..t-90})) / rolling_std_90d,
     shift(1) applied before the rolling window so today's flag never uses
     today's own value (prior-only baseline, no lookahead).
  2. Trigger: z <= -1.5 (retail extremely short-skewed vs own 90-day
     history) on a given UTC daily close.
  3. Entry: buy spot at the NEXT day's 00:00 UTC hourly open (one full day
     of publication/decision lag). Exit: fixed 14-day hold, then flat.
     Cooldown: no new entry while already in a position (non-overlapping
     trades only, matching the FGI/CFTC/DVOL contrarian-family studies for
     direct comparability).
  4. Costs: repo-standard 30bps round trip (15bps/side).
  5. Universe/coverage: BTC/ETH/SOL/XRP, restricted to each asset's real
     Binance futures archive coverage window (BTC from 2020-09-01, ETH/SOL/
     XRP from 2021-12-01 -- same real archive limits as every prior OI-data
     study in this repo, no fabrication).

Baselines: continuous buy-and-hold, daily DCA, cash (implicit via final
capital vs $1 start).

Falsification (preregistered): primary rule must beat both buy-and-hold AND
daily DCA on a given asset, survive doubled round-trip cost, retain a
positive best-trade-excluded terminal value above buy-and-hold (no
concentration artifact), and not lose in the final (2025-onward) partition.
Any single failure on an asset -> that asset REJECTED. Overall verdict
follows the repo's majority-of-4 convention used in prior single-asset
panel studies, unless the result is decisive across all 4 (in either
direction).
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
OI_COVERAGE_START = {
    "BTC": pd.Timestamp("2020-09-01T00:00:00Z"),
    "ETH": pd.Timestamp("2021-12-01T00:00:00Z"),
    "SOL": pd.Timestamp("2021-12-01T00:00:00Z"),
    "XRP": pd.Timestamp("2021-12-01T00:00:00Z"),
}
END_EXCLUSIVE = pd.Timestamp("2026-08-30T00:00:00Z")
ROLLING_WINDOW_DAYS = 90
Z_THRESHOLD = -1.5
HOLD_DAYS = 14
TEST_START = pd.Timestamp("2025-01-01T00:00:00Z")


def load_oi(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.root / "data" / "open_interest" / f"{coin}_oi_daily.csv.gz")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df


def load_spot(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_signal(oi: pd.DataFrame) -> pd.DataFrame:
    frame = oi.copy()
    ratio = frame["count_long_short_ratio"]
    prior = ratio.shift(1)
    roll_mean = prior.rolling(ROLLING_WINDOW_DAYS, min_periods=ROLLING_WINDOW_DAYS).mean()
    roll_std = prior.rolling(ROLLING_WINDOW_DAYS, min_periods=ROLLING_WINDOW_DAYS).std(ddof=1)
    frame["z"] = (ratio - roll_mean) / roll_std
    frame["trigger"] = frame["z"] <= Z_THRESHOLD
    return frame


def non_overlapping_entries(signal: pd.DataFrame, hold_days: int) -> list[pd.Timestamp]:
    entries: list[pd.Timestamp] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for ts, row in signal.iterrows():
        if not bool(row["trigger"]):
            continue
        entry_day = ts + pd.Timedelta(days=1)
        if entry_day < next_ok:
            continue
        entries.append(entry_day)
        next_ok = entry_day + pd.Timedelta(days=hold_days)
    return entries


def simulate(spot: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float) -> dict:
    capital = 1.0
    units = 0.0
    in_position = False
    entry_price = None
    entry_time = None
    exit_target = None
    trade_log = []
    equity_curve = []

    entry_set = set(entries)
    opens = spot["open"]
    closes = spot["close"]
    times = spot.index

    for i, ts in enumerate(times):
        if in_position and ts >= exit_target:
            exec_price = float(closes.iloc[i]) * (1 - one_way_cost)
            proceeds = units * exec_price
            trade_log.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exec_price,
                    "gross_return": exec_price / entry_price - 1.0,
                }
            )
            capital = proceeds
            units = 0.0
            in_position = False
        if (not in_position) and ts in entry_set and ts.hour == 0:
            exec_price = float(opens.iloc[i]) * (1 + one_way_cost)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_time = ts
            exit_target = ts + pd.Timedelta(days=hold_days)
        equity = capital + units * float(closes.iloc[i])
        equity_curve.append({"timestamp": ts, "equity": equity})

    if in_position:
        exec_price = float(closes.iloc[-1]) * (1 - one_way_cost)
        proceeds = units * exec_price
        trade_log.append(
            {
                "entry_time": entry_time,
                "exit_time": times[-1],
                "entry_price": entry_price,
                "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
            }
        )
        capital = proceeds

    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    trades_df = pd.DataFrame(trade_log)
    return {"equity": equity_df, "trades": trades_df, "final_capital": capital}


def buy_and_hold(frame: pd.DataFrame) -> dict:
    closes = frame["close"]
    start_price = float(closes.iloc[0])
    equity = closes / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


def daily_dca(frame: pd.DataFrame, one_way_cost: float) -> dict:
    daily_slots = frame[frame.index.hour == 0]
    if daily_slots.empty:
        daily_slots = frame.iloc[::24]
    n = len(daily_slots)
    tranche = 1.0 / n
    cash = 0.0
    units = 0.0
    equity_curve = []
    opens = frame["open"]
    closes = frame["close"]
    times = frame.index
    slot_set = set(daily_slots.index)
    for i, ts in enumerate(times):
        if ts in slot_set:
            cash += tranche
            exec_price = float(opens.iloc[i]) * (1 + one_way_cost)
            units += cash / exec_price
            cash = 0.0
        equity_curve.append({"timestamp": ts, "equity": cash + units * float(closes.iloc[i])})
    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    return {"equity": equity_df, "final_capital": float(equity_df["equity"].iloc[-1])}


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: float) -> dict:
    if equity_df.empty or len(equity_df) < 2:
        return {"total_return": float("nan"), "sharpe": float("nan"), "sortino": float("nan"), "max_drawdown": float("nan")}
    equity = equity_df["equity"]
    rets = equity.pct_change().dropna()
    mean_r = rets.mean()
    std_r = rets.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(bars_per_year) if std_r > 0 else float("nan")
    downside = rets.clip(upper=0.0)
    downside_dev = np.sqrt((downside**2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(bars_per_year) if downside_dev > 0 else float("nan")
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    return {"total_return": total_return, "sharpe": sharpe, "sortino": sortino, "max_drawdown": float(dd.min())}


def exclude_best_trade_final_capital(spot: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float) -> tuple[float, float]:
    if not entries:
        return float("nan"), float("nan")
    result = simulate(spot, entries, hold_days, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"], float("nan")
    best_idx = trades["gross_return"].idxmax()
    total_pnl = result["final_capital"] - 1.0
    best_leg_return = trades.loc[best_idx, "gross_return"]
    remaining_entries = [e for i, e in enumerate(entries) if i != best_idx]
    result_excl = simulate(spot, remaining_entries, hold_days, one_way_cost)
    top_trade_pnl_share = float("nan")
    if total_pnl != 0:
        top_trade_pnl_share = (result["final_capital"] - result_excl["final_capital"]) / total_pnl
    return result_excl["final_capital"], top_trade_pnl_share


def run_for_asset(coin: str) -> dict:
    oi = load_oi(coin)
    spot = load_spot(coin)
    start = OI_COVERAGE_START[coin]
    oi = oi[oi.index >= start]
    spot = spot[spot.index >= start]
    bars_per_year = 365.25 * 24

    signal = build_signal(oi)
    entries = non_overlapping_entries(signal, HOLD_DAYS)

    primary = simulate(spot, entries, HOLD_DAYS, ONE_WAY_COST)
    doubled = simulate(spot, entries, HOLD_DAYS, ONE_WAY_COST * 2)
    bh = buy_and_hold(spot)
    dca = daily_dca(spot, ONE_WAY_COST)
    excl_best_final, top_trade_pnl_share = exclude_best_trade_final_capital(spot, entries, HOLD_DAYS, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)
    metrics_dca = compute_metrics(dca["equity"], bars_per_year)

    test_entries = [e for e in entries if e >= TEST_START]
    test_spot = spot[spot.index >= TEST_START]
    test_bh = buy_and_hold(test_spot) if len(test_spot) > 48 else None
    test_res = simulate(test_spot, test_entries, HOLD_DAYS, ONE_WAY_COST) if len(test_spot) > 48 else None
    test_beats_bh = None
    if test_res is not None and test_bh is not None:
        test_beats_bh = bool(test_res["final_capital"] > test_bh["final_capital"])

    return {
        "asset": coin,
        "n_days": len(oi),
        "coverage_start": start,
        "n_trades": len(entries),
        "n_test_trades": len(test_entries),
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "exclude_best_trade_final": excl_best_final,
        "top_trade_pnl_share": top_trade_pnl_share,
        "bh_final": bh["final_capital"],
        "dca_final": dca["final_capital"],
        "primary_total_return": metrics_primary["total_return"],
        "primary_sharpe": metrics_primary["sharpe"],
        "primary_sortino": metrics_primary["sortino"],
        "primary_max_dd": metrics_primary["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "dca_total_return": metrics_dca["total_return"],
        "dca_sharpe": metrics_dca["sharpe"],
        "beats_bh": bool(primary["final_capital"] > bh["final_capital"]),
        "beats_dca": bool(primary["final_capital"] > dca["final_capital"]),
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh["final_capital"]),
        "beats_bh_excl_best_trade": bool(excl_best_final > bh["final_capital"]) if not np.isnan(excl_best_final) else False,
        "test_beats_bh": test_beats_bh,
        "trades": primary["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "retail_ratio_contrarian" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for coin, res in results.items():
        summary_rows.append({k: v for k, v in res.items() if k != "trades"})
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)

    print(summary_df.to_string(index=False))

    n_pass_gates = 0
    n_zero_holdout = 0
    n_concentration_fail = 0
    per_asset_verdicts = {}
    for coin, res in results.items():
        gates = [
            res["beats_bh"],
            res["beats_dca"],
            res["beats_bh_doubled_cost"],
            res["beats_bh_excl_best_trade"],
        ]
        zero_holdout = res["n_test_trades"] == 0
        conc_fail = (not np.isnan(res["top_trade_pnl_share"])) and abs(res["top_trade_pnl_share"]) > 0.20
        if zero_holdout:
            n_zero_holdout += 1
        if conc_fail:
            n_concentration_fail += 1
        passed = all(gates) and not zero_holdout and not conc_fail and (res["test_beats_bh"] is not False)
        if passed:
            n_pass_gates += 1
        per_asset_verdicts[coin] = "PASS" if passed else "FAIL"

    print(f"\nPer-asset gate outcome: {per_asset_verdicts}")
    print(f"Assets with zero test-partition trades: {n_zero_holdout}/4")
    print(f"Assets failing concentration cap (|top trade PnL share| > 20%): {n_concentration_fail}/4")

    if n_pass_gates >= 3:
        verdict = "CANDIDATE"
    elif n_pass_gates >= 1:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nAssets passing ALL gates: {n_pass_gates}/4")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"per_asset_verdicts={per_asset_verdicts}\n")
        f.write(f"n_pass_gates={n_pass_gates}\nn_zero_holdout={n_zero_holdout}\n")
        f.write(f"n_concentration_fail={n_concentration_fail}\nverdict={verdict}\n")

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
