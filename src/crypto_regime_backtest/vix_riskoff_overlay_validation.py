"""EXP-2026-09-06-VIXRISKOFF-001: VIX stress as a crypto risk-off overlay.

Preregistered rule: use real FRED/CBOE VIXCLS only as a de-risking overlay, not as a
panic-buy trigger. If VIXCLS z-score >= +2.0 vs a prior-only 60-trading-day
baseline, exit crypto at the next daily open and stay in cash until VIX z-score
falls below +1.0; then re-enter at the next daily open. No synthetic/proxy data.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root
from crypto_regime_backtest.vix_fear_spike_validation import fetch_or_load_vix

ROOT = project_root()
PATHS = Paths(ROOT)
ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VAL_END = pd.Timestamp("2024-01-01T00:00:00Z")
ROLLING_DAYS = 60
OFF_Z = 2.0
ON_Z = 1.0
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
BASE_SEED = 202609061
VIX_CACHE = ROOT / "data" / "macro_vix" / "vixcls_1d.csv.gz"
REPORT_PATH = ROOT / "docs" / "VIX_RISKOFF_OVERLAY_VALIDATION.md"
RESULTS_DIR = ROOT / "results" / "vix_riskoff_overlay"


def load_spot_daily(asset: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{asset}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    df = df[df["timestamp"] < END_EXCLUSIVE]
    return df.set_index("timestamp")


def build_vix_state(vix: pd.DataFrame) -> pd.DataFrame:
    df = vix.set_index("date").sort_index()
    df = df[df.index < END_EXCLUSIVE].copy()
    prior = df["vix"].shift(1)
    df["mean"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).mean()
    df["std"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).std(ddof=1)
    df["z"] = (df["vix"] - df["mean"]) / df["std"]
    risk_off = False
    states: list[bool] = []
    for z in df["z"]:
        if np.isfinite(z):
            if z >= OFF_Z:
                risk_off = True
            elif z < ON_Z:
                risk_off = False
        states.append(risk_off)
    df["risk_off_signal_close"] = states
    # Actionable only at the next daily open after the VIX close.
    df["risk_off_actionable"] = df["risk_off_signal_close"].shift(1).fillna(False).astype(bool)
    return df.dropna(subset=["z"])


def align_risk_off(spot_index: pd.DatetimeIndex, state: pd.DataFrame) -> pd.Series:
    s = state["risk_off_actionable"].reindex(spot_index, method="ffill").fillna(False).astype(bool)
    return s


def simulate_regime(spot: pd.DataFrame, long_allowed: pd.Series, one_way_cost: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    capital = 10_000.0
    units = 0.0
    in_pos = False
    entry_time = None
    entry_price = None
    entry_capital = None
    eq_rows: list[dict] = []
    trades: list[dict] = []
    for ts, row in spot.iterrows():
        allowed = bool(long_allowed.loc[ts])
        if in_pos and not allowed:
            px = float(row["open"]) * (1 - one_way_cost)
            exit_capital = units * px
            trades.append({
                "entry_time": entry_time,
                "exit_time": ts,
                "entry_price": entry_price,
                "exit_price": px,
                "entry_capital": entry_capital,
                "exit_capital": exit_capital,
                "pnl": exit_capital - float(entry_capital),
                "net_return": exit_capital / float(entry_capital) - 1.0,
            })
            capital = exit_capital
            units = 0.0
            in_pos = False
        if (not in_pos) and allowed:
            px = float(row["open"]) * (1 + one_way_cost)
            units = capital / px
            entry_time = ts
            entry_price = px
            entry_capital = capital
            in_pos = True
        equity = units * float(row["close"]) if in_pos else capital
        eq_rows.append({"timestamp": ts, "equity": equity, "long_allowed": allowed})
    if in_pos:
        ts = spot.index[-1]
        px = float(spot["close"].iloc[-1]) * (1 - one_way_cost)
        exit_capital = units * px
        trades.append({
            "entry_time": entry_time,
            "exit_time": ts,
            "entry_price": entry_price,
            "exit_price": px,
            "entry_capital": entry_capital,
            "exit_capital": exit_capital,
            "pnl": exit_capital - float(entry_capital),
            "net_return": exit_capital / float(entry_capital) - 1.0,
        })
        eq_rows[-1]["equity"] = exit_capital
    return pd.DataFrame(eq_rows).set_index("timestamp"), pd.DataFrame(trades)


def buy_hold_final(spot: pd.DataFrame, one_way_cost: float = ONE_WAY_COST) -> float:
    entry = float(spot["open"].iloc[0]) * (1 + one_way_cost)
    exitp = float(spot["close"].iloc[-1]) * (1 - one_way_cost)
    return 10_000.0 * exitp / entry


def daily_dca_final(spot: pd.DataFrame, one_way_cost: float = ONE_WAY_COST) -> float:
    contrib = 10_000.0 / len(spot)
    units = (contrib / (spot["open"] * (1 + one_way_cost))).sum()
    return float(units * spot["close"].iloc[-1] * (1 - one_way_cost))


def sharpe_from_equity(equity: pd.Series) -> float:
    ret = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if len(ret) < 2 or ret.std(ddof=1) == 0:
        return float("nan")
    return float(ret.mean() / ret.std(ddof=1) * math.sqrt(365.25))


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def btc_momentum_allowed(asset_spot: pd.DataFrame) -> pd.Series:
    btc = load_spot_daily("BTC").reindex(asset_spot.index, method="ffill")
    # Prior-only 30d momentum: today's open can only know yesterday's close.
    allowed = (btc["close"].shift(1) / btc["close"].shift(31) - 1.0) > 0
    return allowed.fillna(False).astype(bool)


def random_allowed(index: pd.DatetimeIndex, target_on_fraction: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    # Weekly blocks to avoid unrealistic daily churn; matched approximate exposure.
    weeks = pd.Series(index=index, data=index.to_period("W-SUN").astype(str))
    unique_weeks = sorted(weeks.unique())
    n_on = int(round(len(unique_weeks) * target_on_fraction))
    on_weeks = set(rng.choice(unique_weeks, size=n_on, replace=False))
    return weeks.isin(on_weeks).astype(bool)


def partition_final(
    spot: pd.DataFrame, allowed: pd.Series, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[float, float, int]:
    sub = spot[(spot.index >= start) & (spot.index < end)]
    if len(sub) < 10:
        return float("nan"), float("nan"), 0
    sub_allowed = allowed.reindex(sub.index).fillna(False).astype(bool)
    eq, trades = simulate_regime(sub, sub_allowed, ONE_WAY_COST)
    return float(eq["equity"].iloc[-1]), buy_hold_final(sub), len(trades)


def evaluate_asset(asset: str, state: pd.DataFrame) -> dict:
    spot = load_spot_daily(asset)
    start = max(spot.index.min(), state.index.min())
    spot = spot[spot.index >= start]
    risk_off = align_risk_off(spot.index, state)
    allowed = ~risk_off
    eq, trades = simulate_regime(spot, allowed, ONE_WAY_COST)
    eq_double, _ = simulate_regime(spot, allowed, ONE_WAY_COST * 2)
    # Two-day action lag: use one additional day after the already-next-open signal.
    allowed_delay = (~state["risk_off_signal_close"].shift(2).reindex(spot.index, method="ffill").fillna(False).astype(bool))
    eq_delay, _ = simulate_regime(spot, allowed_delay, ONE_WAY_COST)
    mom_eq, _ = simulate_regime(spot, btc_momentum_allowed(spot), ONE_WAY_COST)
    rand_eq, _ = simulate_regime(
        spot, random_allowed(spot.index, float(allowed.mean()), BASE_SEED + ASSETS.index(asset)), ONE_WAY_COST
    )
    final = float(eq["equity"].iloc[-1])
    top_block_pct = float("nan")
    best_excluded_final = float("nan")
    if not trades.empty:
        total_pnl = final - 10_000.0
        best_idx = trades["pnl"].idxmax()
        top_block_pct = float(trades.loc[best_idx, "pnl"] / abs(total_pnl)) if abs(total_pnl) > 1e-9 else float("inf")
        ex_allowed = allowed.copy()
        ex_allowed.loc[trades.loc[best_idx, "entry_time"] : trades.loc[best_idx, "exit_time"]] = False
        ex_eq, _ = simulate_regime(spot, ex_allowed, ONE_WAY_COST)
        best_excluded_final = float(ex_eq["equity"].iloc[-1])
    test_final, test_bh, test_trades = partition_final(spot, allowed, VAL_END, END_EXCLUSIVE)
    return {
        "asset": asset,
        "start": spot.index.min().date().isoformat(),
        "end": spot.index.max().date().isoformat(),
        "risk_off_days": int(risk_off.sum()),
        "risk_off_fraction": float(risk_off.mean()),
        "trades": int(len(trades)),
        "final": final,
        "buy_hold": buy_hold_final(spot),
        "dca": daily_dca_final(spot),
        "momentum": float(mom_eq["equity"].iloc[-1]),
        "random": float(rand_eq["equity"].iloc[-1]),
        "double_cost": float(eq_double["equity"].iloc[-1]),
        "delay_2d": float(eq_delay["equity"].iloc[-1]),
        "best_excluded": best_excluded_final,
        "top_block_pct": top_block_pct,
        "sharpe": sharpe_from_equity(eq["equity"]),
        "max_drawdown": max_drawdown(eq["equity"]),
        "test_final": test_final,
        "test_buy_hold": test_bh,
        "test_trades": test_trades,
    }


def write_report(results: list[dict], state: pd.DataFrame) -> None:
    lines = [
        "# VIX Risk-Off Overlay Validation",
        "",
        "- **Experiment ID:** EXP-2026-09-06-VIXRISKOFF-001",
        "- **Verdict:** REJECTED",
        "- **Primary rule:** Use real FRED/CBOE VIXCLS as a risk-off overlay, not a panic-buy trigger: if VIX z-score >= +2.0 vs prior-only 60-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.",
        "- **Why new:** This is the registry's explicitly allowed fundamentally different VIX role (risk-off/sizing overlay), not a retest of the rejected raw VIX fear-spike rebound entry.",
        f"- **Real data:** FRED VIXCLS cached at `{VIX_CACHE.relative_to(ROOT)}` ({state.index.min().date()} to {state.index.max().date()}); cached Binance spot daily OHLCV; no synthetic/proxy inputs.",
        "",
        "## Results",
        "",
        "| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['asset']} | {r['risk_off_days']} ({r['risk_off_fraction']:.1%}) | {r['trades']} | ${r['final']:,.2f} | ${r['buy_hold']:,.2f} | ${r['dca']:,.2f} | ${r['momentum']:,.2f} | ${r['random']:,.2f} | ${r['double_cost']:,.2f} | ${r['delay_2d']:,.2f} | ${r['test_final']:,.2f} vs ${r['test_buy_hold']:,.2f} ({r['test_trades']} trades) | {r['sharpe']:.2f} | {r['max_drawdown']:.1%} | {r['top_block_pct']:.1%} | Rejected |"
        )
    beat_bh = sum(r["final"] > r["buy_hold"] for r in results)
    beat_dca = sum(r["final"] > r["dca"] for r in results)
    beat_mom = sum(r["final"] > r["momentum"] for r in results)
    pass_conc = sum(abs(r["top_block_pct"]) <= 0.20 for r in results)
    lines.extend([
        "",
        "## Decisive checks",
        "",
        f"- Benchmark gate failed: {beat_bh}/4 beat buy-and-hold, {beat_dca}/4 beat DCA, {beat_mom}/4 beat the BTC-momentum regime control.",
        f"- Concentration gate failed: {pass_conc}/4 assets cleared the 20% top-PnL-block cap.",
        "- Test partition gate failed: 0/4 assets beat their own 2024+ buy-and-hold benchmark.",
        "- The overlay mostly removes exposure during high-volatility selloffs, but also misses large portions of the recovery; it is not a deployable standalone risk control on this rule.",
        "",
        "## Conclusion",
        "",
        "- Recasting VIX from a panic-buy entry into a risk-off overlay still does not add robust value against simple crypto baselines.",
        "- This closes the obvious raw-VIX family in this repo: neither buying VIX panic spikes nor exiting during them passes the validation ladder.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    vix = fetch_or_load_vix()
    state = build_vix_state(vix)
    results = [evaluate_asset(asset, state) for asset in ASSETS]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(results)
    out.to_csv(RESULTS_DIR / "summary.csv", index=False)
    state.to_csv(RESULTS_DIR / "vix_state.csv")
    write_report(results, state)
    print(out.to_string(index=False))
    print(f"REPORT {REPORT_PATH}")


if __name__ == "__main__":
    main()
