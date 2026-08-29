"""EXP-2026-08-30-SESSION-001: US trading-session return concentration effect.

Hypothesis (preregistered, genuinely new -- not previously tested in this
repo's docs/experiment_registry.md; distinct mechanism from the already-
REJECTED weekend liquidity-withdrawal study, which tested weekday-vs-weekend
calendar days, not intraday session timing):
  Crypto trades 24/7, but the participants most likely to move price on
  persistent directional information (US spot-ETF authorized participants,
  CME/CFTC-regulated futures desks, US options market-makers, US-hours
  institutional order flow) are concentrated during US cash-equity market
  hours. This should show up as returns being disproportionately generated
  during the US session window versus the rest of the day -- i.e. an
  investor who is long only during the US session and flat (cash) the rest
  of each UTC day should do at least as well as continuous buy-and-hold,
  net of the round-trip cost of entering/exiting once per day.

Design (frozen before any result was inspected):
  - Universe: BTC, ETH, SOL, XRP (already-cached real Binance spot 1h OHLCV,
    data/raw/*_1h.csv.gz). No proxy/synthetic data.
  - US session window (primary, chosen a priori from NYSE cash-equity hours
    9:30am-4:00pm ET, rounded to whole UTC hours and widened slightly to
    cover both EST and EDT offsets so the rule does not need to track DST):
    [13:00 UTC, 21:00 UTC) each day -- 8 hourly bars long, 16 hourly bars
    flat, repeating every day. Enter long at the 13:00 UTC bar's open, exit
    to cash at the 21:00 UTC bar's open.
  - Non-US-session mirror control (secondary / directional check): long
    only during the complementary window [21:00 UTC, 13:00 UTC next day),
    cash during the US session. Included to characterize which part of the
    day actually carries the return, not just to test one direction.
  - Costs: repo-standard 30bps round trip (15bps fee+slippage per side,
    FEE_RATE+SLIPPAGE_RATE = ONE_WAY_COST), charged on every entry and exit.
  - Partitions (matching this repo's existing convention):
      development: 2018-01-01 -> 2020-01-01 (BTC/ETH/XRP only; SOL lacks
        history here and is excluded from this partition's assessment)
      validation:  2020-01-01 -> 2024-01-01
      test:        2024-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Benchmark: continuous buy-and-hold, same asset, same window.
  - Falsification (preregistered): US-session-only rule must beat continuous
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

US_SESSION_START_HOUR = 13  # 13:00 UTC inclusive
US_SESSION_END_HOUR = 21    # 21:00 UTC exclusive


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def is_us_session_bar(ts: pd.DatetimeIndex) -> np.ndarray:
    return (ts.hour >= US_SESSION_START_HOUR) & (ts.hour < US_SESSION_END_HOUR)


def build_regime_flag(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(is_us_session_bar(index), index=index, name="is_us_session")


def simulate_calendar_rule(
    frame: pd.DataFrame, hold_when: str, one_way_cost: float
) -> dict:
    """hold_when: 'us_session' -> long [13:00,21:00) UTC, cash otherwise.
    'off_session' -> mirror image, long [21:00,13:00) UTC, cash during US hours."""
    us_flag = build_regime_flag(frame.index)
    if hold_when == "us_session":
        want_long = us_flag
    else:
        want_long = ~us_flag

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

    session_rule = simulate_calendar_rule(frame, "us_session", ONE_WAY_COST)
    off_session_rule = simulate_calendar_rule(frame, "off_session", ONE_WAY_COST)
    session_doubled = simulate_calendar_rule(frame, "us_session", ONE_WAY_COST * 2)
    bh = buy_and_hold(frame)

    metrics_session = compute_metrics(session_rule["equity"], bars_per_year)
    metrics_off = compute_metrics(off_session_rule["equity"], bars_per_year)
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
        p_session = simulate_calendar_rule(pframe, "us_session", ONE_WAY_COST)
        p_bh = buy_and_hold(pframe)
        p_metrics_session = compute_metrics(p_session["equity"], bars_per_year)
        p_metrics_bh = compute_metrics(p_bh["equity"], bars_per_year)
        partition_rows.append({
            "asset": coin, "partition": pname,
            "session_total_return": p_metrics_session["total_return"],
            "session_sharpe": p_metrics_session["sharpe"],
            "bh_total_return": p_metrics_bh["total_return"],
            "bh_sharpe": p_metrics_bh["sharpe"],
            "session_beats_bh": bool(p_metrics_session["total_return"] > p_metrics_bh["total_return"]),
        })

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "n_trades_session": len(session_rule["trades"]),
        "session_final": session_rule["final_capital"],
        "off_session_final": off_session_rule["final_capital"],
        "session_doubled_cost_final": session_doubled["final_capital"],
        "bh_final": bh["final_capital"],
        "session_total_return": metrics_session["total_return"],
        "session_sharpe": metrics_session["sharpe"],
        "session_sortino": metrics_session["sortino"],
        "session_max_dd": metrics_session["max_drawdown"],
        "off_session_total_return": metrics_off["total_return"],
        "off_session_sharpe": metrics_off["sharpe"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "bh_max_dd": metrics_bh["max_drawdown"],
        "session_beats_bh": bool(session_rule["final_capital"] > bh["final_capital"]),
        "session_beats_bh_doubled_cost": bool(session_doubled["final_capital"] > bh["final_capital"]),
        "partition_rows": partition_rows,
        "trades": session_rule["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "us_session_effect" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append({
            "asset": coin, "n_bars": res["n_bars"], "start": res["start"], "end": res["end"],
            "n_trades_session": res["n_trades_session"],
            "session_final": res["session_final"], "off_session_final": res["off_session_final"],
            "bh_final": res["bh_final"],
            "session_doubled_cost_final": res["session_doubled_cost_final"],
            "session_total_return": res["session_total_return"],
            "session_sharpe": res["session_sharpe"], "session_sortino": res["session_sortino"],
            "session_max_dd": res["session_max_dd"],
            "off_session_total_return": res["off_session_total_return"],
            "off_session_sharpe": res["off_session_sharpe"],
            "bh_total_return": res["bh_total_return"], "bh_sharpe": res["bh_sharpe"], "bh_max_dd": res["bh_max_dd"],
            "session_beats_bh": res["session_beats_bh"],
            "session_beats_bh_doubled_cost": res["session_beats_bh_doubled_cost"],
        })
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_session_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    beats_all = bool(summary_df["session_beats_bh"].all())
    beats_doubled = bool(summary_df["session_beats_bh_doubled_cost"].all())
    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test_2024_2026"]["session_beats_bh"].all()
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
