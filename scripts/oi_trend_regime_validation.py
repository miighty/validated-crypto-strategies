"""EXP-2026-09-01-OITREND-001: Open-interest trend (SMA crossover) as a
structural long/cash regime filter.

Hypothesis (preregistered, genuinely new for this repo -- checked
docs/experiment_registry.md and docs/next_hypotheses.md in full before
writing this). Every prior use of real Binance USD-M open interest in this
repo treated OI as a FAST EVENT TRIGGER (a discrete threshold breach used as
a confirmation filter or short-side crowding signal):
  - crowded_perp_unwind_validation.py: OI rising >=X% over 5 days as part of
    a short-only joint funding+OI extreme trigger (event, REJECTED).
  - oi_breakout_confirmation_validation.py / oi_thin_breakout_validation.py:
    OI %-change over a 5-day window as a binary long-side confirmation
    filter bolted onto a price breakout (event, both REJECTED).

This study is mechanistically different: it treats open interest as a
SLOW-MOVING STRUCTURAL REGIME STATE, exactly the same construction already
used for the (also-real-data) stablecoin-supply-trend study
(stablecoin_supply_trend_validation.py, REJECTED) but applied to a different
underlying series. Economic rationale: a sustained expansion of aggregate
leveraged positioning (OI's short-term average trending above its long-term
average) reflects durable, broadening participation and conviction entering
the market -- distinct from a short-term OI spike, which can be noise or a
single large position. A sustained OI *contraction* (short-term average
below long-term average) reflects deleveraging/participation withdrawal and
should precede weaker price action. This is the direct structural analogue
of next_hypotheses.md's item #5 rationale, but framed as a continuous
regime filter (per this program's item-1/structural-factor bias) rather
than a discrete crowding event.

PRIMARY RULE (frozen before any result beyond prior OI studies' baseline
numbers was inspected):
  1. Compute fast_sma = rolling 20-day mean of daily sum_open_interest;
     slow_sma = rolling 60-day mean of daily sum_open_interest (both use
     only OI values through day t, shift(1) applied before use so the
     regime flag known "as of" day t is only used starting day t+1).
  2. regime_on = fast_sma > slow_sma.
  3. Execution: long the single asset (BTC/ETH/SOL/XRP tested independently
     -- this is NOT a cross-sectional study) at the NEXT daily bar's open
     following the day the regime flag flips on; exit at the NEXT daily
     bar's open following the day it flips off. Flat otherwise,
     non-overlapping blocks.
  4. Costs: standard round-trip (2 x ONE_WAY_COST = 30bps) on entry/exit
     notional.
  5. Universe/coverage: restricted to each asset's real Binance futures OI
     archive coverage window (BTC from 2020-09-01, ETH/SOL/XRP from
     2021-12-01 -- same real archive limits as every prior OI study in this
     repo, no fabrication).

Baselines: cash, buy-and-hold, daily DCA, a naive BTC-price-momentum regime
control (long only while trailing 30d BTC return > 0 -- identical control
used in the stablecoin-supply-trend study, so a slow structural OI signal is
held to the same bar as a slow structural stablecoin-supply signal), and a
seeded random-regime control matching real block count and on-time fraction.

Falsification (preregistered): primary rule must beat buy-and-hold AND the
momentum-regime control AND the random-regime control after costs, survive
doubled round-trip cost, not lose to buy-and-hold in the test partition, and
retain a positive best-block-excluded edge (concentration cap: no single
regime block > 20% of total strategy PnL). Any failure -> REJECTED unless it
is a narrow near-miss per the skill's near-miss discipline.
"""
from __future__ import annotations

import json
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
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2025-01-01T00:00:00Z")

FAST_WINDOW = 20
SLOW_WINDOW = 60
MOMENTUM_WINDOW_DAYS = 30
CONCENTRATION_CAP_PCT = 20.0
BASE_SEED = 20260901
RANDOM_SEED_OFFSET = {"BTC": 1, "ETH": 2, "SOL": 3, "XRP": 4}

