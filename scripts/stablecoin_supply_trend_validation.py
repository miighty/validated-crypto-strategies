"""EXP-2026-08-31-STABLETREND-001: Stablecoin supply growth trend as a crypto
risk-on/risk-off regime filter.

Hypothesis (preregistered, genuinely new for this repo -- never tested here;
checked docs/experiment_registry.md and docs/next_hypotheses.md in full before
writing this: no prior study in this repo has used stablecoin supply data.
Mechanistically distinct from every prior study: not calendar (weekend/
session/turn-of-month), not cross-sectional factor L/S (Amihud/funding-carry/
residual-momentum/low-vol), not price-based trend (SMA200), not implied-vol
(DVOL) or composite sentiment (FGI), not funding/basis carry, not event-odds/
Polymarket. This is a *fundamental liquidity-flow* regime filter: real net
stablecoin issuance (new fiat entering the crypto system via USDT/USDC/etc.
minting) as a leading indicator of risk appetite, distinct from every
price-derived or derivatives-derived signal tested so far):

  Aggregate stablecoin supply (USDT+USDC+... total USD circulating, published
  daily by DefiLlama, a real, independently-audited on-chain/exchange-reported
  aggregate) grows when fresh fiat capital enters the crypto ecosystem via
  stablecoin minting, and contracts when capital exits via redemption. A
  short-term average of supply crossing above its own longer-term average
  (a "golden cross" applied to a fundamental flow series instead of price)
  signals accelerating fiat inflow and should precede risk-on price action;
  the inverse crossover signals decelerating/contracting inflow and should
  precede risk-off. A rule that goes long BTC/ETH/SOL/XRP only while this
  slow-moving structural regime filter is "on" should beat continuous
  buy-and-hold after realistic costs, per the skill's explicit guidance to
  bias new factor search toward slow-moving/structural/information-based
  signals (not fast technical oscillators, which are prone to same-bar
  look-ahead artifacts).

Design (frozen before any result was inspected):
  - Data source: DefiLlama public `stablecoincharts/all` endpoint (real,
    free, no API key), daily total circulating USD stablecoin supply
    (`totalCirculatingUSD.peggedUSD`), 2019-06-01 (first date with a
    meaningfully liquid, actively-traded stablecoin market -- pre-2019 the
    series is a handful of dollars of noise) through repo cutoff. Cached to
    `data/stablecoin_supply/total_stablecoin_supply_1d.csv.gz`.
  - Universe: BTC, ETH, SOL, XRP (already-cached real Binance spot 1d OHLCV,
    `data/raw/*_1d.csv.gz`). SOL's real history only starts 2020-08-11 --
    no proxy/backfill, SOL is simply excluded before its real listing date.
  - Signal (computed once per day, using ONLY data published through and
    including that day -- no lookahead):
      fast_sma = rolling 7-day mean of daily total stablecoin supply
      slow_sma = rolling 30-day mean of daily total stablecoin supply
      regime_on = fast_sma_t > slow_sma_t
  - Execution: regime_on decided using day t's close-of-day published supply
    figure; position entered/exited at day (t+1)'s 00:00 UTC open (one full
    day of publication lag, realistic since DefiLlama's snapshot for day t
    is not knowable intraday on day t itself). Long BTC/ETH/SOL/XRP equally
    (fixed static equal-weight basket, no per-asset signal) while regime_on;
    fully flat to cash otherwise. Non-overlapping regime blocks (a single
    continuous holding period each time regime_on stays true).
  - Costs: repo-standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE),
    charged once per entry and once per exit of a regime block.
  - Partitions (matching repo convention):
      development: 2019-06-01 -> 2021-06-01
      validation:  2021-06-01 -> 2024-01-01
      test:        2024-01-01 -> repo cutoff (2026-07-28 exclusive)
  - Benchmarks: cash, continuous buy-and-hold (equal-weight basket and each
    asset individually), always-long same entry/exit schedule is N/A here
    (there is only one schedule -- the regime schedule itself IS the primary
    rule), a fixed-lookback momentum control (12-1 month BTC price momentum
    regime filter, long only while trailing 30d BTC return > 0, same cost
    model) as a "naive regime filter" baseline, and a seeded random-regime
    control (randomly shuffled on/off blocks matching the real regime's
    block-count and total on-time fraction, same seed formula as other
    studies in this repo: base_seed=20260831 + hash(asset)).
  - Falsification (preregistered): primary rule must beat continuous
    buy-and-hold on the equal-weight basket AND beat the momentum-regime
    control AND beat the random-regime control, survive doubled round-trip
    cost, not lose to buy-and-hold in the test partition, and retain a
    positive best-block-excluded edge (no single-regime-block concentration
    artifact, i.e. excluding the single best on-block must not flip the
    result net-negative vs buy-and-hold, per this program's repeated
    concentration-artifact findings e.g. SMA-200, DVOL, ratio-rotation).
    Any single failure -> REJECTED (or PROMISING BUT INCONCLUSIVE if it is a
    narrow near-miss per the skill's near-miss discipline).
"""
from __future__ import annotations

import json
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
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE  # 0.0015
ROUND_TRIP_COST = 2 * ONE_WAY_COST

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
STABLE_START = pd.Timestamp("2019-06-01T00:00:00Z")
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
DEV_END = pd.Timestamp("2021-06-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")

FAST_WINDOW = 7
SLOW_WINDOW = 30
BASE_SEED = 20260831

STABLE_DIR = ROOT / "data" / "stablecoin_supply"
STABLE_URL = "https://stablecoins.llama.fi/stablecoincharts/all"


