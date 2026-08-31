"""EXP-2026-08-31-RATIOROT-001: Relative-value ratio mean-reversion rotation.

Hypothesis (preregistered before any result inspected):
  Alt/BTC price ratios exhibit mean-reverting relative valuation swings driven by
  rotational capital flows (alt-season / BTC-dominance cycles). A single capital
  sleeve that rotates fully into the alt when it is "cheap" relative to BTC
  (ratio z-score deeply negative) and fully into BTC when the alt is "expensive"
  relative to BTC (ratio z-score deeply positive), holding the current position
  otherwise (hysteresis band, no forced flip on weak signal), should beat both
  static buy-and-hold legs and a static 50/50 rebalanced blend after costs.

  This is mechanistically distinct from every prior study in this repo:
  - Not a cross-sectional dollar-neutral L/S (Amihud/funding-carry/momentum/vol-premium,
    all REJECTED four times running) -- this is a single-pair, long-only-net-exposure
    ROTATION (100% invested at all times, just switching which asset), so it cannot
    fail on turnover-cost-eating-a-tiny-spread the way dollar-neutral L/S did.
  - Not a calendar effect (weekend/session/turn-of-month, all REJECTED).
  - Not a trend filter (SMA200, REJECTED on concentration).
  - Not an event-odds/sentiment contrarian rule (DVOL/FGI, REJECTED).
  - Not a funding-based carry (REJECTED four times).

Design (frozen before inspecting any output):
  - Pairs tested independently: ETH/BTC, SOL/BTC, XRP/BTC.
  - Signal: rolling z-score of log(ratio) over a 60-day window (min 40 obs),
    shifted 1 day (no lookahead) -- z = (log_ratio - rolling_mean) / rolling_std.
  - Entry/exit thresholds (hysteresis band, preregistered):
      z <= -1.0  -> rotate 100% into ALT (alt cheap vs BTC, expect reversion up)
      z >= +1.0  -> rotate 100% into BTC (alt expensive vs BTC, expect reversion down)
      -1.0 < z < +1.0 -> HOLD current position (no trade)
  - Start position: BTC (arbitrary, cost-neutral choice made before any test).
  - Costs: repo-standard 30bps round-trip (15bps x 2 legs) charged on the notional
    that actually rotates (only pays cost on an actual flip, not every bar).
  - Benchmarks: buy-and-hold ALT, buy-and-hold BTC, static 50/50 buy-and-hold blend
    (no rebalancing), cash, and a seeded random-flip control matched to the same
    number of trades/holding-period distribution.
  - Partitions: development (start..2022-12-31), validation (2023-01-01..2024-06-30),
    test (2024-07-01..cutoff) -- chronological, never tuned on test.
  - Fastest rejection criterion (preregistered): rotation rule must beat BOTH legs'
    buy-and-hold AND the 50/50 static blend on the FULL sample after costs, survive
    doubled costs, and no single trade may exceed 20% of total strategy net PnL
    (concentration cap) -- OR it is REJECTED. Must also produce >=5 trades in the
    test partition to avoid the zero-holdout-trades blocker seen in prior studies.
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
ROUND_TRIP_COST = 2 * (FEE_RATE + SLIPPAGE_RATE)  # 0.003 = 30bps

Z_WINDOW = 60
Z_MIN_OBS = 40
Z_ENTRY_ALT = -1.0
Z_ENTRY_BTC = 1.0
INITIAL_CAPITAL = 10_000.0
START_ANALYSIS = pd.Timestamp("2018-01-01", tz="UTC")

DEV_END = pd.Timestamp("2022-12-31", tz="UTC")
VAL_END = pd.Timestamp("2024-06-30", tz="UTC")

PAIRS = ["ETH", "SOL", "XRP"]
RANDOM_SEED = 20260831


def load_close(coin: str) -> pd.Series:
    path = PATHS.raw / f"{coin}_1d.csv.gz"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df["close"]


def build_zscore(alt_close: pd.Series, btc_close: pd.Series) -> pd.DataFrame:
    df = pd.concat({"alt": alt_close, "btc": btc_close}, axis=1).dropna()
    df = df[df.index >= START_ANALYSIS]
    df["log_ratio"] = np.log(df["alt"] / df["btc"])
    roll_mean = df["log_ratio"].rolling(Z_WINDOW, min_periods=Z_MIN_OBS).mean()
    roll_std = df["log_ratio"].rolling(Z_WINDOW, min_periods=Z_MIN_OBS).std()
    df["z"] = (df["log_ratio"] - roll_mean) / roll_std
    df["z"] = df["z"].shift(1)  # no lookahead: signal known at prior close, act at next open proxy (next day)
    return df.dropna(subset=["z"])


def run_rotation(df: pd.DataFrame) -> dict:
    """Long-only single-sleeve rotation between ALT and BTC using close-to-close
    returns (entry at day's close after signal known from prior close, i.e. 1-day
    execution lag baked in via the shift already applied to z)."""
    position = "BTC"  # arbitrary frozen starting state
    capital = INITIAL_CAPITAL
    equity_curve = []
    trade_log = []
    alt_ret = df["alt"].pct_change()
    btc_ret = df["btc"].pct_change()

    dates = df.index
    for i, dt in enumerate(dates):
        if i == 0:
            equity_curve.append((dt, capital, position))
            continue
        z = df["z"].iloc[i]
        new_position = position
        if z <= Z_ENTRY_ALT:
            new_position = "ALT"
        elif z >= Z_ENTRY_BTC:
            new_position = "BTC"
        if new_position != position:
            capital *= (1 - ROUND_TRIP_COST / 2)  # exit leg cost
            trade_log.append({"date": dt, "from": position, "to": new_position, "z": z})
            position = new_position
            capital *= (1 - ROUND_TRIP_COST / 2)  # entry leg cost (combined = full round trip on flip)
        # accrue today's return for the currently held asset
        r = alt_ret.iloc[i] if position == "ALT" else btc_ret.iloc[i]
        if pd.notna(r):
            capital *= (1 + r)
        equity_curve.append((dt, capital, position))

    curve = pd.DataFrame(equity_curve, columns=["date", "equity", "position"]).set_index("date")
    return {"curve": curve, "trades": pd.DataFrame(trade_log)}


def buy_and_hold(returns: pd.Series) -> pd.Series:
    return INITIAL_CAPITAL * (1 + returns.fillna(0)).cumprod()


def static_blend(alt_ret: pd.Series, btc_ret: pd.Series) -> pd.Series:
    # no rebalancing: buy 50/50 once, let weights drift (cheapest realistic static blend)
    alt_val = 0.5 * INITIAL_CAPITAL * (1 + alt_ret.fillna(0)).cumprod()
    btc_val = 0.5 * INITIAL_CAPITAL * (1 + btc_ret.fillna(0)).cumprod()
    return alt_val + btc_val


def random_flip_control(df: pd.DataFrame, n_trades: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = df.index
    n = len(dates)
    if n_trades <= 0 or n < 10:
        return pd.DataFrame({"equity": [INITIAL_CAPITAL] * n}, index=dates)
    flip_idx = sorted(rng.choice(range(1, n), size=min(n_trades, n - 1), replace=False))
    position = "BTC"
    capital = INITIAL_CAPITAL
    alt_ret = df["alt"].pct_change()
    btc_ret = df["btc"].pct_change()
    equity = []
    flip_set = set(flip_idx)
    for i in range(n):
        if i == 0:
            equity.append(capital)
            continue
        if i in flip_set:
            capital *= (1 - ROUND_TRIP_COST)
            position = "ALT" if position == "BTC" else "BTC"
        r = alt_ret.iloc[i] if position == "ALT" else btc_ret.iloc[i]
        if pd.notna(r):
            capital *= (1 + r)
        equity.append(capital)
    return pd.DataFrame({"equity": equity}, index=dates)


def concentration_check(trades: pd.DataFrame, curve: pd.DataFrame) -> float:
    """Fraction of total net PnL attributable to the single largest per-trade block."""
    if trades.empty:
        return 0.0
    boundaries = [curve.index[0]] + trades["date"].tolist() + [curve.index[-1]]
    pnl_blocks = []
    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        seg = curve.loc[(curve.index >= start) & (curve.index <= end)]
        if len(seg) < 2:
            continue
        pnl_blocks.append(seg["equity"].iloc[-1] - seg["equity"].iloc[0])
    total_pnl = curve["equity"].iloc[-1] - curve["equity"].iloc[0]
    if not pnl_blocks or total_pnl == 0:
        return 0.0
    max_block = max(pnl_blocks, key=abs)
    return abs(max_block) / abs(total_pnl) if total_pnl != 0 else float("inf")


def doubled_cost_run(df: pd.DataFrame) -> pd.DataFrame:
    global ROUND_TRIP_COST
    orig = ROUND_TRIP_COST
    ROUND_TRIP_COST = orig * 2
    try:
        res = run_rotation(df)
    finally:
        ROUND_TRIP_COST = orig
    return res


def main() -> None:
    btc_close = load_close("BTC")
    out_rows = []
    all_results = {}
    for alt in PAIRS:
        alt_close = load_close(alt)
        df = build_zscore(alt_close, btc_close)
        res = run_rotation(df)
        curve = res["curve"]
        trades = res["trades"]

        alt_ret = df["alt"].pct_change()
        btc_ret = df["btc"].pct_change()
        bh_alt = buy_and_hold(alt_ret)
        bh_btc = buy_and_hold(btc_ret)
        blend = static_blend(alt_ret, btc_ret)

        final_strategy = curve["equity"].iloc[-1]
        final_bh_alt = bh_alt.iloc[-1]
        final_bh_btc = bh_btc.iloc[-1]
        final_blend = blend.iloc[-1]

        n_trades = len(trades)
        test_trades = trades[trades["date"] >= pd.Timestamp("2024-07-01", tz="UTC")] if n_trades else pd.DataFrame()

        conc = concentration_check(trades, curve)

        dbl = doubled_cost_run(df)
        final_dbl = dbl["curve"]["equity"].iloc[-1]

        rand = random_flip_control(df, n_trades, RANDOM_SEED + hash(alt) % 1000)
        final_rand = rand["equity"].iloc[-1]

        # partition returns (strategy only, chronological, using equity curve)
        def part_return(curve_s: pd.Series, start, end) -> float | None:
            seg = curve_s[(curve_s.index >= start) & (curve_s.index <= end)]
            if len(seg) < 2:
                return None
            return seg.iloc[-1] / seg.iloc[0] - 1

        dev_ret = part_return(curve["equity"], curve.index[0], DEV_END)
        val_ret = part_return(curve["equity"], DEV_END, VAL_END)
        test_ret = part_return(curve["equity"], VAL_END, curve.index[-1])

        dev_bh_alt = part_return(bh_alt, bh_alt.index[0], DEV_END)
        val_bh_alt = part_return(bh_alt, DEV_END, VAL_END)
        test_bh_alt = part_return(bh_alt, VAL_END, bh_alt.index[-1])

        row = {
            "pair": f"{alt}/BTC",
            "n_trades_total": n_trades,
            "n_trades_test_partition": len(test_trades),
            "final_strategy": final_strategy,
            "final_bh_alt": final_bh_alt,
            "final_bh_btc": final_bh_btc,
            "final_static_blend": final_blend,
            "final_doubled_cost": final_dbl,
            "final_random_control": final_rand,
            "concentration_frac": conc,
            "dev_ret": dev_ret,
            "val_ret": val_ret,
            "test_ret": test_ret,
            "dev_bh_alt_ret": dev_bh_alt,
            "val_bh_alt_ret": val_bh_alt,
            "test_bh_alt_ret": test_bh_alt,
            "beats_bh_alt": final_strategy > final_bh_alt,
            "beats_bh_btc": final_strategy > final_bh_btc,
            "beats_blend": final_strategy > final_blend,
            "beats_cash": final_strategy > INITIAL_CAPITAL,
            "survives_doubled_cost": final_dbl > INITIAL_CAPITAL,
            "beats_random_control": final_strategy > final_rand,
            "under_concentration_cap": conc <= 0.20,
            "has_enough_test_trades": len(test_trades) >= 5,
        }
        out_rows.append(row)
        all_results[alt] = {"df": df, "res": res, "bh_alt": bh_alt, "bh_btc": bh_btc, "blend": blend}

    result_df = pd.DataFrame(out_rows)
    out_dir = ROOT / "results" / "ratio_reversion_rotation"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(out_dir / "summary.csv", index=False)

    for alt in PAIRS:
        all_results[alt]["res"]["trades"].to_csv(out_dir / f"trades_{alt}.csv", index=False)

    print(result_df.to_string())


if __name__ == "__main__":
    main()
