"""EXP-2026-09-03-TAKERFLOW-001: Aggressor-side (taker) buy-volume-ratio trend
as a slow structural demand regime filter.

Preflight: read docs/experiment_registry.md and docs/next_hypotheses.md in
full before writing this. Confirmed this repo has never used Binance's
taker_buy_base_asset_volume field (aggressor-side trade classification --
who "crossed the spread" and paid the taker fee) as a signal. Every prior
positioning/flow study used derivatives data (funding, OI, top-trader/retail
ratios) or price/volume OHLCV alone; this is real SPOT trade-flow data,
distinct data source and distinct mechanism from all of them.

Hypothesis (preregistered, genuinely new for this repo):
  Binance's public klines endpoint discloses, per hourly bar, the fraction of
  base-asset trading volume initiated by market-buy (taker-buy) orders vs the
  total volume in that bar. A sustained excess of taker buying over taker
  selling (buy ratio > 0.5, aggregated over a slow rolling window) reflects
  persistent aggressive spot demand -- distinct from open interest (which
  reflects LEVERED positioning) and from funding (which reflects derivatives
  crowding), because this is unlevered SPOT order-flow aggression. Per the
  skill's explicit bias toward slow-moving/structural signals over fast
  single-bar oscillators (to avoid same-bar look-ahead artifacts), this is
  built as a 7-day rolling mean of the hourly taker-buy ratio, not a
  single-bar reading.

Design (frozen before any result was inspected):
  - Data: real Binance spot hourly klines including taker_buy_base_asset_volume
    (data/taker_flow/{ASSET}_taker_flow_1h.csv.gz, newly fetched this run via
    the public /api/v3/klines endpoint -- fields already returned by Binance's
    standard endpoint, no proxy/estimation), BTC/ETH/SOL/XRP, full available
    history matching each asset's existing OHLCV coverage.
  - Signal (computed once per completed UTC day, using only bars through and
    including that day -- no lookahead):
      hourly_buy_ratio = taker_buy_base_volume / volume  (per hour)
      daily_buy_ratio  = volume-weighted mean of hourly_buy_ratio over the day
      fast_sma = rolling 3-day mean of daily_buy_ratio
      slow_sma = rolling 14-day mean of daily_buy_ratio
      regime_on = fast_sma_t > slow_sma_t   (persistent buy-side dominance)
  - Execution: regime decided using data through day t's close; position
    entered/exited at day (t+1)'s 00:00 UTC open (matches the stablecoin-
    supply-trend and OI-trend studies' publication-lag convention). Long the
    single asset (independently, not a basket) while regime_on, cash
    otherwise. Non-overlapping regime blocks.
  - Costs: repo-standard 30bps round trip (15bps/side).
  - Partitions: development 2020-01-01->2022-06-01, validation ->2024-06-01,
    test ->2026-07-28 (test start pushed later than other studies' 2024-01-01
    convention only where an asset's real history is short; matched to each
    asset's own available window with the same three-way split proportions).
  - Benchmarks: cash, buy-and-hold, a naive BTC-price-momentum regime control
    (long only while trailing-30d BTC return > 0, same lag/cost convention,
    reused from prior studies), and a seeded random-regime control (same
    block count / on-time fraction as the real regime, randomly placed).
  - Falsification (preregistered): primary must beat buy-and-hold, the
    momentum control, AND the random control on a MAJORITY (>=3/4) of
    assets; survive doubled round-trip cost; not lose to buy-and-hold in the
    test partition; and clear a 20% single-block concentration cap
    (exclude-best-block result must remain above buy-and-hold). Any
    decisive multi-gate failure -> REJECTED. A narrow 1-2-gate miss with
    otherwise-clean results -> PROMISING BUT INCONCLUSIVE.
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
FAST_WINDOW = 3
SLOW_WINDOW = 14
BASE_SEED = 20260903

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


def build_regime_signal(hourly: pd.DataFrame) -> pd.DataFrame:
    daily_vol = hourly["volume"].resample("1D").sum()
    daily_buy_vol = hourly["taker_buy_base_volume"].resample("1D").sum()
    daily_buy_ratio = (daily_buy_vol / daily_vol.replace(0, np.nan)).rename("daily_buy_ratio")
    frame = daily_buy_ratio.to_frame()
    frame["fast_sma"] = frame["daily_buy_ratio"].rolling(FAST_WINDOW, min_periods=FAST_WINDOW).mean()
    frame["slow_sma"] = frame["daily_buy_ratio"].rolling(SLOW_WINDOW, min_periods=SLOW_WINDOW).mean()
    frame["regime_on"] = frame["fast_sma"] > frame["slow_sma"]
    frame = frame.dropna(subset=["fast_sma", "slow_sma"])
    return frame


def regime_blocks(regime: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    on = regime["regime_on"]
    blocks = []
    in_block = False
    block_start_day = None
    prev_day = None
    for day, val in on.items():
        if val and not in_block:
            in_block = True
            block_start_day = day
        elif not val and in_block:
            in_block = False
            entry_ts = block_start_day + pd.Timedelta(days=1)
            exit_ts = day + pd.Timedelta(days=1)
            blocks.append((entry_ts, exit_ts))
        prev_day = day
    if in_block:
        entry_ts = block_start_day + pd.Timedelta(days=1)
        exit_ts = prev_day + pd.Timedelta(days=1)
        blocks.append((entry_ts, exit_ts))
    return blocks


def simulate_blocks(price: pd.Series, blocks: list[tuple[pd.Timestamp, pd.Timestamp]], one_way_cost: float) -> dict:
    capital = 1.0
    trade_log = []
    idx = price.index
    equity = pd.Series(index=idx, dtype=float)
    equity.iloc[0] = capital
    cur_block_idx = 0
    in_position = False
    entry_price = None
    entry_ts = None
    units = 0.0

    for i, ts in enumerate(idx):
        if cur_block_idx < len(blocks):
            b_entry, b_exit = blocks[cur_block_idx]
        else:
            b_entry, b_exit = None, None

        if in_position and b_exit is not None and ts >= b_exit:
            exec_price = float(price.iloc[i]) * (1 - one_way_cost)
            capital = units * exec_price
            trade_log.append({
                "entry_time": entry_ts, "exit_time": ts, "entry_price": entry_price,
                "exit_price": exec_price, "gross_return": exec_price / entry_price - 1.0,
            })
            units = 0.0
            in_position = False
            cur_block_idx += 1
            if cur_block_idx < len(blocks):
                b_entry, b_exit = blocks[cur_block_idx]
            else:
                b_entry, b_exit = None, None

        if (not in_position) and b_entry is not None and ts >= b_entry and (b_exit is None or ts < b_exit):
            exec_price = float(price.iloc[i]) * (1 + one_way_cost)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_ts = ts

        equity.iloc[i] = capital + units * float(price.iloc[i])

    if in_position:
        exec_price = float(price.iloc[-1]) * (1 - one_way_cost)
        capital = units * exec_price
        trade_log.append({
            "entry_time": entry_ts, "exit_time": idx[-1], "entry_price": entry_price,
            "exit_price": exec_price, "gross_return": exec_price / entry_price - 1.0,
        })

    trades_df = pd.DataFrame(trade_log)
    return {"equity": equity.to_frame("equity"), "trades": trades_df, "final_capital": float(equity.iloc[-1])}


def buy_and_hold(price: pd.Series) -> dict:
    start_price = float(price.iloc[0])
    equity = price / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


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


def momentum_regime_blocks(btc_close: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    ret_30d = btc_close.pct_change(30)
    on = (ret_30d > 0).dropna()
    frame = on.to_frame("regime_on")
    return regime_blocks(frame)


def random_regime_blocks(real_blocks, index: pd.DatetimeIndex, seed: int):
    if not real_blocks:
        return []
    rng = np.random.default_rng(seed)
    durations_days = [max(1, int((b_exit - b_entry) / pd.Timedelta(days=1))) for b_entry, b_exit in real_blocks]
    n_days = len(index)
    day_positions = list(range(n_days))
    blocks = []
    used = np.zeros(n_days, dtype=bool)
    for dur in durations_days:
        candidates = [p for p in day_positions if p + dur < n_days and not used[p:p + dur + 1].any()]
        if not candidates:
            continue
        start_pos = int(rng.choice(candidates))
        used[start_pos:start_pos + dur + 1] = True
        entry_ts = index[start_pos]
        exit_ts = index[min(start_pos + dur, n_days - 1)]
        blocks.append((entry_ts, exit_ts))
    blocks.sort(key=lambda b: b[0])
    return blocks


def partition_slice(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    mask = frame.index >= start
    if end is not None:
        mask &= frame.index < end
    return frame.loc[mask]


def exclude_best_block(price: pd.Series, blocks, one_way_cost: float) -> float:
    if not blocks:
        return float("nan")
    result = simulate_blocks(price, blocks, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"]
    total_pnl = (trades["gross_return"]).sum()
    best_idx = trades["gross_return"].idxmax()
    remaining = [b for i, b in enumerate(blocks) if i != best_idx]
    result_excl = simulate_blocks(price, remaining, one_way_cost)
    return result_excl["final_capital"]


def top_block_pct_of_pnl(trades: pd.DataFrame) -> float:
    if trades.empty:
        return float("nan")
    pnl = trades["gross_return"]
    total = pnl.sum()
    if total == 0:
        return float("nan")
    return float(pnl.abs().max() / abs(total))


def run_for_asset(coin: str, btc_close_daily: pd.Series) -> dict:
    hourly = load_taker_flow(coin)
    regime = build_regime_signal(hourly)
    daily = load_daily(coin)
    price = daily["close"]
    start = max(regime.index.min(), price.index.min())
    price = price[price.index >= start]
    bars_per_year = 365.25

    blocks = regime_blocks(regime[regime.index >= (start - pd.Timedelta(days=1))])
    blocks = [(e, x) for e, x in blocks if e >= price.index.min() and e <= price.index.max()]
    blocks = [(e, min(x, price.index.max())) for e, x in blocks]

    primary = simulate_blocks(price, blocks, ONE_WAY_COST)
    doubled = simulate_blocks(price, blocks, ONE_WAY_COST * 2)
    bh = buy_and_hold(price)
    excl_best_final = exclude_best_block(price, blocks, ONE_WAY_COST)
    top_pct = top_block_pct_of_pnl(primary["trades"])

    mom_blocks_full = momentum_regime_blocks(btc_close_daily)
    mom_blocks = [(e, x) for e, x in mom_blocks_full if e >= price.index.min() and e <= price.index.max()]
    mom_blocks = [(e, min(x, price.index.max())) for e, x in mom_blocks]
    mom_result = simulate_blocks(price, mom_blocks, ONE_WAY_COST)

    seed = BASE_SEED + (hash(coin) % 10_000)
    rand_blocks = random_regime_blocks(blocks, price.index, seed)
    rand_result = simulate_blocks(price, rand_blocks, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)

    n = len(price)
    dev_end = price.index[int(n * 0.5)]
    test_start = price.index[int(n * 0.8)]
    partitions = {
        "development": (price.index.min(), dev_end),
        "validation": (dev_end, test_start),
        "test": (test_start, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pprice = partition_slice(price.to_frame("close"), pstart, pend)["close"]
        if len(pprice) < 30:
            continue
        pblocks = [(e, x) for e, x in blocks if e >= pstart and (pend is None or e < pend)]
        pblocks = [(max(e, pprice.index.min()), min(x, pprice.index.max())) for e, x in pblocks]
        p_res = simulate_blocks(pprice, pblocks, ONE_WAY_COST)
        p_bh = buy_and_hold(pprice)
        partition_rows.append({
            "asset": coin, "partition": pname, "n_blocks": len(pblocks),
            "strategy_final": p_res["final_capital"], "bh_final": p_bh["final_capital"],
            "strategy_beats_bh": bool(p_res["final_capital"] > p_bh["final_capital"]),
        })

    return {
        "asset": coin, "n_blocks": len(blocks),
        "primary_final": primary["final_capital"], "doubled_cost_final": doubled["final_capital"],
        "exclude_best_block_final": excl_best_final, "bh_final": bh["final_capital"],
        "momentum_control_final": mom_result["final_capital"], "random_control_final": rand_result["final_capital"],
        "top_block_pct_of_pnl": top_pct,
        "primary_total_return": metrics_primary["total_return"], "primary_sharpe": metrics_primary["sharpe"],
        "primary_sortino": metrics_primary["sortino"], "primary_max_dd": metrics_primary["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"], "bh_sharpe": metrics_bh["sharpe"],
        "beats_bh": bool(primary["final_capital"] > bh["final_capital"]),
        "beats_momentum_control": bool(primary["final_capital"] > mom_result["final_capital"]),
        "beats_random_control": bool(primary["final_capital"] > rand_result["final_capital"]),
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh["final_capital"]),
        "beats_bh_excl_best_block": bool(excl_best_final > bh["final_capital"]),
        "concentration_ok": bool(not np.isfinite(top_pct) or top_pct <= 0.20),
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    btc_daily = load_daily("BTC")
    btc_close_daily = btc_daily["close"]

    results = {coin: run_for_asset(coin, btc_close_daily) for coin in ASSETS}

    out_dir = ROOT / "results" / "taker_flow_trend" / "runs"
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

    n_assets = len(summary_df)
    beats_bh_n = int(summary_df["beats_bh"].sum())
    beats_mom_n = int(summary_df["beats_momentum_control"].sum())
    beats_rand_n = int(summary_df["beats_random_control"].sum())
    beats_doubled_n = int(summary_df["beats_bh_doubled_cost"].sum())
    concentration_ok_n = int(summary_df["concentration_ok"].sum())
    beats_excl_best_n = int(summary_df["beats_bh_excl_best_block"].sum())

    test_partition = partition_df[partition_df["partition"] == "test"]
    test_pass_n = int(test_partition["strategy_beats_bh"].sum()) if not test_partition.empty else 0
    test_total = len(test_partition)

    majority = lambda x: x >= 3  # noqa: E731

    all_majority_gates = (
        majority(beats_bh_n) and majority(beats_mom_n) and majority(beats_rand_n)
        and majority(beats_doubled_n) and majority(concentration_ok_n)
        and (test_total == 0 or test_pass_n >= max(1, test_total - 1))
    )
    decisive_reject = (
        beats_bh_n <= 1 or beats_mom_n <= 1 or concentration_ok_n <= 1
    )

    if all_majority_gates:
        verdict = "CANDIDATE"
    elif decisive_reject:
        verdict = "REJECTED"
    else:
        verdict = "PROMISING BUT INCONCLUSIVE"

    print(
        f"\nBeats B&H: {beats_bh_n}/{n_assets}; Beats momentum control: {beats_mom_n}/{n_assets}; "
        f"Beats random control: {beats_rand_n}/{n_assets}; Survives doubled cost: {beats_doubled_n}/{n_assets}; "
        f"Concentration OK: {concentration_ok_n}/{n_assets}; Excl-best-block ok: {beats_excl_best_n}/{n_assets}; "
        f"Test partition pass: {test_pass_n}/{test_total}"
    )
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh={beats_bh_n}/{n_assets}\nbeats_momentum_control={beats_mom_n}/{n_assets}\n"
            f"beats_random_control={beats_rand_n}/{n_assets}\nbeats_doubled_cost={beats_doubled_n}/{n_assets}\n"
            f"concentration_ok={concentration_ok_n}/{n_assets}\nbeats_excl_best_block={beats_excl_best_n}/{n_assets}\n"
            f"test_partition_pass={test_pass_n}/{test_total}\nverdict={verdict}\n"
        )

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
