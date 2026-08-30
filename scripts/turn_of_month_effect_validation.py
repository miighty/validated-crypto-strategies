"""EXP-2026-08-30-TOM-001: Crypto turn-of-month calendar effect.

Hypothesis (preregistered, genuinely new for this repo -- never tested here;
distinct mechanism from every prior calendar study: WEEKEND-EFFECT and
US-SESSION-EFFECT both tested *intra-week* liquidity/session timing and were
both REJECTED. This tests a *monthly* institutional-flow-cycle mechanism
(Ariel 1987 "turn-of-month" effect, well documented in TradFi equities):
  Recurring end-of-month/start-of-month capital flows -- payroll-cycle
  retail DCA, institutional month-end rebalancing/settlement, index and
  fund NAV-strike-driven buying -- concentrate a disproportionate share of
  an asset's return in a narrow window spanning the last calendar day of
  the month through the first few calendar days of the next month. A rule
  that holds long ONLY during this turn-of-month window and cash otherwise
  should beat continuous buy-and-hold after realistic round-trip costs,
  because it captures the disproportionate-return window while avoiding
  costless "dead" time in between (unlike the already-rejected weekday/
  session rules, this rule trades only ~12 times/year, not thousands).

Design (frozen before any result was inspected):
  - Universe: BTC, ETH, SOL, XRP (already-cached real Binance spot 1d
    OHLCV, data/raw/*_1d.csv.gz). No proxy/synthetic data.
  - Turn-of-month window (classic Ariel definition, adapted to crypto's
    24/7 daily bars since there is no trading-day/weekend distinction to
    make here): the LAST calendar day of the month through the 3rd
    calendar day of the following month, inclusive (4 calendar days total
    per month transition). This is a purely calendar-based, known-in-advance
    rule -- no lookahead.
  - Primary rule: long ONLY during the turn-of-month window; cash the rest
    of the month. Enter at the window's first daily open, exit at the day
    immediately following the window's last day (i.e. exit at the open of
    day 4 of the new month).
  - Costs: repo-standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE).
  - Benchmark: continuous buy-and-hold, same asset, same window.
  - Partitions (matching repo convention):
      development: earliest available -> 2020-01-01
      validation:  2020-01-01 -> 2024-01-01
      test:        2024-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Falsification (preregistered): primary rule must beat continuous
    buy-and-hold after costs on ALL FOUR assets, survive doubled round-trip
    costs, not lose to buy-and-hold in the test partition on any asset, and
    retain a positive best-trade-excluded edge (no single-month concentration
    artifact, given this program's repeated concentration-artifact findings
    e.g. SMA-200). Any single failure -> REJECTED (or PROMISING BUT
    INCONCLUSIVE if it is a narrow, sample-limited near-miss).
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
VALIDATION_START = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")

TOM_TAIL_DAYS = 1   # last N calendar days of the month included
TOM_HEAD_DAYS = 3   # first N calendar days of the following month included


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_tom_flag(index: pd.DatetimeIndex) -> pd.Series:
    """True on days in [last TOM_TAIL_DAYS days of month] union
    [first TOM_HEAD_DAYS days of following month]. Purely calendar based."""
    days_in_month = index.days_in_month
    day = index.day
    is_tail = day > (days_in_month - TOM_TAIL_DAYS)
    is_head = day <= TOM_HEAD_DAYS
    return pd.Series(is_tail | is_head, index=index, name="is_tom")


def simulate_rule(frame: pd.DataFrame, one_way_cost: float) -> dict:
    tom_flag = build_tom_flag(frame.index)
    want_long = tom_flag.to_numpy()

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

    for i in range(len(frame)):
        target_long = bool(want_long[i])
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


def partition_slice(frame: pd.DataFrame, start: pd.Timestamp | None, end: pd.Timestamp | None) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= frame.index >= start
    if end is not None:
        mask &= frame.index < end
    return frame.loc[mask]


def best_trade_excluded_final(trades_df: pd.DataFrame, one_way_cost: float) -> float:
    """Recompute compounded final capital excluding the single best trade
    (by gross_return), to detect concentration artifacts."""
    if trades_df.empty:
        return float("nan")
    idx_best = trades_df["gross_return"].idxmax()
    filtered = trades_df.drop(index=idx_best)
    if filtered.empty:
        return 1.0
    capital = 1.0
    for _, row in filtered.iterrows():
        net_mult = (1 + row["gross_return"])
        capital *= net_mult
    return capital


def run_for_asset(coin: str) -> dict:
    frame = load_asset(coin)
    bars_per_year = 365.25

    rule = simulate_rule(frame, ONE_WAY_COST)
    rule_doubled = simulate_rule(frame, ONE_WAY_COST * 2)
    bh = buy_and_hold(frame)

    metrics_rule = compute_metrics(rule["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)

    best_excluded_final = best_trade_excluded_final(rule["trades"], ONE_WAY_COST)

    partitions = {
        "development": (None, VALIDATION_START),
        "validation_2020_2024": (VALIDATION_START, TEST_START),
        "test_2024_2026": (TEST_START, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pframe = partition_slice(frame, pstart, pend)
        if len(pframe) < 60:
            continue
        p_rule = simulate_rule(pframe, ONE_WAY_COST)
        p_bh = buy_and_hold(pframe)
        p_metrics_rule = compute_metrics(p_rule["equity"], bars_per_year)
        p_metrics_bh = compute_metrics(p_bh["equity"], bars_per_year)
        partition_rows.append({
            "asset": coin, "partition": pname,
            "n_bars": len(pframe),
            "rule_total_return": p_metrics_rule["total_return"],
            "rule_sharpe": p_metrics_rule["sharpe"],
            "bh_total_return": p_metrics_bh["total_return"],
            "bh_sharpe": p_metrics_bh["sharpe"],
            "rule_beats_bh": bool(p_rule["final_capital"] > p_bh["final_capital"]),
        })

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "n_trades": len(rule["trades"]),
        "rule_final": rule["final_capital"],
        "bh_final": bh["final_capital"],
        "rule_doubled_cost_final": rule_doubled["final_capital"],
        "rule_best_trade_excluded_final": best_excluded_final,
        "rule_total_return": metrics_rule["total_return"],
        "rule_sharpe": metrics_rule["sharpe"],
        "rule_sortino": metrics_rule["sortino"],
        "rule_max_dd": metrics_rule["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "bh_max_dd": metrics_bh["max_drawdown"],
        "rule_beats_bh": bool(rule["final_capital"] > bh["final_capital"]),
        "rule_beats_bh_doubled_cost": bool(rule_doubled["final_capital"] > bh["final_capital"]),
        "rule_survives_best_trade_exclusion": bool(best_excluded_final > 1.0),
        "partition_rows": partition_rows,
        "trades": rule["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "turn_of_month_effect" / "runs"
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
            "rule_final": res["rule_final"], "bh_final": res["bh_final"],
            "rule_doubled_cost_final": res["rule_doubled_cost_final"],
            "rule_best_trade_excluded_final": res["rule_best_trade_excluded_final"],
            "rule_total_return": res["rule_total_return"],
            "rule_sharpe": res["rule_sharpe"], "rule_sortino": res["rule_sortino"],
            "rule_max_dd": res["rule_max_dd"],
            "bh_total_return": res["bh_total_return"], "bh_sharpe": res["bh_sharpe"],
            "bh_max_dd": res["bh_max_dd"],
            "rule_beats_bh": res["rule_beats_bh"],
            "rule_beats_bh_doubled_cost": res["rule_beats_bh_doubled_cost"],
            "rule_survives_best_trade_exclusion": res["rule_survives_best_trade_exclusion"],
        })
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_tom_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    beats_all = bool(summary_df["rule_beats_bh"].all())
    beats_doubled = bool(summary_df["rule_beats_bh_doubled_cost"].all())
    survives_concentration = bool(summary_df["rule_survives_best_trade_exclusion"].all())
    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test_2024_2026"]["rule_beats_bh"].all()
    )
    all_pass = beats_all and beats_doubled and test_pass and survives_concentration
    n_pass_checks = sum([beats_all, beats_doubled, test_pass, survives_concentration])
    if all_pass:
        verdict = "CANDIDATE"
    elif n_pass_checks >= 3:
        verdict = "PROMISING_BUT_INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nBeats B&H on all 4 assets: {beats_all}; Survives doubled cost: {beats_doubled}; "
          f"Test partition pass: {test_pass}; Survives best-trade exclusion: {survives_concentration}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_all_assets={beats_all}\nbeats_doubled_cost={beats_doubled}\n"
            f"test_partition_pass={test_pass}\nsurvives_best_trade_exclusion={survives_concentration}\n"
            f"verdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
