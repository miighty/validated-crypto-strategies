"""EXP-2026-09-04-TAKERFLOWSPIKE-001: Aggressor-side (taker) buy-ratio EXTREME
z-score as a discrete event-trigger continuation signal (distinct from the
already-REJECTED slow-SMA taker-flow-trend regime filter).

Preflight: read docs/experiment_registry.md and docs/next_hypotheses.md in
full. Confirmed the slow-structural taker-flow construction
(EXP-2026-09-03-TAKERFLOW-001, fast-SMA3 vs slow-SMA14 regime filter) was
REJECTED. This is a genuinely different construction on the SAME already-
cached real data source (no new fetch): a discrete EVENT trigger (z-score
extreme of the daily taker-buy ratio vs its own trailing history) rather than
a slow trend-following regime state, mirroring how this program has
previously tested both "slow regime" and "fast event" constructions on OI
(all rejected) and top-trader/retail ratios.

Hypothesis (preregistered, genuinely new for this repo):
  A single day's aggressor-side (taker) buy-volume ratio spiking to an
  unusually high z-score vs its own trailing 90-day history reflects a burst
  of aggressive spot buying pressure that should predict short-term
  continuation (persistent informed/momentum buying, not mean reversion).

Design (frozen before any result was inspected):
  - Data: real Binance spot hourly klines already cached in this repo
    (data/taker_flow/{ASSET}_taker_flow_1h.csv.gz), BTC/ETH/SOL/XRP -- ZERO
    new fetch this run.
  - Signal (prior-only, no lookahead):
      daily_buy_ratio_t = volume-weighted taker_buy_base_volume / volume for
      day t (uses only bars within day t).
      z_t = (daily_buy_ratio_t - trailing_90d_mean_prior_only) / trailing_90d_std_prior_only
      (the trailing window for z_t is days [t-90, t-1], EXCLUDING day t
      itself, so the z-score cannot leak day t's own realized ratio into its
      own baseline).
  - Entry trigger: z_t >= +2.0 (extreme one-day aggressive-buying spike).
  - Execution: enter at day (t+1)'s 00:00 UTC open (one full day of lag from
    the trigger day's close), hold a fixed 5-day horizon, exit at day
    (t+1+5)'s open. Non-overlapping: no new entry accepted while a position
    is open. Cooldown: no new entry within 2 days of the last exit (avoid
    re-triggering on the tail of the same spike).
  - CRITICAL execution-delay robustness gate (added per this skill's
    "fast oscillator artifact" pitfall, since this is a single-bar-reactive
    trigger unlike the parent slow-SMA study): also run an identical variant
    with entry delayed ONE ADDITIONAL full day (day t+2's open instead of
    t+1's) and report Sharpe/return retention side by side as a first-pass
    screening gate, not deferred to a later deep-dive.
  - Costs: repo-standard 30bps round trip (15bps/side).
  - Partitions: development (first 50%), validation (next 30%), test (final
    20%) by row count, matching this program's existing partition
    convention.
  - Benchmarks: cash, buy-and-hold, a seeded random-timing control (same
    trade count / holding period, randomly placed, no overlap), and a naive
    BTC-price-momentum control is NOT applicable here (this is a fixed-
    horizon event trigger, not a regime filter) -- use the random-timing
    control as the primary "does timing add value" comparison, consistent
    with this program's event-trigger studies (volume-flush, panic-flush,
    stablecoin-depeg, NVT).
  - Falsification (preregistered): primary must beat buy-and-hold AND the
    random-timing control on a MAJORITY (>=3/4) of assets; survive doubled
    round-trip cost; retain >50% of its no-delay Sharpe (and stay positive)
    under the 1-extra-day delay gate; clear a 20% single-trade concentration
    cap (best-trade-exclusion result stays above buy-and-hold). Any decisive
    multi-gate failure -> REJECTED. A narrow 1-2-gate miss with otherwise-
    clean results -> PROMISING BUT INCONCLUSIVE.
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
Z_WINDOW = 90
Z_THRESHOLD = 2.0
HOLD_DAYS = 5
COOLDOWN_DAYS = 2
BASE_SEED = 20260904

TAKER_DIR = ROOT / "data" / "taker_flow"


def load_taker_flow(coin: str) -> pd.DataFrame:
    path = TAKER_DIR / f"{coin}_taker_flow_1h.csv.gz"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def load_daily(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_zscore_signal(hourly: pd.DataFrame) -> pd.DataFrame:
    daily_vol = hourly["volume"].resample("1D").sum()
    daily_buy_vol = hourly["taker_buy_base_volume"].resample("1D").sum()
    daily_buy_ratio = (daily_buy_vol / daily_vol.replace(0, np.nan)).rename("daily_buy_ratio")
    frame = daily_buy_ratio.to_frame()
    # prior-only trailing window: shift(1) before rolling so day t's baseline
    # excludes day t's own ratio
    prior = frame["daily_buy_ratio"].shift(1)
    frame["trail_mean"] = prior.rolling(Z_WINDOW, min_periods=Z_WINDOW).mean()
    frame["trail_std"] = prior.rolling(Z_WINDOW, min_periods=Z_WINDOW).std(ddof=1)
    frame["z"] = (frame["daily_buy_ratio"] - frame["trail_mean"]) / frame["trail_std"].replace(0, np.nan)
    frame = frame.dropna(subset=["z"])
    return frame


def generate_triggers(z_frame: pd.DataFrame) -> list[pd.Timestamp]:
    """Trigger days (t) where z_t >= threshold, with cooldown dedup."""
    triggers = z_frame.index[z_frame["z"] >= Z_THRESHOLD].tolist()
    deduped = []
    last_kept = None
    for t in triggers:
        if last_kept is None or (t - last_kept) > pd.Timedelta(days=COOLDOWN_DAYS):
            deduped.append(t)
            last_kept = t
    return deduped


def build_trades(trigger_days: list[pd.Timestamp], price_index: pd.DatetimeIndex,
                  entry_lag_days: int, hold_days: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Non-overlapping fixed-horizon trades from trigger days."""
    trades = []
    last_exit = None
    for t in trigger_days:
        entry_ts = t + pd.Timedelta(days=entry_lag_days)
        exit_ts = entry_ts + pd.Timedelta(days=hold_days)
        # snap to nearest available price index (next available bar on/after)
        entry_candidates = price_index[price_index >= entry_ts]
        exit_candidates = price_index[price_index >= exit_ts]
        if len(entry_candidates) == 0 or len(exit_candidates) == 0:
            continue
        entry_snap = entry_candidates[0]
        exit_snap = exit_candidates[0]
        if last_exit is not None and entry_snap < last_exit:
            continue  # overlap with existing position, skip
        if entry_snap >= exit_snap:
            continue
        trades.append((entry_snap, exit_snap))
        last_exit = exit_snap
    return trades


