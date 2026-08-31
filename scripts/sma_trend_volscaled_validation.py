"""EXP-2026-08-31-SMA-TREND-VOLSCALED-001: SMA(200) trend-following with
inverse-realized-vol position sizing (current-equity based, capped at 1x,
no leverage) -- a preregistered, explicit fix to the already-REJECTED plain
binary SMA(200) study (EXP-2026-08-30-SMA-TREND-001), per that study's own
follow-up note and the skill's position-sizing-ablation discipline.

Hypothesis (preregistered before any result was inspected):
  The plain binary SMA(200) rule (100% notional whenever price > SMA200,
  0% otherwise) was REJECTED not because the trend-following mechanism is
  false, but because a single all-in trade captured 130% of total PnL on
  every asset -- a concentration artifact of all-or-nothing sizing, not
  evidence the trend signal itself lacks value. Continuously scaling
  position size by inverse trailing realized volatility (current-equity
  based, capped at 100% notional -- never leveraged) should reduce this
  concentration by taking smaller positions exactly during the highest-
  volatility trades (which are disproportionately the ones that drove the
  artifact), while preserving the underlying long-when-trending signal.
  This is a genuinely distinct mechanism (continuous vol-scaled exposure)
  from the already-rejected binary version, not a cosmetic threshold tweak.

Design (frozen before any result was inspected):
  - Universe: BTC, ETH, SOL, XRP, real Binance spot 1d OHLCV
    (data/raw/*_1d.csv.gz, already cached, no proxy/synthetic data).
  - Trend signal: close[t] > SMA200[t] (completed bars only), decision
    shifted 1 day for next-day application (no lookahead).
  - Realized vol: rolling 21-day stdev of daily log returns, shifted 1 day
    (no lookahead) -- same window convention as this program's existing
    volatility-premium cross-sectional study.
  - Position weight: target_daily_vol (2%) / realized_vol_21d, clipped to
    [0, 1.0] (hard cap: no leverage, ever), multiplied by the (already
    shifted) trend signal. Sizing is CURRENT-EQUITY based (applied to that
    day's equity level), matching this program's documented finding that
    current-equity sizing outperforms peak-equity sizing on both Sharpe and
    drawdown.
  - Costs: repo-standard 30bps round-trip, applied to the fraction of
    notional turned over each day (|weight_t - weight_{t-1}|), matching the
    cost convention already used in this program's cross-sectional scripts.
  - Partitions (matching repo/prior-SMA-study convention):
      development: data start -> 2020-01-01
      validation:  2020-01-01 -> 2024-01-01
      test:        2024-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Benchmarks: continuous buy-and-hold (same asset), cash, and the
    already-rejected plain binary SMA(200) rule (for direct before/after
    comparison of the concentration fix).
  - Concentration check: group into contiguous long-exposure blocks
    (weight > 0), sum PnL per block, and require the single largest block's
    PnL not exceed 20% of total strategy PnL (identical cap/methodology to
    the rejected binary study, for apples-to-apples comparison).
  - Falsification (preregistered): the vol-scaled rule must (a) beat
    buy-and-hold net of costs on a strict majority (>=3 of 4) of assets over
    the full sample, (b) pass the 20% concentration cap on every asset where
    it wins in (a), and (c) survive doubled round-trip costs on those same
    assets. Failing any of these -> REJECTED. A partial pass -> PROMISING
    BUT INCONCLUSIVE.
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
ROUND_TRIP_COST = 2 * ONE_WAY_COST  # 0.003

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
SMA_WINDOW = 200
VOL_WINDOW = 21
TARGET_DAILY_VOL = 0.02  # 2% target daily vol, no leverage (weight capped at 1.0)
MAX_WEIGHT = 1.0
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VALIDATION_START = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_weights(frame: pd.DataFrame) -> pd.Series:
    close = frame["close"]
    sma = close.rolling(SMA_WINDOW, min_periods=SMA_WINDOW).mean()
    trend_long = (close > sma)
    log_ret = np.log(close / close.shift(1))
    realized_vol = log_ret.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std(ddof=1)
    raw_weight = (TARGET_DAILY_VOL / realized_vol).clip(upper=MAX_WEIGHT).fillna(0.0)
    weight = (trend_long.astype(float) * raw_weight).clip(lower=0.0, upper=MAX_WEIGHT)
    # Shift 1 day: decision made using data through close[t], applied to day t+1's return.
    return weight.shift(1).fillna(0.0)


def simulate_volscaled(frame: pd.DataFrame, weight: pd.Series, round_trip_cost: float) -> dict:
    close = frame["close"]
    daily_ret = close.pct_change().fillna(0.0)
    equity = 1.0
    prev_weight = 0.0
    records = []
    for ts in frame.index:
        w = float(weight.loc[ts])
        r = float(daily_ret.loc[ts])
        turnover = abs(w - prev_weight)
        cost = equity * turnover * round_trip_cost
        gross_pnl = equity * w * r
        equity_before = equity
        equity = equity + gross_pnl - cost
        records.append({
            "timestamp": ts, "weight": w, "daily_return": r, "turnover": turnover,
            "cost": cost, "gross_pnl": gross_pnl, "equity_before": equity_before,
            "equity": equity, "net_pnl": equity - equity_before,
        })
        prev_weight = w
    df = pd.DataFrame(records).set_index("timestamp")
    return {"equity": df[["equity"]], "detail": df, "final_capital": equity}


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


def concentration_check(detail: pd.DataFrame) -> float:
    """Group contiguous weight>0 exposure blocks; find the largest block's
    share of total net PnL, matching the rejected binary study's methodology."""
    if detail.empty:
        return float("nan")
    in_pos = (detail["weight"] > 0).astype(int)
    block_id = (in_pos.diff().fillna(in_pos.iloc[0]) != 0).cumsum()
    block_pnl = detail.groupby(block_id).apply(
        lambda g: g["net_pnl"].sum() if g["weight"].iloc[0] > 0 else 0.0
    )
    block_pnl = block_pnl[block_pnl != 0.0]
    total_pnl = detail["net_pnl"].sum()
    if total_pnl == 0 or block_pnl.empty:
        return float("nan")
    return float(block_pnl.max() / total_pnl) if total_pnl > 0 else float("nan")


