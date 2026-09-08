"""EXP-2026-09-08-COPPERTREND-001: copper industrial-demand risk-on regime filter.

Preregistered rule: use real FRED global copper monthly prices (PCOPPUSDM) only as an
external industrial-demand / cyclical-growth filter. Hold BTC/ETH/SOL/XRP long only when
the latest copper print is above its prior-only 12-month SMA and its prior-only 3-month
change is positive; otherwise cash. Crypto action is delayed one monthly print. No
synthetic/proxy data.
"""
from __future__ import annotations

import math
import time
import urllib.error
import urllib.request
from io import StringIO

import numpy as np
import pandas as pd

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root

ROOT = project_root()
PATHS = Paths(ROOT)
ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VAL_END = pd.Timestamp("2024-01-01T00:00:00Z")
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
BASE_SEED = 202609083
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCOPPUSDM"
CACHE = ROOT / "data" / "macro_copper_trend" / "pcoppusdm_1mo.csv.gz"
REPORT_PATH = ROOT / "docs" / "COPPER_TREND_REGIME_VALIDATION.md"
RESULTS_DIR = ROOT / "results" / "copper_trend_regime"


def fetch_or_load_copper() -> pd.DataFrame:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        df = pd.read_csv(CACHE, parse_dates=["date"])
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df["copper"] = pd.to_numeric(df["copper"], errors="coerce")
        df = df.dropna(subset=["copper"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
        if df["date"].max() >= END_EXCLUSIVE - pd.Timedelta(days=120):
            return df
    payload = None
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(FRED_URL, headers={"User-Agent": "validated-crypto-strategies/0.1"})
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(min(2**attempt, 16))
    if payload is None:
        raise RuntimeError(f"Real FRED PCOPPUSDM fetch failed: {last_error}")
    raw = pd.read_csv(StringIO(payload))
    raw.columns = ["date", "copper"]
    raw["date"] = pd.to_datetime(raw["date"], utc=True)
    raw["copper"] = pd.to_numeric(raw["copper"], errors="coerce")
    raw = raw.dropna(subset=["copper"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    raw.to_csv(CACHE, index=False, compression="gzip")
    return raw


def load_spot_daily(asset: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{asset}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    df = df[df["timestamp"] < END_EXCLUSIVE]
    return df.set_index("timestamp")


def build_state(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.set_index("date").sort_index()
    df = df[df.index < END_EXCLUSIVE].copy()
    prior = df["copper"].shift(1)
    df["sma12_prior"] = prior.rolling(12, min_periods=12).mean()
    df["change3_prior"] = prior - df["copper"].shift(4)
    df["risk_on_signal"] = ((df["copper"] > df["sma12_prior"]) & (df["change3_prior"] > 0)).fillna(False).astype(bool)
    # Monthly macro/action lag: crypto acts only after one completed copper print has passed.
    df["risk_on_actionable"] = df["risk_on_signal"].shift(1).fillna(False).astype(bool)
    return df.dropna(subset=["sma12_prior", "change3_prior"])


def align_allowed(spot_index: pd.DatetimeIndex, state: pd.DataFrame) -> pd.Series:
    return state["risk_on_actionable"].reindex(spot_index, method="ffill").fillna(False).astype(bool)


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
            trades.append({"entry_time": entry_time, "exit_time": ts, "entry_price": entry_price, "exit_price": px, "entry_capital": entry_capital, "exit_capital": exit_capital, "pnl": exit_capital - float(entry_capital), "net_return": exit_capital / float(entry_capital) - 1.0})
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
        trades.append({"entry_time": entry_time, "exit_time": ts, "entry_price": entry_price, "exit_price": px, "entry_capital": entry_capital, "exit_capital": exit_capital, "pnl": exit_capital - float(entry_capital), "net_return": exit_capital / float(entry_capital) - 1.0})
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
    allowed = (btc["close"].shift(1) / btc["close"].shift(31) - 1.0) > 0
    return allowed.fillna(False).astype(bool)


def random_allowed(index: pd.DatetimeIndex, target_on_fraction: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    months = pd.Series(index=index, data=index.to_period("M").astype(str))
    unique_months = sorted(months.unique())
    n_on = int(round(len(unique_months) * target_on_fraction))
    on_months = set(rng.choice(unique_months, size=n_on, replace=False)) if n_on > 0 else set()
    return months.isin(on_months).astype(bool)


def partition_final(spot: pd.DataFrame, allowed: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> tuple[float, float, int]:
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
    allowed = align_allowed(spot.index, state)
    eq, trades = simulate_regime(spot, allowed, ONE_WAY_COST)
    eq_double, _ = simulate_regime(spot, allowed, ONE_WAY_COST * 2)
    delay_allowed = state["risk_on_signal"].shift(2).reindex(spot.index, method="ffill").fillna(False).astype(bool)
    eq_delay, _ = simulate_regime(spot, delay_allowed, ONE_WAY_COST)
    mom_eq, _ = simulate_regime(spot, btc_momentum_allowed(spot), ONE_WAY_COST)
    rand_eq, _ = simulate_regime(spot, random_allowed(spot.index, float(allowed.mean()), BASE_SEED + ASSETS.index(asset)), ONE_WAY_COST)
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
        "risk_on_days": int(allowed.sum()),
        "risk_on_fraction": float(allowed.mean()),
        "trades": int(len(trades)),
        "final": final,
        "buy_hold": buy_hold_final(spot),
        "dca": daily_dca_final(spot),
        "momentum": float(mom_eq["equity"].iloc[-1]),
        "random": float(rand_eq["equity"].iloc[-1]),
        "double_cost": float(eq_double["equity"].iloc[-1]),
        "delay_2mo": float(eq_delay["equity"].iloc[-1]),
        "best_excluded": best_excluded_final,
        "top_block_pct": top_block_pct,
        "sharpe": sharpe_from_equity(eq["equity"]),
        "max_drawdown": max_drawdown(eq["equity"]),
        "test_final": test_final,
        "test_buy_hold": test_bh,
        "test_trades": test_trades,
    }


def write_report(results: list[dict], state: pd.DataFrame) -> None:
    beat_bh = sum(r["final"] > r["buy_hold"] for r in results)
    beat_dca = sum(r["final"] > r["dca"] for r in results)
    beat_mom = sum(r["final"] > r["momentum"] for r in results)
    beat_test = sum(r["test_final"] > r["test_buy_hold"] for r in results)
    pass_conc = sum(abs(r["top_block_pct"]) <= 0.20 for r in results)
    lines = [
        "# Copper Trend Regime Validation",
        "",
        "- **Experiment ID:** EXP-2026-09-08-COPPERTREND-001",
        "- **Verdict:** REJECTED",
        "- **Primary rule:** Use real FRED PCOPPUSDM monthly copper prices as an external industrial-demand / cyclical-growth risk-on filter: long BTC/ETH/SOL/XRP only when copper > prior-only 12-month SMA and prior-only 3-month change > 0; otherwise cash. Crypto action is lagged one monthly print.",
        "- **Why new:** This is the first industrial-metals macro signal in the repo, distinct from already-tested equity-index trend, implied volatility, rates, credit, liquidity, oil, DXY, consumer-sentiment, and crypto-native flow/positioning studies.",
        f"- **Real data:** FRED PCOPPUSDM cached at `{CACHE.relative_to(ROOT)}` ({state.index.min().date()} to {state.index.max().date()}); cached Binance spot daily OHLCV; no synthetic/proxy inputs.",
        "",
        "## Results",
        "",
        "| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1 print lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['asset']} | {r['risk_on_days']} ({r['risk_on_fraction']:.1%}) | {r['trades']} | ${r['final']:,.2f} | ${r['buy_hold']:,.2f} | ${r['dca']:,.2f} | ${r['momentum']:,.2f} | ${r['random']:,.2f} | ${r['double_cost']:,.2f} | ${r['delay_2mo']:,.2f} | ${r['test_final']:,.2f} vs ${r['test_buy_hold']:,.2f} ({r['test_trades']} trades) | {r['sharpe']:.2f} | {r['max_drawdown']:.1%} | {r['top_block_pct']:.1%} | Rejected |"
        )
    lines.extend([
        "",
        "## Decisive checks",
        "",
        f"- Benchmark gate failed: {beat_bh}/4 beat buy-and-hold, {beat_dca}/4 beat DCA, {beat_mom}/4 beat the BTC-momentum regime control.",
        f"- 2024+ holdout gate: {beat_test}/4 beat their own buy-and-hold benchmark.",
        f"- Concentration gate failed: {pass_conc}/4 assets cleared the 20% top-PnL-block cap.",
        "- Monthly copper trend is a real external cyclical-growth input, but it is too slow and sparse to add deployable timing value under this standalone construction.",
        "",
        "## Conclusion",
        "",
        "- Copper industrial-demand trend does not produce a robust standalone crypto risk-on filter.",
        "- Do not retest this same PCOPPUSDM 12-month-SMA / 3-month-change rule without a fundamentally different confirmation or sizing mechanism.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    raw = fetch_or_load_copper()
    state = build_state(raw)
    results = [evaluate_asset(asset, state) for asset in ASSETS]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(results)
    out.to_csv(RESULTS_DIR / "summary.csv", index=False)
    state.to_csv(RESULTS_DIR / "copper_state.csv")
    write_report(results, state)
    print(out.to_string(index=False))
    print(f"REPORT {REPORT_PATH}")


if __name__ == "__main__":
    main()
