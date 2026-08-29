"""EXP-2026-08-29-WEEKEND-001: Crypto weekend liquidity-withdrawal effect.

Hypothesis (preregistered, genuinely new -- not previously tested in this
repo's docs/experiment_registry.md):
  Crypto trades 24/7, but the participants who provide the deepest liquidity
  and the most persistent directional demand (spot ETF authorized
  participants, CME/CFTC-regulated futures desks, options market-makers,
  TradFi-linked funds) are largely absent on weekends. This should show up
  as weekend price action carrying a return/risk profile inferior to
  weekday price action -- i.e. an investor who is long only Monday 00:00 UTC
  through Friday 24:00 UTC and flat (cash) over the weekend should do at
  least as well as continuous buy-and-hold, net of the round-trip cost of
  exiting/re-entering ~52 times/year, because the "removed" weekend segment
  contributes disproportionately little (or negative) return relative to
  its volatility/drawdown contribution.

Design (frozen before any result was inspected):
  - Universe: BTC, ETH, SOL, XRP (already-cached real Binance spot 1h OHLCV,
    data/raw/*_1h.csv.gz). SOL history starts 2020-08-11; BTC/ETH/XRP/others
    start 2018-01-01 (or later real listing date). No proxy/synthetic data.
  - Weekday-only rule (primary): flat over the weekend window
    [Saturday 00:00 UTC, Monday 00:00 UTC). Sell the full position at the
    Saturday 00:00 UTC open; buy back the full position at the Monday 00:00
    UTC open. Otherwise stay continuously long (no other timing signal).
    This is a pure calendar rule -- the weekday/weekend boundary is known
    with certainty in advance, so there is no lookahead.
  - Weekend-only rule (secondary / directionally opposite control): the
    mirror-image rule, long only Saturday 00:00 UTC -> Monday 00:00 UTC,
    cash the rest of the week. Included to characterize which regime (if
    either) carries the return, not just to test one direction.
  - Costs: repo-standard 30bps round trip (15bps fee+slippage per side,
    FEE_RATE+SLIPPAGE_RATE = ONE_WAY_COST), charged on every entry and exit.
  - Partitions (matching this repo's existing convention):
      development: 2018-01-01 -> 2020-01-01 (BTC/ETH/XRP only; SOL lacks
        history here and is excluded from this partition's assessment)
      validation:  2020-01-01 -> 2024-01-01
      test:        2024-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Benchmark: continuous buy-and-hold, same asset, same window.
  - Falsification (preregistered): weekday-only rule must beat continuous
    buy-and-hold after costs on ALL FOUR assets, AND must not lose to
    buy-and-hold in the test partition on any asset, AND must survive
    doubled round-trip costs. Any single failure -> REJECTED.
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
ROUND_TRIP_COST = 2 * ONE_WAY_COST       # 0.003

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
DEV_START = pd.Timestamp("2018-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def is_weekend_bar(ts: pd.DatetimeIndex) -> np.ndarray:
    # weekend window = Sat 00:00 UTC (inclusive) through Mon 00:00 UTC (exclusive)
    return np.isin(ts.weekday, [5, 6])


def build_regime_flag(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(is_weekend_bar(index), index=index, name="is_weekend")


def simulate_calendar_rule(
    frame: pd.DataFrame, hold_when: str, one_way_cost: float
) -> dict:
    """hold_when: 'weekday' -> long Mon00:00-Sat00:00, cash Sat00:00-Mon00:00.
    'weekend' -> long Sat00:00-Mon00:00, cash the rest."""
    weekend_flag = build_regime_flag(frame.index)
    if hold_when == "weekday":
        want_long = ~weekend_flag
    else:
        want_long = weekend_flag

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

    # close out any open position at the final close
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
    final_capital = capital
    return {"equity": equity_df, "trades": trades_df, "final_capital": final_capital}


def buy_and_hold(frame: pd.DataFrame) -> dict:
    closes = frame["close"]
    start_price = float(closes.iloc[0])
    equity = closes / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: float) -> dict:
    if equity_df.empty or len(equity_df) < 2:
        return {"total_return": float("nan"), "sharpe": float("nan"), "sortino": float("nan"),
                "max_drawdown": float("nan")}
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


def run_for_asset(coin: str) -> dict:
    frame = load_asset(coin)
    bars_per_year = 365.25 * 24

    weekday_rule = simulate_calendar_rule(frame, "weekday", ONE_WAY_COST)
    weekend_rule = simulate_calendar_rule(frame, "weekend", ONE_WAY_COST)
    weekday_doubled = simulate_calendar_rule(frame, "weekday", ONE_WAY_COST * 2)
    bh = buy_and_hold(frame)

    metrics_weekday = compute_metrics(weekday_rule["equity"], bars_per_year)
    metrics_weekend = compute_metrics(weekend_rule["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)

    partitions = {
        "development_2018_2020": (DEV_START, VALIDATION_START),
        "validation_2020_2024": (VALIDATION_START, TEST_START),
        "test_2024_2026": (TEST_START, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pframe = partition_slice(frame, pstart, pend)
        if len(pframe) < 48:
            continue
        p_weekday = simulate_calendar_rule(pframe, "weekday", ONE_WAY_COST)
        p_bh = buy_and_hold(pframe)
        p_metrics_weekday = compute_metrics(p_weekday["equity"], bars_per_year)
        p_metrics_bh = compute_metrics(p_bh["equity"], bars_per_year)
        partition_rows.append({
            "asset": coin, "partition": pname,
            "weekday_total_return": p_metrics_weekday["total_return"],
            "weekday_sharpe": p_metrics_weekday["sharpe"],
            "bh_total_return": p_metrics_bh["total_return"],
            "bh_sharpe": p_metrics_bh["sharpe"],
            "weekday_beats_bh": bool(p_metrics_weekday["total_return"] > p_metrics_bh["total_return"]),
        })

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "n_trades_weekday": len(weekday_rule["trades"]),
        "weekday_final": weekday_rule["final_capital"],
        "weekend_final": weekend_rule["final_capital"],
        "weekday_doubled_cost_final": weekday_doubled["final_capital"],
        "bh_final": bh["final_capital"],
        "weekday_total_return": metrics_weekday["total_return"],
        "weekday_sharpe": metrics_weekday["sharpe"],
        "weekday_sortino": metrics_weekday["sortino"],
        "weekday_max_dd": metrics_weekday["max_drawdown"],
        "weekend_total_return": metrics_weekend["total_return"],
        "weekend_sharpe": metrics_weekend["sharpe"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "bh_max_dd": metrics_bh["max_drawdown"],
        "weekday_beats_bh": bool(weekday_rule["final_capital"] > bh["final_capital"]),
        "weekday_beats_bh_doubled_cost": bool(weekday_doubled["final_capital"] > bh["final_capital"]),
        "partition_rows": partition_rows,
        "trades": weekday_rule["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "weekend_effect" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append({
            "asset": coin, "n_bars": res["n_bars"], "start": res["start"], "end": res["end"],
            "n_trades_weekday": res["n_trades_weekday"],
            "weekday_final": res["weekday_final"], "weekend_final": res["weekend_final"],
            "bh_final": res["bh_final"],
            "weekday_doubled_cost_final": res["weekday_doubled_cost_final"],
            "weekday_total_return": res["weekday_total_return"],
            "weekday_sharpe": res["weekday_sharpe"], "weekday_sortino": res["weekday_sortino"],
            "weekday_max_dd": res["weekday_max_dd"],
            "weekend_total_return": res["weekend_total_return"], "weekend_sharpe": res["weekend_sharpe"],
            "bh_total_return": res["bh_total_return"], "bh_sharpe": res["bh_sharpe"], "bh_max_dd": res["bh_max_dd"],
            "weekday_beats_bh": res["weekday_beats_bh"],
            "weekday_beats_bh_doubled_cost": res["weekday_beats_bh_doubled_cost"],
        })
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_weekday_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    beats_all = bool(summary_df["weekday_beats_bh"].all())
    beats_doubled = bool(summary_df["weekday_beats_bh_doubled_cost"].all())
    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test_2024_2026"]["weekday_beats_bh"].all()
    )
    verdict = "CANDIDATE" if (beats_all and beats_doubled and test_pass) else "REJECTED"
    print(f"\nBeats B&H on all 4 assets: {beats_all}; Survives doubled cost: {beats_doubled}; "
          f"Test partition pass: {test_pass}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_all_assets={beats_all}\nbeats_doubled_cost={beats_doubled}\n"
            f"test_partition_pass={test_pass}\nverdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
