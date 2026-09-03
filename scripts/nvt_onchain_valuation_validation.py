"""EXP-2026-09-03-NVT-001: Bitcoin NVT (Network-Value-to-Transactions) on-chain
valuation contrarian mean-reversion.

Hypothesis (preregistered, genuinely new for this repo -- checked
docs/experiment_registry.md and docs/next_hypotheses.md in full before
writing this: no prior study in this repo has used real BTC blockchain
on-chain network-value/transaction data. Mechanistically distinct from every
prior study: not a derivatives signal (DVOL implied vol, funding, OI, CFTC
COT, top-trader/retail positioning), not a composite sentiment index (FGI),
not price-derived (SMA200, breakout, momentum), not a stablecoin-flow proxy,
not miner economics (Hash Ribbons uses hashrate -- a *production-cost*
signal; NVT is a *valuation* signal using actual settled transaction value)):

  NVT (Network Value to Transactions ratio) = BTC market capitalization /
  real on-chain estimated USD transaction volume. This is the closest
  on-chain analogue to a P/E ratio: a network trading at a high multiple of
  its actual settled economic throughput is "expensive" relative to its
  fundamental usage, and a network trading at a low multiple is "cheap".
  The classic Willy Woo "NVT Signal" thesis holds that NVT extremes are
  mean-reverting and historically preceded major turning points (very high
  NVT preceded the 2018 and 2021 tops; very low NVT preceded 2015 and 2019
  bottoms). A rule that buys spot BTC when a smoothed NVT z-score is deeply
  NEGATIVE (network cheap relative to its own recent on-chain usage history)
  and holds a fixed period should beat continuous buy-and-hold and DCA after
  realistic costs.

Design (frozen before any result was inspected):
  - Universe: BTC only. On-chain transaction-value data is a Bitcoin-specific
    metric published by Blockchain.com's public charts API; no proxy was
    fabricated for ETH/SOL/XRP (none of which have a comparable long-history
    free on-chain USD-transaction-value feed available to this repo).
  - Data sources (both real, free, public, no API key, first use in this
    repo):
      - `https://api.blockchain.info/charts/market-cap` (real total BTC
        market capitalization, USD)
      - `https://api.blockchain.info/charts/estimated-transaction-volume-usd`
        (real estimated on-chain transaction value, USD, Blockchain.com's own
        heuristic-adjusted estimate excluding self-churn/change outputs)
    Both fetched with `sampled=false` for true daily granularity, cached to
    `data/onchain_nvt/{market_cap,tx_volume_usd}_1d.csv.gz`. Real Binance spot
    BTC/USDT daily+hourly OHLCV (already cached, `data/raw/BTC_1{d,h}.csv.gz`)
    for execution.
  - Signal construction (uses ONLY data published through and including day
    t; smoothing per Woo's original NVT-Signal convention to reduce single-
    day tx-volume noise):
      raw_nvt_t = market_cap_t / rolling_90d_mean(tx_volume_usd)_t
      (90-day trailing mean of tx volume, inclusive of day t, matches the
      published "NVT Signal" convention)
      z_t = (raw_nvt_t - mean(raw_nvt_{t-365..t-1})) / std(raw_nvt_{t-365..t-1})
      (a full trailing YEAR of prior-only NVT history as the baseline --
      deliberately slow-moving/structural, per the skill's explicit guidance
      to prefer structural over fast-oscillator signals; the rolling window
      excludes day t itself via shift(1) before the 365d rolling stats)
  - Entry trigger: z_t <= -1.25 (network cheap vs its own trailing-year
    valuation history). Enter spot long BTC at the NEXT day's 00:00 UTC open
    (one full day of publication lag -- Blockchain.com's daily chart value
    for day t is not knowable intraday on day t).
  - Exit: fixed hold of 30 days, then flat. Non-overlapping trades only (no
    new entry while already in a position).
  - Costs: repo-standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE).
  - Benchmarks: cash, continuous BTC buy-and-hold, daily BTC DCA (same
    released-capital schedule), a seeded random-timing control matching the
    real trade count and 30-day hold length (base_seed=20260903).
  - Partitions: development 2018-01-01->2020-01-01, validation 2020-01-01->
    2023-01-01, test 2023-01-01->repo cutoff (2026-07-27), matching this
    repo's standard three-way split convention. (NVT z-score baseline itself
    warms up on real on-chain history back to 2010, but tradeable execution
    is restricted to the Binance spot BTC coverage window, 2018-01-01
    onward.)
  - Falsification (preregistered): primary rule must beat continuous
    buy-and-hold AND daily DCA AND its own random-timing control, survive
    doubled round-trip cost, retain a positive best-trade-excluded terminal
    value (single trade must not exceed 20% of total realized PnL, this
    program's standard concentration cap), and not lose to buy-and-hold in
    the test partition. Any single failure -> REJECTED (or PROMISING BUT
    INCONCLUSIVE if it is a narrow near-miss per the skill's near-miss
    discipline: clears the harder statistical/robustness bars but narrowly
    misses one check).
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

ASSET = "BTC"
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")  # matches BTC_1h.csv.gz coverage
EXEC_START = pd.Timestamp("2018-01-01T00:00:00Z")
DEV_END = pd.Timestamp("2020-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2023-01-01T00:00:00Z")

TX_VOL_SMOOTH_DAYS = 90
Z_BASELINE_DAYS = 365
Z_THRESHOLD = -1.25
HOLD_DAYS = 30
BASE_SEED = 20260903

RAW_DIR = ROOT / "data" / "onchain_nvt"
MKTCAP_URL = "https://api.blockchain.info/charts/market-cap?timespan=all&format=json&sampled=false"
TXVOL_URL = (
    "https://api.blockchain.info/charts/estimated-transaction-volume-usd"
    "?timespan=all&format=json&sampled=false"
)


def _fetch_json(url: str, attempts: int = 5) -> dict:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "validated-crypto-strategies/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(f"Blockchain.com fetch failed for {url}: {error}") from error
            time.sleep(min(2**attempt, 16))
    raise RuntimeError(f"unreachable: {url}")


def fetch_or_load_series(name: str, url: str, value_col: str) -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{name}_1d.csv.gz"
    if cache_path.exists():
        frame = pd.read_csv(cache_path, parse_dates=["date"])
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        if frame["date"].max() >= (END_EXCLUSIVE - pd.Timedelta(days=3)):
            return frame
    payload = _fetch_json(url)
    values = payload.get("values")
    if not values:
        raise RuntimeError(f"No real Blockchain.com data returned for {name}")
    frame = pd.DataFrame(values)
    frame["date"] = pd.to_datetime(frame["x"], unit="s", utc=True).dt.floor("D")
    frame = frame.rename(columns={"y": value_col})
    frame = frame.groupby("date", as_index=False)[value_col].last()
    frame = frame.sort_values("date").reset_index(drop=True)
    frame.to_csv(cache_path, index=False, compression="gzip")
    return frame


def load_btc_daily() -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / "BTC_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def load_btc_hourly() -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / "BTC_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_signal(mktcap: pd.DataFrame, txvol: pd.DataFrame) -> pd.DataFrame:
    mc = mktcap.set_index("date")["market_cap_usd"]
    tv = txvol.set_index("date")["tx_volume_usd"]
    frame = pd.concat([mc, tv], axis=1).dropna().sort_index()
    frame.columns = ["market_cap_usd", "tx_volume_usd"]
    frame["tx_vol_smoothed"] = frame["tx_volume_usd"].rolling(
        TX_VOL_SMOOTH_DAYS, min_periods=TX_VOL_SMOOTH_DAYS
    ).mean()
    frame["nvt"] = frame["market_cap_usd"] / frame["tx_vol_smoothed"]
    prior_nvt = frame["nvt"].shift(1)  # baseline never includes day t's own NVT
    roll_mean = prior_nvt.rolling(Z_BASELINE_DAYS, min_periods=Z_BASELINE_DAYS).mean()
    roll_std = prior_nvt.rolling(Z_BASELINE_DAYS, min_periods=Z_BASELINE_DAYS).std(ddof=1)
    frame["z"] = (frame["nvt"] - roll_mean) / roll_std
    frame["trigger"] = frame["z"] <= Z_THRESHOLD
    frame = frame.dropna(subset=["z"])
    return frame


def non_overlapping_entries(signal: pd.DataFrame, hold_days: int, exec_start: pd.Timestamp) -> list[pd.Timestamp]:
    entries: list[pd.Timestamp] = []
    next_ok = exec_start
    for ts, row in signal.iterrows():
        if not bool(row["trigger"]):
            continue
        entry_day = ts + pd.Timedelta(days=1)
        if entry_day < exec_start:
            continue
        if entry_day < next_ok:
            continue
        entries.append(entry_day)
        next_ok = entry_day + pd.Timedelta(days=hold_days)
    return entries


def simulate_entries(spot_hourly: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float) -> dict:
    capital = 1.0
    units = 0.0
    in_position = False
    entry_price = None
    entry_time = None
    exit_target = None
    trade_log = []
    equity_curve = []

    entry_set = set(entries)
    opens = spot_hourly["open"]
    closes = spot_hourly["close"]
    times = spot_hourly.index

    for i, ts in enumerate(times):
        if in_position and ts >= exit_target:
            exec_price = float(closes.iloc[i]) * (1 - one_way_cost)
            capital = units * exec_price
            trade_log.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exec_price,
                    "gross_return": exec_price / entry_price - 1.0,
                }
            )
            units = 0.0
            in_position = False
        if (not in_position) and ts in entry_set and ts.hour == 0:
            exec_price = float(opens.iloc[i]) * (1 + one_way_cost)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_time = ts
            exit_target = ts + pd.Timedelta(days=hold_days)
        equity_curve.append({"timestamp": ts, "equity": capital + units * float(closes.iloc[i])})

    if in_position:
        exec_price = float(closes.iloc[-1]) * (1 - one_way_cost)
        capital = units * exec_price
        trade_log.append(
            {
                "entry_time": entry_time,
                "exit_time": times[-1],
                "entry_price": entry_price,
                "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
            }
        )

    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    trades_df = pd.DataFrame(trade_log)
    return {"equity": equity_df, "trades": trades_df, "final_capital": float(capital)}


def buy_and_hold(frame: pd.DataFrame) -> dict:
    closes = frame["close"]
    start_price = float(closes.iloc[0])
    equity = closes / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


def daily_dca(frame: pd.DataFrame, one_way_cost: float) -> dict:
    daily_slots = frame[frame.index.hour == 0]
    if daily_slots.empty:
        daily_slots = frame.iloc[::24]
    n = len(daily_slots)
    tranche = 1.0 / n
    cash = 0.0
    units = 0.0
    equity_curve = []
    opens = frame["open"]
    closes = frame["close"]
    times = frame.index
    slot_set = set(daily_slots.index)
    for i, ts in enumerate(times):
        if ts in slot_set:
            cash += tranche
            exec_price = float(opens.iloc[i]) * (1 + one_way_cost)
            units += cash / exec_price
            cash = 0.0
        equity_curve.append({"timestamp": ts, "equity": cash + units * float(closes.iloc[i])})
    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    return {"equity": equity_df, "final_capital": float(equity_df["equity"].iloc[-1])}


def random_timing_control(
    spot_hourly: pd.DataFrame, n_trades: int, hold_days: int, one_way_cost: float, seed: int
) -> dict:
    if n_trades <= 0:
        return {"final_capital": float("nan"), "trades": pd.DataFrame()}
    rng = np.random.default_rng(seed)
    daily_opens = spot_hourly[spot_hourly.index.hour == 0].index
    candidates = list(daily_opens[: len(daily_opens) - hold_days - 1])
    if not candidates:
        return {"final_capital": float("nan"), "trades": pd.DataFrame()}
    chosen = sorted(rng.choice(candidates, size=min(n_trades, len(candidates)), replace=False))
    entries = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for ts in chosen:
        if ts < next_ok:
            continue
        entries.append(ts)
        next_ok = ts + pd.Timedelta(days=hold_days)
    return simulate_entries(spot_hourly, entries, hold_days, one_way_cost)


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


def partition_slice(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    mask = frame.index >= start
    if end is not None:
        mask &= frame.index < end
    return frame.loc[mask]


def exclude_best_trade_final_capital(
    spot_hourly: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float
) -> tuple[float, float]:
    """Return (final_capital_excl_best, top_trade_pnl_share)."""
    if not entries:
        return float("nan"), float("nan")
    result = simulate_entries(spot_hourly, entries, hold_days, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"], float("nan")
    best_idx = trades["gross_return"].idxmax()
    remaining_entries = [e for i, e in enumerate(entries) if i != best_idx]
    result_excl = simulate_entries(spot_hourly, remaining_entries, hold_days, one_way_cost)
    # top-trade PnL share vs total net PnL (base 1.0 starting capital)
    total_pnl = result["final_capital"] - 1.0
    excl_pnl = result_excl["final_capital"] - 1.0
    top_trade_pnl = total_pnl - excl_pnl
    top_trade_share = (top_trade_pnl / total_pnl) if total_pnl != 0 else float("nan")
    return result_excl["final_capital"], top_trade_share


def main() -> None:
    mktcap = fetch_or_load_series("market_cap", MKTCAP_URL, "market_cap_usd")
    txvol = fetch_or_load_series("tx_volume_usd", TXVOL_URL, "tx_volume_usd")
    print(f"Real on-chain rows: market_cap={len(mktcap)}, tx_volume={len(txvol)}")

    signal = build_signal(mktcap, txvol)
    print(f"NVT z-score series: {len(signal)} days, range {signal.index.min()} -> {signal.index.max()}")
    print(f"Trigger fraction (full on-chain sample): {signal['trigger'].mean():.4f}")

    spot_daily = load_btc_daily()
    spot_hourly = load_btc_hourly()
    exec_start = max(EXEC_START, spot_hourly.index.min())
    spot_hourly = spot_hourly[spot_hourly.index >= exec_start]
    bars_per_year = 365.25 * 24

    entries = non_overlapping_entries(signal, HOLD_DAYS, exec_start)
    print(f"Non-overlapping trade entries (execution window {exec_start.date()}+): {len(entries)}")

    primary = simulate_entries(spot_hourly, entries, HOLD_DAYS, ONE_WAY_COST)
    doubled = simulate_entries(spot_hourly, entries, HOLD_DAYS, ONE_WAY_COST * 2)
    bh = buy_and_hold(spot_hourly)
    dca = daily_dca(spot_hourly, ONE_WAY_COST)
    excl_best_final, top_trade_share = exclude_best_trade_final_capital(spot_hourly, entries, HOLD_DAYS, ONE_WAY_COST)

    seed = BASE_SEED + (hash(ASSET) % 10_000)
    random_result = random_timing_control(spot_hourly, len(entries), HOLD_DAYS, ONE_WAY_COST, seed)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)
    metrics_dca = compute_metrics(dca["equity"], bars_per_year)

    partitions = {
        "development": (exec_start, DEV_END),
        "validation": (DEV_END, TEST_START),
        "test": (TEST_START, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pentries = [e for e in entries if e >= pstart and (pend is None or e < pend)]
        pspot = partition_slice(spot_hourly, pstart, pend)
        if len(pspot) < 48:
            continue
        p_res = simulate_entries(pspot, pentries, HOLD_DAYS, ONE_WAY_COST)
        p_bh = buy_and_hold(pspot)
        partition_rows.append(
            {
                "asset": ASSET,
                "partition": pname,
                "n_trades": len(pentries),
                "strategy_final": p_res["final_capital"],
                "bh_final": p_bh["final_capital"],
                "strategy_beats_bh": bool(p_res["final_capital"] > p_bh["final_capital"]),
            }
        )

    summary = {
        "asset": ASSET,
        "n_onchain_days": len(signal),
        "n_trades": len(entries),
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "exclude_best_trade_final": excl_best_final,
        "top_trade_pnl_share": top_trade_share,
        "bh_final": bh["final_capital"],
        "dca_final": dca["final_capital"],
        "random_control_final": random_result["final_capital"],
        "primary_total_return": metrics_primary["total_return"],
        "primary_sharpe": metrics_primary["sharpe"],
        "primary_sortino": metrics_primary["sortino"],
        "primary_max_dd": metrics_primary["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "bh_sharpe": metrics_bh["sharpe"],
        "dca_total_return": metrics_dca["total_return"],
        "dca_sharpe": metrics_dca["sharpe"],
        "beats_bh": bool(primary["final_capital"] > bh["final_capital"]),
        "beats_dca": bool(primary["final_capital"] > dca["final_capital"]),
        "beats_random_control": bool(
            primary["final_capital"] > random_result["final_capital"]
            if not np.isnan(random_result["final_capital"])
            else False
        ),
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh["final_capital"]),
        "beats_bh_excl_best_trade": bool(excl_best_final > bh["final_capital"]),
        "concentration_cap_ok": bool(abs(top_trade_share) <= 0.20) if not np.isnan(top_trade_share) else False,
    }

    out_dir = ROOT / "results" / "nvt_onchain_valuation" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_df = pd.DataFrame([summary])
    partition_df = pd.DataFrame(partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)
    signal.to_csv(run_dir / "nvt_signal.csv.gz", compression="gzip")
    primary["trades"].to_csv(run_dir / "BTC_trades.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test"]["strategy_beats_bh"].all()
    )

    gates = {
        "beats_bh": summary["beats_bh"],
        "beats_dca": summary["beats_dca"],
        "beats_random_control": summary["beats_random_control"],
        "beats_bh_doubled_cost": summary["beats_bh_doubled_cost"],
        "beats_bh_excl_best_trade": summary["beats_bh_excl_best_trade"],
        "concentration_cap_ok": summary["concentration_cap_ok"],
        "test_partition_pass": test_pass,
    }
    n_pass = sum(1 for v in gates.values() if v)
    n_gates = len(gates)

    if all(gates.values()):
        verdict = "CANDIDATE"
    elif gates["beats_bh"] and gates["beats_random_control"] and n_pass >= n_gates - 1:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nGates: {gates}")
    print(f"Gates passed: {n_pass}/{n_gates}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(f"gates={gates}\nn_pass={n_pass}/{n_gates}\nverdict={verdict}\n")
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
