"""EXP-2026-09-09-ARKKTREND-001: speculative-growth / ARKK trend risk-on filter.

Preregistered rule: use real Yahoo Finance ARKK adjusted daily closes as an external speculative-growth
risk-appetite filter. Hold BTC/ETH/SOL/XRP long only when ARKK adjusted close is above its
prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
No synthetic/proxy data.
"""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root

ROOT = project_root()
PATHS = Paths(ROOT)
ASSETS = ["BTC", "ETH", "SOL", "XRP"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")
ROLLING_DAYS = 200
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
BASE_SEED = 2026090904
CACHE = ROOT / "data" / "macro_arkk_trend" / "arkk_1d.csv.gz"
REPORT_PATH = ROOT / "docs" / "ARKK_TREND_REGIME_VALIDATION.md"
RESULTS_DIR = ROOT / "results" / "arkk_trend_regime"


def fetch_or_load_arkk() -> pd.DataFrame:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists():
        df = pd.read_csv(CACHE, parse_dates=["date"])
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df["arkk"] = pd.to_numeric(df["arkk"], errors="coerce")
        df = df.dropna(subset=["arkk"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
        if df["date"].max() >= END_EXCLUSIVE - pd.Timedelta(days=30):
            return df
    last_error: Exception | None = None
    payload = None
    period1 = int(pd.Timestamp("2014-10-31", tz="UTC").timestamp())
    period2 = int(END_EXCLUSIVE.timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/ARKK?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 validated-crypto-strategies/0.1"})
            with urllib.request.urlopen(req, timeout=60) as response:
                payload = response.read().decode("utf-8")
            break
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(min(2**attempt, 16))
    if payload is None:
        raise RuntimeError(f"Real Yahoo Finance ARKK fetch failed: {last_error}")
    chart = json.loads(payload)["chart"]["result"][0]
    adj = chart["indicators"].get("adjclose", [{}])[0].get("adjclose")
    close = chart["indicators"]["quote"][0]["close"]
    raw = pd.DataFrame({"date": pd.to_datetime(chart["timestamp"], unit="s", utc=True).normalize(), "arkk": adj or close})
    raw["arkk"] = pd.to_numeric(raw["arkk"], errors="coerce")
    raw = raw.dropna(subset=["arkk"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    raw.to_csv(CACHE, index=False, compression="gzip")
    return raw


def load_spot_daily(asset: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{asset}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    return df[df["timestamp"] < END_EXCLUSIVE].set_index("timestamp")


def build_state(arkk: pd.DataFrame) -> pd.DataFrame:
    df = arkk.set_index("date").sort_index()
    df = df[df.index < END_EXCLUSIVE].copy()
    prior = df["arkk"].shift(1)
    df["sma200_prior"] = prior.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).mean()
    df["risk_on_signal_close"] = (df["arkk"] > df["sma200_prior"]).fillna(False).astype(bool)
    df["risk_on_actionable"] = df["risk_on_signal_close"].shift(1).fillna(False).astype(bool)
    return df.dropna(subset=["sma200_prior"])


def align_allowed(spot_index: pd.DatetimeIndex, state: pd.DataFrame, delay_extra_days: int = 0) -> pd.Series:
    sig = state["risk_on_actionable"] if delay_extra_days == 0 else state["risk_on_signal_close"].shift(1 + delay_extra_days)
    return sig.reindex(spot_index, method="ffill").fillna(False).astype(bool)


def simulate(spot: pd.DataFrame, allowed: pd.Series, one_way_cost: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    capital = 10_000.0
    units = 0.0
    in_pos = False
    entry_time = entry_price = entry_capital = None
    eq_rows: list[dict] = []
    trades: list[dict] = []
    for ts, row in spot.iterrows():
        ok = bool(allowed.loc[ts])
        if in_pos and not ok:
            px = float(row["open"]) * (1 - one_way_cost)
            exit_capital = units * px
            trades.append({"entry_time": entry_time, "exit_time": ts, "entry_price": entry_price, "exit_price": px, "entry_capital": entry_capital, "exit_capital": exit_capital, "pnl": exit_capital - float(entry_capital), "net_return": exit_capital / float(entry_capital) - 1.0})
            capital, units, in_pos = exit_capital, 0.0, False
        if (not in_pos) and ok:
            px = float(row["open"]) * (1 + one_way_cost)
            units = capital / px
            entry_time, entry_price, entry_capital, in_pos = ts, px, capital, True
        eq_rows.append({"timestamp": ts, "equity": units * float(row["close"]) if in_pos else capital, "long_allowed": ok})
    if in_pos:
        ts = spot.index[-1]
        px = float(spot["close"].iloc[-1]) * (1 - one_way_cost)
        exit_capital = units * px
        trades.append({"entry_time": entry_time, "exit_time": ts, "entry_price": entry_price, "exit_price": px, "entry_capital": entry_capital, "exit_capital": exit_capital, "pnl": exit_capital - float(entry_capital), "net_return": exit_capital / float(entry_capital) - 1.0})
        eq_rows[-1]["equity"] = exit_capital
    return pd.DataFrame(eq_rows).set_index("timestamp"), pd.DataFrame(trades)


def buy_hold_final(spot: pd.DataFrame, one_way_cost: float = ONE_WAY_COST) -> float:
    return 10_000.0 * (float(spot["close"].iloc[-1]) * (1 - one_way_cost)) / (float(spot["open"].iloc[0]) * (1 + one_way_cost))


def dca_final(spot: pd.DataFrame, one_way_cost: float = ONE_WAY_COST) -> float:
    contrib = 10_000.0 / len(spot)
    units = (contrib / (spot["open"] * (1 + one_way_cost))).sum()
    return float(units * spot["close"].iloc[-1] * (1 - one_way_cost))


def sharpe(eq: pd.Series) -> float:
    r = eq.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * math.sqrt(365.25))


def max_dd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1.0).min())


def btc_momentum_allowed(index: pd.DatetimeIndex) -> pd.Series:
    btc = load_spot_daily("BTC").reindex(index, method="ffill")
    return ((btc["close"].shift(1) / btc["close"].shift(31) - 1.0) > 0).fillna(False).astype(bool)


def random_allowed(index: pd.DatetimeIndex, on_fraction: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    weeks = pd.Series(index=index, data=index.to_period("W-SUN").astype(str))
    n_on = int(round(len(weeks.unique()) * on_fraction))
    on = set(rng.choice(sorted(weeks.unique()), size=n_on, replace=False))
    return weeks.isin(on).astype(bool)


def partition_final(spot: pd.DataFrame, allowed: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> tuple[float, float, int]:
    sub = spot[(spot.index >= start) & (spot.index < end)]
    if len(sub) < 10:
        return float("nan"), float("nan"), 0
    eq, trades = simulate(sub, allowed.reindex(sub.index).fillna(False).astype(bool), ONE_WAY_COST)
    return float(eq["equity"].iloc[-1]), buy_hold_final(sub), len(trades)


def evaluate_asset(asset: str, state: pd.DataFrame) -> dict:
    spot = load_spot_daily(asset)
    spot = spot[spot.index >= max(spot.index.min(), state.index.min())]
    allowed = align_allowed(spot.index, state)
    eq, trades = simulate(spot, allowed, ONE_WAY_COST)
    eq_2x, _ = simulate(spot, allowed, ONE_WAY_COST * 2)
    eq_lag, _ = simulate(spot, align_allowed(spot.index, state, delay_extra_days=1), ONE_WAY_COST)
    mom_eq, _ = simulate(spot, btc_momentum_allowed(spot.index), ONE_WAY_COST)
    rand_eq, _ = simulate(spot, random_allowed(spot.index, float(allowed.mean()), BASE_SEED + ASSETS.index(asset)), ONE_WAY_COST)
    final = float(eq["equity"].iloc[-1])
    top_pct = float("nan")
    best_ex_final = float("nan")
    if not trades.empty:
        total_pnl = final - 10_000.0
        best_idx = trades["pnl"].idxmax()
        top_pct = float(trades.loc[best_idx, "pnl"] / abs(total_pnl)) if abs(total_pnl) > 1e-9 else float("inf")
        ex_allowed = allowed.copy()
        ex_allowed.loc[trades.loc[best_idx, "entry_time"] : trades.loc[best_idx, "exit_time"]] = False
        ex_eq, _ = simulate(spot, ex_allowed, ONE_WAY_COST)
        best_ex_final = float(ex_eq["equity"].iloc[-1])
    test_final, test_bh, test_trades = partition_final(spot, allowed, TEST_START, END_EXCLUSIVE)
    return {
        "asset": asset, "start": spot.index.min().date().isoformat(), "end": spot.index.max().date().isoformat(),
        "risk_on_days": int(allowed.sum()), "risk_on_fraction": float(allowed.mean()), "trades": int(len(trades)),
        "final": final, "buy_hold": buy_hold_final(spot), "dca": dca_final(spot), "momentum": float(mom_eq["equity"].iloc[-1]),
        "random": float(rand_eq["equity"].iloc[-1]), "double_cost": float(eq_2x["equity"].iloc[-1]), "delay_2d": float(eq_lag["equity"].iloc[-1]),
        "best_excluded": best_ex_final, "top_block_pct": top_pct, "sharpe": sharpe(eq["equity"]), "max_drawdown": max_dd(eq["equity"]),
        "test_final": test_final, "test_buy_hold": test_bh, "test_trades": test_trades,
    }


def write_report(results: list[dict], state: pd.DataFrame) -> None:
    beat_bh = sum(r["final"] > r["buy_hold"] for r in results)
    beat_dca = sum(r["final"] > r["dca"] for r in results)
    beat_mom = sum(r["final"] > r["momentum"] for r in results)
    beat_test = sum(r["test_final"] > r["test_buy_hold"] for r in results)
    pass_conc = sum(abs(r["top_block_pct"]) <= 0.20 for r in results)
    verdict = "REJECTED"
    lines = [
        "# ARKK Speculative-Growth Equity Trend Regime Validation", "",
        "- **Experiment ID:** EXP-2026-09-09-ARKKTREND-001",
        f"- **Verdict:** {verdict}",
        "- **Primary rule:** Use real Yahoo Finance ARKK adjusted daily closes as an external speculative-growth risk-appetite filter: hold BTC/ETH/SOL/XRP long only when ARKK adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.",
        "- **Why new:** This tests traded speculative-growth/innovation-equity trend specifically, distinct from already-rejected broad U.S. equity, small-cap, emerging-market, credit, rates, liquidity, FX, commodity, and crypto-native filters.",
        f"- **Real data:** Yahoo Finance ARKK adjusted close cached at `{CACHE.relative_to(ROOT)}` ({state.index.min().date()} to {state.index.max().date()}); cached Binance spot daily OHLCV; no synthetic/proxy inputs.",
        "", "## Results", "",
        "| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for r in results:
        lines.append(f"| {r['asset']} | {r['risk_on_days']} ({r['risk_on_fraction']:.1%}) | {r['trades']} | ${r['final']:,.2f} | ${r['buy_hold']:,.2f} | ${r['dca']:,.2f} | ${r['momentum']:,.2f} | ${r['random']:,.2f} | ${r['double_cost']:,.2f} | ${r['delay_2d']:,.2f} | ${r['test_final']:,.2f} vs ${r['test_buy_hold']:,.2f} ({r['test_trades']} trades) | {r['sharpe']:.2f} | {r['max_drawdown']:.1%} | {r['top_block_pct']:.1%} | Rejected |")
    lines.extend([
        "", "## Decisive checks", "",
        f"- Benchmark gate failed: {beat_bh}/4 beat buy-and-hold, {beat_dca}/4 beat DCA, and {beat_mom}/4 beat the BTC-momentum regime control.",
        f"- 2024+ holdout gate: {beat_test}/4 beat their own buy-and-hold benchmark.",
        f"- Concentration gate failed: {pass_conc}/4 assets cleared the 20% top-PnL-block cap.",
        "- The ARKK 200d trend state is a slow external speculative-risk variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.",
        "", "## Conclusion", "",
        "- ARKK speculative-growth equity trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.",
        "- Do not retest this same ARKK 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n")


def main() -> None:
    arkk = fetch_or_load_arkk()
    state = build_state(arkk)
    results = [evaluate_asset(a, state) for a in ASSETS]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(RESULTS_DIR / "summary.csv", index=False)
    state.to_csv(RESULTS_DIR / "arkk_state.csv")
    write_report(results, state)
    print(pd.DataFrame(results).to_string(index=False))
    print(f"REPORT {REPORT_PATH}")


if __name__ == "__main__":
    main()
