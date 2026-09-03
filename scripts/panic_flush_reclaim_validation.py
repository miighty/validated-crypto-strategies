"""EXP-2026-09-03-FLUSHRECLAIM-001: Wick-sensitive panic-flush + price-reclaim
confirmation entry (long-only, single-asset).

Hypothesis (preregistered; checked docs/experiment_registry.md and
docs/next_hypotheses.md in full first -- genuinely new for this repo).

Every prior "buy the panic" study in this program (DVOL fear-spike, FGI
extreme-fear, volume-spike capitulation flush, NVT valuation-extreme,
Coinbase-premium contrarian, stablecoin-depeg rebound) bought IMMEDIATELY on
the trigger bar/day with a FIXED forward hold, and every one was REJECTED --
several reports explicitly diagnosed the failure as "no price-reclaim
confirmation, so the rule keeps buying into ongoing declines" and named a
reclaim-confirmation filter as the recommended next step (VOLUME_FLUSH,
NVT, DVOL rejection notes all say this explicitly). The skill's own
pitfalls section ("panic-flush detection") also explicitly calls for
testing a "reclaim back above the breach threshold" confirmation variant
alongside strict trigger-only detectors.

This is the first time in this program that a genuine reclaim-CONFIRMATION
gate (as opposed to a fixed-hold entry) is applied to a wick-flush panic
signal. Mechanically distinct from EXP-2026-09-01-VOLFLUSH-001 (that study
required a volume spike, no confirmation, fixed 24h hold; this study
requires NO volume filter, but DOES require the price to reclaim its own
breach level before any capital is committed -- confirmation timing, not
volume magnitude, is the new ingredient).

PRIMARY RULE (frozen before any result was inspected):
  1. On real Binance spot 1h OHLCV (already cached, no new fetch needed):
     prior-only rolling 24h high = high.shift(1).rolling(24).max().
  2. Flush trigger at bar t: low_t <= prior_24h_high_t * (1 - 0.04)
     (a violent wick-sensitive drop of >=4% intrabar from the preceding
     24h's high -- distinct from VOLFLUSH's close-vs-prior-close trigger).
  3. breach_level_t = prior_24h_high_t * (1 - 0.04) (the exact threshold
     price that was breached).
  4. Confirmation window: look forward up to 24 bars (24h) from t
     (inclusive of t) for the first bar whose CLOSE >= breach_level_t
     (price has reclaimed back above its own breach threshold -- NOT full
     recovery to the pre-flush high, just reclaiming the breach line
     itself, a deliberately modest confirmation bar).
  5. If confirmed: enter LONG at the NEXT bar's open after the confirming
     close. If not confirmed within 24 bars: no trade, discard this event
     (the flush never stabilized -- do not chase it).
  6. Exit: first of (a) close >= entry_price * 1.03 (3% profit target,
     exit at NEXT bar's open after that close) or (b) 72 hours elapsed
     since entry (timeout, exit at close of the bar 72h after entry).
  7. Cooldown / dedup: while a flush is awaiting confirmation or a position
     is open, no new flush triggers are considered -- one cascade produces
     at most one trade, not dozens of overlapping signals.
  8. Costs: standard 30bps round trip (15bps/side, FEE_RATE+SLIPPAGE_RATE).
  9. Universe: BTC/ETH/SOL/XRP independently (single-asset study).

Baselines: cash, buy-and-hold, hourly-equivalent DCA (accumulate over full
sample), seeded random-timing control matching trade count and mean hold.

Partitions (frozen before inspecting results): development (start->2024-01-01),
validation (2024-01-01->2025-01-01), test (2025-01-01->repo cutoff).

Falsification (preregistered): primary must beat buy-and-hold AND DCA AND
its own random-timing control after costs, survive doubled round-trip cost,
retain a positive best-trade-excluded edge (no single trade >20% of total
strategy PnL), and have real trades in the 2025+ test partition. Any single
failure -> REJECTED unless a narrow, decisive near-miss.
"""
from __future__ import annotations

import json
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

ASSETS = ["BTC", "ETH", "SOL", "XRP"]
LOOKBACK_HOURS = 24
FLUSH_PCT = 0.04
CONFIRM_WINDOW_HOURS = 24
PROFIT_TARGET_PCT = 0.03
TIMEOUT_HOURS = 72
CONCENTRATION_CAP_PCT = 20.0
BASE_SEED = 20260903

VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2025-01-01T00:00:00Z")


def load_price(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.set_index("timestamp").sort_index()


def build_signal(price: pd.DataFrame) -> pd.DataFrame:
    frame = price.copy()
    frame["prior_24h_high"] = frame["high"].shift(1).rolling(LOOKBACK_HOURS, min_periods=LOOKBACK_HOURS).max()
    frame["breach_level"] = frame["prior_24h_high"] * (1 - FLUSH_PCT)
    frame["flush_trigger"] = frame["low"] <= frame["breach_level"]
    return frame


def partition_label(ts: pd.Timestamp) -> str:
    if ts < VALIDATION_START:
        return "development"
    if ts < TEST_START:
        return "validation_2024"
    return "test_2025_onward"


def simulate_primary(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    n = len(frame)
    timestamps = frame.index.to_list()
    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    breach_levels = frame["breach_level"].to_numpy()
    triggers = frame["flush_trigger"].fillna(False).to_numpy()

    capital = 1.0
    equity_rows = []
    trade_rows = []

    state = "idle"  # idle -> awaiting_confirm -> pending_entry -> in_position
    trigger_idx = None
    confirm_deadline_idx = None
    entry_index = None
    entry_price = None
    entry_time = None
    entry_capital = None
    exit_signal_idx = None  # bar index where exit condition became true; execute at exit_signal_idx+1 open
    timeout_idx = None
    n_events_seen = 0
    n_confirmed = 0

    for i in range(n):
        ts = timestamps[i]

        if state == "idle":
            if triggers[i]:
                state = "awaiting_confirm"
                trigger_idx = i
                confirm_deadline_idx = min(i + CONFIRM_WINDOW_HOURS, n - 1)
                n_events_seen += 1

        elif state == "awaiting_confirm":
            if closes[i] >= breach_levels[trigger_idx]:
                if i + 1 < n:
                    entry_index = i + 1
                    entry_price = opens[i + 1]
                    entry_capital = capital
                    entry_time = timestamps[i + 1]
                    capital *= (1 - ONE_WAY_COST)
                    state = "pending_entry"
                    timeout_idx = i + 1 + TIMEOUT_HOURS
                    n_confirmed += 1
                else:
                    state = "idle"
            elif i >= confirm_deadline_idx:
                state = "idle"  # never reclaimed within window; discard event

        elif state == "pending_entry":
            if i == entry_index:
                state = "in_position"

        if state == "in_position" and entry_index is not None and i >= entry_index:
            hit_target = closes[i] >= entry_price * (1 + PROFIT_TARGET_PCT)
            hit_timeout = timeout_idx is not None and i >= timeout_idx
            if (hit_target or hit_timeout) and i > entry_index and exit_signal_idx is None:
                exit_signal_idx = i
            if exit_signal_idx is not None and i == exit_signal_idx + 1:
                exit_price = opens[i]
                gross_return = (exit_price - entry_price) / entry_price
                capital *= (1 + gross_return)
                capital *= (1 - ONE_WAY_COST)
                trade_rows.append(
                    {
                        "trigger_time": timestamps[trigger_idx],
                        "entry_time": entry_time,
                        "exit_time": ts,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "gross_return": gross_return,
                        "capital_at_entry": entry_capital,
                        "capital_at_exit": capital,
                        "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                        "exit_reason": "profit_target" if hit_target else "timeout",
                    }
                )
                state = "idle"
                entry_index = None
                entry_price = None
                entry_time = None
                entry_capital = None
                exit_signal_idx = None
                timeout_idx = None
                trigger_idx = None
                confirm_deadline_idx = None

        equity_rows.append({"timestamp": ts, "capital": capital, "state": state})

    if state == "in_position" and entry_index is not None:
        exit_price = closes[-1]
        gross_return = (exit_price - entry_price) / entry_price
        capital *= (1 + gross_return)
        capital *= (1 - ONE_WAY_COST)
        trade_rows.append(
            {
                "trigger_time": timestamps[trigger_idx] if trigger_idx is not None else None,
                "entry_time": entry_time,
                "exit_time": timestamps[-1],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_return": gross_return,
                "capital_at_entry": entry_capital,
                "capital_at_exit": capital,
                "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                "exit_reason": "forced_close_at_sample_end",
            }
        )
        if equity_rows:
            equity_rows[-1]["capital"] = capital

    equity = pd.DataFrame(equity_rows).set_index("timestamp")
    trades = pd.DataFrame(trade_rows)
    return equity, trades, n_events_seen, n_confirmed


def simulate_buy_and_hold(price: pd.DataFrame) -> pd.Series:
    entry_price = float(price["open"].iloc[0]) * (1 + ONE_WAY_COST)
    units = 1.0 / entry_price
    return (units * price["close"]).rename("capital")


def simulate_dca(price: pd.DataFrame) -> pd.Series:
    tranche = 1.0 / len(price)
    units = 0.0
    rows = []
    for _, row in price.iterrows():
        exec_price = float(row["open"]) * (1 + ONE_WAY_COST)
        units += tranche / exec_price
        rows.append(units * float(row["close"]))
    return pd.Series(rows, index=price.index, name="capital")


def simulate_random_control(price: pd.DataFrame, n_trades: int, mean_hold_hours: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n = len(price)
    hold = max(1, int(round(mean_hold_hours)))
    opens = price["open"].to_numpy()
    closes = price["close"].to_numpy()
    timestamps = price.index.to_list()
    if n_trades == 0 or n < hold + 2:
        return pd.DataFrame(), pd.DataFrame()
    max_start = n - hold - 1
    if max_start <= 0:
        return pd.DataFrame(), pd.DataFrame()
    candidate_starts = rng.choice(np.arange(max_start), size=min(n_trades * 5, max_start), replace=False)
    candidate_starts.sort()
    chosen = []
    last_end = -10**9
    for s in candidate_starts:
        if s - last_end >= hold:
            chosen.append(s)
            last_end = s + hold
        if len(chosen) >= n_trades:
            break

    capital = 1.0
    trade_rows = []
    equity_rows = []
    positions = {s: min(s + hold, n - 1) for s in chosen}
    in_position = False
    entry_price = None
    entry_capital = None
    entry_time = None
    exit_idx = None
    for i in range(n):
        if not in_position and i in positions:
            entry_price = opens[i]
            entry_capital = capital
            entry_time = timestamps[i]
            capital *= (1 - ONE_WAY_COST)
            in_position = True
            exit_idx = positions[i]
        if in_position and i == exit_idx and i > 0:
            exit_price = opens[min(i + 1, n - 1)] if i + 1 < n else closes[i]
            gross_return = (exit_price - entry_price) / entry_price
            capital *= (1 + gross_return)
            capital *= (1 - ONE_WAY_COST)
            trade_rows.append(
                {
                    "entry_time": entry_time,
                    "exit_time": timestamps[i],
                    "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                }
            )
            in_position = False
        equity_rows.append({"timestamp": timestamps[i], "capital": capital})
    equity = pd.DataFrame(equity_rows).set_index("timestamp")
    trades = pd.DataFrame(trade_rows)
    return equity, trades


def doubled_cost_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    extra_factor = 1 - 2 * ONE_WAY_COST
    capital = 1.0
    for r in trades["trade_return"]:
        capital *= (1 + r) * extra_factor
    return capital


def top_trade_pct(trades: pd.DataFrame, final_capital: float) -> float | None:
    if trades.empty:
        return None
    total_pnl = final_capital - 1.0
    if total_pnl == 0:
        return None
    best_idx = trades["trade_return"].abs().idxmax()
    best_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
    return float(best_pnl / total_pnl) * 100


def best_trade_excluded_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    best_idx = trades["trade_return"].abs().idxmax()
    capital = 1.0
    for i, row in trades.iterrows():
        r = row["trade_return"] if i != best_idx else 0.0
        capital *= (1 + r)
    return capital


def run_asset(coin: str) -> dict:
    price = load_price(coin)
    frame = build_signal(price)
    equity, trades, n_events, n_confirmed = simulate_primary(frame)

    bh = simulate_buy_and_hold(price)
    dca = simulate_dca(price)

    mean_hold_hours = 24.0
    if not trades.empty:
        holds = [(row["exit_time"] - row["entry_time"]).total_seconds() / 3600 for _, row in trades.iterrows()]
        mean_hold_hours = float(np.mean(holds)) if holds else 24.0

    seed = BASE_SEED + (hash(coin) % 1000)
    random_equity, random_trades = simulate_random_control(price, len(trades), mean_hold_hours, seed)

    final_capital = float(equity["capital"].iloc[-1])
    bh_final = float(bh.iloc[-1])
    dca_final = float(dca.iloc[-1])
    random_final = float(random_equity["capital"].iloc[-1]) if not random_equity.empty else 1.0
    doubled_final = doubled_cost_final(trades)
    excluded_final = best_trade_excluded_final(trades)
    top_pct = top_trade_pct(trades, final_capital)

    partition_rows = []
    if not trades.empty:
        trades["partition"] = trades["entry_time"].apply(partition_label)
    for label in ("development", "validation_2024", "test_2025_onward"):
        part = trades[trades["partition"] == label] if not trades.empty else pd.DataFrame()
        partition_rows.append(
            {
                "asset": coin,
                "partition": label,
                "n_trades": len(part),
                "mean_trade_return_pct": float(part["trade_return"].mean() * 100) if len(part) else np.nan,
            }
        )

    holdout_trades = partition_rows[2]["n_trades"] if partition_rows else 0

    gates = {
        "beats_cash": final_capital > 1.0,
        "beats_bh": final_capital > bh_final,
        "beats_dca": final_capital > dca_final,
        "beats_random_control": final_capital > random_final,
        "survives_doubled_cost": doubled_final > 1.0,
        "survives_best_trade_exclusion": excluded_final > 1.0,
        "concentration_ok": (top_pct is None) or (abs(top_pct) < CONCENTRATION_CAP_PCT),
        "has_holdout_trades": holdout_trades > 0,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"

    return {
        "asset": coin,
        "n_flush_events": n_events,
        "n_confirmed": n_confirmed,
        "n_trades": len(trades),
        "mean_hold_hours": mean_hold_hours,
        "primary_final": final_capital,
        "bh_final": bh_final,
        "dca_final": dca_final,
        "random_final": random_final,
        "random_n_trades": len(random_trades),
        "doubled_final": doubled_final,
        "excluded_final": excluded_final,
        "top_trade_pct": top_pct,
        "partition_rows": partition_rows,
        "gates": gates,
        "verdict": verdict,
        "trades": trades,
    }


def main() -> None:
    results = {coin: run_asset(coin) for coin in ASSETS}

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = PATHS.results / "panic_flush_reclaim" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    combined_trades = []
    for coin, res in results.items():
        t = res["trades"].copy()
        if not t.empty:
            t["asset"] = coin
        combined_trades.append(t)
        with open(out_dir / f"{coin}_gates.json", "w") as f:
            json.dump({"verdict": res["verdict"], "gates": res["gates"]}, f, indent=2, default=str)
    if combined_trades:
        pd.concat(combined_trades, ignore_index=True).to_csv(out_dir / "trades.csv", index=False)

    summary_rows = []
    for coin, res in results.items():
        summary_rows.append(
            {
                "asset": coin,
                "n_flush_events": res["n_flush_events"],
                "n_confirmed": res["n_confirmed"],
                "n_trades": res["n_trades"],
                "mean_hold_hours": round(res["mean_hold_hours"], 1),
                "primary_final": round(res["primary_final"], 4),
                "bh_final": round(res["bh_final"], 4),
                "dca_final": round(res["dca_final"], 4),
                "random_final": round(res["random_final"], 4),
                "doubled_final": round(res["doubled_final"], 4),
                "excluded_final": round(res["excluded_final"], 4),
                "top_trade_pct": res["top_trade_pct"],
                "verdict": res["verdict"],
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out_dir / "summary.csv", index=False)
    print(summary_df.to_string(index=False))
    print(f"\nOutput dir: {out_dir}")

    n_candidate = sum(1 for r in results.values() if r["verdict"] == "CANDIDATE")
    print(f"\n{n_candidate}/{len(results)} assets cleared every gate.")


if __name__ == "__main__":
    main()
