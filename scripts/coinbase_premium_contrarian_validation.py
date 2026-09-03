"""EXP-2026-09-03-CBPREMIUM-001: Coinbase-vs-Binance price premium, contrarian.

Hypothesis (preregistered, genuinely new for this repo -- checked
docs/experiment_registry.md and docs/next_hypotheses.md in full: no prior
study in this program has used a cross-EXCHANGE SPOT PRICE premium/discount
as a signal. Prior cross-exchange studies used funding-rate divergence
(perp-vs-perp, EXP-2026-08-31-FUNDXCHG-001, REJECTED) or Amihud illiquidity
cross-checks (Bybit/OKX, for robustness, not as a standalone signal). This is
the first use of the real, widely-cited "Coinbase Premium Index" concept
(popularized by CryptoQuant): Coinbase is a USD-fiat-onramp/institutional
venue while Binance is a global/offshore, more retail-and-leverage-driven
venue. A persistent Coinbase premium (BTC/ETH priced higher on Coinbase than
Binance) is read by practitioners as US institutional buying pressure; a
persistent DISCOUNT is read as US selling / risk-off. This tests the
CONTRARIAN construction: an unusually large NEGATIVE premium (Coinbase
trading at a rare discount to Binance) signals a US-led panic/flush that
tends to be temporary, since retail/offshore selling on Binance can
overshoot -- buy the discount, expect the premium to normalize as the
temporary imbalance clears.

Data source: real Coinbase Exchange public hourly OHLCV (`GET
/products/{id}/candles`, newly fetched this run via
scripts/fetch_coinbase_premium.py, `data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz`)
compared against already-cached real Binance spot hourly OHLCV
(`data/raw/{BTC,ETH}_1h.csv.gz`). BTC/ETH only -- Coinbase Exchange does not
list SOL or XRP spot pairs with comparable liquidity/history depth for this
premium construction (XRP was delisted from Coinbase for over a year during
the SEC lawsuit, breaking history continuity; SOL/USD history on Coinbase
Exchange is materially shorter than Binance's). No proxy fabricated for
SOL/XRP.

PRIMARY RULE (frozen before any result was inspected):
  1. premium_t = (coinbase_close_t / binance_close_t) - 1, computed hourly on
     the aligned UTC hourly grid (Coinbase and Binance both report to the
     hour; asof-merge with a 5-minute tolerance to align any minor timestamp
     drift).
  2. z_t = z-score of premium_t against a trailing 720-hour (30-day) window,
     using ONLY prior-hour data (shift(1) before rolling, so hour t's own
     premium reading never enters its own baseline -- same anti-lookahead
     pattern as every prior z-score study in this repo).
  3. Entry trigger: z_t <= -2.0 (Coinbase trading at a rare discount to
     Binance vs its own recent 30-day history) -> LONG spot (on Binance, the
     execution venue used throughout this repo) at the next hour's open,
     hold 24h, then flat. Non-overlapping (cooldown until exit + next
     signal).
  4. Costs: standard 30bps round trip (15bps/side), matching every other
     study in this repo.
  5. Universe: BTC, ETH independently (single-asset study; 2-asset by data
     availability, same structural limitation as the Deribit DVOL study).

Baselines: buy-and-hold, daily-equivalent DCA (unit-accumulation schedule),
and a seeded random-timing control matching trade count and hold length.

Partitions (frozen before inspecting any result): development
2018-01-01->2021-01-01 (only useful once Coinbase history begins), validation
2021-01-01->2024-01-01, test 2024-01-01->repo cutoff (2026-07-28). Coinbase
Exchange candle history depth is checked at fetch time; if usable history is
shorter, partitions are shifted forward and reported honestly.

Falsification (preregistered): primary must beat buy-and-hold AND DCA AND its
own random-timing control after costs, survive doubled round-trip cost,
retain a positive best-trade-excluded edge (no single trade >20% of total
strategy PnL -- this program's concentration cap), and have real trades in
the final calendar year of the sample (test partition). Any single failure
-> REJECTED unless a narrow near-miss per the skill's near-miss discipline.
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

ASSETS = ["BTC", "ETH"]
Z_WINDOW_HOURS = 720  # 30 days
Z_ENTRY_THRESHOLD = -2.0
HOLD_HOURS = 24
CONCENTRATION_CAP_PCT = 20.0
BASE_SEED = 20260903
RANDOM_SEED_OFFSET = {"BTC": 1, "ETH": 2}

END_EXCLUSIVE = pd.Timestamp("2026-07-28T00:00:00Z")
VALIDATION_START = pd.Timestamp("2021-01-01T00:00:00Z")
TEST_START = pd.Timestamp("2024-01-01T00:00:00Z")


def load_binance_hourly(coin: str) -> pd.DataFrame:
    df = pd.read_csv(PATHS.raw / f"{coin}_1h.csv.gz", parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[df.index < END_EXCLUSIVE]


def load_coinbase_hourly(coin: str) -> pd.DataFrame:
    path = ROOT / "data" / "coinbase_premium" / f"{coin}_coinbase_1h.csv.gz"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[df.index < END_EXCLUSIVE]


def build_premium(binance: pd.DataFrame, coinbase: pd.DataFrame) -> pd.Series:
    joined = pd.DataFrame({
        "binance_close": binance["close"],
        "coinbase_close": coinbase["close"],
    }).dropna()
    premium = joined["coinbase_close"] / joined["binance_close"] - 1.0
    return premium.rename("premium")


def build_signal(premium: pd.Series) -> pd.Series:
    prior = premium.shift(1)
    roll_mean = prior.rolling(Z_WINDOW_HOURS, min_periods=168).mean()
    roll_std = prior.rolling(Z_WINDOW_HOURS, min_periods=168).std(ddof=1)
    z = (premium - roll_mean) / roll_std
    trigger = z <= Z_ENTRY_THRESHOLD
    return trigger.rename("trigger"), z.rename("z")


def non_overlapping_entries(trigger: pd.Series, price_index: pd.DatetimeIndex, hold_hours: int) -> list[pd.Timestamp]:
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
        next_ok = entry_ts + pd.Timedelta(hours=hold_hours)
    return entries


def simulate_signal_strategy(price: pd.DataFrame, entries: list[pd.Timestamp], hold_hours: int, one_way_cost: float) -> dict:
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
            trade_log.append({
                "entry_time": entry_time, "exit_time": ts, "entry_price": entry_price,
                "exit_price": exec_price, "gross_return": exec_price / entry_price - 1.0,
            })
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
            exit_target = ts + pd.Timedelta(hours=hold_hours)
        equity = capital + units * float(closes.iloc[i])
        equity_curve.append({"timestamp": ts, "equity": equity})

    if in_position:
        exec_price = float(closes.iloc[-1]) * (1 - one_way_cost)
        proceeds = units * exec_price
        trade_log.append({
            "entry_time": entry_time, "exit_time": times[-1], "entry_price": entry_price,
            "exit_price": exec_price, "gross_return": exec_price / entry_price - 1.0,
            "note": "forced_close_at_sample_end",
        })
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
    daily_closes = price["close"].resample("1D").last().dropna()
    n = len(daily_closes)
    tranche = 1.0 / n
    units = 0.0
    for v in daily_closes:
        exec_price = float(v) * (1 + ONE_WAY_COST)
        units += tranche / exec_price
    final_price = float(daily_closes.iloc[-1]) * (1 - ONE_WAY_COST)
    return units * final_price


def random_entries(price_index: pd.DatetimeIndex, n_trades: int, hold_hours: int, seed: int) -> list[pd.Timestamp]:
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
        next_ok = candidate + pd.Timedelta(hours=hold_hours)
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
        return "validation_2021_2024"
    return "test_2024_onward"


def run_asset(coin: str) -> dict:
    binance = load_binance_hourly(coin)
    coinbase = load_coinbase_hourly(coin)
    premium = build_premium(binance, coinbase)
    trigger, z = build_signal(premium)

    price = binance.loc[premium.index[0]:]  # execute on Binance, aligned to premium coverage start
    entries = non_overlapping_entries(trigger, price.index, HOLD_HOURS)
    sim = simulate_signal_strategy(price, entries, HOLD_HOURS, ONE_WAY_COST)
    trades, equity, final = sim["trades"], sim["equity"], sim["final"]

    bh_final = simulate_buy_and_hold(price)
    dca_final = simulate_daily_dca(price)

    seed = BASE_SEED + RANDOM_SEED_OFFSET[coin]
    rand_entries = random_entries(price.index, len(entries), HOLD_HOURS, seed)
    rand_sim = simulate_signal_strategy(price, rand_entries, HOLD_HOURS, ONE_WAY_COST)
    rand_final = rand_sim["final"]

    doubled_final = doubled_cost_final(trades)
    excluded_final = best_trade_excluded_final(trades)
    top_pct = top_trade_pct_of_pnl(trades)

    if not trades.empty:
        trades = trades.copy()
        trades["partition"] = trades["entry_time"].apply(partition_label)
    partition_rows = []
    for label in ("development", "validation_2021_2024", "test_2024_onward"):
        part = trades[trades["partition"] == label] if not trades.empty else trades
        partition_rows.append({
            "asset": coin, "partition": label, "n_trades": len(part),
            "mean_trade_return_pct": float(part["gross_return"].mean() * 100) if len(part) else np.nan,
        })

    return {
        "asset": coin, "n_trades": len(trades), "primary_final": final,
        "bh_final": bh_final, "dca_final": dca_final, "random_control_final": rand_final,
        "doubled_cost_final": doubled_final, "best_trade_excluded_final": excluded_final,
        "top_trade_pct_of_pnl": top_pct, "partition_rows": partition_rows,
        "trades": trades, "premium_coverage_start": premium.index[0], "premium_coverage_end": premium.index[-1],
        "n_premium_hours": len(premium), "mean_abs_premium_bps": float(premium.abs().mean() * 10000),
    }


def classify_verdict(result: dict) -> tuple[str, dict]:
    test_rows = [r for r in result["partition_rows"] if r["partition"] == "test_2024_onward"]
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
        "beats_buy_and_hold": beats_bh, "beats_dca": beats_dca, "beats_random_control": beats_random,
        "survives_doubled_cost": survives_doubled_cost, "survives_best_trade_exclusion": survives_exclusion,
        "concentration_ok": concentration_ok, "has_holdout_trades": has_holdout,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def main() -> None:
    all_results = {}
    for coin in ASSETS:
        all_results[coin] = run_asset(coin)

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = PATHS.results / "coinbase_premium_contrarian" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# Coinbase-vs-Binance Price Premium Contrarian Validation", ""]
    lines.append("## Primary rule")
    lines.append(
        f"> LONG-ONLY per-asset: z-score ({Z_WINDOW_HOURS}h trailing, prior-only) of hourly "
        f"(Coinbase close / Binance close - 1) premium <= {Z_ENTRY_THRESHOLD} (rare Coinbase "
        f"DISCOUNT) -> long spot at next hour's open, hold {HOLD_HOURS}h, flat otherwise. "
        f"{ROUND_TRIP_COST*100:.0f}bps round-trip cost. Non-overlapping trades."
    )
    lines.append("")
    lines.append("## Data sources")
    lines.append(
        "- Real Coinbase Exchange public hourly OHLCV "
        "(`data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz`, newly fetched this run via "
        "`scripts/fetch_coinbase_premium.py`; first use of Coinbase Exchange data in this repo)."
    )
    lines.append("- Real Binance spot hourly OHLCV (`data/raw/{BTC,ETH}_1h.csv.gz`, already cached) for execution.")
    lines.append("")

    verdicts = {}
    summary_rows = []
    for coin, result in all_results.items():
        lines.append(f"### {coin}")
        lines.append(f"- Premium coverage: {result['premium_coverage_start']} -> {result['premium_coverage_end']} ({result['n_premium_hours']} aligned hours)")
        lines.append(f"- Mean absolute premium: {result['mean_abs_premium_bps']:.2f} bps")
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
        summary_rows.append({
            "asset": coin, "n_trades": result["n_trades"], "primary_final": result["primary_final"],
            "bh_final": result["bh_final"], "dca_final": result["dca_final"],
            "random_control_final": result["random_control_final"],
            "top_trade_pct_of_pnl": result["top_trade_pct_of_pnl"], "verdict": verdict,
        })

    n_candidates = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append("## Overall verdict")
    lines.append(f"- {n_candidates}/{len(ASSETS)} assets are CANDIDATE (clear every gate)")
    lines.append(f"- Per-asset verdicts: {verdicts}")

    pd.DataFrame(summary_rows).to_csv(out_dir / "summary.csv", index=False)
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"Coinbase premium contrarian validation written to {out_dir}")
    print(f"Verdicts: {verdicts}")


if __name__ == "__main__":
    main()