def run_for_asset(coin: str) -> dict:
    full_frame = load_asset(coin)
    close = full_frame["close"]
    sma = close.rolling(SMA_WINDOW, min_periods=SMA_WINDOW).mean()
    log_ret = np.log(close / close.shift(1))
    vol = log_ret.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std(ddof=1)
    valid_from = pd.Series(sma.notna() & vol.notna(), index=full_frame.index)
    valid_from = valid_from[valid_from].index.min()
    frame = full_frame.loc[full_frame.index >= valid_from]

    weight = build_weights(full_frame).loc[frame.index]

    bars_per_year = 365.25
    vol_scaled = simulate_volscaled(frame, weight, ROUND_TRIP_COST)
    vol_scaled_doubled = simulate_volscaled(frame, weight, ROUND_TRIP_COST * 2)
    bh = buy_and_hold(frame)

    metrics_vs = compute_metrics(vol_scaled["equity"], bars_per_year)
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
        p_weight = weight.loc[pframe.index]
        p_vs = simulate_volscaled(pframe, p_weight, ROUND_TRIP_COST)
        p_bh = buy_and_hold(pframe)
        p_metrics_vs = compute_metrics(p_vs["equity"], bars_per_year)
        p_metrics_bh = compute_metrics(p_bh["equity"], bars_per_year)
        partition_rows.append({
            "asset": coin, "partition": pname,
            "vs_total_return": p_metrics_vs["total_return"],
            "vs_sharpe": p_metrics_vs["sharpe"],
            "bh_total_return": p_metrics_bh["total_return"],
            "bh_sharpe": p_metrics_bh["sharpe"],
            "vs_beats_bh": bool(p_metrics_vs["total_return"] > p_metrics_bh["total_return"]),
        })

    conc = concentration_check(vol_scaled["detail"])
    mean_weight = float(weight[weight.index >= valid_from].mean())
    pct_days_capped = float((weight >= MAX_WEIGHT - 1e-9).mean())

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "vs_final": vol_scaled["final_capital"],
        "vs_doubled_cost_final": vol_scaled_doubled["final_capital"],
        "bh_final": bh["final_capital"],
        "vs_total_return": metrics_vs["total_return"],
        "vs_sharpe": metrics_vs["sharpe"],
        "vs_sortino": metrics_vs["sortino"],
        "vs_max_dd": metrics_vs["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "bh_max_dd": metrics_bh["max_drawdown"],
        "vs_beats_bh": bool(vol_scaled["final_capital"] > bh["final_capital"]),
        "vs_beats_bh_doubled_cost": bool(vol_scaled_doubled["final_capital"] > bh["final_capital"]),
        "concentration_top_block_frac": conc,
        "mean_weight": mean_weight,
        "pct_days_at_cap": pct_days_capped,
        "partition_rows": partition_rows,
        "detail": vol_scaled["detail"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "sma_trend_volscaled" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append({
            "asset": coin, "n_bars": res["n_bars"], "start": res["start"], "end": res["end"],
            "vs_final": res["vs_final"], "bh_final": res["bh_final"],
            "vs_doubled_cost_final": res["vs_doubled_cost_final"],
            "vs_total_return": res["vs_total_return"], "vs_sharpe": res["vs_sharpe"],
            "vs_sortino": res["vs_sortino"], "vs_max_dd": res["vs_max_dd"],
            "bh_total_return": res["bh_total_return"], "bh_sharpe": res["bh_sharpe"],
            "bh_max_dd": res["bh_max_dd"],
            "vs_beats_bh": res["vs_beats_bh"],
            "vs_beats_bh_doubled_cost": res["vs_beats_bh_doubled_cost"],
            "concentration_top_block_frac": res["concentration_top_block_frac"],
            "mean_weight": res["mean_weight"], "pct_days_at_cap": res["pct_days_at_cap"],
        })
        all_partition_rows.extend(res["partition_rows"])
        res["detail"].assign(asset=coin).to_csv(run_dir / f"{coin}_volscaled_detail.csv")

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    n_assets_beat = int(summary_df["vs_beats_bh"].sum())
    beats_majority = n_assets_beat >= 3
    winners = summary_df.loc[summary_df["vs_beats_bh"]]
    concentration_ok = bool(
        (winners["concentration_top_block_frac"] <= 0.20).all()
        if beats_majority and not winners.empty else False
    )
    doubled_ok = bool(
        winners["vs_beats_bh_doubled_cost"].all() if beats_majority and not winners.empty else False
    )
    test_partition = partition_df[partition_df["partition"] == "test_2024_2026"]
    n_test_losses = int((~test_partition["vs_beats_bh"]).sum()) if not test_partition.empty else 4
    test_ok = n_test_losses <= 1

    if beats_majority and concentration_ok and doubled_ok and test_ok:
        verdict = "CANDIDATE"
    elif n_assets_beat >= 1:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nAssets beating B&H: {n_assets_beat}/4; majority pass: {beats_majority}; "
          f"concentration OK: {concentration_ok}; doubled-cost survives: {doubled_ok}; "
          f"test-partition losses: {n_test_losses}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"n_assets_beat={n_assets_beat}\nbeats_majority={beats_majority}\n"
            f"concentration_ok={concentration_ok}\ndoubled_cost_ok={doubled_ok}\n"
            f"test_partition_losses={n_test_losses}\nverdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