def simulate_trades(price: pd.Series, trades: list[tuple[pd.Timestamp, pd.Timestamp]],
                     one_way_cost: float) -> dict:
    rows = []
    for entry_ts, exit_ts in trades:
        entry_price = float(price.loc[entry_ts]) * (1 + one_way_cost)
        exit_price = float(price.loc[exit_ts]) * (1 - one_way_cost)
        gross_return = exit_price / entry_price - 1.0
        rows.append({"entry_time": entry_ts, "exit_time": exit_ts,
                     "entry_price": entry_price, "exit_price": exit_price,
                     "gross_return": gross_return})
    trades_df = pd.DataFrame(rows)
    if trades_df.empty:
        return {"trades": trades_df, "final_capital": 1.0, "equity": pd.Series([1.0], index=[price.index[0]])}
    capital = 1.0
    equity_points = [(price.index[0], 1.0)]
    for _, row in trades_df.iterrows():
        capital *= (1.0 + row["gross_return"])
        equity_points.append((row["exit_time"], capital))
    equity = pd.Series([v for _, v in equity_points], index=[t for t, _ in equity_points])
    return {"trades": trades_df, "final_capital": capital, "equity": equity}


def buy_and_hold(price: pd.Series) -> float:
    return float(price.iloc[-1] / price.iloc[0])


