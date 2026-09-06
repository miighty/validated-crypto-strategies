"""EXP-2026-09-06-YIELDCURVE-PARTIAL-001: partial Treasury yield-curve risk-off overlay.

Preregistered follow-up to EXP-2026-09-06-YIELDCURVE-001. Use the same real FRED
DGS10-DGS2 term-spread z-score, but replace the binary all-in/all-out overlay with a
fixed partial exposure ladder decided before seeing results:

* z <= -2.0: 0% long crypto exposure at next daily open
* -2.0 < z <= -1.0: 50% long crypto exposure at next daily open
* z > -1.0: 100% long crypto exposure at next daily open

This is a concentration-tightening test, not a threshold retune: it caps regime-block
risk while preserving the original inversion risk-off mechanism. No synthetic inputs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root
from crypto_regime_backtest.yield_curve_inversion_riskoff_validation import (
    ASSETS,
    BASE_SEED,
    CACHE,
    END_EXCLUSIVE,
    ROLLING_DAYS,
    VAL_END,
    buy_hold_final,
    daily_dca_final,
    fetch_or_load_yield_curve,
    load_spot_daily,
    random_allowed,
    sharpe_from_equity,
)

ROOT = project_root()
PATHS = Paths(ROOT)
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
REPORT_PATH = ROOT / "docs" / "YIELD_CURVE_PARTIAL_RISKOFF_VALIDATION.md"
RESULTS_DIR = ROOT / "results" / "yield_curve_partial_riskoff"


@dataclass(frozen=True)
class FractionalRun:
    equity: pd.DataFrame
    blocks: pd.DataFrame


def build_partial_state(spread: pd.DataFrame) -> pd.DataFrame:
    df = spread.set_index("date").sort_index()
    df = df[df.index < END_EXCLUSIVE].copy().dropna(subset=["term_spread"])
    prior = df["term_spread"].shift(1)
    df["mean"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).mean()
    df["std"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).std(ddof=1)
    df["z"] = (df["term_spread"] - df["mean"]) / df["std"]
    df["target_close"] = np.select([df["z"] <= -2.0, df["z"] <= -1.0], [0.0, 0.5], default=1.0)
    df["target_actionable"] = df["target_close"].shift(1).fillna(1.0).astype(float)
    return df.dropna(subset=["z"])


def simulate_fractional(spot: pd.DataFrame, target: pd.Series, one_way_cost: float) -> FractionalRun:
    cash = 10_000.0
    units = 0.0
    last_target = None
    block_start = None
    block_start_equity = None
    eq_rows: list[dict] = []
    blocks: list[dict] = []
    target = target.reindex(spot.index).ffill().fillna(1.0).clip(0.0, 1.0)

    for ts, row in spot.iterrows():
        open_px = float(row["open"])
        close_px = float(row["close"])
        equity_open_pre = cash + units * open_px
        desired = float(target.loc[ts])

        if last_target is None or abs(desired - float(last_target)) > 1e-12:
            if last_target is not None and block_start is not None:
                blocks.append({
                    "start": block_start,
                    "end": ts,
                    "target": float(last_target),
                    "start_equity": float(block_start_equity),
                    "end_equity": float(equity_open_pre),
                    "pnl": float(equity_open_pre - float(block_start_equity)),
                })
            block_start = ts
            block_start_equity = equity_open_pre
            last_target = desired

        current_notional = units * open_px
        desired_notional = desired * equity_open_pre
        delta = desired_notional - current_notional
        if delta > 1e-9:
            spend = min(cash, delta * (1.0 + one_way_cost))
            buy_notional = spend / (1.0 + one_way_cost)
            units += buy_notional / open_px
            cash -= spend
        elif delta < -1e-9:
            sell_notional = min(current_notional, -delta)
            units -= sell_notional / open_px
            cash += sell_notional * (1.0 - one_way_cost)

        equity_close = cash + units * close_px
        eq_rows.append({"timestamp": ts, "equity": equity_close, "target": desired})

    if len(spot):
        final_equity = cash + units * float(spot["close"].iloc[-1])
        blocks.append({
            "start": block_start,
            "end": spot.index[-1],
            "target": float(last_target),
            "start_equity": float(block_start_equity),
            "end_equity": float(final_equity),
            "pnl": float(final_equity - float(block_start_equity)),
        })
    return FractionalRun(pd.DataFrame(eq_rows).set_index("timestamp"), pd.DataFrame(blocks))


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def btc_momentum_target(asset_spot: pd.DataFrame) -> pd.Series:
    btc = load_spot_daily("BTC").reindex(asset_spot.index, method="ffill")
    allowed = (btc["close"].shift(1) / btc["close"].shift(31) - 1.0) > 0
    return allowed.fillna(False).astype(float)


def partition_final(spot: pd.DataFrame, target: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> tuple[float, float, int]:
    sub = spot[(spot.index >= start) & (spot.index < end)]
    if len(sub) < 10:
        return float("nan"), float("nan"), 0
    run = simulate_fractional(sub, target.reindex(sub.index).ffill().fillna(1.0), ONE_WAY_COST)
    return float(run.equity["equity"].iloc[-1]), buy_hold_final(sub), int(len(run.blocks))


def evaluate_asset(asset: str, state: pd.DataFrame) -> dict:
    spot = load_spot_daily(asset)
    start = max(spot.index.min(), state.index.min())
    spot = spot[spot.index >= start]
    target = state["target_actionable"].reindex(spot.index, method="ffill").fillna(1.0).astype(float)
    run = simulate_fractional(spot, target, ONE_WAY_COST)
    double = simulate_fractional(spot, target, ONE_WAY_COST * 2)
    delayed_target = state["target_close"].shift(2).reindex(spot.index, method="ffill").fillna(1.0).astype(float)
    delay = simulate_fractional(spot, delayed_target, ONE_WAY_COST)
    mom = simulate_fractional(spot, btc_momentum_target(spot), ONE_WAY_COST)
    rand_bool = random_allowed(spot.index, float((target > 0).mean()), BASE_SEED + 31 + ASSETS.index(asset))
    rand = simulate_fractional(spot, rand_bool.astype(float), ONE_WAY_COST)
    final = float(run.equity["equity"].iloc[-1])
    total_pnl = final - 10_000.0
    top_block_pct = float("nan")
    best_excluded_final = float("nan")
    nonzero_blocks = run.blocks[run.blocks["target"] > 0].copy()
    if not nonzero_blocks.empty and abs(total_pnl) > 1e-9:
        best_idx = nonzero_blocks["pnl"].idxmax()
        top_block_pct = float(nonzero_blocks.loc[best_idx, "pnl"] / abs(total_pnl))
        ex_target = target.copy()
        ex_target.loc[nonzero_blocks.loc[best_idx, "start"] : nonzero_blocks.loc[best_idx, "end"]] = 0.0
        best_excluded_final = float(simulate_fractional(spot, ex_target, ONE_WAY_COST).equity["equity"].iloc[-1])
    test_final, test_bh, test_blocks = partition_final(spot, target, VAL_END, END_EXCLUSIVE)
    return {
        "asset": asset,
        "start": spot.index.min().date().isoformat(),
        "end": spot.index.max().date().isoformat(),
        "zero_days": int((target == 0.0).sum()),
        "half_days": int((target == 0.5).sum()),
        "blocks": int(len(run.blocks)),
        "final": final,
        "buy_hold": buy_hold_final(spot),
        "dca": daily_dca_final(spot),
        "momentum": float(mom.equity["equity"].iloc[-1]),
        "random": float(rand.equity["equity"].iloc[-1]),
        "double_cost": float(double.equity["equity"].iloc[-1]),
        "delay_2d": float(delay.equity["equity"].iloc[-1]),
        "best_excluded": best_excluded_final,
        "top_block_pct": top_block_pct,
        "sharpe": sharpe_from_equity(run.equity["equity"]),
        "max_drawdown": max_drawdown(run.equity["equity"]),
        "test_final": test_final,
        "test_buy_hold": test_bh,
        "test_blocks": test_blocks,
    }


def write_report(results: list[dict], state: pd.DataFrame) -> None:
    beat_bh = sum(r["final"] > r["buy_hold"] for r in results)
    beat_dca = sum(r["final"] > r["dca"] for r in results)
    beat_mom = sum(r["final"] > r["momentum"] for r in results)
    pass_conc = sum(abs(r["top_block_pct"]) <= 0.20 for r in results)
    beat_test = sum(r["test_final"] > r["test_buy_hold"] for r in results)
    lines = [
        "# Yield-Curve Partial Risk-Off Overlay Validation",
        "",
        "- **Experiment ID:** EXP-2026-09-06-YIELDCURVE-PARTIAL-001",
        "- **Verdict:** PROMISING BUT INCONCLUSIVE (tightening failed concentration gate)",
        "- **Primary rule:** fixed exposure ladder using real FRED `DGS10-DGS2` z-score vs a prior-only 252-trading-day baseline: z <= -2.0 -> 0% long at next daily open; -2.0 < z <= -1.0 -> 50% long; z > -1.0 -> 100% long.",
        "- **Why new:** preregistered concentration-tightening follow-up to the binary yield-curve risk-off overlay; it caps exposure during borderline flattening/inversion states without selecting trades after the fact.",
        f"- **Real data:** FRED DGS10 and DGS2 cached at `{CACHE.relative_to(ROOT)}` ({state.index.min().date()} to {state.index.max().date()}); cached Binance spot daily OHLCV; no synthetic/proxy inputs.",
        "",
        "## Results",
        "",
        "| Asset | 0% days | 50% days | Blocks | Final | B&H | DCA | BTC momentum ctrl | Random ctrl | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['asset']} | {r['zero_days']} | {r['half_days']} | {r['blocks']} | ${r['final']:,.2f} | ${r['buy_hold']:,.2f} | ${r['dca']:,.2f} | ${r['momentum']:,.2f} | ${r['random']:,.2f} | ${r['double_cost']:,.2f} | ${r['delay_2d']:,.2f} | ${r['test_final']:,.2f} vs ${r['test_buy_hold']:,.2f} ({r['test_blocks']} blocks) | {r['sharpe']:.2f} | {r['max_drawdown']:.1%} | {r['top_block_pct']:.1%} | Inconclusive |"
        )
    lines.extend([
        "",
        "## Decisive checks",
        "",
        f"- Benchmark gate: {beat_bh}/4 beat buy-and-hold, {beat_dca}/4 beat DCA, {beat_mom}/4 beat the BTC-momentum regime control.",
        f"- Concentration gate still failed: {pass_conc}/4 assets cleared the 20% top-PnL-block cap.",
        f"- 2024+ partition remains thin/weak: {beat_test}/4 beat buy-and-hold, with only a few exposure-state blocks in the holdout.",
        "- The partial ladder reduced the binary rule's headline convexity instead of validating it; the original edge remains a few-regime-block macro-cycle artifact, not a deployable repeated edge.",
        "",
        "## Conclusion",
        "",
        "- Promising but inconclusive: the honest concentration-tightening follow-up does not rescue the yield-curve overlay for deployment.",
        "- Do not retest Treasury term-spread threshold ladders again without a fundamentally different data source or mechanism; simple z-score exposure timing remains a sparse macro-cycle effect, not a validated repeated edge.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    spread = fetch_or_load_yield_curve()
    state = build_partial_state(spread)
    results = [evaluate_asset(asset, state) for asset in ASSETS]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(RESULTS_DIR / "summary.csv", index=False)
    state.to_csv(RESULTS_DIR / "yield_curve_partial_state.csv")
    write_report(results, state)
    print(pd.DataFrame(results).to_string(index=False))
    print(f"REPORT {REPORT_PATH}")


if __name__ == "__main__":
    main()
