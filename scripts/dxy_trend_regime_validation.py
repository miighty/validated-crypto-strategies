"""EXP-2026-09-04-DXYTREND-001: US Dollar Index (DXY/broad trade-weighted)
downtrend as a crypto risk-on regime filter.

Hypothesis (preregistered; checked docs/experiment_registry.md and
docs/next_hypotheses.md in full before writing this -- genuinely new for
this repo: no prior study has used any macro/TradFi FX data. Mechanistically
distinct from every prior study: not calendar, not cross-sectional factor
L/S, not derivatives positioning (funding/OI/top-trader/retail/CFTC-COT),
not price-based trend on the asset itself (SMA200), not implied/sentiment
vol (DVOL/FGI), not on-chain (NVT/hash-ribbons), not cross-exchange spot
premium (Coinbase). Every prior "slow structural regime filter" study in
this program (stablecoin-supply-trend, OI-trend, top-trader-trend,
taker-flow-trend, Coinbase-premium-trend) derived its signal FROM the
crypto market itself (OI, funding, spot flow, price), and every one of them
lost to a naive BTC-price-momentum control -- because a signal derived from
crypto's own price/flow data is mechanically correlated with crypto's own
future price momentum, so it can rarely add orthogonal information beyond
trivial momentum. The US Dollar Index (DXY / Fed's broad trade-weighted
index) is a genuinely EXTERNAL macro variable computed from FX markets
entirely independent of crypto positioning/flow -- if a inverse dollar-
strength regime has real explanatory power for crypto risk appetite (the
classic "weak dollar -> risk-on" macro thesis), it would be the first test
in this program of a truly orthogonal (non-crypto-derived) macro signal.

Design (frozen before any result was inspected):
  - Data source: FRED (Federal Reserve Economic Data) public CSV endpoint,
    series DTWEXBGS (Nominal Broad U.S. Dollar Index, daily, 2006-01-02
    onward, no API key required). Cached to
    `data/macro_dxy/dtwexbgs_1d.csv.gz`. No proxy -- if the fetch fails,
    this study is blocked and reported as such, not fabricated.
  - Universe: BTC, ETH, SOL, XRP (already-cached real Binance spot 1d
    OHLCV, `data/raw/*_1d.csv.gz`). Each asset's regime blocks are clipped
    to its own real listing date (no backfill).
  - Signal (computed once per FRED-published day, using ONLY data through
    and including that day -- no lookahead; DTWEXBGS is a business-day-only
    series, FRED publishes with ~1 business day lag which this design
    already respects via the execution-lag rule below):
      fast_sma = rolling 20-business-day mean of DTWEXBGS
      slow_sma = rolling 60-business-day mean of DTWEXBGS
      regime_on = fast_sma_t < slow_sma_t   (dollar WEAKENING -> risk-on)
  - Execution: regime_on decided using day t's published FRED value;
    position entered/exited at day (t+1)'s 00:00 UTC crypto open (one full
    day publication lag, consistent with every prior slow-regime study in
    this repo). Long BTC/ETH/SOL/XRP independently (same regime signal
    applied per-asset, each asset's own price return) while regime_on;
    flat to cash otherwise. Non-overlapping regime blocks.
  - Costs: repo-standard 30bps round trip (15bps/side).
  - Partitions: development 2006-01-02->2018-01-01 (DXY-only, pre-crypto,
    used only to build a burned-in SMA, not scored), pre-crypto data
    excluded from scoring; scored partitions:
      development: first crypto listing -> 2020-01-01
      validation:  2020-01-01 -> 2023-01-01
      test:        2023-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Benchmarks: cash, continuous buy-and-hold per asset, a naive BTC-price-
    momentum regime control (trailing 30d BTC return > 0, same lag/cost
    convention -- the exact control every prior regime study in this
    program has been compared against), and a seeded random-regime control
    (same block count / on-fraction as the real regime, base_seed=20260904).
  - Falsification (preregistered): primary rule must beat continuous
    buy-and-hold AND the momentum-regime control AND the random-regime
    control on a majority (>=3/4) of assets, survive doubled round-trip
    cost, not lose to buy-and-hold in the test partition, and retain a
    positive best-block-excluded edge (no single-block concentration
    artifact, cap 20% of total PnL per block) -- any decisive failure ->
    REJECTED (or PROMISING BUT INCONCLUSIVE if narrow near-miss).
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
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

FAST_WINDOW = 20
SLOW_WINDOW = 60
BASE_SEED = 20260904

DXY_DIR = ROOT / "data" / "macro_dxy"
DXY_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS"


def fetch_or_load_dxy() -> pd.DataFrame:
    DXY_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DXY_DIR / "dtwexbgs_1d.csv.gz"
    if cache_path.exists():
        frame = pd.read_csv(cache_path, parse_dates=["date"])
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        if frame["date"].max() >= (END_EXCLUSIVE - pd.Timedelta(days=10)):
            return frame
    attempts = 0
    payload = None
    last_error = None
    while attempts < 5:
        try:
            request = urllib.request.Request(
                DXY_URL, headers={"User-Agent": "validated-crypto-strategies/0.1"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            attempts += 1
            time.sleep(min(2**attempts, 16))
    if not payload:
        raise RuntimeError(f"Real FRED DTWEXBGS fetch failed after retries: {last_error}")
    from io import StringIO

    raw = pd.read_csv(StringIO(payload))
    raw.columns = ["date", "dxy"]
    raw = raw[raw["dxy"] != "."]
    raw["date"] = pd.to_datetime(raw["date"], utc=True)
    raw["dxy"] = raw["dxy"].astype(float)
    raw = raw.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    raw.to_csv(cache_path, index=False, compression="gzip")
    return raw


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_regime_signal(dxy: pd.DataFrame) -> pd.DataFrame:
    frame = dxy.copy().set_index("date").sort_index()
    frame = frame[frame.index < END_EXCLUSIVE]
    frame["fast_sma"] = frame["dxy"].rolling(FAST_WINDOW, min_periods=FAST_WINDOW).mean()
    frame["slow_sma"] = frame["dxy"].rolling(SLOW_WINDOW, min_periods=SLOW_WINDOW).mean()
    frame["regime_on"] = frame["fast_sma"] < frame["slow_sma"]  # dollar weakening -> risk-on
    frame = frame.dropna(subset=["fast_sma", "slow_sma"])
    # forward-fill across weekends/holidays onto a full daily calendar so
    # crypto (which trades 7 days/week) always has a defined regime state
    full_idx = pd.date_range(frame.index.min(), END_EXCLUSIVE - pd.Timedelta(days=1), freq="D", tz="UTC")
    frame = frame.reindex(full_idx).ffill()
    frame.index.name = "date"
    return frame


def regime_blocks(regime: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    on = regime["regime_on"]
    blocks = []
    in_block = False
    block_start_day = None
    prev_day = None
    for day, val in on.items():
        if bool(val) and not in_block:
            in_block = True
            block_start_day = day
        elif not bool(val) and in_block:
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


def simulate_blocks(
    price: pd.Series, blocks: list[tuple[pd.Timestamp, pd.Timestamp]], one_way_cost: float
) -> dict:
    capital = 1.0
    trade_log = []
    equity = pd.Series(index=price.index, dtype=float)
    equity.iloc[0] = capital
    cur_block_idx = 0
    in_position = False
    entry_price = None
    entry_ts = None
    units = 0.0

    idx = price.index
    for i, ts in enumerate(idx):
        if cur_block_idx < len(blocks):
            b_entry, b_exit = blocks[cur_block_idx]
        else:
            b_entry, b_exit = None, None

        if in_position and b_exit is not None and ts >= b_exit:
            exec_price = float(price.iloc[i]) * (1 - one_way_cost)
            capital = units * exec_price
            trade_log.append(
                {
                    "entry_time": entry_ts,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exec_price,
                    "gross_return": exec_price / entry_price - 1.0,
                }
            )
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
        trade_log.append(
            {
                "entry_time": entry_ts,
                "exit_time": idx[-1],
                "entry_price": entry_price,
                "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
            }
        )

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


def random_regime_blocks(
    real_blocks: list[tuple[pd.Timestamp, pd.Timestamp]], index: pd.DatetimeIndex, seed: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if not real_blocks:
        return []
    rng = np.random.default_rng(seed)
    durations_days = [
        max(1, int((b_exit - b_entry) / pd.Timedelta(days=1))) for b_entry, b_exit in real_blocks
    ]
    n_days = len(index)
    day_positions = list(range(n_days))
    blocks = []
    used = np.zeros(n_days, dtype=bool)
    for dur in durations_days:
        candidates = [p for p in day_positions if p + dur < n_days and not used[p : p + dur + 1].any()]
        if not candidates:
            continue
        start_pos = int(rng.choice(candidates))
        used[start_pos : start_pos + dur + 1] = True
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


def exclude_best_block(
    price: pd.Series, blocks: list[tuple[pd.Timestamp, pd.Timestamp]], one_way_cost: float
) -> float:
    if not blocks:
        return float("nan")
    result = simulate_blocks(price, blocks, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"]
    best_idx = trades["gross_return"].idxmax()
    remaining = [b for i, b in enumerate(blocks) if i != best_idx]
    result_excl = simulate_blocks(price, remaining, one_way_cost)
    return result_excl["final_capital"]


def top_block_pnl_share(price: pd.Series, blocks, one_way_cost: float) -> float:
    result = simulate_blocks(price, blocks, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return float("nan")
    pnl_per_block = trades["gross_return"]
    total_pnl = pnl_per_block.sum()
    if total_pnl == 0:
        return float("nan")
    return float(pnl_per_block.abs().max() / abs(total_pnl))


def run_for_asset(coin: str, regime: pd.DataFrame, btc_close_daily: pd.Series) -> dict:
    asset_df = load_asset(coin)
    start = max(regime.index.min(), asset_df.index.min())
    asset_df = asset_df[asset_df.index >= start]
    price = asset_df["close"]
    bars_per_year = 365.25

    aligned_regime = regime[regime.index >= (start - pd.Timedelta(days=1))]
    blocks = regime_blocks(aligned_regime)
    blocks = [(e, x) for e, x in blocks if e >= price.index.min() and e <= price.index.max()]
    blocks = [(e, min(x, price.index.max())) for e, x in blocks]

    primary = simulate_blocks(price, blocks, ONE_WAY_COST)
    doubled = simulate_blocks(price, blocks, ONE_WAY_COST * 2)
    bh = buy_and_hold(price)
    excl_best_final = exclude_best_block(price, blocks, ONE_WAY_COST)
    top_block_share = top_block_pnl_share(price, blocks, ONE_WAY_COST)

    mom_blocks_full = momentum_regime_blocks(btc_close_daily)
    mom_blocks = [(e, x) for e, x in mom_blocks_full if e >= price.index.min() and e <= price.index.max()]
    mom_blocks = [(e, min(x, price.index.max())) for e, x in mom_blocks]
    mom_result = simulate_blocks(price, mom_blocks, ONE_WAY_COST)

    seed = BASE_SEED + (hash(coin) % 10_000)
    rand_blocks = random_regime_blocks(blocks, price.index, seed)
    rand_result = simulate_blocks(price, rand_blocks, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)

    partitions = {
        "development": (start, VALIDATION_START),
        "validation": (VALIDATION_START, TEST_START),
        "test": (TEST_START, None),
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
        partition_rows.append(
            {
                "asset": coin,
                "partition": pname,
                "n_blocks": len(pblocks),
                "strategy_final": p_res["final_capital"],
                "bh_final": p_bh["final_capital"],
                "strategy_beats_bh": bool(p_res["final_capital"] > p_bh["final_capital"]),
            }
        )

    return {
        "asset": coin,
        "n_blocks": len(blocks),
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "exclude_best_block_final": excl_best_final,
        "top_block_pnl_share": top_block_share,
        "bh_final": bh["final_capital"],
        "momentum_control_final": mom_result["final_capital"],
        "random_control_final": rand_result["final_capital"],
        "primary_total_return": metrics_primary["total_return"],
        "primary_sharpe": metrics_primary["sharpe"],
        "primary_sortino": metrics_primary["sortino"],
        "primary_max_dd": metrics_primary["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "beats_bh": bool(primary["final_capital"] > bh["final_capital"]),
        "beats_momentum_control": bool(primary["final_capital"] > mom_result["final_capital"]),
        "beats_random_control": bool(primary["final_capital"] > rand_result["final_capital"]),
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh["final_capital"]),
        "beats_bh_excl_best_block": bool(excl_best_final > bh["final_capital"]),
        "concentration_ok": bool((not np.isnan(top_block_share)) and top_block_share <= 0.20),
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    dxy_raw = fetch_or_load_dxy()
    regime = build_regime_signal(dxy_raw)
    print(f"DXY rows: {len(dxy_raw)}; regime rows (daily-reindexed): {len(regime)}")
    print(f"Regime on fraction (dollar-weakening, full sample): {regime['regime_on'].mean():.3f}")

    btc_daily = load_asset("BTC")
    btc_close_daily = btc_daily["close"]

    results = {coin: run_for_asset(coin, regime, btc_close_daily) for coin in ASSETS}

    out_dir = ROOT / "results" / "dxy_trend_regime" / "runs"
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
    regime.to_csv(run_dir / "regime_signal.csv.gz", compression="gzip")

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    beats_bh_n = int(summary_df["beats_bh"].sum())
    beats_mom_n = int(summary_df["beats_momentum_control"].sum())
    beats_rand_n = int(summary_df["beats_random_control"].sum())
    beats_doubled_n = int(summary_df["beats_bh_doubled_cost"].sum())
    beats_excl_best_n = int(summary_df["beats_bh_excl_best_block"].sum())
    concentration_ok_n = int(summary_df["concentration_ok"].sum())
    n_assets = len(summary_df)

    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test"]["strategy_beats_bh"].all()
    )

    majority = lambda n: n >= 3  # 3/4 assets

    beats_bh_all = beats_bh_n == n_assets
    beats_mom_all = beats_mom_n == n_assets
    beats_rand_all = beats_rand_n == n_assets
    beats_doubled_all = beats_doubled_n == n_assets
    beats_excl_best_all = beats_excl_best_n == n_assets
    concentration_ok_all = concentration_ok_n == n_assets

    if (
        beats_bh_all
        and beats_mom_all
        and beats_rand_all
        and beats_doubled_all
        and beats_excl_best_all
        and concentration_ok_all
        and test_pass
    ):
        verdict = "CANDIDATE"
    elif (
        majority(beats_bh_n)
        and majority(beats_mom_n)
        and majority(beats_rand_n)
        and (beats_doubled_n >= 2 or beats_excl_best_n >= 2)
    ):
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(
        f"\nBeats B&H: {beats_bh_n}/{n_assets}; Beats momentum control: {beats_mom_n}/{n_assets}; "
        f"Beats random control: {beats_rand_n}/{n_assets}; Survives doubled cost: {beats_doubled_n}/{n_assets}; "
        f"Survives best-block exclusion: {beats_excl_best_n}/{n_assets}; "
        f"Concentration OK: {concentration_ok_n}/{n_assets}; Test partition pass: {test_pass}"
    )
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh={beats_bh_n}/{n_assets}\nbeats_momentum_control={beats_mom_n}/{n_assets}\n"
            f"beats_random_control={beats_rand_n}/{n_assets}\nbeats_doubled_cost={beats_doubled_n}/{n_assets}\n"
            f"beats_excl_best_block={beats_excl_best_n}/{n_assets}\n"
            f"concentration_ok={concentration_ok_n}/{n_assets}\ntest_partition_pass={test_pass}\n"
            f"verdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
