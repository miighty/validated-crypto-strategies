"""EXP-2026-09-02-OBIMBALANCE-001: Order-book depth imbalance, contrarian-liquidity signal.

Hypothesis (preregistered, genuinely new for this repo -- checked
docs/experiment_registry.md and docs/next_hypotheses.md in full before
writing this; confirmed no prior study has ever used real Binance limit
order-book depth). Every prior positioning/crowding study in this program
used either perp funding, perp open interest (Binance/Hyperliquid/Bybit),
regulated CME futures COT, or external sentiment indices (DVOL, FGI,
stablecoin supply). None used the raw limit order book itself.

Data source: Binance USD-M futures public daily order-book-depth archive
(`data.binance.vision/.../bookDepth/{SYMBOL}/...zip`), ~288 five-minute
snapshots/day of standing depth at -5%..-1%/+1%..+5% from mid. First use of
this data source in this repo (fetched and aggregated to one row/day by
scripts/fetch_orderbook_depth.py: mean notional depth resting within 1-2%
of mid on each side, and the resulting bid/ask imbalance ratio). Coverage
2023-01-01 through 2026-09-01 on all 4 assets (real archive limit, not
fabricated -- Binance's public bookDepth archive itself starts there).

Economic rationale: a large positive imbalance (bid-side resting depth
within 1-2% of mid meaningfully exceeds ask-side resting depth) reflects
market makers/large participants willing to absorb selling pressure near
the current price -- a real liquidity-provision signal distinct from either
executed order flow (taker volume) or positioning (funding/OI/COT), which
this repo has already tested five times. This is the first LIQUIDITY-side
(not positioning-side, not sentiment-side) real-data mechanism tested here.

PRIMARY RULE (frozen before any result was inspected):
  1. imbalance_t = (bid_depth_1_2pct - ask_depth_1_2pct) / (bid_depth_1_2pct
     + ask_depth_1_2pct), already computed and cached daily.
  2. z_t = z-score of imbalance_t against a trailing 90-day window using
     ONLY prior days (shift(1) before rolling, so day t's own reading never
     enters its own baseline -- same anti-lookahead pattern as the CFTC-COT
     and OI-trend studies).
  3. Entry trigger: z_t >= +1.5 (book unusually bid-heavy vs its own recent
     history) -> LONG spot at the next daily bar's open, hold 7 days, then
     flat. Non-overlapping (cooldown until exit + next signal).
  4. Costs: standard 30bps round trip (15bps/side).
  5. Universe: BTC/ETH/SOL/XRP independently (single-asset study, not
     cross-sectional).

Baselines: buy-and-hold, daily DCA (same released-capital-equivalent
schedule via unit accumulation), and a seeded random-timing control
matching trade count and hold length.

Partitions (frozen before inspecting any per-partition result): development
2023-01-01->2024-01-01, validation 2024-01-01->2025-01-01, test
2025-01-01->repo cutoff (2026-09-01).

Falsification (preregistered): primary must beat buy-and-hold AND daily DCA
AND its own random-timing control after costs, survive doubled round-trip
cost, retain a positive best-trade-excluded edge (no single trade >20% of
total strategy PnL -- this program's concentration cap), and have real
trades in the 2025+ test partition. Any single failure -> REJECTED unless a
narrow near-miss per the skill's near-miss discipline.
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
Z_WINDOW = 90
Z_ENTRY_THRESHOLD = 1.5
HOLD_DAYS = 7
CONCENTRATION_CAP_PCT = 20.0
BASE_SEED = 20260902
RANDOM_SEED_OFFSET = {"BTC": 1, "ETH": 2, "SOL": 3, "XRP": 4}

END_EXCLUSIVE = pd.Timestamp("2026-09-01T00:00:00Z")
DEV_START = pd.Timestamp("2023-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2025-01-01T00:00:00Z")


def load_price(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[(df.index >= DEV_START) & (df.index < END_EXCLUSIVE)]


def load_depth(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.data / "orderbook_depth" / f"{coin}_depth_imbalance_1d.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[df.index < END_EXCLUSIVE]


def build_signal(depth: pd.DataFrame) -> pd.Series:
    imbalance = depth["imbalance"]
    prior = imbalance.shift(1)
    roll_mean = prior.rolling(Z_WINDOW, min_periods=30).mean()
    roll_std = prior.rolling(Z_WINDOW, min_periods=30).std(ddof=1)
    z = (imbalance - roll_mean) / roll_std
    trigger = z >= Z_ENTRY_THRESHOLD
    return trigger.rename("trigger")


def non_overlapping_entries(trigger: pd.Series, price_index: pd.DatetimeIndex, hold_days: int) -> list[pd.Timestamp]:
    entries: list[pd.Timestamp] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for ts, val in trigger.items():
        if not bool(val):
            continue
        if ts < next_ok:
            continue
        candidates = price_index[price_index > ts]
        if len(candidates) == 0:
            continue
        entry_ts = candidates[0]
        entries.append(entry_ts)
        next_ok = entry_ts + pd.Timedelta(days=hold_days)
    return entries


def simulate_signal_strategy(price: pd.DataFrame, entries: list[pd.Timestamp], hold_days: int, one_way_cost: float) -> dict:
    capital = 1.0
    units = 0.0
    in_position = False
    entry_price = None
    entry_time = None
    exit_target = None
    trade_log = []
    equity_curve = []

    entry_set = set(entries)
    opens = price["open"] if "open" in price.columns else price["close"]
    closes = price["close"]
    times = price.index

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
                "note": "forced_close_at_sample_end",
            }
        )
        capital = proceeds

    trades_df = pd.DataFrame(trade_log)
    equity_df = pd.DataFrame(equity_curve).set_index("timestamp")
    final = float(equity_df["equity"].iloc[-1]) if len(equity_df) else 1.0
    return {"trades": trades_df, "equity": equity_df, "final": final}


def simulate_buy_and_hold(price: pd.DataFrame) -> float:
    opens = price["open"] if "open" in price.columns else price["close"]
    entry_price = float(opens.iloc[0]) * (1 + ONE_WAY_COST)
    exit_price = float(price["close"].iloc[-1]) * (1 - ONE_WAY_COST)
    units = 1.0 / entry_price
    return units * exit_price


def simulate_daily_dca(price: pd.DataFrame) -> float:
    closes = price["close"]
    n = len(closes)
    tranche = 1.0 / n
    units = 0.0
    for v in closes:
        exec_price = float(v) * (1 + ONE_WAY_COST)
        units += tranche / exec_price
    final_price = float(closes.iloc[-1]) * (1 - ONE_WAY_COST)
    return units * final_price


def random_entries(price_index: pd.DatetimeIndex, n_trades: int, hold_days: int, seed: int) -> list[pd.Timestamp]:
    rng = np.random.default_rng(seed)
    entries: list[pd.Timestamp] = []
    if n_trades == 0:
        return entries
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    available = list(price_index)
    attempts = 0
    while len(entries) < n_trades and attempts < n_trades * 200:
        attempts += 1
        candidate = available[rng.integers(0, len(available))]
        if candidate < next_ok:
            continue
        entries.append(candidate)
        next_ok = candidate + pd.Timedelta(days=hold_days)
    return sorted(entries)


def doubled_cost_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    extra_factor = 1 - 2 * ONE_WAY_COST
    capital = 1.0
    for r in trades["gross_return"]:
        capital *= (1 + r) * extra_factor
    return capital


def best_trade_excluded_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    idx_best = trades["gross_return"].abs().idxmax()
    capital = 1.0
    for i, r in trades["gross_return"].items():
        rr = 0.0 if i == idx_best else r
        capital *= 1 + rr
    return capital


def top_trade_pct_of_pnl(trades: pd.DataFrame) -> float | None:
    if trades.empty:
        return None
    total_multiplier = 1.0
    contributions = []
    for r in trades["gross_return"]:
        contributions.append(total_multiplier * r)
        total_multiplier *= 1 + r
    total_pnl = total_multiplier - 1.0
    if total_pnl == 0:
        return None
    best = max(contributions, key=abs)
    return float(best / total_pnl) * 100


def partition_label(ts: pd.Timestamp) -> str:
    if ts < VALIDATION_START:
        return "development"
    if ts < TEST_START:
        return "validation_2024"
    return "test_2025_onward"


def run_asset(coin: str) -> dict:
    price = load_price(coin)
    depth = load_depth(coin)
    trigger = build_signal(depth)

    entries = non_overlapping_entries(trigger, price.index, HOLD_DAYS)
    sim = simulate_signal_strategy(price, entries, HOLD_DAYS, ONE_WAY_COST)
    trades, equity, final = sim["trades"], sim["equity"], sim["final"]

    bh_final = simulate_buy_and_hold(price)
    dca_final = simulate_daily_dca(price)

    seed = BASE_SEED + RANDOM_SEED_OFFSET[coin]
    rand_entries = random_entries(price.index, len(entries), HOLD_DAYS, seed)
    rand_sim = simulate_signal_strategy(price, rand_entries, HOLD_DAYS, ONE_WAY_COST)
    rand_final = rand_sim["final"]

    doubled_final = doubled_cost_final(trades)
    excluded_final = best_trade_excluded_final(trades)
    top_pct = top_trade_pct_of_pnl(trades)

    if not trades.empty:
        trades = trades.copy()
        trades["partition"] = trades["entry_time"].apply(partition_label)
    partition_rows = []
    for label in ("development", "validation_2024", "test_2025_onward"):
        part = trades[trades["partition"] == label] if not trades.empty else trades
        partition_rows.append(
            {
                "asset": coin,
                "partition": label,
                "n_trades": len(part),
                "mean_trade_return_pct": float(part["gross_return"].mean() * 100) if len(part) else np.nan,
            }
        )

    return {
        "asset": coin,
        "n_trades": len(trades),
        "primary_final": final,
        "bh_final": bh_final,
        "dca_final": dca_final,
        "random_control_final": rand_final,
        "doubled_cost_final": doubled_final,
        "best_trade_excluded_final": excluded_final,
        "top_trade_pct_of_pnl": top_pct,
        "partition_rows": partition_rows,
        "trades": trades,
    }


def classify_verdict(result: dict) -> tuple[str, dict]:
    test_rows = [r for r in result["partition_rows"] if r["partition"] == "test_2025_onward"]
    has_holdout = bool(test_rows and test_rows[0]["n_trades"] > 0)
    beats_bh = result["primary_final"] > result["bh_final"]
    beats_dca = result["primary_final"] > result["dca_final"]
    beats_random = result["primary_final"] > result["random_control_final"]
    survives_doubled_cost = result["doubled_cost_final"] > 1.0
    survives_exclusion = result["best_trade_excluded_final"] > result["bh_final"]
    concentration_ok = (
        result["top_trade_pct_of_pnl"] is None or abs(result["top_trade_pct_of_pnl"]) < CONCENTRATION_CAP_PCT
    )
    gates = {
        "beats_buy_and_hold": beats_bh,
        "beats_dca": beats_dca,
        "beats_random_control": beats_random,
        "survives_doubled_cost": survives_doubled_cost,
        "survives_best_trade_exclusion": survives_exclusion,
        "concentration_ok": concentration_ok,
        "has_holdout_trades": has_holdout,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def main() -> None:
    all_results = {}
    for coin in ASSETS:
        all_results[coin] = run_asset(coin)

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = PATHS.results / "orderbook_imbalance" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# Order-Book Depth Imbalance (Contrarian-Liquidity) Validation", ""]
    lines.append("## Primary rule")
    lines.append(
        f"> LONG-ONLY per-asset: z-score (90d trailing, prior-only) of daily bid-vs-ask "
        f"order-book notional-depth imbalance (1-2% from mid) >= +{Z_ENTRY_THRESHOLD} -> "
        f"long spot at next day's open, hold {HOLD_DAYS} days, flat otherwise. "
        f"{ROUND_TRIP_COST*100:.0f}bps round-trip cost. Non-overlapping trades."
    )
    lines.append("")
    lines.append("## Data sources")
    lines.append(
        "- Real Binance USD-M futures order-book depth archive "
        "(`data/orderbook_depth/*_depth_imbalance_1d.csv.gz`, newly fetched this run via "
        "`scripts/fetch_orderbook_depth.py`; first use of L2 order-book data in this repo), "
        "coverage 2023-01-01 through 2026-09-01."
    )
    lines.append("- Real Binance spot daily OHLCV (`data/raw/*_1d.csv.gz`, already cached).")
    lines.append("")

    verdicts = {}
    summary_rows = []
    for coin, result in all_results.items():
        lines.append(f"### {coin}")
        lines.append(f"- Trades: **{result['n_trades']}**")
        lines.append(f"- Primary final (start=1.0): **{result['primary_final']:.4f}**")
        lines.append(f"- Buy-and-hold final: **{result['bh_final']:.4f}**")
        lines.append(f"- Daily DCA final: **{result['dca_final']:.4f}**")
        lines.append(f"- Random-timing control final: **{result['random_control_final']:.4f}**")
        lines.append(f"- Doubled-cost final: **{result['doubled_cost_final']:.4f}**")
        lines.append(f"- Best-trade-excluded final: **{result['best_trade_excluded_final']:.4f}**")
        lines.append(f"- Top trade % of PnL: {result['top_trade_pct_of_pnl']}")
        verdict, gates = classify_verdict(result)
        verdicts[coin] = verdict
        lines.append(f"- Gates: {gates}")
        lines.append(f"- Verdict: **{verdict}**")
        lines.append("")
        lines.append("Partition breakdown:")
        for row in result["partition_rows"]:
            lines.append(f"  - {row}")
        lines.append("")
        if not result["trades"].empty:
            result["trades"].to_csv(out_dir / f"{coin}_trades.csv", index=False)
        with open(out_dir / f"{coin}_gates.json", "w") as f:
            json.dump({"verdict": verdict, "gates": gates}, f, indent=2, default=str)
        summary_rows.append(
            {
                "asset": coin,
                "n_trades": result["n_trades"],
                "primary_final": result["primary_final"],
                "bh_final": result["bh_final"],
                "dca_final": result["dca_final"],
                "random_control_final": result["random_control_final"],
                "top_trade_pct_of_pnl": result["top_trade_pct_of_pnl"],
                "verdict": verdict,
            }
        )

    n_candidates = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append("## Overall verdict")
    lines.append(f"- {n_candidates}/{len(ASSETS)} assets are CANDIDATE (clear every gate)")
    lines.append(f"- Per-asset verdicts: {verdicts}")

    pd.DataFrame(summary_rows).to_csv(out_dir / "summary.csv", index=False)
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"Order-book imbalance validation written to {out_dir}")
    print(f"Verdicts: {verdicts}")


if __name__ == "__main__":
    main()
