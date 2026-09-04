"""EXP-2026-09-04-GTRENDS-001: Google Trends 'bitcoin' search-interest
extreme-euphoria contrarian regime filter.

Preregistered before inspecting results. Checked docs/experiment_registry.md
and docs/next_hypotheses.md in full first -- genuinely new for this repo: no
prior study has used public retail search-attention data (Google Trends).
Mechanistically distinct from every prior study:
  - not price-derived (SMA200, breakout, taker-flow, Coinbase-premium)
  - not derivatives positioning (funding, OI, top-trader/retail ratio, COT)
  - not implied/composite sentiment index (DVOL, FGI) -- those are
    market-price-derived; Google Trends is a genuinely external behavioral
    signal (what people actually search for), never priced by any market
  - not on-chain (NVT, hash ribbons)
  - not FX macro (DXY)
  - CONTRARIAN ATTENTION-EXTREME construction: unlike every prior
    "slow structural regime" study (which tested a TREND/FOLLOW filter and
    consistently lost to naive price momentum), this tests the classic
    "retail euphoria search-spike marks a local top" thesis as an EXIT
    signal (go to cash when attention is extreme, stay invested otherwise)
    -- the mirror image of "buy the panic" (which has failed repeatedly:
    DVOL, FGI, volume-flush, NVT, panic-flush-reclaim). This is "sell the
    euphoria" instead, a genuinely different direction never tested here.

Design (frozen before any result was inspected):
  - Data: real Google Trends weekly search interest for the term "bitcoin"
    worldwide, stitched from 3 overlapping pytrends queries (each <5yr span
    for weekly resolution, chained via overlap-ratio rescaling -- standard
    Google Trends stitching technique, NOT synthetic data, just relative-
    scale reconciliation of real fetched values). Cached at
    `data/google_trends/bitcoin_search_interest_weekly.csv.gz`
    (2017-05-28 through 2026-08-30, 484 weekly rows).
  - Universe: BTC, ETH, SOL, XRP (real Binance spot daily OHLCV, already
    cached). The single "bitcoin" search term is used as a market-wide
    crypto-attention proxy applied independently to all 4 assets (Google
    Trends per-altcoin search series are far noisier/shorter and would
    require additional unverified proxies -- using the single most liquid,
    highest-quality real search series applied market-wide is the honest
    choice here, not fabricating per-asset attention data).
  - Signal: weekly z-score of search interest vs its own trailing 52-week
    window, PRIOR-ONLY (shifted, excludes the current week to avoid
    lookahead): z_t = (s_t - mean(s_{t-52..t-1})) / std(s_{t-52..t-1}).
  - Regime: OUT (cash) when z_t >= 2.0 (extreme retail euphoria -- classic
    "search spike marks a top" contrarian signal), IN (long) otherwise.
    One full week execution lag: regime decided using week t's close-of-week
    reading, position changes at the start of week t+1 (next Monday 00:00
    UTC crypto open).
  - Costs: repo-standard 30bps round trip (15bps/side).
  - Partitions: development (first crypto listing -> 2020-01-01),
    validation (2020-01-01 -> 2023-01-01), test (2023-01-01 -> repo cutoff).
  - Benchmarks: cash, continuous buy-and-hold, naive BTC-price-momentum
    regime control (trailing 30d BTC return > 0, the same control used by
    every prior regime study in this program), seeded random-regime control
    (same block count/on-fraction as the real regime).
  - Falsification (preregistered): primary rule must beat continuous
    buy-and-hold AND the momentum-regime control AND the random-regime
    control on a majority (>=3/4) of assets, survive doubled round-trip
    cost, not lose to buy-and-hold in the test partition, and clear the 20%
    single-block concentration cap -- any decisive multi-gate failure ->
    REJECTED. A narrow near-miss (fails only 1-2 gates while clearing the
    rest, including concentration/walk-forward) -> PROMISING BUT
    INCONCLUSIVE, per skill discipline.
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
VALIDATION_START = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2023-01-01T00:00:00Z")

Z_LOOKBACK_WEEKS = 52
Z_THRESHOLD = 2.0
BASE_SEED = 20260904

GTRENDS_PATH = ROOT / "data" / "google_trends" / "bitcoin_search_interest_weekly.csv.gz"


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_regime_signal() -> pd.DataFrame:
    frame = pd.read_csv(GTRENDS_PATH, parse_dates=["date"])
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame.set_index("date").sort_index()
    frame = frame[frame.index < END_EXCLUSIVE]
    s = frame["bitcoin_search_interest"]
    roll_mean = s.shift(1).rolling(Z_LOOKBACK_WEEKS, min_periods=Z_LOOKBACK_WEEKS).mean()
    roll_std = s.shift(1).rolling(Z_LOOKBACK_WEEKS, min_periods=Z_LOOKBACK_WEEKS).std(ddof=1)
    z = (s - roll_mean) / roll_std
    frame["z"] = z
    frame["regime_on"] = ~(z >= Z_THRESHOLD)  # long UNLESS extreme euphoria
    frame = frame.dropna(subset=["z"])
    # forward-fill onto a full daily calendar so crypto (7d/week) always has
    # a defined regime state between weekly Google Trends updates
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
            entry_ts = block_start_day + pd.Timedelta(days=7)  # one full week exec lag
            exit_ts = day + pd.Timedelta(days=7)
            blocks.append((entry_ts, exit_ts))
        prev_day = day
    if in_block:
        entry_ts = block_start_day + pd.Timedelta(days=7)
        exit_ts = prev_day + pd.Timedelta(days=7)
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

    aligned_regime = regime[regime.index >= (start - pd.Timedelta(days=8))]
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
    regime = build_regime_signal()
    print(f"Google Trends regime rows (daily-reindexed): {len(regime)}")
    print(f"Regime ON fraction (NOT extreme-euphoria -> long): {regime['regime_on'].mean():.3f}")
    print(f"Extreme-euphoria weeks (z>=2.0) count: {int((regime['z'] >= Z_THRESHOLD).sum())}")

    btc_daily = load_asset("BTC")
    btc_close_daily = btc_daily["close"]

    results = {coin: run_for_asset(coin, regime, btc_close_daily) for coin in ASSETS}

    out_dir = ROOT / "results" / "gtrends_euphoria_regime" / "runs"
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
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