def fetch_or_load_stablecoin_supply() -> pd.DataFrame:
    STABLE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = STABLE_DIR / "total_stablecoin_supply_1d.csv.gz"
    if cache_path.exists():
        frame = pd.read_csv(cache_path, parse_dates=["date"])
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        if frame["date"].max() >= (END_EXCLUSIVE - pd.Timedelta(days=2)):
            return frame
    attempts = 0
    payload = None
    while attempts < 5:
        try:
            request = urllib.request.Request(
                STABLE_URL, headers={"User-Agent": "validated-crypto-strategies/0.1"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read())
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            attempts += 1
            if attempts >= 5:
                raise RuntimeError(f"DefiLlama stablecoincharts fetch failed: {error}") from error
            time.sleep(min(2**attempts, 16))
    if not payload:
        raise RuntimeError("No real DefiLlama stablecoin data returned")
    rows = []
    for row in payload:
        ts = int(row["date"])
        usd = row.get("totalCirculatingUSD", {}).get("peggedUSD")
        if usd is None:
            continue
        rows.append((ts, float(usd)))
    frame = pd.DataFrame(rows, columns=["ts", "total_supply_usd"])
    frame["date"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
    frame = frame[["date", "total_supply_usd"]].sort_values("date").drop_duplicates("date")
    frame = frame.reset_index(drop=True)
    frame.to_csv(cache_path, index=False, compression="gzip")
    return frame


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_regime_signal(stable: pd.DataFrame) -> pd.DataFrame:
    frame = stable.copy().set_index("date").sort_index()
    frame = frame[(frame.index >= STABLE_START) & (frame.index < END_EXCLUSIVE)]
    frame["fast_sma"] = frame["total_supply_usd"].rolling(FAST_WINDOW, min_periods=FAST_WINDOW).mean()
    frame["slow_sma"] = frame["total_supply_usd"].rolling(SLOW_WINDOW, min_periods=SLOW_WINDOW).mean()
    frame["regime_on"] = frame["fast_sma"] > frame["slow_sma"]
    frame = frame.dropna(subset=["fast_sma", "slow_sma"])
    return frame


def regime_blocks(regime: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return (entry_open_ts, exit_open_ts) pairs. Entry/exit at NEXT day's
    00:00 UTC open following the day the regime flag changed (one full day
    publication lag, no lookahead)."""
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


def simulate_blocks(
    price: pd.Series, blocks: list[tuple[pd.Timestamp, pd.Timestamp]], one_way_cost: float
) -> dict:
    """Simulate a long/cash schedule on a daily close-indexed price series
    using open-of-day proxy = prior day's close (daily bars only carry
    close here), consistent with other daily-bar studies in this repo."""
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
    """Naive momentum-regime control: long only while trailing 30d BTC
    return > 0, decided using data through day t, executed at day (t+1) open,
    identical lag convention to the primary rule."""
    ret_30d = btc_close.pct_change(30)
    on = (ret_30d > 0).dropna()
    frame = on.to_frame("regime_on")
    return regime_blocks(frame)


def random_regime_blocks(
    real_blocks: list[tuple[pd.Timestamp, pd.Timestamp]], index: pd.DatetimeIndex, seed: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Seeded random control: same number of blocks and same total on-time
    fraction as the real regime, but placed at uniformly random start points
    within the available index (non-overlapping, clipped to index bounds)."""
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


def run_for_asset(coin: str, regime: pd.DataFrame, btc_close_daily: pd.Series) -> dict:
    asset_df = load_asset(coin)
    start = max(STABLE_START, asset_df.index.min())
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
        "development": (start, DEV_END),
        "validation": (DEV_END, TEST_START),
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
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    stable_raw = fetch_or_load_stablecoin_supply()
    regime = build_regime_signal(stable_raw)
    print(f"Stablecoin supply rows: {len(stable_raw)}; regime rows: {len(regime)}")
    print(f"Regime on fraction (full sample): {regime['regime_on'].mean():.3f}")

    btc_daily = load_asset("BTC")
    btc_close_daily = btc_daily["close"]

    results = {coin: run_for_asset(coin, regime, btc_close_daily) for coin in ASSETS}

    out_dir = ROOT / "results" / "stablecoin_supply_trend" / "runs"
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

    beats_bh_all = bool(summary_df["beats_bh"].all())
    beats_mom_all = bool(summary_df["beats_momentum_control"].all())
    beats_rand_all = bool(summary_df["beats_random_control"].all())
    beats_doubled_all = bool(summary_df["beats_bh_doubled_cost"].all())
    beats_excl_best_all = bool(summary_df["beats_bh_excl_best_block"].all())
    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test"]["strategy_beats_bh"].all()
    )

    if (
        beats_bh_all
        and beats_mom_all
        and beats_rand_all
        and beats_doubled_all
        and beats_excl_best_all
        and test_pass
    ):
        verdict = "CANDIDATE"
    elif beats_bh_all and beats_rand_all and (beats_doubled_all or beats_excl_best_all):
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(
        f"\nBeats B&H (all assets): {beats_bh_all}; Beats momentum control: {beats_mom_all}; "
        f"Beats random control: {beats_rand_all}; Survives doubled cost: {beats_doubled_all}; "
        f"Survives best-block exclusion: {beats_excl_best_all}; Test partition pass: {test_pass}"
    )
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh_all={beats_bh_all}\nbeats_momentum_control_all={beats_mom_all}\n"
            f"beats_random_control_all={beats_rand_all}\nbeats_doubled_cost_all={beats_doubled_all}\n"
            f"beats_excl_best_block_all={beats_excl_best_all}\ntest_partition_pass={test_pass}\n"
            f"verdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
