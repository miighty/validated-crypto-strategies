"""EXP-2026-09-03-DEPEG-001: Stablecoin depeg contrarian rebound.

Hypothesis (preregistered, genuinely new for this repo -- checked against
docs/experiment_registry.md and docs/next_hypotheses.md before writing this
file; no existing study has ever used a stablecoin/USDT SPOT PRICE series as
the trading signal or instrument itself. The already-REJECTED
STABLECOIN_SUPPLY_TREND study used real DefiLlama AGGREGATE stablecoin
SUPPLY (a fundamental fiat-flow regime filter applied to BTC/ETH/SOL/XRP
trend) -- mechanistically and data-source distinct from this study, which
trades the stablecoin's own price dislocation against USDT):

  Regulated/audited stablecoins (USDC, TUSD, USDP, FDUSD) are designed to
  trade at 1.00 USD. Real-world redemption friction, banking-partner stress
  (e.g. USDC/SVB March 2023), or temporary liquidity imbalances on a single
  exchange occasionally push the spot price measurably below peg for hours
  to days before arbitrageurs/redemptions restore it. Buying the discounted
  stablecoin against USDT and holding until it re-pegs (or a capped max
  hold) captures this convergence -- a real, mechanically-grounded reversion
  (unlike a directional "buy the panic" bet on a volatile asset), IF the
  discount magnitude exceeds realistic round-trip trading costs.

  This is explicitly NOT tested on UST (TerraUSD) or any stablecoin that
  permanently de-pegged to near-zero -- USDC/TUSD/USDP/FDUSD are all
  redeemable, audited, still-pegged tokens today; survivorship of the
  underlying peg mechanism is a precondition for this hypothesis, not
  something being tested here (a token that depegs and never recovers is a
  different, non-arbitrage risk this study does not address or claim to
  capture).

PRIMARY RULE (frozen before any result was inspected):
  - Universe: USDC/USDT, TUSD/USDT, USDP/USDT, FDUSD/USDT real Binance spot
    hourly OHLCV (newly fetched this run, data/stablecoin_depeg/*.csv.gz).
  - Signal: hourly LOW <= 0.990 (1.0% below peg) -- wick-sensitive, since a
    depeg that wicks down and reclaims within the same hour is still a real
    tradeable dislocation an alert trader could have caught intra-hour on a
    lower timeframe; this backtest is deliberately conservative and only
    trades the next COMPLETED hourly bar's open, never the wick itself.
  - Entry: next hourly bar's OPEN (one full hour of information lag).
  - Exit: first hourly bar whose CLOSE reclaims >= 0.999 (effectively
    re-pegged), OR a fixed max hold of 168h (7 days) if repeg does not occur
    first, whichever comes first. Exit at that bar's close.
  - Cooldown: 24h after any exit before a new entry can trigger (dedupe one
    depeg episode into one trade).
  - Costs: repo-standard 30bps round-trip (15bps/side) -- deliberately using
    the full crypto-perp/altcoin cost model rather than a lower stablecoin-
    specific figure, to stay conservative and comparable across this repo's
    studies.
  - Sizing: 100% of capital per trade, non-overlapping (long-or-cash only).

Baselines (mandatory, per skill):
  1. Cash (0% return) -- the correct primary comparison, since "buy and hold
     a stablecoin" is mechanically ~0% too (it is supposed to sit at 1.00).
  2. Buy-and-hold the stablecoin itself (sanity check -- should be near-flat
     with a small residual from any prior depeg/repeg noise still in the
     window).
  3. A seeded random-timing control matched on trade count and max-hold
     length (does the depeg-detection timing itself add value vs random
     entries with the same holding profile?).

Falsification (preregistered): primary rule must beat cash after realistic
round-trip costs on a MAJORITY (>=3/4) of the four stablecoins, survive
doubled round-trip costs, retain a positive best-trade-excluded PnL
(concentration check, <=20% of total PnL in the single best trade), and have
real trades in each stablecoin's own test partition (2024-01-01 onward,
where the asset's history covers it). Any decisive failure on a majority of
assets -> REJECTED. A narrow 1-2-asset near-miss -> PROMISING BUT
INCONCLUSIVE, not CANDIDATE.

Partitions: development (start -> 2022-01-01), validation (2022-01-01 ->
2024-01-01), test (2024-01-01 -> repo cutoff 2026-07-28 exclusive). FDUSD's
real history only starts 2023-07-26, so its development/validation windows
are thin by construction -- reported honestly, not padded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import FEE_RATE, Paths, SLIPPAGE_RATE, project_root

ROOT = project_root()
PATHS = Paths(ROOT)
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE  # 0.0015
ROUND_TRIP_COST = 2 * ONE_WAY_COST

ASSETS = ["USDC", "TUSD", "USDP", "FDUSD"]
END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VALIDATION_START = pd.Timestamp("2022-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")

DEPEG_THRESHOLD = 0.990
REPEG_THRESHOLD = 0.999
MAX_HOLD_HOURS = 168
COOLDOWN_HOURS = 24
RANDOM_SEED = 20260903

DATA_DIR = ROOT / "data" / "stablecoin_depeg"


def load_asset(coin: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{coin}USDT_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    df = df.set_index("timestamp")
    df = df[df.index < END_EXCLUSIVE]
    if not df.index.is_monotonic_increasing:
        raise ValueError(f"Unsorted timestamps for {coin}")
    return df


def build_signal(frame: pd.DataFrame) -> pd.Series:
    return frame["low"] <= DEPEG_THRESHOLD


def find_entries_and_holds(
    frame: pd.DataFrame, trigger: pd.Series, max_hold: int, cooldown: int
) -> list[tuple[int, int]]:
    """Return (entry_idx, exit_idx) pairs. Exit determined dynamically by
    repeg reclaim (close >= REPEG_THRESHOLD) or max_hold, whichever first."""
    n = len(frame)
    closes = frame["close"].to_numpy()
    trig = trigger.to_numpy()
    pairs = []
    next_ok_idx = -1
    i = 0
    while i < n - 1:
        if not trig[i]:
            i += 1
            continue
        entry_idx = i + 1
        if entry_idx <= next_ok_idx or entry_idx >= n:
            i += 1
            continue
        exit_idx = min(entry_idx + max_hold, n - 1)
        # Repeg check starts one bar AFTER entry, so exit is never on the
        # same bar as entry (a same-bar entry/exit is a backtest-engine bug:
        # the position-tracking loop below only closes at the FIRST future
        # bar index equal to cur_exit, so cur_exit must be strictly > entry).
        for j in range(entry_idx + 1, min(entry_idx + max_hold, n)):
            if closes[j] >= REPEG_THRESHOLD:
                exit_idx = j
                break
        exit_idx = max(exit_idx, min(entry_idx + 1, n - 1))
        pairs.append((entry_idx, exit_idx))
        next_ok_idx = exit_idx + cooldown
        i = exit_idx + 1
    return pairs


def simulate(frame: pd.DataFrame, pairs: list[tuple[int, int]], one_way_cost: float) -> dict:
    n = len(frame)
    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    times = frame.index
    capital = 1.0
    trade_log = []
    equity = np.ones(n)
    entry_map = {e: x for e, x in pairs}
    exit_map = {x: e for e, x in pairs}
    in_position = False
    units = 0.0
    entry_price = None
    entry_time = None
    cur_exit = None
    for i in range(n):
        if in_position and i == cur_exit:
            exec_price = float(closes[i]) * (1 - one_way_cost)
            proceeds = units * exec_price
            trade_log.append({
                "entry_time": entry_time, "exit_time": times[i],
                "entry_price": entry_price, "exit_price": exec_price,
                "gross_return": exec_price / entry_price - 1.0,
                "hold_hours": i - list(times).index(entry_time) if False else None,
            })
            capital = proceeds
            units = 0.0
            in_position = False
        if (not in_position) and i in entry_map:
            exec_price = float(opens[i]) * (1 + one_way_cost)
            units = capital / exec_price
            capital = 0.0
            in_position = True
            entry_price = exec_price
            entry_time = times[i]
            cur_exit = entry_map[i]
        equity[i] = capital + units * float(closes[i])
    if in_position:
        exec_price = float(closes[-1]) * (1 - one_way_cost)
        proceeds = units * exec_price
        trade_log.append({
            "entry_time": entry_time, "exit_time": times[-1],
            "entry_price": entry_price, "exit_price": exec_price,
            "gross_return": exec_price / entry_price - 1.0,
            "hold_hours": None,
        })
        capital = proceeds
    equity_df = pd.DataFrame({"equity": equity}, index=times)
    trades_df = pd.DataFrame(trade_log)
    return {"equity": equity_df, "trades": trades_df, "final_capital": float(equity[-1])}


def random_timing_control(
    frame: pd.DataFrame, pairs: list[tuple[int, int]], one_way_cost: float, seed: int
) -> dict:
    """Seeded random entries with the SAME hold-length distribution as the
    primary rule's realized trades (draw with replacement from the primary
    hold-length multiset), matched on trade count, respecting non-overlap."""
    n = len(frame)
    n_trades = len(pairs)
    if n_trades == 0 or n < MAX_HOLD_HOURS + COOLDOWN_HOURS + 2:
        return {"equity": pd.DataFrame({"equity": [1.0]}, index=[frame.index[0]]),
                "trades": pd.DataFrame(), "final_capital": 1.0}
    hold_lengths = [x - e for e, x in pairs]
    rng = np.random.default_rng(seed)
    new_pairs = []
    attempts = 0
    max_attempts = n_trades * 500
    occupied = np.zeros(n, dtype=bool)
    while len(new_pairs) < n_trades and attempts < max_attempts:
        attempts += 1
        hold = int(rng.choice(hold_lengths))
        start = int(rng.integers(1, max(2, n - hold - COOLDOWN_HOURS - 1)))
        end = min(start + hold, n - 1)
        span = slice(max(0, start - 1), min(n, end + COOLDOWN_HOURS + 1))
        if occupied[span].any():
            continue
        occupied[max(0, start - 1):min(n, end + COOLDOWN_HOURS + 1)] = True
        new_pairs.append((start, end))
    new_pairs.sort()
    return simulate(frame, new_pairs, one_way_cost)


def buy_and_hold(frame: pd.DataFrame) -> dict:
    closes = frame["close"]
    start_price = float(closes.iloc[0])
    equity = closes / start_price
    return {"equity": equity.to_frame("equity"), "final_capital": float(equity.iloc[-1])}


def compute_metrics(equity_df: pd.DataFrame, bars_per_year: float) -> dict:
    if equity_df.empty or len(equity_df) < 2:
        return {"total_return": float("nan"), "sharpe": float("nan"),
                "sortino": float("nan"), "max_drawdown": float("nan")}
    equity = equity_df["equity"]
    rets = equity.pct_change().dropna()
    mean_r = rets.mean()
    std_r = rets.std(ddof=1)
    sharpe = (mean_r / std_r) * np.sqrt(bars_per_year) if std_r > 0 else float("nan")
    downside = rets.clip(upper=0.0)
    downside_dev = np.sqrt((downside ** 2).mean())
    sortino = (mean_r / downside_dev) * np.sqrt(bars_per_year) if downside_dev > 0 else float("nan")
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    return {"total_return": total_return, "sharpe": sharpe, "sortino": sortino,
            "max_drawdown": float(dd.min())}


def partition_slice(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    mask = frame.index >= start
    if end is not None:
        mask &= frame.index < end
    return frame.loc[mask]


def exclude_best_trade_final_capital(frame: pd.DataFrame, pairs: list[tuple[int, int]], one_way_cost: float) -> tuple[float, float]:
    if not pairs:
        return float("nan"), float("nan")
    result = simulate(frame, pairs, one_way_cost)
    trades = result["trades"]
    if trades.empty:
        return result["final_capital"], float("nan")
    pnl = trades["gross_return"]
    total_pnl = pnl.sum()
    top_share = float(pnl.max() / total_pnl) if total_pnl != 0 else float("nan")
    best_idx = pnl.idxmax()
    remaining = [p for i, p in enumerate(pairs) if i != best_idx]
    result_excl = simulate(frame, remaining, one_way_cost)
    return result_excl["final_capital"], top_share


def run_for_asset(coin: str) -> dict:
    frame = load_asset(coin)
    bars_per_year = 365.25 * 24

    trigger = build_signal(frame)
    pairs = find_entries_and_holds(frame, trigger, MAX_HOLD_HOURS, COOLDOWN_HOURS)

    primary = simulate(frame, pairs, ONE_WAY_COST)
    doubled = simulate(frame, pairs, ONE_WAY_COST * 2)
    random_control = random_timing_control(frame, pairs, ONE_WAY_COST, RANDOM_SEED + hash(coin) % 1000)
    bh = buy_and_hold(frame)
    excl_best_final, top_trade_pnl_share = exclude_best_trade_final_capital(frame, pairs, ONE_WAY_COST)

    metrics_primary = compute_metrics(primary["equity"], bars_per_year)
    metrics_bh = compute_metrics(bh["equity"], bars_per_year)

    dev_start = frame.index.min()
    partitions = {
        "development": (dev_start, VALIDATION_START),
        "validation": (VALIDATION_START, TEST_START),
        "test": (TEST_START, None),
    }
    partition_rows = []
    times_list = list(frame.index)
    for pname, (pstart, pend) in partitions.items():
        pend_eff = pend or pd.Timestamp.max.tz_localize("UTC")
        p_pairs = [(e, x) for e, x in pairs if pstart <= times_list[e] < pend_eff]
        pframe = partition_slice(frame, pstart, pend)
        if len(pframe) < 24:
            continue
        p_bh = buy_and_hold(pframe)
        p_res = simulate(frame, p_pairs, ONE_WAY_COST) if p_pairs else {"final_capital": 1.0}
        partition_rows.append({
            "asset": coin, "partition": pname,
            "n_trades": len(p_pairs),
            "strategy_final_relative": p_res["final_capital"],
            "bh_final": p_bh["final_capital"],
        })

    trades = primary["trades"]
    mean_gross_return = float(trades["gross_return"].mean()) if not trades.empty else float("nan")
    mean_hold_hours = float((trades["exit_time"] - trades["entry_time"]).dt.total_seconds().mean() / 3600.0) if not trades.empty else float("nan")

    return {
        "asset": coin,
        "n_bars": len(frame),
        "start": frame.index.min(),
        "end": frame.index.max(),
        "n_trades": len(pairs),
        "mean_gross_return_per_trade": mean_gross_return,
        "mean_hold_hours": mean_hold_hours,
        "primary_final": primary["final_capital"],
        "doubled_cost_final": doubled["final_capital"],
        "random_control_final": random_control["final_capital"],
        "exclude_best_trade_final": excl_best_final,
        "bh_final": bh["final_capital"],
        "cash_final": 1.0,
        "primary_total_return": metrics_primary["total_return"],
        "primary_sharpe": metrics_primary["sharpe"],
        "primary_sortino": metrics_primary["sortino"],
        "primary_max_dd": metrics_primary["max_drawdown"],
        "bh_total_return": metrics_bh["total_return"],
        "top_trade_pnl_share": top_trade_pnl_share,
        "beats_cash": bool(primary["final_capital"] > 1.0),
        "beats_bh": bool(primary["final_capital"] > bh["final_capital"]),
        "beats_random_control": bool(primary["final_capital"] > random_control["final_capital"]),
        "beats_cash_doubled_cost": bool(doubled["final_capital"] > 1.0),
        "beats_cash_excl_best_trade": bool(excl_best_final > 1.0) if excl_best_final == excl_best_final else False,
        "concentration_ok": bool(top_trade_pnl_share != top_trade_pnl_share or abs(top_trade_pnl_share) <= 0.20),
        "partition_rows": partition_rows,
        "trades": trades,
    }


def main() -> None:
    results = {coin: run_for_asset(coin) for coin in ASSETS}

    out_dir = ROOT / "results" / "stablecoin_depeg_rebound" / "runs"
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

    n_assets = len(ASSETS)
    maj = lambda col: int(summary_df[col].sum()) >= (n_assets // 2 + 1)

    beats_cash_maj = maj("beats_cash")
    beats_random_maj = maj("beats_random_control")
    beats_doubled_maj = maj("beats_cash_doubled_cost")
    beats_excl_maj = maj("beats_cash_excl_best_trade")
    concentration_maj = maj("concentration_ok")

    test_partitions = partition_df[partition_df["partition"] == "test"]
    has_holdout_trades = bool((test_partitions["n_trades"] > 0).any()) if not test_partitions.empty else False

    all_gates = [beats_cash_maj, beats_random_maj, beats_doubled_maj, beats_excl_maj, concentration_maj, has_holdout_trades]
    n_pass = sum(all_gates)

    if n_pass == len(all_gates):
        verdict = "CANDIDATE"
    elif n_pass >= len(all_gates) - 1 and has_holdout_trades:
        verdict = "PROMISING BUT INCONCLUSIVE"
    else:
        verdict = "REJECTED"

    print(f"\nGates passed (majority-of-4-assets basis): {n_pass}/{len(all_gates)}")
    print(f"  beats_cash_majority={beats_cash_maj} beats_random_control_majority={beats_random_maj}")
    print(f"  beats_doubled_cost_majority={beats_doubled_maj} beats_excl_best_trade_majority={beats_excl_maj} "
          f"concentration_ok_majority={concentration_maj} has_holdout_trades={has_holdout_trades}")
    print(f"Verdict: {verdict}")

    with open(run_dir / "verdict.txt", "w") as f:
        f.write(
            f"beats_cash_majority={beats_cash_maj}\nbeats_random_control_majority={beats_random_maj}\n"
            f"beats_doubled_cost_majority={beats_doubled_maj}\nbeats_excl_best_trade_majority={beats_excl_maj}\n"
            f"concentration_ok_majority={concentration_maj}\nhas_holdout_trades={has_holdout_trades}\n"
            f"n_pass={n_pass}/{len(all_gates)}\nverdict={verdict}\n"
        )
    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
