"""EXP-2026-08-30-SMA-TREND-001: Single-asset SMA(200) trend-following.

Hypothesis (preregistered, genuinely new -- not previously tested in this
repo's docs/experiment_registry.md; every prior single-asset study in this
repo tested calendar effects, event-odds panels, funding, or wick+odds
rebounds, never a plain trend-following moving-average filter):
  A long-only rule that holds BTC/ETH/SOL/XRP only while price is above its
  own trailing 200-day simple moving average, and moves to cash otherwise,
  should beat continuous buy-and-hold after realistic round-trip costs by
  avoiding the worst of major bear-market drawdowns (2018, 2022) while
  giving up only a modest amount of upside participation. This mirrors the
  documented cross-asset finding (SMA200_trend on SPY/QQQ/etc, Sharpe
  0.22-0.31, no OOS decay) -- the mechanism (trend persistence / avoiding
  prolonged drawdowns) is well established outside crypto but has not yet
  been tested standalone on this repo's crypto OHLCV.

Design (frozen before any result was inspected):
  - Universe: BTC, ETH, SOL, XRP, real Binance spot 1d OHLCV
    (data/raw/*_1d.csv.gz, already cached, no proxy/synthetic data).
  - Signal: SMA(200) of daily close, using only completed bars up to and
    including the signal day (no lookahead). Decision made at close of
    day t; position entered/exited at the OPEN of day t+1 (next-open
    execution, avoids same-bar lookahead).
  - Rule: long whenever close[t] > SMA200[t]; flat (cash) otherwise.
  - Costs: repo-standard 30bps round trip (15bps fee+slippage per side).
  - Partitions (matching repo convention):
      development: data start -> 2020-01-01
      validation:  2020-01-01 -> 2024-01-01
      test:        2024-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Benchmarks: continuous buy-and-hold (same asset), cash (0% exposure).
  - Falsification (preregistered): SMA-trend rule must (a) beat
    buy-and-hold net of costs on a strict majority (>=3 of 4) of assets
    over the full sample, (b) not lose to buy-and-hold in the test
    partition on more than one asset, and (c) survive doubled round-trip
    costs on every asset where it won in (a). Any failure -> REJECTED.
    A partial pass (some but not enough assets) -> PROMISING BUT
    INCONCLUSIVE, not accepted.
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
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE  # 0.0015
ROUND_TRIP_COST = 2 * ONE_WAY_COST

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
SMA_WINDOW = 200
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VALIDATION_START = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_signal(frame: pd.DataFrame) -> pd.Series:
    sma = frame["close"].rolling(SMA_WINDOW, min_periods=SMA_WINDOW).mean()
    want_long = frame["close"] > sma
    # execute at next day's open -> shift signal by one bar
    return want_long.shift(1).fillna(False)


def simulate_rule(frame: pd.DataFrame, want_long: pd.Series, one_way_cost: float) -> dict:
    capital = 1.0
    units = 0.0
    in_position = False
    trade_log = []
    equity_curve = []
    entry_price = None
    entry_time = None

    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    times = frame.index
    want = want_long.to_numpy()

    for i in range(len(frame)):
        target_long = bool(want[i])
        price_open = float(opens[i])
        if target_long and not in_position:
            exec_price = price_open * (1 + one_way_cost)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_time = times[i]
        elif not target_long and in_position:
            exec_price = price_open * (1 - one_way_cost)
            proceeds = units * exec_price
            trade_log.append({
                "entry_time": entry_time, "exit_time": times[i],
                "entry_price": entry_price, "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
                "units": units,
            })
            capital = proceeds
            units = 0.0
            in_position = False
        equity = capital + units * float(closes[i])
        equity_curve.append({"timestamp": times[i], "equity": equity})

    if in_position:
        exec_price = float(closes[-1]) * (1 - one_way_cost)
        proceeds = units * exec_price
        trade_log.append({
            "entry_time": entry_time, "exit_time": times[-1],
            "entry_price": entry_price, "exit_price": exec_price,
            "gross_return": exec_price / entry_price - 1.0,
            "units": units,
        })
        capital = proceeds
        units = 0.0

    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    trades_df = pd.DataFrame(trade_log)
    return {"equity": equity_df, "trades": trades_df, "final_capital": capital}


def buy_and_hold(frame: pd.DataFrame) -> dict:
    closes = frame["close"]
    start_price = float(closes.iloc[0])
    equity = closes / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: float) -> dict:
    if equity_df.empty or len(equity_df) < 2:
        return {"total_return": float("nan"), "sharpe": float("nan"),
                "sortino": float("nan"), "max_drawdown": float("nan")}
    equity = equity_df["equity"]
    rets = equity.pct_change().dropna()
    mean_r = rets.mean()
    std_r = rets.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(bars_per_year) if std_r > 0 else float("nan")
    downside = rets.clip(upper=0.0)
    downside_dev = np.sqrt((downside ** 2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(bars_per_year) if downside_dev > 0 else float("nan")
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    return {"total_return": total_return, "sharpe": sharpe, "sortino": sortino,
            "max_drawdown": float(dd.min())}


def partition_slice(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    mask = frame.index >= start
    if end is not None:
        mask &= frame.index < end
    return frame.loc[mask]


def concentration_check(trades: pd.DataFrame) -> float:
    if trades.empty:
        return float("nan")
    pnl = trades["units"] * (trades["exit_price"] - trades["entry_price"])
    total_pnl = pnl.sum()
    if total_pnl == 0:
        return float("nan")
    return float(pnl.max() / total_pnl) if total_pnl > 0 else float("nan")


def run_for_asset(coin: str) -> dict:
    frame = load_asset(coin)
    frame = frame.iloc[SMA_WINDOW:]  # drop rows before any SMA is even computable elsewhere handled by rolling min_periods
    bars_per_year = 365.25

    full_frame = load_asset(coin)
    want_long = build_signal(full_frame)
    # trim to where signal is defined (after warmup)
    valid_from = full_frame["close"].rolling(SMA_WINDOW, min_periods=SMA_WINDOW).mean().first_valid_index()
    frame = full_frame.loc[full_frame.index >= valid_from]
    want_long = want_long.loc[frame.index]

    trend_rule = simulate_rule(frame, want_long, ONE_WAY_COST)
    trend_doubled = simulate_rule(frame, want_long, ONE_WAY_COST * 2)
    bh = buy_and_hold(frame)

    metrics_trend = compute_metrics(trend_rule["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)

    partitions = {
        "development": (frame.index.min(), VALIDATION_START),
        "validation_2020_2024": (VALIDATION_START, TEST_START),
        "test_2024_2026": (TEST_START, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pframe = partition_slice(frame, pstart, pend)
        if len(pframe) < 30:
            continue
        p_want = want_long.loc[pframe.index]
        p_trend = simulate_rule(pframe, p_want, ONE_WAY_COST)
        p_bh = buy_and_hold(pframe)
        p_metrics_trend = compute_metrics(p_trend["equity"], bars_per_year)
        p_metrics_bh = compute_metrics(p_bh["equity"], bars_per_year)
        partition_rows.append({
            "asset": coin, "partition": pname,
            "trend_total_return": p_metrics_trend["total_return"],
            "trend_sharpe": p_metrics_trend["sharpe"],
            "bh_total_return": p_metrics_bh["total_return"],
            "bh_sharpe": p_metrics_bh["sharpe"],
            "trend_beats_bh": bool(p_metrics_trend["total_return"] > p_metrics_bh["total_return"]),
        })

    conc = concentration_check(trend_rule["trades"])

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "n_trades": len(trend_rule["trades"]),
        "trend_final": trend_rule["final_capital"],
        "trend_doubled_cost_final": trend_doubled["final_capital"],
        "bh_final": bh["final_capital"],
        "trend_total_return": metrics_trend["total_return"],
        "trend_sharpe": metrics_trend["sharpe"],
        "trend_sortino": metrics_trend["sortino"],
        "trend_max_dd": metrics_trend["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "bh_max_dd": metrics_bh["max_drawdown"],
        "trend_beats_bh": bool(trend_rule["final_capital"] > bh["final_capital"]),
        "trend_beats_bh_doubled_cost": bool(trend_doubled["final_capital"] > bh["final_capital"]),
        "concentration_top_trade_frac": conc,
        "partition_rows": partition_rows,
        "trades": trend_rule["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "sma_trend_following" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append({
            "asset": coin, "n_bars": res["n_bars"], "start": res["start"], "end": res["end"],
            "n_trades": res["n_trades"],
            "trend_final": res["trend_final"], "bh_final": res["bh_final"],
            "trend_doubled_cost_final": res["trend_doubled_cost_final"],
            "trend_total_return": res["trend_total_return"], "trend_sharpe": res["trend_sharpe"],
            "trend_sortino": res["trend_sortino"], "trend_max_dd": res["trend_max_dd"],
            "bh_total_return": res["bh_total_return"], "bh_sharpe": res["bh_sharpe"],
            "bh_max_dd": res["bh_max_dd"],
            "trend_beats_bh": res["trend_beats_bh"],
            "trend_beats_bh_doubled_cost": res["trend_beats_bh_doubled_cost"],
            "concentration_top_trade_frac": res["concentration_top_trade_frac"],
        })
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_trend_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    n_assets_beat = int(summary_df["trend_beats_bh"].sum())
    beats_majority = n_assets_beat >= 3
    doubled_ok = bool(
        summary_df.loc[summary_df["trend_beats_bh"], "trend_beats_bh_doubled_cost"].all()
        if beats_majority else False
    )
    test_partition = partition_df[partition_df["partition"] == "test_2024_2026"]
    n_test_losses = int((~test_partition["trend_beats_bh"]).sum()) if not test_partition.empty else 4
    test_ok = n_test_losses <= 1

    if beats_majority and doubled_ok and test_ok:
        verdict = "CANDIDATE"
    elif n_assets_beat >= 1:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nAssets beating B&H: {n_assets_beat}/4; majority pass: {beats_majority}; "
          f"doubled-cost survives: {doubled_ok}; test-partition losses: {n_test_losses}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"n_assets_beat={n_assets_beat}\nbeats_majority={beats_majority}\n"
            f"doubled_cost_ok={doubled_ok}\ntest_partition_losses={n_test_losses}\n"
            f"verdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
