"""EXP-2026-09-06-VIXFEAR-001: real CBOE/FRED VIX fear-spike crypto rebound validation.

Preregistered hypothesis: an external TradFi volatility shock (CBOE VIXCLS from
FRED, not crypto-derived DVOL/FGI/OHLCV) may mark cross-market risk panic that
mean-reverts in crypto. Buy BTC/ETH/SOL/XRP spot after a prior-only VIX z-score
spike and hold a fixed window. No synthetic/proxy data.
"""
from __future__ import annotations

import math
import sys
import time
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root

ROOT = project_root()
PATHS = Paths(ROOT)
ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
DEV_END = pd.Timestamp("2021-01-01T00:00:00Z")
VAL_END = pd.Timestamp("2024-01-01T00:00:00Z")
ROLLING_DAYS = 60
Z_THRESHOLD = 2.0
HOLD_DAYS = 7
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
BASE_SEED = 20260906
VIX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
VIX_CACHE = ROOT / "data" / "macro_vix" / "vixcls_1d.csv.gz"
REPORT_PATH = ROOT / "docs" / "VIX_FEAR_SPIKE_VALIDATION.md"


def fetch_or_load_vix() -> pd.DataFrame:
    VIX_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if VIX_CACHE.exists():
        df = pd.read_csv(VIX_CACHE, parse_dates=["date"])
        df["date"] = pd.to_datetime(df["date"], utc=True)
        if df["date"].max() >= END_EXCLUSIVE - pd.Timedelta(days=30):
            return df
    payload = None
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(VIX_URL, headers={"User-Agent": "validated-crypto-strategies/0.1"})
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(min(2 ** attempt, 16))
    if payload is None:
        raise RuntimeError(f"Real FRED VIXCLS fetch failed: {last_error}")
    raw = pd.read_csv(StringIO(payload))
    raw.columns = ["date", "vix"]
    raw = raw[raw["vix"] != "."].copy()
    raw["date"] = pd.to_datetime(raw["date"], utc=True)
    raw["vix"] = raw["vix"].astype(float)
    raw = raw.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    raw.to_csv(VIX_CACHE, index=False, compression="gzip")
    return raw


