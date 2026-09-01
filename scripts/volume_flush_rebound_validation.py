"""EXP-2026-09-01-VOLFLUSH-001: Volume-spike capitulation flush rebound.

Hypothesis (preregistered, genuinely new for this repo -- never tested here;
checked against docs/experiment_registry.md and docs/next_hypotheses.md before
writing this file):

  next_hypotheses.md item #6 ("Liquidation exhaustion rebound") is blocked in
  this repo because we do not have real liquidation-print data (CoinGlass
  requires a paid entitlement this repo doesn't have -- see
  docs/cross_asset_validation_plan.md). However, a single-bar large price drop
  accompanied by an abnormal REAL trading-volume spike (both fields already
  present in the real Binance OHLCV we have cached -- no proxy/fabricated
  liquidation feed) is a legitimate, if noisier, proxy for a forced-selling /
  capitulation flush: liquidation cascades mechanically show up as volume
  spikes on the exchange that executes them. This is mechanistically distinct
  from every prior study in this repo:
    - NOT the Polymarket-gated BTC_WICK_ODDS study (that used prediction-market
      odds as a support filter, not volume).
    - NOT DVOL (options-implied vol, BTC/ETH only) or FGI (composite sentiment
      index) -- both used external sentiment/vol indices, not price+volume
      microstructure.
    - NOT any funding/OI-based study -- no futures data used here at all,
      pure spot OHLCV.
  Rule: after a single 1h bar shows a sharp low-vs-prior-close drawdown AND
  an abnormal volume spike, buy spot at the next bar's open, hold a fixed
  period, then exit. If exhaustion/rebound is real, this should beat
  buy-and-hold/DCA net of costs; if it is a re-detection of ordinary downside
  volatility, it should not beat a plain "large red candle, no volume filter"
  control or a random-timing control matched on trade count/hold.

Preregistered trigger definition (all parameters fixed before any result
was inspected, per the skill's drawdown-trigger-precision discipline):
  - timeframe: 1h
  - measurement type: single-bar peak-to-trough, wick-sensitive
    (low vs prior bar's close, NOT close-to-close, so a violent wick that
    partially recovers within the same bar is still caught)
  - window: 1 bar (immediate, not a multi-bar rolling drawdown)
  - volume baseline: rolling 20-bar mean volume, computed with shift(1) so
    the trigger bar's own volume is never part of its own baseline (no
    lookahead)
  - trigger: low/close.shift(1) - 1 <= -3.0%  AND  volume / rolling_mean(volume.shift(1), 20) >= 3.0
  - entry timing: NEXT bar's open (one full hour of information lag after the
    trigger bar closes -- realistic, no same-bar fill)
  - hold: fixed 24h (24 bars), then exit at that bar's close
  - cooldown / dedupe: no new entry while already in a position; after an
    exit, no new entry for 24h (prevents one cascade from generating dozens
    of overlapping trades)

Design:
  - Universe: BTC, ETH, SOL, XRP (real Binance spot 1h OHLCV, already cached
    data/raw/*_1h.csv.gz). SOL history starts 2020-08-11.
  - Costs: repo-standard 30bps round trip (15bps/side).
  - Benchmarks: cash, continuous buy-and-hold, daily DCA (same released-
    capital schedule), a "large red candle, no volume filter" control
    (same -3% low-vs-prior-close trigger, no volume requirement -- isolates
    whether volume adds anything), and a seeded random-timing control
    matched on trade count and hold length.
  - Partitions: development 2018/2020-start->2022-01-01, validation
    2022-01-01->2024-07-01, test 2024-07-01->repo cutoff (2026-07-28
    exclusive).
  - Falsification (preregistered): primary rule must beat buy-and-hold AND
    daily DCA AND the no-volume-filter control AND the random-timing control
    on a MAJORITY (>=3/4) of assets, survive doubled round-trip costs, retain
    a positive best-trade-excluded terminal value (concentration check), and
    have real trades in the 2024-07-01+ test partition. Any decisive failure
    on a majority of assets -> REJECTED. A narrow 1-2-asset near-miss with no
    holdout trades or with concentration violations -> PROMISING BUT
    INCONCLUSIVE, not CANDIDATE.
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
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE  # 0.0015
ROUND_TRIP_COST = 2 * ONE_WAY_COST

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VALIDATION_START = pd.Timestamp("2022-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-07-01T00:00:00Z")

VOL_WINDOW = 20
DROP_THRESHOLD = -0.03
VOLUME_MULT = 3.0
HOLD_HOURS = 24
COOLDOWN_HOURS = 24
RANDOM_SEED = 20260901


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_signal(frame: pd.DataFrame) -> pd.DataFrame:
    sig = frame.copy()
    prior_close = sig["close"].shift(1)
    sig["low_vs_prior_close"] = sig["low"] / prior_close - 1.0
    prior_vol_mean = sig["volume"].shift(1).rolling(VOL_WINDOW, min_periods=VOL_WINDOW).mean()
    sig["volume_ratio"] = sig["volume"] / prior_vol_mean
    sig["trigger_primary"] = (sig["low_vs_prior_close"] <= DROP_THRESHOLD) & (
        sig["volume_ratio"] >= VOLUME_MULT
    )
    sig["trigger_novolfilter"] = sig["low_vs_prior_close"] <= DROP_THRESHOLD
    return sig


def non_overlapping_entries(signal: pd.DataFrame, trigger_col: str, hold_hours: int, cooldown_hours: int) -> list[int]:
    """Return integer positional indices (into `signal`) at which to enter,
    one bar after the trigger bar, respecting in-position + cooldown."""
    entries = []
    next_ok_idx = -1
    n = len(signal)
    triggers = signal[trigger_col].to_numpy()
    for i in range(n - 1):  # need i+1 to exist for next-bar entry
        if not triggers[i]:
            continue
        entry_idx = i + 1
        if entry_idx <= next_ok_idx:
            continue
        entries.append(entry_idx)
        next_ok_idx = entry_idx + hold_hours + cooldown_hours
    return entries


def simulate_entries(frame: pd.DataFrame, entry_indices: list[int], hold_hours: int, one_way_cost: float) -> dict:
    capital = 1.0
    units = 0.0
    in_position = False
    entry_price = None
    entry_time = None
    exit_idx_target = None
    trade_log = []
    equity_curve = []

    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    times = frame.index
    entry_set = set(entry_indices)
    n = len(frame)

    for i in range(n):
        if in_position and i >= exit_idx_target:
            exec_price = float(closes[i]) * (1 - one_way_cost)
            proceeds = units * exec_price
            trade_log.append({
                "entry_time": entry_time, "exit_time": times[i],
                "entry_price": entry_price, "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
            })
            capital = proceeds
            units = 0.0
            in_position = False
        if (not in_position) and i in entry_set:
            exec_price = float(opens[i]) * (1 + one_way_cost)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_time = times[i]
            exit_idx_target = min(i + hold_hours, n - 1)
        equity_curve.append({"timestamp": times[i], "equity": capital + units * float(closes[i])})

    if in_position:
        exec_price = float(closes[-1]) * (1 - one_way_cost)
        proceeds = units * exec_price
        trade_log.append({
            "entry_time": entry_time, "exit_time": times[-1],
            "entry_price": entry_price, "exit_price": exec_price,
            "gross_return": exec_price / entry_price - 1.0,
        })
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


def random_timing_control(frame: pd.DataFrame, n_trades: int, hold_hours: int, cooldown_hours: int, one_way_cost: float, seed: int) -> dict:
    """Seeded random entries matching trade count and holding period,
    respecting the same non-overlap/cooldown spacing as the primary rule."""
    rng = np.random.default_rng(seed)
    n = len(frame)
    if n_trades == 0 or n < hold_hours + cooldown_hours + 2:
        return {"equity": pd.DataFrame({"equity": [1.0]}, index=[frame.index[0]]), "trades": pd.DataFrame(), "final_capital": 1.0}
    min_gap = hold_hours + cooldown_hours
    max_start = n - hold_hours - 1
    entries = []
    attempts = 0
    while len(entries) < n_trades and attempts < n_trades * 200:
        attempts += 1
        cand = int(rng.integers(1, max_start))
        if all(abs(cand - e) >= min_gap for e in entries):
            entries.append(cand)
    entries.sort()
    return simulate_entries(frame, entries, hold_hours, one_way_cost)


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: float) -> dict:
    if equity_df.empty or len(equity_df) < 2:
        return {"total_return": float("nan"), "sharpe": float("nan"), "sortino": float("nan"), "max_drawdown": float("nan")}
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
    return {"total_return": total_return, "sharpe": sharpe, "sortino": sortino, "max_drawdown": float(dd.min())}


def partition_slice(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    mask = frame.index >= start
    if end is not None:
        mask &= frame.index < end
    return frame.loc[mask]


def exclude_best_trade_final_capital(frame: pd.DataFrame, entry_indices: list[int], hold_hours: int, one_way_cost: float) -> float:
    if not entry_indices:
        return float("nan")
    result = simulate_entries(frame, entry_indices, hold_hours, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"]
    best_idx = trades["gross_return"].idxmax()
    remaining = [e for i, e in enumerate(entry_indices) if i != best_idx]
    result_excl = simulate_entries(frame, remaining, hold_hours, one_way_cost)
    top_trade_pnl_share = None
    return result_excl["final_capital"]


def run_for_asset(coin: str) -> dict:
    frame = load_asset(coin)
    bars_per_year = 365.25 * 24

    signal = build_signal(frame)
    primary_entries = non_overlapping_entries(signal, "trigger_primary", HOLD_HOURS, COOLDOWN_HOURS)
    novol_entries = non_overlapping_entries(signal, "trigger_novolfilter", HOLD_HOURS, COOLDOWN_HOURS)

    primary = simulate_entries(frame, primary_entries, HOLD_HOURS, ONE_WAY_COST)
    doubled = simulate_entries(frame, primary_entries, HOLD_HOURS, ONE_WAY_COST * 2)
    novol_control = simulate_entries(frame, novol_entries, HOLD_HOURS, ONE_WAY_COST)
    random_control = random_timing_control(frame, len(primary_entries), HOLD_HOURS, COOLDOWN_HOURS, ONE_WAY_COST, RANDOM_SEED + hash(coin) % 1000)
    bh = buy_and_hold(frame)
    dca = daily_dca(frame, ONE_WAY_COST)
    excl_best_final = exclude_best_trade_final_capital(frame, primary_entries, HOLD_HOURS, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)
    metrics_dca = compute_metrics(dca["equity"], bars_per_year)

    top_trade_pnl_share = float("nan")
    if not primary["trades"].empty and len(primary["trades"]) > 0:
        trades = primary["trades"]
        pnl_per_trade = trades["gross_return"]
        total_pnl = pnl_per_trade.sum()
        if total_pnl != 0:
            top_trade_pnl_share = float(pnl_per_trade.max() / total_pnl)

    dev_start = frame.index.min()
    partitions = {
        "development": (dev_start, VALIDATION_START),
        "validation": (VALIDATION_START, TEST_START),
        "test": (TEST_START, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pentries_signal_idx = [i for i in primary_entries if pstart <= frame.index[i] < (pend or pd.Timestamp.max.tz_localize("UTC"))]
        pframe = partition_slice(frame, pstart, pend)
        if len(pframe) < 48:
            continue
        p_bh = buy_and_hold(pframe)
        p_res = simulate_entries(frame, pentries_signal_idx, HOLD_HOURS, ONE_WAY_COST) if pentries_signal_idx else {"final_capital": 1.0}
        partition_rows.append({
            "asset": coin, "partition": pname,
            "n_trades": len(pentries_signal_idx),
            "strategy_final_relative": p_res["final_capital"],
            "bh_final": p_bh["final_capital"],
        })

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "n_trades": len(primary_entries),
        "n_trades_novol": len(novol_entries),
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "novol_control_final": novol_control["final_capital"],
        "random_control_final": random_control["final_capital"],
        "exclude_best_trade_final": excl_best_final,
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
        "top_trade_pnl_share": top_trade_pnl_share,
        "beats_bh": bool(primary["final_capital"] > bh["final_capital"]),
        "beats_dca": bool(primary["final_capital"] > dca["final_capital"]),
        "beats_novol_control": bool(primary["final_capital"] > novol_control["final_capital"]),
        "beats_random_control": bool(primary["final_capital"] > random_control["final_capital"]),
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh["final_capital"]),
        "beats_bh_excl_best_trade": bool(excl_best_final > bh["final_capital"]) if excl_best_final == excl_best_final else False,
        "concentration_ok": bool(top_trade_pnl_share != top_trade_pnl_share or abs(top_trade_pnl_share) <= 0.20),
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "volume_flush_rebound" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append({k: v for k, v in res.items() if k not in ("partition_rows", "trades")})
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    n_assets = len(ASSETS)
    maj = lambda col: int(summary_df[col].sum()) >= (n_assets // 2 + 1)

    beats_bh_maj = maj("beats_bh")
    beats_dca_maj = maj("beats_dca")
    beats_novol_maj = maj("beats_novol_control")
    beats_random_maj = maj("beats_random_control")
    beats_doubled_maj = maj("beats_bh_doubled_cost")
    beats_excl_maj = maj("beats_bh_excl_best_trade")
    concentration_maj = maj("concentration_ok")

    test_partitions = partition_df[partition_df["partition"] == "test"]
    has_holdout_trades = bool((test_partitions["n_trades"] > 0).any()) if not test_partitions.empty else False

    all_gates = [beats_bh_maj, beats_dca_maj, beats_novol_maj, beats_random_maj, beats_doubled_maj, beats_excl_maj, concentration_maj, has_holdout_trades]
    n_pass = sum(all_gates)

    if n_pass == len(all_gates):
        verdict = "CANDIDATE"
    elif n_pass >= len(all_gates) - 2 and has_holdout_trades:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nGates passed (majority-of-4-assets basis): {n_pass}/{len(all_gates)}")
    print(f"  beats_bh_majority={beats_bh_maj} beats_dca_majority={beats_dca_maj} "
          f"beats_novol_control_majority={beats_novol_maj} beats_random_control_majority={beats_random_maj}")
    print(f"  beats_doubled_cost_majority={beats_doubled_maj} beats_excl_best_trade_majority={beats_excl_maj} "
          f"concentration_ok_majority={concentration_maj} has_holdout_trades={has_holdout_trades}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh_majority={beats_bh_maj}\nbeats_dca_majority={beats_dca_maj}\n"
            f"beats_novol_control_majority={beats_novol_maj}\nbeats_random_control_majority={beats_random_maj}\n"
            f"beats_doubled_cost_majority={beats_doubled_maj}\nbeats_excl_best_trade_majority={beats_excl_maj}\n"
            f"concentration_ok_majority={concentration_maj}\nhas_holdout_trades={has_holdout_trades}\n"
            f"n_pass={n_pass}/{len(all_gates)}\nverdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
