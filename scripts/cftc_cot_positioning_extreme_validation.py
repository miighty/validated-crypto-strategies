"""EXP-2026-09-01-CFTCCOT-001: CFTC COT leveraged-fund positioning extreme, contrarian.

Hypothesis (preregistered, genuinely new for this repo -- never tested here;
uses a data source, the CFTC's weekly public Commitment of Traders (COT)
report for CME-listed Bitcoin and Ether futures, that no prior study in
docs/experiment_registry.md has used. Mechanistically distinct from every
prior study: not perp funding/OI (Binance-native leveraged positioning), not
Deribit implied-vol, not alternative.me sentiment composite, not calendar,
not cross-sectional factor, not SMA-trend. This is the classic TradFi COT
"crowded positioning reverts" contrarian signal, applied for the first time
here to regulated (not perp) futures positioning in crypto):

  The CFTC's weekly COT report discloses aggregate net positioning of
  "Leveraged Funds" (hedge funds / CTAs / other money managers using
  leverage) in CME Bitcoin and Ether futures. When Leveraged Funds are
  extremely net-short relative to their own recent history (a crowded short),
  the classic COT contrarian thesis says the position is vulnerable to a
  short-covering squeeze and should precede positive spot returns (and vice
  versa for extremely net-long). This report is real, public, weekly, and
  entirely independent of the Binance/Hyperliquid/Bybit perp funding+OI data
  already exhausted by five prior REJECTED single-asset OI/funding studies
  in this repo.

Design (frozen before any result was inspected):
  - Universe: BTC (CME "BITCOIN" futures, real history 2018-04-10 onward,
    438 weekly reports) and ETH (CME "ETHER CASH SETTLED" futures, real
    history 2021-04-06 onward, 282 weekly reports). No proxy for SOL/XRP --
    CME does not list regulated futures for either, so this is necessarily a
    2-asset study (same data-availability constraint pattern as the
    Deribit-DVOL study).
  - Data: real CFTC Socrata public API
    (publicreporting.cftc.gov/resource/gpe5-46if.json, "Legacy Futures Only"
    disaggregated report), weekly, cached at
    data/cftc_cot/cme_{btc,eth}_cot_raw.json. Real Binance spot 1h OHLCV
    (already cached) for trade execution prices.
  - Signal (weekly, prior-only rolling window to avoid lookahead): compute
    lev_net_pct_oi = (lev_money_positions_long - lev_money_positions_short)
    / open_interest_all for each weekly report. Z-score this against a
    trailing 52-week window computed using only PRIOR completed reports
    (shift(1) before rolling, so the current week's own reading never enters
    its own baseline).
  - Entry trigger: z <= -1.5 (leveraged funds crowded net-short vs their own
    recent history) -> contrarian LONG. (Long-only spot strategy per skill
    guidance; z >= +1.5 crowded-long condition is tracked as a control but
    not traded, since a spot strategy cannot short.)
  - Real-world publication lag: the COT report as of Tuesday's positions is
    published the following Friday at 15:30 ET. To avoid lookahead, treat
    the signal as knowable only as of report_date + 4 calendar days (the
    Friday release), then enter at the NEXT hourly bar's open >= that
    timestamp.
  - Exit: fixed hold of 14 days (336h) -- roughly 2 COT reporting cycles,
    then flat. Cooldown: no new entry while already in a position
    (non-overlapping trades only).
  - Costs: repo-standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE).
  - Benchmarks: continuous buy-and-hold, daily DCA (same released-capital
    schedule), a seeded random-timing control (same trade count/hold length).
  - Partitions: BTC development 2018-04-10->2021-01-01, validation
    2021-01-01->2024-01-01, test 2024-01-01->repo cutoff. ETH (shorter real
    history): development 2021-04-06->2023-01-01, validation 2023-01-01->
    2024-07-01, test 2024-07-01->repo cutoff.
  - Falsification (preregistered): primary rule must beat both buy-and-hold
    AND daily DCA on BOTH assets, survive doubled round-trip cost, retain a
    positive best-trade-excluded terminal value beating B&H (no
    concentration artifact: best trade <=20% of total strategy PnL), beat
    its own seeded random-timing control, and not lose in the test partition
    on either asset. Any single failure -> REJECTED (or PROMISING BUT
    INCONCLUSIVE if it's a narrow near-miss per the skill's near-miss
    discipline).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
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

COT_DIR = ROOT / "data" / "cftc_cot"
COT_DIR.mkdir(parents=True, exist_ok=True)
COT_ENDPOINT = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"

ASSET_MARKETS = {
    "BTC": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
    "ETH": "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE",
}

END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")  # repo Binance spot cutoff
PARTITIONS = {
    "BTC": {
        "development": (pd.Timestamp("2018-04-10T00:00:00Z"), pd.Timestamp("2021-01-01T00:00:00Z")),
        "validation": (pd.Timestamp("2021-01-01T00:00:00Z"), pd.Timestamp("2024-01-01T00:00:00Z")),
        "test": (pd.Timestamp("2024-01-01T00:00:00Z"), None),
    },
    "ETH": {
        "development": (pd.Timestamp("2021-04-06T00:00:00Z"), pd.Timestamp("2023-01-01T00:00:00Z")),
        "validation": (pd.Timestamp("2023-01-01T00:00:00Z"), pd.Timestamp("2024-07-01T00:00:00Z")),
        "test": (pd.Timestamp("2024-07-01T00:00:00Z"), None),
    },
}

Z_WINDOW = 52  # weeks
Z_ENTRY_THRESHOLD = -1.5
HOLD_DAYS = 14
PUBLICATION_LAG_DAYS = 4  # Tuesday report -> Friday release
RANDOM_SEED = 20260901


def fetch_or_load_cot(coin: str) -> pd.DataFrame:
    raw_path = COT_DIR / f"cme_{coin.lower()}_cot_raw.json"
    if raw_path.exists():
        with open(raw_path) as f:
            payload = json.load(f)
    else:
        market_name = ASSET_MARKETS[coin]
        where_clause = f"upper(market_and_exchange_names)='{market_name}'"
        params = {
            "$where": where_clause,
            "$select": (
                "report_date_as_yyyy_mm_dd,open_interest_all,"
                "lev_money_positions_long,lev_money_positions_short"
            ),
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": 2000,
        }
        url = COT_ENDPOINT + "?" + urllib.parse.urlencode(params)
        attempts = 0
        while True:
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "validated-crypto-strategies/0.1"}
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read())
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                attempts += 1
                if attempts > 5:
                    raise RuntimeError(f"CFTC COT fetch failed for {coin}: {error}") from error
                time.sleep(min(2**attempts, 16))
        if not payload:
            raise RuntimeError(f"No real CFTC COT data returned for {coin}")
        with open(raw_path, "w") as f:
            json.dump(payload, f)

    frame = pd.DataFrame(payload)
    for col in ["open_interest_all", "lev_money_positions_long", "lev_money_positions_short"]:
        frame[col] = pd.to_numeric(frame[col])
    frame["report_date"] = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"], utc=True)
    frame = frame.sort_values("report_date").reset_index(drop=True)
    frame["lev_net"] = frame["lev_money_positions_long"] - frame["lev_money_positions_short"]
    frame["lev_net_pct_oi"] = frame["lev_net"] / frame["open_interest_all"]
    return frame


def build_signal(cot: pd.DataFrame) -> pd.DataFrame:
    frame = cot.copy()
    # prior-only rolling z-score: shift(1) before rolling so current week's
    # own reading never enters its own baseline
    prior = frame["lev_net_pct_oi"].shift(1)
    roll_mean = prior.rolling(Z_WINDOW, min_periods=13).mean()
    roll_std = prior.rolling(Z_WINDOW, min_periods=13).std(ddof=1)
    frame["z"] = (frame["lev_net_pct_oi"] - roll_mean) / roll_std
    frame["trigger"] = frame["z"] <= Z_ENTRY_THRESHOLD
    frame["trigger_short_side"] = frame["z"] >= -Z_ENTRY_THRESHOLD  # control only, not traded
    frame["available_ts"] = frame["report_date"] + pd.Timedelta(days=PUBLICATION_LAG_DAYS)
    return frame


def load_spot(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[df.index < END_EXCLUSIVE]
    return df


def non_overlapping_entries(signal: pd.DataFrame, spot_index: pd.DatetimeIndex, hold_days: int) -> list[pd.Timestamp]:
    entries: list[pd.Timestamp] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for _, row in signal.iterrows():
        if not bool(row["trigger"]):
            continue
        available = row["available_ts"]
        if available < next_ok:
            continue
        candidates = spot_index[spot_index >= available]
        if len(candidates) == 0:
            continue
        entry_ts = candidates[0]
        entries.append(entry_ts)
        next_ok = entry_ts + pd.Timedelta(days=hold_days)
    return entries


def simulate_signal_strategy(spot: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float) -> dict:
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
        if (not in_position) and ts in entry_set:
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


def random_timing_control(spot: pd.DataFrame, n_trades: int, hold_days: int, one_way_cost: float, seed: int) -> dict:
    if n_trades == 0:
        return {"final_capital": float("nan")}
    rng = np.random.default_rng(seed)
    times = spot.index
    max_start_idx = len(times) - 1
    entries: list[pd.Timestamp] = []
    next_ok_idx = 0
    attempts = 0
    while len(entries) < n_trades and attempts < n_trades * 200:
        attempts += 1
        idx = int(rng.integers(0, max_start_idx))
        ts = times[idx]
        if ts < times[next_ok_idx] if entries else False:
            continue
        if entries and ts < entries[-1] + pd.Timedelta(days=hold_days):
            continue
        entries.append(ts)
    entries = sorted(entries)
    result = simulate_signal_strategy(spot, entries, hold_days, one_way_cost)
    return result


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


def exclude_best_trade(spot: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float) -> tuple[float, float]:
    if not entries:
        return float("nan"), float("nan")
    result = simulate_signal_strategy(spot, entries, hold_days, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"], 0.0
    total_pnl = result["final_capital"] - 1.0
    best_idx = trades["gross_return"].idxmax()
    remaining_entries = [e for i, e in enumerate(entries) if i != best_idx]
    result_excl = simulate_signal_strategy(spot, remaining_entries, hold_days, one_way_cost)
    best_trade_pnl_share = float("nan")
    if total_pnl != 0:
        excl_pnl = result_excl["final_capital"] - 1.0
        best_trade_pnl_share = (total_pnl - excl_pnl) / total_pnl
    return result_excl["final_capital"], best_trade_pnl_share


def run_for_asset(coin: str) -> dict:
    cot = fetch_or_load_cot(coin)
    signal = build_signal(cot)
    spot = load_spot(coin)
    spot_start = max(spot.index.min(), signal["available_ts"].min())
    spot = spot[spot.index >= spot_start]
    bars_per_year = 365.25 * 24

    entries = non_overlapping_entries(signal, spot.index, HOLD_DAYS)
    entries = [e for e in entries if e >= spot.index.min() and e <= spot.index.max()]

    n_control_signal_weeks = int(signal["trigger"].sum())

    primary = simulate_signal_strategy(spot, entries, HOLD_DAYS, ONE_WAY_COST)
    doubled = simulate_signal_strategy(spot, entries, HOLD_DAYS, ONE_WAY_COST * 2)
    bh = buy_and_hold(spot)
    dca = daily_dca(spot, ONE_WAY_COST)
    excl_best_final, best_trade_pnl_share = exclude_best_trade(spot, entries, HOLD_DAYS, ONE_WAY_COST)
    random_ctrl = random_timing_control(spot, len(entries), HOLD_DAYS, ONE_WAY_COST, RANDOM_SEED)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)
    metrics_dca = compute_metrics(dca["equity"], bars_per_year)

    partitions = PARTITIONS[coin]
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
        "n_cot_weeks": len(cot),
        "n_trigger_weeks": n_control_signal_weeks,
        "n_trades": len(entries),
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "exclude_best_trade_final": excl_best_final,
        "best_trade_pnl_share": best_trade_pnl_share,
        "random_control_final": random_ctrl["final_capital"],
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
        "beats_bh_excl_best_trade": bool(excl_best_final > bh["final_capital"]) if not np.isnan(excl_best_final) else False,
        "beats_random_control": bool(primary["final_capital"] > random_ctrl["final_capital"]) if not np.isnan(random_ctrl["final_capital"]) else False,
        "concentration_ok": bool(best_trade_pnl_share <= 0.20) if not np.isnan(best_trade_pnl_share) else False,
        "partition_rows": partition_rows,
        "trades": primary["trades"],
    }


def main() -> None:
    results = {}
    for coin in ["BTC", "ETH"]:
        print(f"Running CFTC COT positioning-extreme study for {coin}...")
        results[coin] = run_for_asset(coin)

    out_dir = ROOT / "results" / "cftc_cot_positioning_extreme" / "runs"
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
    beats_random_all = bool(summary_df["beats_random_control"].all())
    concentration_ok_all = bool(summary_df["concentration_ok"].all())
    test_pass = bool(
        not partition_df.empty
        and partition_df[partition_df["partition"] == "test"]["strategy_beats_bh"].all()
        and (partition_df[partition_df["partition"] == "test"]["n_trades"] > 0).all()
    )

    if (
        beats_bh_all
        and beats_dca_all
        and beats_doubled_all
        and beats_excl_best_all
        and beats_random_all
        and concentration_ok_all
        and test_pass
    ):
        verdict = "CANDIDATE"
    elif beats_bh_all and beats_dca_all and (beats_doubled_all or beats_excl_best_all) and beats_random_all:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(
        f"\nBeats B&H (all assets): {beats_bh_all}; Beats DCA: {beats_dca_all}; "
        f"Survives doubled cost: {beats_doubled_all}; Survives best-trade exclusion: {beats_excl_best_all}; "
        f"Beats random control: {beats_random_all}; Concentration OK: {concentration_ok_all}; "
        f"Test partition pass: {test_pass}"
    )
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_bh_all={beats_bh_all}\nbeats_dca_all={beats_dca_all}\n"
            f"beats_doubled_cost_all={beats_doubled_all}\nbeats_excl_best_trade_all={beats_excl_best_all}\n"
            f"beats_random_control_all={beats_random_all}\nconcentration_ok_all={concentration_ok_all}\n"
            f"test_partition_pass={test_pass}\nverdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