def trade_returns_sharpe(trades_df: pd.DataFrame, bars_per_year_equiv: float) -> float:
    if trades_df.empty or len(trades_df) < 2:
        return float("nan")
    r = trades_df["gross_return"]
    if r.std(ddof=1) == 0 or np.isnan(r.std(ddof=1)):
        return float("nan")
    # annualize using trade frequency (approx trades/year)
    return float(r.mean() / r.std(ddof=1) * np.sqrt(bars_per_year_equiv))


def random_trades(n_trades: int, hold_days: int, price_index: pd.DatetimeIndex, seed: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    rng = np.random.default_rng(seed)
    n = len(price_index)
    trades = []
    used = np.zeros(n, dtype=bool)
    attempts = 0
    while len(trades) < n_trades and attempts < n_trades * 200:
        attempts += 1
        start_pos = int(rng.integers(0, max(1, n - hold_days - 1)))
        end_pos = min(start_pos + hold_days, n - 1)
        if used[start_pos:end_pos + 1].any():
            continue
        used[start_pos:end_pos + 1] = True
        trades.append((price_index[start_pos], price_index[end_pos]))
    trades.sort(key=lambda b: b[0])
    return trades


def best_trade_excluded_final(trades_df: pd.DataFrame, one_way_cost: float) -> float:
    if trades_df.empty:
        return float("nan")
    best_idx = trades_df["gross_return"].abs().idxmax()
    remaining = trades_df.drop(index=best_idx)
    capital = 1.0
    for _, row in remaining.iterrows():
        capital *= (1.0 + row["gross_return"])
    return capital


def top_trade_pct_of_pnl(trades_df: pd.DataFrame) -> float:
    if trades_df.empty:
        return float("nan")
    r = trades_df["gross_return"]
    total = r.sum()
    if total == 0:
        return float("nan")
    return float(r.abs().max() / abs(total))


def partition_split(index: pd.DatetimeIndex) -> dict:
    n = len(index)
    dev_end = index[int(n * 0.5)]
    val_end = index[int(n * 0.8)]
    return {"development": (index.min(), dev_end), "validation": (dev_end, val_end), "test": (val_end, None)}


def run_for_asset(coin: str) -> dict:
    hourly = load_taker_flow(coin)
    zframe = build_zscore_signal(hourly)
    daily = load_daily(coin)
    price = daily["close"]
    price = price[price.index >= zframe.index.min()]

    triggers = generate_triggers(zframe)

    # primary: 1-day entry lag
    trades_primary = build_trades(triggers, price.index, entry_lag_days=1, hold_days=HOLD_DAYS)
    primary = simulate_trades(price, trades_primary, ONE_WAY_COST)

    # delay-robustness: 2-day entry lag (1 extra day)
    trades_delayed = build_trades(triggers, price.index, entry_lag_days=2, hold_days=HOLD_DAYS)
    delayed = simulate_trades(price, trades_delayed, ONE_WAY_COST)

    doubled = simulate_trades(price, trades_primary, ONE_WAY_COST * 2)
    bh_final = buy_and_hold(price)
    excl_best = best_trade_excluded_final(primary["trades"], ONE_WAY_COST)
    top_pct = top_trade_pct_of_pnl(primary["trades"])

    seed = BASE_SEED + (hash(coin) % 10_000)
    rand_trades = random_trades(len(trades_primary), HOLD_DAYS, price.index, seed)
    rand = simulate_trades(price, rand_trades, ONE_WAY_COST)

    trades_per_year_equiv = 365.25 / HOLD_DAYS
    sharpe_primary = trade_returns_sharpe(primary["trades"], trades_per_year_equiv)
    sharpe_delayed = trade_returns_sharpe(delayed["trades"], trades_per_year_equiv)

    partitions = partition_split(price.index)
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        ptrades = [(e, x) for e, x in trades_primary if e >= pstart and (pend is None or e < pend)]
        p_res = simulate_trades(price, ptrades, ONE_WAY_COST)
        p_bh = float(price[(price.index >= pstart) & (pend is None or price.index < pend)].pipe(
            lambda s: s.iloc[-1] / s.iloc[0] if len(s) > 1 else float("nan")))
        partition_rows.append({
            "asset": coin, "partition": pname, "n_trades": len(ptrades),
            "strategy_final": p_res["final_capital"], "bh_final": p_bh,
            "strategy_beats_bh": bool(p_res["final_capital"] > p_bh) if not np.isnan(p_bh) else None,
        })

    delay_retention = (sharpe_delayed / sharpe_primary) if (np.isfinite(sharpe_primary) and sharpe_primary != 0) else float("nan")

    return {
        "asset": coin,
        "n_triggers": len(triggers), "n_trades": len(trades_primary),
        "primary_final": primary["final_capital"], "delayed_final": delayed["final_capital"],
        "doubled_cost_final": doubled["final_capital"], "bh_final": bh_final,
        "random_control_final": rand["final_capital"], "excl_best_trade_final": excl_best,
        "top_trade_pct_of_pnl": top_pct,
        "sharpe_primary": sharpe_primary, "sharpe_delayed": sharpe_delayed,
        "delay_sharpe_retention": delay_retention,
        "beats_bh": bool(primary["final_capital"] > bh_final),
        "beats_random_control": bool(primary["final_capital"] > rand["final_capital"]),
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh_final),
        "beats_bh_excl_best_trade": bool(excl_best > bh_final) if np.isfinite(excl_best) else False,
        "concentration_ok": bool(not np.isfinite(top_pct) or top_pct <= 0.20),
        "delay_robust": bool(np.isfinite(delay_retention) and delay_retention > 0.5 and delayed["final_capital"] > 1.0),
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "taker_flow_spike_event" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append({k: v for k, v in res.items() if k not in ("partition_rows", "trades")})
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].to_csv(run_dir / f"{coin}_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    n_assets = len(summary_df)
    beats_bh_n = int(summary_df["beats_bh"].sum())
    beats_rand_n = int(summary_df["beats_random_control"].sum())
    beats_doubled_n = int(summary_df["beats_bh_doubled_cost"].sum())
    concentration_ok_n = int(summary_df["concentration_ok"].sum())
    beats_excl_best_n = int(summary_df["beats_bh_excl_best_trade"].sum())
    delay_robust_n = int(summary_df["delay_robust"].sum())

    test_partition = partition_df[partition_df["partition"] == "test"]
    test_pass_n = int(test_partition["strategy_beats_bh"].fillna(False).sum()) if not test_partition.empty else 0
    test_total = len(test_partition)

    majority = lambda x: x >= 3  # noqa: E731

    all_majority_gates = (
        majority(beats_bh_n) and majority(beats_rand_n) and majority(beats_doubled_n)
        and majority(concentration_ok_n) and majority(delay_robust_n)
        and (test_total == 0 or test_pass_n >= max(1, test_total - 1))
    )
    decisive_reject = (
        beats_bh_n <= 1 or beats_rand_n <= 1 or delay_robust_n <= 1
    )

    if all_majority_gates:
        verdict = "CANDIDATE"
    elif decisive_reject:
        verdict = "REJECTED"
    else:
        verdict = "PROMISING BUT INCONCLUSIVE"

    print(
        f"\nBeats B&H: {beats_bh_n}/{n_assets}; Beats random control: {beats_rand_n}/{n_assets}; "
        f"Survives doubled cost: {beats_doubled_n}/{n_assets}; Concentration OK: {concentration_ok_n}/{n_assets}; "
        f"Excl-best-trade ok: {beats_excl_best_n}/{n_assets}; Delay-robust: {delay_robust_n}/{n_assets}; "
        f"Test partition pass: {test_pass_n}/{test_total}"
    )
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh={beats_bh_n}/{n_assets}\nbeats_random_control={beats_rand_n}/{n_assets}\n"
            f"beats_doubled_cost={beats_doubled_n}/{n_assets}\nconcentration_ok={concentration_ok_n}/{n_assets}\n"
            f"beats_excl_best_trade={beats_excl_best_n}/{n_assets}\ndelay_robust={delay_robust_n}/{n_assets}\n"
            f"test_partition_pass={test_pass_n}/{test_total}\nverdict={verdict}\n"
        )

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