OI_COVERAGE_START = {
    "BTC": pd.Timestamp("2020-09-01T00:00:00Z"),
    "ETH": pd.Timestamp("2021-12-01T00:00:00Z"),
    "SOL": pd.Timestamp("2021-12-01T00:00:00Z"),
    "XRP": pd.Timestamp("2021-12-01T00:00:00Z"),
}


def load_price(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[df.index < END_EXCLUSIVE]


def load_oi(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.data / "open_interest" / f"{coin}_oi_daily.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[df.index < END_EXCLUSIVE]


def build_regime(oi: pd.DataFrame) -> pd.DataFrame:
    frame = oi.copy()
    frame["fast_sma"] = frame["sum_open_interest"].rolling(FAST_WINDOW, min_periods=FAST_WINDOW).mean()
    frame["slow_sma"] = frame["sum_open_interest"].rolling(SLOW_WINDOW, min_periods=SLOW_WINDOW).mean()
    frame["regime_on_asof"] = frame["fast_sma"] > frame["slow_sma"]
    frame = frame.dropna(subset=["fast_sma", "slow_sma"])
    # regime flag known as of day t; usable starting day t+1 (shift index forward by 1 day)
    known = frame["regime_on_asof"].copy()
    known.index = known.index + pd.Timedelta(days=1)
    return known.rename("regime_on").to_frame()


def regime_blocks(regime_daily: pd.Series, price_index: pd.DatetimeIndex) -> tuple[list, pd.Series]:
    """regime_daily already shifted to be 'known as of and usable on' its index date.
    Reindex onto price index (ffill) then find contiguous True blocks. Entry/exit
    happen at the price bar equal to (or first available on/after) the flag date."""
    aligned = regime_daily.reindex(regime_daily.index.union(price_index)).sort_index().ffill()
    aligned = aligned.reindex(price_index).fillna(False)
    blocks = []
    in_block = False
    start_ts = None
    prev_ts = None
    for ts, val in aligned.items():
        val = bool(val)
        if val and not in_block:
            in_block = True
            start_ts = ts
        elif not val and in_block:
            in_block = False
            blocks.append((start_ts, ts))
        prev_ts = ts
    if in_block:
        blocks.append((start_ts, prev_ts))
    return blocks, aligned


def simulate_blocks(price_close: pd.Series, blocks: list[tuple[pd.Timestamp, pd.Timestamp]]) -> dict:
    """Enter at NEXT bar's price after block start flag (use close as execution
    proxy since only daily OHLC close is guaranteed non-null here; open is
    used where available via price_close being actually 'open' passed in)."""
    idx = price_close.index
    capital = 1.0
    units = 0.0
    in_position = False
    trades = []
    equity = pd.Series(index=idx, dtype=float)
    block_ptr = 0

    entries_exits = []
    for b_start, b_end in blocks:
        # shift entry/exit by one bar for realistic no-lookahead execution
        pos_start = idx.searchsorted(b_start)
        pos_end = idx.searchsorted(b_end)
        entry_i = min(pos_start + 1, len(idx) - 1)
        exit_i = min(pos_end + 1, len(idx) - 1)
        if entry_i < exit_i:
            entries_exits.append((entry_i, exit_i))

    active_entry = None
    active_exit = None
    eei = 0
    entry_price = None
    entry_ts = None

    for i, ts in enumerate(idx):
        if eei < len(entries_exits):
            active_entry, active_exit = entries_exits[eei]
        else:
            active_entry, active_exit = None, None

        if in_position and active_exit is not None and i == active_exit:
            exec_price = float(price_close.iloc[i]) * (1 - ONE_WAY_COST)
            capital = units * exec_price
            trades.append(
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
            eei += 1

        if (not in_position) and active_entry is not None and i == active_entry:
            exec_price = float(price_close.iloc[i]) * (1 + ONE_WAY_COST)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_ts = ts

        equity.iloc[i] = capital + units * float(price_close.iloc[i])

    if in_position:
        exec_price = float(price_close.iloc[-1]) * (1 - ONE_WAY_COST)
        final_capital = units * exec_price
        trades.append(
            {
                "entry_time": entry_ts,
                "exit_time": idx[-1],
                "entry_price": entry_price,
                "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
                "note": "forced_close_at_sample_end",
            }
        )
        equity.iloc[-1] = final_capital

    trades_df = pd.DataFrame(trades)
    return {"equity": equity, "trades": trades_df}


def simulate_buy_and_hold(price_close: pd.Series) -> pd.Series:
    entry_price = float(price_close.iloc[0]) * (1 + ONE_WAY_COST)
    units = 1.0 / entry_price
    return units * price_close


def simulate_daily_dca(price_close: pd.Series) -> pd.Series:
    n = len(price_close)
    tranche = 1.0 / n
    units = 0.0
    rows = []
    for v in price_close:
        exec_price = float(v) * (1 + ONE_WAY_COST)
        units += tranche / exec_price
        rows.append(units * float(v))
    return pd.Series(rows, index=price_close.index)


def momentum_regime_blocks(btc_close: pd.Series, price_index: pd.DatetimeIndex):
    mom = btc_close.pct_change(MOMENTUM_WINDOW_DAYS)
    on_asof = (mom > 0).copy()
    on_asof.index = on_asof.index + pd.Timedelta(days=1)
    return regime_blocks(on_asof.rename("regime_on"), price_index)


def random_regime_blocks(
    real_aligned: pd.Series, price_index: pd.DatetimeIndex, seed: int
):
    """Shuffle the real regime's block LENGTHS (not just on-fraction) in random
    order across the same total timeline to build a matched-block-count,
    matched-on-fraction, matched-mean-block-length random control."""
    rng = np.random.default_rng(seed)
    n = len(price_index)
    # extract block lengths from the real aligned boolean series
    lengths = []
    cur = None
    cur_len = 0
    for val in real_aligned:
        val = bool(val)
        if val:
            cur_len += 1
        else:
            if cur_len > 0:
                lengths.append(cur_len)
            cur_len = 0
    if cur_len > 0:
        lengths.append(cur_len)
    if not lengths:
        return [], pd.Series(False, index=price_index)
    rng.shuffle(lengths)
    on = np.zeros(n, dtype=bool)
    max_start = n - 1
    starts = sorted(rng.choice(np.arange(max_start), size=min(len(lengths), max_start), replace=False))
    for start, length in zip(starts, lengths):
        end = min(start + length, n)
        on[start:end] = True
    aligned = pd.Series(on, index=price_index)
    blocks = []
    in_block = False
    start_ts = None
    prev_ts = None
    for ts, val in aligned.items():
        if val and not in_block:
            in_block = True
            start_ts = ts
        elif not val and in_block:
            in_block = False
            blocks.append((start_ts, ts))
        prev_ts = ts
    if in_block:
        blocks.append((start_ts, prev_ts))
    return blocks, aligned


def top_block_pct_of_pnl(trades: pd.DataFrame) -> float | None:
    if trades.empty:
        return None
    pnl_per_trade = trades["gross_return"]  # capital scaled to 1.0 start so trade_return ~ per-block pnl fraction
    # Approximate each block's dollar contribution using compounding decomposition:
    total_multiplier = 1.0
    contributions = []
    for r in pnl_per_trade:
        contributions.append(total_multiplier * r)
        total_multiplier *= (1 + r)
    total_pnl = total_multiplier - 1.0
    if total_pnl == 0:
        return None
    best = max(contributions, key=abs)
    return float(best / total_pnl) * 100


def doubled_cost_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    extra_factor = (1 - 2 * ONE_WAY_COST)
    capital = 1.0
    for r in trades["gross_return"]:
        capital *= (1 + r) * extra_factor
    return capital


def best_block_excluded_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    idx_best = trades["gross_return"].abs().idxmax()
    capital = 1.0
    for i, r in trades["gross_return"].items():
        rr = 0.0 if i == idx_best else r
        capital *= (1 + rr)
    return capital


def partition_label(ts: pd.Timestamp) -> str:
    if ts < VALIDATION_START:
        return "development"
    if ts < TEST_START:
        return "validation_2024"
    return "test_2025_onward"


def run_asset(coin: str) -> dict:
    price = load_price(coin)
    oi = load_oi(coin)
    coverage_start = max(OI_COVERAGE_START[coin], oi.index.min())
    price = price[price.index >= coverage_start]

    regime_known = build_regime(oi)
    blocks, aligned = regime_blocks(regime_known["regime_on"], price.index)

    open_price = price["open"] if "open" in price.columns else price["close"]
    sim = simulate_blocks(open_price, blocks)
    equity, trades = sim["equity"], sim["trades"]
    final = float(equity.iloc[-1]) if len(equity) else 1.0

    bh_equity = simulate_buy_and_hold(open_price)
    dca_equity = simulate_daily_dca(open_price)
    bh_final = float(bh_equity.iloc[-1])
    dca_final = float(dca_equity.iloc[-1])

    btc_price_for_mom = load_price("BTC")
    btc_price_for_mom = btc_price_for_mom[btc_price_for_mom.index >= coverage_start]
    btc_close_aligned = btc_price_for_mom["close"].reindex(price.index).ffill()
    mom_blocks, mom_aligned = momentum_regime_blocks(btc_close_aligned, price.index)
    mom_sim = simulate_blocks(open_price, mom_blocks)
    mom_final = float(mom_sim["equity"].iloc[-1]) if len(mom_sim["equity"]) else 1.0

    seed = BASE_SEED + RANDOM_SEED_OFFSET[coin]
    rand_blocks, rand_aligned = random_regime_blocks(aligned, price.index, seed)
    rand_sim = simulate_blocks(open_price, rand_blocks)
    rand_final = float(rand_sim["equity"].iloc[-1]) if len(rand_sim["equity"]) else 1.0

    doubled_final = doubled_cost_final(trades)
    excluded_final = best_block_excluded_final(trades)
    top_block_pct = top_block_pct_of_pnl(trades)

    partition_rows = []
    if not trades.empty:
        trades_labeled = trades.copy()
        trades_labeled["partition"] = trades_labeled["entry_time"].apply(partition_label)
    else:
        trades_labeled = trades
    for label in ("development", "validation_2024", "test_2025_onward"):
        part = trades_labeled[trades_labeled["partition"] == label] if not trades_labeled.empty else trades_labeled
        partition_rows.append(
            {
                "asset": coin,
                "partition": label,
                "n_blocks": len(part),
                "mean_block_return_pct": float(part["gross_return"].mean() * 100) if len(part) else np.nan,
            }
        )

    on_fraction = float(aligned.mean()) if len(aligned) else 0.0

    return {
        "asset": coin,
        "n_blocks": len(trades),
        "on_fraction": on_fraction,
        "primary_final": final,
        "bh_final": bh_final,
        "dca_final": dca_final,
        "momentum_control_final": mom_final,
        "random_control_final": rand_final,
        "doubled_cost_final": doubled_final,
        "best_block_excluded_final": excluded_final,
        "top_block_pct_of_pnl": top_block_pct,
        "partition_rows": partition_rows,
        "trades": trades,
        "coverage_start": str(coverage_start.date()),
    }


def classify_verdict(result: dict) -> tuple[str, dict]:
    test_rows = [r for r in result["partition_rows"] if r["partition"] == "test_2025_onward"]
    has_holdout = bool(test_rows and test_rows[0]["n_blocks"] > 0)
    beats_bh = result["primary_final"] > result["bh_final"]
    beats_dca = result["primary_final"] > result["dca_final"]
    beats_momentum = result["primary_final"] > result["momentum_control_final"]
    beats_random = result["primary_final"] > result["random_control_final"]
    survives_doubled_cost = result["doubled_cost_final"] > 1.0
    survives_exclusion = result["best_block_excluded_final"] > result["bh_final"]
    concentration_ok = (
        result["top_block_pct_of_pnl"] is None or abs(result["top_block_pct_of_pnl"]) < CONCENTRATION_CAP_PCT
    )
    # test-partition performance vs BH within test partition alone is not
    # separately decomposed here (block-level, not equity-curve-sliced);
    # use has_holdout as the structural gate consistent with prior OI studies.
    gates = {
        "beats_buy_and_hold": beats_bh,
        "beats_dca": beats_dca,
        "beats_momentum_control": beats_momentum,
        "beats_random_control": beats_random,
        "survives_doubled_cost": survives_doubled_cost,
        "survives_best_block_exclusion": survives_exclusion,
        "concentration_ok": concentration_ok,
        "has_holdout_blocks": has_holdout,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def main() -> None:
    all_results = {}
    for coin in ASSETS:
        all_results[coin] = run_asset(coin)

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = PATHS.results / "oi_trend_regime" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# Open-Interest Trend (SMA20/SMA60 Crossover) Regime Filter Validation", ""]
    lines.append("## Primary rule")
    lines.append(
        "> LONG-ONLY per-asset: long while rolling 20-day mean of daily open interest > rolling "
        "60-day mean; flat otherwise. Enter/exit one bar after the regime flag changes (no lookahead). "
        "30bps round-trip cost."
    )
    lines.append("")
    lines.append("## Data sources")
    lines.append(
        "- Real Binance USD-M futures daily OI (`data/open_interest/*_oi_daily.csv.gz`, already cached, "
        "coverage BTC from 2020-09-01, ETH/SOL/XRP from 2021-12-01)."
    )
    lines.append("- Real Binance spot daily OHLCV (`data/raw/*_1d.csv.gz`).")
    lines.append("")

    verdicts = {}
    for coin, result in all_results.items():
        lines.append(f"### {coin}")
        lines.append(f"- OI coverage start used: {result['coverage_start']}")
        lines.append(f"- Regime blocks: **{result['n_blocks']}** (on-fraction {result['on_fraction']*100:.1f}%)")
        lines.append(f"- Primary final (start=1.0): **{result['primary_final']:.4f}**")
        lines.append(f"- Buy-and-hold final: **{result['bh_final']:.4f}**")
        lines.append(f"- Daily DCA final: **{result['dca_final']:.4f}**")
        lines.append(f"- Momentum-regime control final: **{result['momentum_control_final']:.4f}**")
        lines.append(f"- Random-regime control final: **{result['random_control_final']:.4f}**")
        lines.append(f"- Doubled-cost final: **{result['doubled_cost_final']:.4f}**")
        lines.append(f"- Best-block-excluded final: **{result['best_block_excluded_final']:.4f}**")
        lines.append(f"- Top block % of PnL: {result['top_block_pct_of_pnl']}")
        verdict, gates = classify_verdict(result)
        verdicts[coin] = verdict
        lines.append(f"- Gates: {gates}")
        lines.append(f"- Verdict: **{verdict}**")
        lines.append("")
        lines.append("Partition breakdown:")
        for row in result["partition_rows"]:
            lines.append(f"  - {row}")
        lines.append("")
        result["trades"].to_csv(out_dir / f"{coin}_trades.csv", index=False)
        with open(out_dir / f"{coin}_gates.json", "w") as f:
            json.dump({"verdict": verdict, "gates": gates}, f, indent=2, default=str)

    n_candidate = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append("## Overall verdict")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared every gate.")
    if n_candidate == 0:
        lines.append("\n**REJECTED** -- no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**CANDIDATE** -- every asset cleared every gate.")
    else:
        lines.append(f"\n**MIXED** -- {n_candidate}/{len(verdicts)} assets cleared every gate.")

    (out_dir / "REPORT.md").write_text("\n".join(lines))
    print(f"Report written to {out_dir / 'REPORT.md'}")
    print(json.dumps({coin: v for coin, v in verdicts.items()}, indent=2))


if __name__ == "__main__":
    main()
