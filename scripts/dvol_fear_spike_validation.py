"""EXP-2026-08-30-DVOL-FEAR-001: Deribit implied-vol fear-spike contrarian rebound.

Hypothesis (preregistered, genuinely new for this repo -- never tested here;
uses a data source (Deribit DVOL, real published implied-volatility index)
that no prior study in docs/experiment_registry.md has used. Mechanistically
distinct from every prior study: not calendar (weekend/session), not
cross-sectional factor (Amihud/funding-carry/residual-momentum/low-vol), not
realized-volatility-based, not event-odds/Polymarket, not SMA-trend):

  A sharp spike in Deribit's DVOL (the crypto options market's forward-looking
  implied-volatility index, the crypto analogue of VIX) above its own recent
  trailing baseline signals acute fear / forced deleveraging / capitulation
  among leveraged options and futures participants. This fear is often
  overpriced relative to the eventual realized outcome (a well-documented
  TradFi VIX-spike mean-reversion effect). A rule that buys spot BTC/ETH when
  DVOL spikes >= 2 std devs above its trailing 30-day mean, holds a fixed
  short period, then exits, should beat buy-and-hold and DCA after realistic
  costs on the assets Deribit actually publishes DVOL for (BTC, ETH only --
  no proxy for other assets).

Design (frozen before any result was inspected):
  - Universe: BTC, ETH only (Deribit DVOL is published for BTC and ETH; no
    proxy/synthetic vol index for SOL/XRP -- if DVOL doesn't exist for an
    asset, it is excluded, not faked).
  - Data: real Deribit public `get_volatility_index_data` API, daily
    resolution, 2021-03-28 (earliest available) through repo cutoff. Real
    Binance spot 1h OHLCV (already cached, data/raw/{BTC,ETH}_1h.csv.gz) for
    trade execution prices.
  - Signal (daily, prior-completed-day only): z = (DVOL_t - mean(DVOL_{t-30..t-1})) / std(DVOL_{t-30..t-1}).
    Rolling window is prior-only (shift(1) before rolling) -- no lookahead.
  - Entry trigger: z >= 2.0 at a given UTC daily close. Enter spot long at the
    NEXT day's 00:00 UTC hourly open (one full day of information lag, real
    execution).
  - Exit: fixed hold of 7 days (168h), then flat. Cooldown: no new entry while
    already in a position (non-overlapping trades only).
  - Costs: repo-standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE).
  - Benchmarks: continuous buy-and-hold, daily DCA (same released-capital
    schedule), cash.
  - Partitions: development 2021-03-28->2023-01-01, validation 2023-01-01->
    2024-07-01, test 2024-07-01->repo cutoff (roughly even thirds given
    DVOL's shorter real history vs. the repo's other studies).
  - Falsification (preregistered): primary rule must beat both buy-and-hold
    AND daily DCA on both assets, survive doubled round-trip cost, retain a
    positive best-trade-excluded terminal value (no concentration artifact),
    and not lose in the test partition. Any single failure -> REJECTED (or
    PROMISING BUT INCONCLUSIVE if it's a narrow near-miss per the skill's
    near-miss discipline).
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

ASSETS = ["BTC", "ETH"]
DVOL_ENDPOINT = "https://www.deribit.com/api/v2/public/get_volatility_index_data"

DVOL_START = pd.Timestamp("2021-03-28T00:00:00Z")
END_EXCLUSIVE = pd.Timestamp("2026-08-30T00:00:00Z")  # repo cutoff for this run
DEV_END = pd.Timestamp("2023-01-01T00:00:00Z")
VALIDATION_END = pd.Timestamp("2024-07-01T00:00:00Z")

ROLLING_WINDOW_DAYS = 30
Z_THRESHOLD = 2.0
HOLD_DAYS = 7
RAW_DIR = ROOT / "data" / "deribit_dvol"


def fetch_dvol_raw(currency: str, start_ms: int, end_ms: int) -> list[list[float]]:
    """Paginate Deribit DVOL backwards from end_ms since the API's
    `continuation` cursor moves toward older data when start<->end straddle
    the 1000-row page limit."""
    rows: list[list[float]] = []
    cur_end = end_ms
    attempts = 0
    while True:
        url = (
            f"{DVOL_ENDPOINT}?currency={currency}&start_timestamp={start_ms}"
            f"&end_timestamp={cur_end}&resolution=86400"
        )
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "validated-crypto-strategies/0.1"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            attempts += 1
            if attempts > 5:
                raise RuntimeError(f"Deribit DVOL fetch failed for {currency}: {error}") from error
            time.sleep(min(2**attempts, 16))
            continue
        data = payload["result"]["data"]
        if not data:
            break
        rows.extend(data)
        first_ts = data[0][0]
        if first_ts <= start_ms:
            break
        cur_end = first_ts - 86_400_000
        time.sleep(0.05)
    unique_rows = sorted({tuple(r) for r in rows}, key=lambda r: r[0])
    return [list(r) for r in unique_rows]


def fetch_or_load_dvol(currency: str) -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{currency}_dvol_1d.csv.gz"
    if cache_path.exists():
        frame = pd.read_csv(cache_path, parse_dates=["timestamp"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        if frame["timestamp"].max() >= (END_EXCLUSIVE - pd.Timedelta(days=2)):
            return frame
    start_ms = int(DVOL_START.timestamp() * 1000)
    end_ms = int(END_EXCLUSIVE.timestamp() * 1000)
    rows = fetch_dvol_raw(currency, start_ms, end_ms)
    if not rows:
        raise RuntimeError(f"No real Deribit DVOL data returned for {currency}")
    frame = pd.DataFrame(rows, columns=["ts_ms", "open", "high", "low", "close"])
    frame["timestamp"] = pd.to_datetime(frame["ts_ms"], unit="ms", utc=True)
    frame = frame[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True)
    frame.to_csv(cache_path, index=False, compression="gzip")
    return frame


def load_spot(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_signal(dvol: pd.DataFrame) -> pd.DataFrame:
    frame = dvol.copy().set_index("timestamp").sort_index()
    frame["dvol_close"] = frame["close"]
    prior = frame["dvol_close"].shift(1)  # never uses same-day close for its own baseline
    rolling_mean = prior.rolling(ROLLING_WINDOW_DAYS, min_periods=ROLLING_WINDOW_DAYS).mean()
    rolling_std = prior.rolling(ROLLING_WINDOW_DAYS, min_periods=ROLLING_WINDOW_DAYS).std(ddof=1)
    frame["z"] = (frame["dvol_close"] - rolling_mean) / rolling_std
    frame["trigger"] = frame["z"] >= Z_THRESHOLD
    return frame


def non_overlapping_entries(signal: pd.DataFrame, hold_days: int) -> list[pd.Timestamp]:
    entries: list[pd.Timestamp] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for ts, row in signal.iterrows():
        if not bool(row["trigger"]):
            continue
        entry_day = ts + pd.Timedelta(days=1)  # next day's open, one-day info lag
        if entry_day < next_ok:
            continue
        entries.append(entry_day)
        next_ok = entry_day + pd.Timedelta(days=hold_days)
    return entries


def simulate_signal_strategy(
    spot: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float
) -> dict:
    capital = 1.0
    units = 0.0
    in_position = False
    entry_price = None
    entry_time = None
    exit_target = None
    trade_log = []
    equity_curve = []

    entry_set = set(entries)
    opens = spot["open"]
    closes = spot["close"]
    times = spot.index

    for i, ts in enumerate(times):
        if in_position and ts >= exit_target:
            exec_price = float(closes.iloc[i]) * (1 - one_way_cost)
            proceeds = units * exec_price
            trade_log.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exec_price,
                    "gross_return": exec_price / entry_price - 1.0,
                }
            )
            capital = proceeds
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
        equity = capital + units * float(closes.iloc[i])
        equity_curve.append({"timestamp": ts, "equity": equity})

    if in_position:
        exec_price = float(closes.iloc[-1]) * (1 - one_way_cost)
        proceeds = units * exec_price
        trade_log.append(
            {
                "entry_time": entry_time,
                "exit_time": times[-1],
                "entry_price": entry_price,
                "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
            }
        )
        capital = proceeds

    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    trades_df = pd.DataFrame(trade_log)
    return {"equity": equity_df, "trades": trades_df, "final_capital": capital}


def buy_and_hold(frame: pd.DataFrame) -> dict:
    closes = frame["close"]
    start_price = float(closes.iloc[0])
    equity = closes / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


def daily_dca(frame: pd.DataFrame, one_way_cost: float) -> dict:
    """Equal daily contribution released over the sample window, same total
    capital as the signal strategy's implicit lump sum, for a fair released-
    capital comparison."""
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
    spot: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float
) -> float:
    if not entries:
        return float("nan")
    result = simulate_signal_strategy(spot, entries, hold_days, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"]
    best_idx = trades["gross_return"].idxmax()
    remaining_entries = [e for i, e in enumerate(entries) if i != best_idx]
    result_excl = simulate_signal_strategy(spot, remaining_entries, hold_days, one_way_cost)
    return result_excl["final_capital"]


def run_for_asset(coin: str) -> dict:
    dvol = fetch_or_load_dvol(coin)
    spot = load_spot(coin)
    spot = spot[spot.index >= DVOL_START]
    bars_per_year = 365.25 * 24

    signal = build_signal(dvol)
    entries = non_overlapping_entries(signal, HOLD_DAYS)

    primary = simulate_signal_strategy(spot, entries, HOLD_DAYS, ONE_WAY_COST)
    doubled = simulate_signal_strategy(spot, entries, HOLD_DAYS, ONE_WAY_COST * 2)
    bh = buy_and_hold(spot)
    dca = daily_dca(spot, ONE_WAY_COST)
    excl_best_final = exclude_best_trade_final_capital(spot, entries, HOLD_DAYS, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)
    metrics_dca = compute_metrics(dca["equity"], bars_per_year)

    partitions = {
        "development": (DVOL_START, DEV_END),
        "validation": (DEV_END, VALIDATION_END),
        "test": (VALIDATION_END, None),
    }
    partition_rows = []
    for pname, (pstart, pend) in partitions.items():
        pentries = [e for e in entries if e >= pstart and (pend is None or e < pend)]
        pspot = partition_slice(spot, pstart, pend)
        if len(pspot) < 48:
            continue
        p_res = simulate_signal_strategy(pspot, pentries, HOLD_DAYS, ONE_WAY_COST)
        p_bh = buy_and_hold(pspot)
        partition_rows.append(
            {
                "asset": coin,
                "partition": pname,
                "n_trades": len(pentries),
                "strategy_final": p_res["final_capital"],
                "bh_final": p_bh["final_capital"],
                "strategy_beats_bh": bool(p_res["final_capital"] > p_bh["final_capital"]),
            }
        )

    return {
        "asset": coin,
        "n_dvol_days": len(dvol),
        "dvol_start": dvol["timestamp"].min(),
        "dvol_end": dvol["timestamp"].max(),
        "n_trades": len(entries),
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "exclude_best_trade_final": excl_best_final,
        "bh_final": bh["final_capital"],
        "dca_final": dca["final_capital"],
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
        "beats_bh_doubled_cost": bool(doubled["final_capital"] > bh["final_capital"]),
        "beats_bh_excl_best_trade": bool(excl_best_final > bh["final_capital"]),
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "dvol_fear_spike" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    all_partition_rows = []
    for coin, res in results.items():
        summary_rows.append(
            {
                "asset": coin,
                "n_dvol_days": res["n_dvol_days"],
                "dvol_start": res["dvol_start"],
                "dvol_end": res["dvol_end"],
                "n_trades": res["n_trades"],
                "primary_final": res["primary_final"],
                "doubled_cost_final": res["doubled_cost_final"],
                "exclude_best_trade_final": res["exclude_best_trade_final"],
                "bh_final": res["bh_final"],
                "dca_final": res["dca_final"],
                "primary_total_return": res["primary_total_return"],
                "primary_sharpe": res["primary_sharpe"],
                "primary_sortino": res["primary_sortino"],
                "primary_max_dd": res["primary_max_dd"],
                "bh_total_return": res["bh_total_return"],
                "bh_sharpe": res["bh_sharpe"],
                "dca_total_return": res["dca_total_return"],
                "dca_sharpe": res["dca_sharpe"],
                "beats_bh": res["beats_bh"],
                "beats_dca": res["beats_dca"],
                "beats_bh_doubled_cost": res["beats_bh_doubled_cost"],
                "beats_bh_excl_best_trade": res["beats_bh_excl_best_trade"],
            }
        )
        all_partition_rows.extend(res["partition_rows"])
        res["trades"].assign(asset=coin).to_csv(run_dir / f"{coin}_trades.csv", index=False)

    summary_df = pd.DataFrame(summary_rows)
    partition_df = pd.DataFrame(all_partition_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    print(summary_df.to_string(index=False))
    print()
    print(partition_df.to_string(index=False))

    beats_bh_all = bool(summary_df["beats_bh"].all())
    beats_dca_all = bool(summary_df["beats_dca"].all())
    beats_doubled_all = bool(summary_df["beats_bh_doubled_cost"].all())
    beats_excl_best_all = bool(summary_df["beats_bh_excl_best_trade"].all())
    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test"]["strategy_beats_bh"].all()
    )

    if beats_bh_all and beats_dca_all and beats_doubled_all and beats_excl_best_all and test_pass:
        verdict = "CANDIDATE"
    elif beats_bh_all and beats_dca_all and (beats_doubled_all or beats_excl_best_all):
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(
        f"\nBeats B&H (both assets): {beats_bh_all}; Beats DCA: {beats_dca_all}; "
        f"Survives doubled cost: {beats_doubled_all}; Survives best-trade exclusion: {beats_excl_best_all}; "
        f"Test partition pass: {test_pass}"
    )
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh_all={beats_bh_all}\nbeats_dca_all={beats_dca_all}\n"
            f"beats_doubled_cost_all={beats_doubled_all}\nbeats_excl_best_trade_all={beats_excl_best_all}\n"
            f"test_partition_pass={test_pass}\nverdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