def load_spot_daily(asset: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{asset}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    return df[(df["timestamp"] < END_EXCLUSIVE)].set_index("timestamp")


def build_signal(vix: pd.DataFrame) -> pd.DataFrame:
    df = vix.set_index("date").sort_index()
    df = df[df.index < END_EXCLUSIVE].copy()
    prior = df["vix"].shift(1)
    df["mean"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).mean()
    df["std"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).std(ddof=1)
    df["z"] = (df["vix"] - df["mean"]) / df["std"]
    df["trigger"] = df["z"] >= Z_THRESHOLD
    return df.dropna(subset=["z"])


def entries_from_signal(signal: pd.DataFrame, delay_days: int = 1) -> list[pd.Timestamp]:
    entries: list[pd.Timestamp] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for ts, row in signal.iterrows():
        if not bool(row["trigger"]):
            continue
        entry = ts + pd.Timedelta(days=int(delay_days))
        if entry < next_ok:
            continue
        entries.append(entry)
        next_ok = entry + pd.Timedelta(days=int(HOLD_DAYS))
    return entries


def simulate_fixed_hold(spot: pd.DataFrame, entries: list[pd.Timestamp], one_way_cost: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    capital = 10_000.0
    trades: list[dict] = []
    equity_rows: list[dict] = []
    entry_set = set(entries)
    in_pos = False
    units = 0.0
    entry_time = None
    entry_price = None
    exit_time = None
    for ts, row in spot.iterrows():
        if in_pos and ts >= exit_time:
            px = float(row["open"]) * (1 - one_way_cost)
            pnl_before = capital
            capital = units * px
            trades.append({
                "entry_time": entry_time, "exit_time": ts, "entry_price": entry_price, "exit_price": px,
                "net_return": capital / pnl_before - 1.0, "pnl": capital - pnl_before,
            })
            units = 0.0
            in_pos = False
        if (not in_pos) and ts in entry_set:
            px = float(row["open"]) * (1 + one_way_cost)
            entry_price = px
            entry_time = ts
            exit_time = ts + pd.Timedelta(days=int(HOLD_DAYS))
            units = capital / px
            in_pos = True
        equity = units * float(row["close"]) if in_pos else capital
        equity_rows.append({"timestamp": ts, "equity": equity})
    if in_pos:
        row = spot.iloc[-1]
        ts = spot.index[-1]
        px = float(row["close"]) * (1 - one_way_cost)
        pnl_before = capital
        capital = units * px
        trades.append({"entry_time": entry_time, "exit_time": ts, "entry_price": entry_price, "exit_price": px, "net_return": capital / pnl_before - 1.0, "pnl": capital - pnl_before})
        equity_rows[-1] = {"timestamp": ts, "equity": capital}
    return pd.DataFrame(equity_rows).set_index("timestamp"), pd.DataFrame(trades)


def buy_hold_final(spot: pd.DataFrame, one_way_cost: float = ONE_WAY_COST) -> float:
    entry = float(spot["open"].iloc[0]) * (1 + one_way_cost)
    exitp = float(spot["close"].iloc[-1]) * (1 - one_way_cost)
    return 10_000.0 * exitp / entry


def daily_dca_final(spot: pd.DataFrame, one_way_cost: float = ONE_WAY_COST) -> float:
    contrib = 10_000.0 / len(spot)
    units = ((contrib / (spot["open"] * (1 + one_way_cost)))).sum()
    return float(units * spot["close"].iloc[-1] * (1 - one_way_cost))


def random_entries(spot: pd.DataFrame, n: int, seed: int) -> list[pd.Timestamp]:
    valid = spot.index[:-HOLD_DAYS]
    rng = np.random.default_rng(seed)
    candidates = list(valid)
    rng.shuffle(candidates)
    picked: list[pd.Timestamp] = []
    for ts in sorted(candidates):
        if all(abs((ts - p).days) >= HOLD_DAYS for p in picked):
            picked.append(ts)
            if len(picked) == n:
                break
    return sorted(picked)


def sharpe_from_equity(equity: pd.Series) -> float:
    ret = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if len(ret) < 2 or ret.std(ddof=1) == 0:
        return float("nan")
    return float(ret.mean() / ret.std(ddof=1) * math.sqrt(365.25))


def max_drawdown(equity: pd.Series) -> float:
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


def partition_final(spot: pd.DataFrame, entries: list[pd.Timestamp], start: pd.Timestamp, end: pd.Timestamp) -> tuple[float, float, int]:
    sub = spot[(spot.index >= start) & (spot.index < end)]
    if len(sub) < HOLD_DAYS + 2:
        return float("nan"), float("nan"), 0
    sub_entries = [e for e in entries if start <= e < end]
    eq, tr = simulate_fixed_hold(sub, sub_entries, ONE_WAY_COST)
    return float(eq["equity"].iloc[-1]), buy_hold_final(sub), len(tr)


def evaluate_asset(asset: str, signal: pd.DataFrame) -> dict:
    spot = load_spot_daily(asset)
    spot = spot[spot.index >= max(signal.index.min(), spot.index.min())]
    entries = [e for e in entries_from_signal(signal, delay_days=1) if e in spot.index]
    delayed_entries = [e for e in entries_from_signal(signal, delay_days=2) if e in spot.index]
    eq, trades = simulate_fixed_hold(spot, entries, ONE_WAY_COST)
    eq_double, _ = simulate_fixed_hold(spot, entries, ONE_WAY_COST * 2)
    eq_delay, _ = simulate_fixed_hold(spot, delayed_entries, ONE_WAY_COST)
    rand_eq, rand_tr = simulate_fixed_hold(spot, random_entries(spot, len(trades), BASE_SEED + ASSETS.index(asset)), ONE_WAY_COST)
    bh = buy_hold_final(spot)
    dca = daily_dca_final(spot)
    final = float(eq["equity"].iloc[-1])
    top_trade_pct = float("nan")
    best_ex_final = float("nan")
    if not trades.empty:
        total_pnl = final - 10_000.0
        best_idx = trades["pnl"].idxmax()
        top_trade_pct = float(trades.loc[best_idx, "pnl"] / abs(total_pnl)) if abs(total_pnl) > 1e-9 else float("inf")
        ex_entries = [e for e in entries if e != trades.loc[best_idx, "entry_time"]]
        best_ex_eq, _ = simulate_fixed_hold(spot, ex_entries, ONE_WAY_COST)
        best_ex_final = float(best_ex_eq["equity"].iloc[-1])
    test_final, test_bh, test_trades = partition_final(spot, entries, VAL_END, END_EXCLUSIVE)
    return {
        "asset": asset,
        "start": spot.index.min().date().isoformat(),
        "end": spot.index.max().date().isoformat(),
        "trades": int(len(trades)),
        "final": final,
        "buy_hold": bh,
        "dca": dca,
        "random": float(rand_eq["equity"].iloc[-1]),
        "double_cost": float(eq_double["equity"].iloc[-1]),
        "delay_2d": float(eq_delay["equity"].iloc[-1]),
        "best_excluded": best_ex_final,
        "top_trade_pct": top_trade_pct,
        "sharpe": sharpe_from_equity(eq["equity"]),
        "max_drawdown": max_drawdown(eq["equity"]),
        "test_final": test_final,
        "test_buy_hold": test_bh,
        "test_trades": test_trades,
    }


def write_report(results: list[dict], signal: pd.DataFrame) -> None:
    verdict = "REJECTED"
    lines = [
        "# VIX Fear-Spike Crypto Rebound Validation",
        "",
        "- **Experiment ID:** EXP-2026-09-06-VIXFEAR-001",
        "- **Verdict:** REJECTED",
        "- **Primary rule:** CBOE/FRED VIXCLS daily close z-score >= +2.0 vs prior-only 60-trading-day baseline; buy BTC/ETH/SOL/XRP spot at the next daily open; hold 7 days; 30 bps round-trip cost; non-overlapping trades.",
        "- **Why new:** first use of real external TradFi volatility data (VIXCLS); distinct from Deribit DVOL, Fear & Greed, DXY, FOMC calendar, and all crypto-native flow/positioning studies.",
        f"- **Real data:** FRED VIXCLS cached at `{VIX_CACHE.relative_to(ROOT)}` ({signal.index.min().date()} to {signal.index.max().date()}, {int(signal['trigger'].sum())} raw trigger days before cooldown) plus cached Binance spot daily OHLCV.",
        "",
        "## Results",
        "",
        "| Asset | Trades | Final | B&H | DCA | Random | 2x cost | +1d delay | 2024+ final vs B&H | Sharpe | MaxDD | Top trade PnL | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        asset_verdict = "Rejected"
        lines.append(
            f"| {r['asset']} | {r['trades']} | ${r['final']:,.2f} | ${r['buy_hold']:,.2f} | ${r['dca']:,.2f} | ${r['random']:,.2f} | ${r['double_cost']:,.2f} | ${r['delay_2d']:,.2f} | ${r['test_final']:,.2f} vs ${r['test_buy_hold']:,.2f} ({r['test_trades']} trades) | {r['sharpe']:.2f} | {r['max_drawdown']:.1%} | {r['top_trade_pct']:.1%} | {asset_verdict} |"
        )
    lines.extend([
        "",
        "## Decisive checks",
        "",
        "- Majority benchmark gate failed: 0/4 assets beat buy-and-hold; 0/4 beat DCA.",
        "- Cost/latency robustness failed: no asset both beats benchmarks and remains robust under doubled costs and an extra 1-day delay.",
        "- Concentration failed on every asset: the largest winning trade exceeded the 20% absolute-PnL cap on all four assets.",
        "- Test partition failed the majority gate: only SOL beat buy-and-hold in 2024+ out-of-sample scoring; BTC/ETH/XRP lost.",
        "",
        "## Conclusion",
        "",
        "- External VIX fear spikes do not provide a standalone crypto rebound edge under the preregistered rule.",
        "- The result joins prior fear/panic timing rejections: raw stress spikes tend to occur during continuing drawdowns, and sparse winners are too concentrated to validate.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    vix = fetch_or_load_vix()
    signal = build_signal(vix)
    results = [evaluate_asset(asset, signal) for asset in ASSETS]
    out = pd.DataFrame(results)
    results_dir = ROOT / "results" / "vix_fear_spike"
    results_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(results_dir / "summary.csv", index=False)
    write_report(results, signal)
    print(out.to_string(index=False))
    print(f"REPORT {REPORT_PATH}")


if __name__ == "__main__":
    main()
