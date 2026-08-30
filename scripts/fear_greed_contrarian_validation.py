"""EXP-2026-08-30-FGI-001: Crypto Fear & Greed Index extreme-fear contrarian rebound.

Hypothesis (preregistered, genuinely new for this repo -- never tested here;
uses a data source, alternative.me's daily Crypto Fear & Greed Index, that no
prior study in docs/experiment_registry.md has used. Mechanistically distinct
from every prior study: not calendar (weekend/session/turn-of-month), not
cross-sectional factor (Amihud/funding-carry/residual-momentum/low-vol), not
Deribit-DVOL implied-vol, not event-odds/Polymarket, not SMA-trend, not
funding-rate panels):

  alternative.me publishes a daily composite crypto "Fear & Greed Index" (FGI,
  0-100) built from volatility, momentum/volume, social media, surveys,
  dominance, and Google Trends. A reading in the "Extreme Fear" zone (<=25)
  is widely cited as a contrarian buy signal ("be greedy when others are
  fearful"). This is a market-wide composite index (one series covers the
  whole crypto market, not per-asset), so the same trigger is tested applied
  identically across BTC/ETH/SOL/XRP.

Design (frozen before any result was inspected):
  - Universe: BTC, ETH, SOL, XRP (real Binance spot 1h OHLCV, already cached:
    data/raw/{BTC,ETH,SOL,XRP}_1h.csv.gz).
  - Data: real alternative.me Fear & Greed Index, daily, full published
    history (2018-02-01 through repo cutoff), fetched via the public
    `api.alternative.me/fng/` endpoint and cached at
    data/fear_greed/fng_raw.json / fear_greed_index.csv.gz. No proxy/synthetic
    fear index -- if the API is down, the study is blocked, not faked.
  - Signal (daily, using only the PRIOR completed day's published index value,
    to avoid any same-day lookahead -- the index for day T is treated as
    known only as of day T's close/next day's open): trigger when
    FGI_t <= 25 ("Extreme Fear").
  - Entry: next day's 00:00 UTC hourly open (one full day of information lag).
  - Exit: fixed hold of 14 days (336h), then flat. Cooldown: no new entry
    while already in a position (non-overlapping trades only, matches the
    DVOL-fear-spike study's non-overlap design).
  - Costs: repo-standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE).
  - Benchmarks: continuous buy-and-hold, daily DCA (same released-capital
    schedule) per asset.
  - Partitions: development 2018-02-01->2021-01-01, validation 2021-01-01->
    2024-01-01, test 2024-01-01->repo cutoff.
  - Falsification (preregistered): primary rule must beat both buy-and-hold
    AND daily DCA on ALL FOUR assets, survive doubled round-trip cost, retain
    a positive best-trade-excluded terminal value beating B&H (no
    concentration artifact), and not lose in the test partition on any asset.
    Any single failure -> REJECTED (or PROMISING BUT INCONCLUSIVE if it's a
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
FNG_ENDPOINT = "https://api.alternative.me/fng/?limit=0&format=json"

END_EXCLUSIVE = pd.Timestamp("2026-08-30T00:00:00Z")  # repo cutoff for this run
DEV_END = pd.Timestamp("2021-01-01T00:00:00Z")
VALIDATION_END = pd.Timestamp("2024-01-01T00:00:00Z")

EXTREME_FEAR_THRESHOLD = 25
HOLD_DAYS = 14
RAW_DIR = ROOT / "data" / "fear_greed"


def fetch_or_load_fng() -> pd.DataFrame:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_json_path = RAW_DIR / "fng_raw.json"
    cache_path = RAW_DIR / "fear_greed_index.csv.gz"
    if cache_path.exists():
        frame = pd.read_csv(cache_path, parse_dates=["timestamp"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        if frame["timestamp"].max() >= (END_EXCLUSIVE - pd.Timedelta(days=3)):
            return frame
    if not raw_json_path.exists():
        attempts = 0
        while True:
            try:
                request = urllib.request.Request(
                    FNG_ENDPOINT, headers={"User-Agent": "validated-crypto-strategies/0.1"}
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read())
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                attempts += 1
                if attempts > 5:
                    raise RuntimeError(f"alternative.me FNG fetch failed: {error}") from error
                time.sleep(min(2**attempts, 16))
        with open(raw_json_path, "w") as f:
            json.dump(payload, f)
    else:
        with open(raw_json_path) as f:
            payload = json.load(f)
    rows = payload["data"]
    if not rows:
        raise RuntimeError("No real alternative.me Fear & Greed data returned")
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype(int), unit="s", utc=True)
    frame["value"] = frame["value"].astype(int)
    frame = frame[["timestamp", "value", "value_classification"]].sort_values("timestamp").reset_index(drop=True)
    # normalize to midnight UTC (daily index)
    frame["timestamp"] = frame["timestamp"].dt.floor("D")
    frame.to_csv(cache_path, index=False, compression="gzip")
    return frame


def load_spot(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def build_signal(fng: pd.DataFrame) -> pd.DataFrame:
    frame = fng.copy().set_index("timestamp").sort_index()
    frame["trigger"] = frame["value"] <= EXTREME_FEAR_THRESHOLD
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


def run_for_asset(coin: str, signal: pd.DataFrame, fng_start: pd.Timestamp) -> dict:
    spot = load_spot(coin)
    spot = spot[spot.index >= fng_start]
    bars_per_year = 365.25 * 24

    entries = non_overlapping_entries(signal, HOLD_DAYS)
    entries = [e for e in entries if e >= spot.index.min() and e <= spot.index.max()]

    primary = simulate_signal_strategy(spot, entries, HOLD_DAYS, ONE_WAY_COST)
    doubled = simulate_signal_strategy(spot, entries, HOLD_DAYS, ONE_WAY_COST * 2)
    bh = buy_and_hold(spot)
    dca = daily_dca(spot, ONE_WAY_COST)
    excl_best_final = exclude_best_trade_final_capital(spot, entries, HOLD_DAYS, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)
    metrics_dca = compute_metrics(dca["equity"], bars_per_year)

    partitions = {
        "development": (fng_start, DEV_END),
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
    fng = fetch_or_load_fng()
    signal = build_signal(fng)
    fng_start = fng["timestamp"].min()
    print(f"FGI data: {len(fng)} days, {fng_start} -> {fng['timestamp'].max()}")
    print(f"Extreme Fear (<={EXTREME_FEAR_THRESHOLD}) days: {int(signal['trigger'].sum())} / {len(signal)}")

    results = {coin: run_for_asset(coin, signal, fng_start) for coin in ASSETS}

    out_dir = ROOT / "results" / "fear_greed_contrarian" / "runs"
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
        f"\nBeats B&H (all assets): {beats_bh_all}; Beats DCA: {beats_dca_all}; "
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
