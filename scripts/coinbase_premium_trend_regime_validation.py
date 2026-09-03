"""EXP-2026-09-03-CBPREMIUM-TREND-001: Coinbase-vs-Binance price premium, TREND-FOLLOWING regime.

Hypothesis (preregistered, genuinely new for this repo -- checked
docs/experiment_registry.md and docs/next_hypotheses.md in full before writing
this). The already-REJECTED Coinbase premium CONTRARIAN study
(EXP-2026-09-03-CBPREMIUM-001, docs/COINBASE_PREMIUM_CONTRARIAN_VALIDATION.md)
tested "buy a rare Coinbase DISCOUNT, expect mean reversion" and was rejected
decisively (both assets lost ~98-99% of capital, underperformed their own
random-timing control). That study's registry note explicitly named "the
mirror TREND-FOLLOWING construction -- persistent premium predicts
continuation, not reversion -- has not been tested" as the recommended
follow-up. This is that follow-up: a fundamentally different mechanism
(regime-following a SUSTAINED premium, not event-triggered mean-reversion off
a single-hour z-spike), reusing already-cached real Coinbase Exchange data
(no new data fetch, no proxy).

Economic mechanism under test: Coinbase is a USD-fiat-onramp/institutional
venue; a SUSTAINED (not momentary) positive premium reflects persistent US
institutional net buying pressure that should precede/accompany continued
upside, analogous to a slow structural regime filter (mirrors this program's
already-tested OI-trend and stablecoin-supply-trend regime constructions,
but applied to a genuinely new data field: cross-exchange spot premium).

PRIMARY RULE (frozen before any result was inspected):
  1. premium_t = (coinbase_close_t / binance_close_t) - 1, hourly, same
     construction as the contrarian study (asof-merge, 5-min tolerance).
  2. regime_t = rolling mean of premium over the trailing 24h window, using
     ONLY prior-hour data (shift(1) before rolling -- premium_t's own value
     never enters its own regime baseline, standard anti-lookahead pattern).
  3. Regime "on" (long) while regime_t > 0 (sustained positive premium =
     persistent Coinbase buying pressure); flat (cash) otherwise. Entries execute
     at the next hour's open, exits at the next hour's open after the
     regime flips off (matches this repo's existing regime-filter execution
     convention, e.g. OI_TREND_REGIME, STABLECOIN_SUPPLY_TREND).
  4. Costs: standard 30bps round trip (15bps/side) per regime block.
  5. Universe: BTC, ETH independently (2-asset by real data availability,
     same structural limitation as the contrarian study and Deribit DVOL).

Baselines: cash, buy-and-hold, daily DCA, a naive BTC-price-momentum regime
control (long only while trailing 30d BTC return > 0 -- the same control used
in this repo's OI-trend/stablecoin-trend/top-trader-trend regime studies,
applied per-asset here using each asset's OWN trailing 30d return since this
is a per-asset study, not BTC-conditioned), and a seeded random-regime control
(same number of blocks/total on-time, randomly placed).

Partitions (frozen before inspecting any result): development
2018-01-01->2021-01-01 (dev/pre-Coinbase-history-quality), validation
2021-01-01->2024-01-01, test 2024-01-01->repo cutoff (2026-07-28).

Falsification (preregistered): primary must beat cash AND buy-and-hold AND
the price-momentum regime control AND the random-regime control after costs,
survive doubled round-trip cost, retain a positive best-block-excluded edge
(no single regime block >20% of total strategy PnL -- this program's
concentration cap), and have real on-blocks in the test partition. Any single
failure -> REJECTED unless a narrow near-miss per the skill's near-miss
discipline (only if it clears concentration + walk-forward but fails
significance-style gates only).
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
REGIME_WINDOW_HOURS = 24
MOMENTUM_WINDOW_HOURS = 24 * 30  # 30 days, own-asset trailing return
CONCENTRATION_CAP_PCT = 20.0
BASE_SEED = 20260903
RANDOM_SEED_OFFSET = {"BTC": 11, "ETH": 12}

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


def build_regime(premium: pd.Series) -> pd.Series:
    prior = premium.shift(1)
    regime_mean = prior.rolling(REGIME_WINDOW_HOURS, min_periods=REGIME_WINDOW_HOURS).mean()
    on = regime_mean > 0
    return on.rename("regime_on")


def blocks_from_regime(on: pd.Series, price_index: pd.DatetimeIndex) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Convert a boolean regime series into (entry, exit) block timestamps,
    executed at the NEXT bar's open after a flip (prevents same-bar lookahead)."""
    on = on.reindex(price_index).fillna(False)
    flips = on.astype(int).diff().fillna(on.astype(int).iloc[0] if len(on) else 0)
    blocks = []
    in_block = False
    entry_ts = None
    for i in range(1, len(price_index)):
        ts = price_index[i]
        prev_on = bool(on.iloc[i - 1])
        cur_on = bool(on.iloc[i])
        if (not in_block) and cur_on:
            entry_ts = ts
            in_block = True
        elif in_block and (not cur_on):
            blocks.append((entry_ts, ts))
            in_block = False
    if in_block:
        blocks.append((entry_ts, price_index[-1]))
    return blocks


def simulate_blocks(price: pd.DataFrame, blocks: list[tuple[pd.Timestamp, pd.Timestamp]], one_way_cost: float) -> dict:
    opens = price["open"] if "open" in price.columns else price["close"]
    closes = price["close"]
    trade_log = []
    total_multiplier = 1.0
    for entry_ts, exit_ts in blocks:
        if entry_ts not in price.index or exit_ts not in price.index:
            continue
        entry_price = float(opens.loc[entry_ts]) * (1 + one_way_cost)
        exit_price = float(closes.loc[exit_ts]) * (1 - one_way_cost)
        gross_return = exit_price / entry_price - 1.0
        trade_log.append({
            "entry_time": entry_ts, "exit_time": exit_ts,
            "entry_price": entry_price, "exit_price": exit_price,
            "gross_return": gross_return,
        })
        total_multiplier *= (1 + gross_return)
    trades_df = pd.DataFrame(trade_log)
    return {"trades": trades_df, "final": total_multiplier}


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


def momentum_control_blocks(price: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    closes = price["close"]
    trailing_ret = closes.pct_change(MOMENTUM_WINDOW_HOURS).shift(1)
    on = (trailing_ret > 0).fillna(False)
    return blocks_from_regime(on, price.index)


def random_regime_blocks(price_index: pd.DatetimeIndex, n_blocks: int, total_on_hours: int, seed: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    rng = np.random.default_rng(seed)
    if n_blocks == 0 or total_on_hours == 0:
        return []
    n = len(price_index)
    avg_block_len = max(1, total_on_hours // n_blocks)
    blocks = []
    attempts = 0
    used = np.zeros(n, dtype=bool)
    while len(blocks) < n_blocks and attempts < n_blocks * 500:
        attempts += 1
        block_len = max(1, int(rng.normal(avg_block_len, avg_block_len * 0.3)))
        start_idx = int(rng.integers(0, max(1, n - block_len)))
        end_idx = min(n - 1, start_idx + block_len)
        if used[start_idx:end_idx + 1].any():
            continue
        used[start_idx:end_idx + 1] = True
        blocks.append((price_index[start_idx], price_index[end_idx]))
    blocks.sort()
    return blocks


def doubled_cost_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    extra_factor = 1 - 2 * ONE_WAY_COST
    capital = 1.0
    for r in trades["gross_return"]:
        capital *= (1 + r) * extra_factor
    return capital


def best_block_excluded_final(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 1.0
    idx_best = trades["gross_return"].abs().idxmax()
    capital = 1.0
    for i, r in trades["gross_return"].items():
        rr = 0.0 if i == idx_best else r
        capital *= 1 + rr
    return capital


def top_block_pct_of_pnl(trades: pd.DataFrame) -> float | None:
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
    regime_on = build_regime(premium)

    price = binance.loc[premium.index[0]:]
    blocks = blocks_from_regime(regime_on, price.index)
    sim = simulate_blocks(price, blocks, ONE_WAY_COST)
    trades, final = sim["trades"], sim["final"]

    bh_final = simulate_buy_and_hold(price)
    dca_final = simulate_daily_dca(price)

    mom_blocks = momentum_control_blocks(price)
    mom_sim = simulate_blocks(price, mom_blocks, ONE_WAY_COST)
    mom_final = mom_sim["final"]

    total_on_hours = int(sum((e[1] - e[0]).total_seconds() / 3600 for e in blocks))
    seed = BASE_SEED + RANDOM_SEED_OFFSET[coin]
    rand_blocks = random_regime_blocks(price.index, len(blocks), total_on_hours, seed)
    rand_sim = simulate_blocks(price, rand_blocks, ONE_WAY_COST)
    rand_final = rand_sim["final"]

    doubled_final = doubled_cost_final(trades)
    excluded_final = best_block_excluded_final(trades)
    top_pct = top_block_pct_of_pnl(trades)

    if not trades.empty:
        trades = trades.copy()
        trades["partition"] = trades["entry_time"].apply(partition_label)
    partition_rows = []
    for label in ("development", "validation_2021_2024", "test_2024_onward"):
        part = trades[trades["partition"] == label] if not trades.empty else trades
        partition_rows.append({
            "asset": coin, "partition": label, "n_blocks": len(part),
            "mean_block_return_pct": float(part["gross_return"].mean() * 100) if len(part) else np.nan,
        })

    return {
        "asset": coin, "n_blocks": len(trades), "primary_final": final,
        "bh_final": bh_final, "dca_final": dca_final,
        "momentum_control_final": mom_final, "random_control_final": rand_final,
        "doubled_cost_final": doubled_final, "best_block_excluded_final": excluded_final,
        "top_block_pct_of_pnl": top_pct, "partition_rows": partition_rows,
        "trades": trades, "premium_coverage_start": premium.index[0],
        "premium_coverage_end": premium.index[-1], "n_premium_hours": len(premium),
        "pct_time_on": 100.0 * total_on_hours / len(price) if len(price) else 0.0,
    }


def classify_verdict(result: dict) -> tuple[str, dict]:
    test_rows = [r for r in result["partition_rows"] if r["partition"] == "test_2024_onward"]
    has_holdout = bool(test_rows and test_rows[0]["n_blocks"] > 0)
    beats_cash = result["primary_final"] > 1.0
    beats_bh = result["primary_final"] > result["bh_final"]
    beats_dca = result["primary_final"] > result["dca_final"]
    beats_momentum = result["primary_final"] > result["momentum_control_final"]
    beats_random = result["primary_final"] > result["random_control_final"]
    survives_doubled_cost = result["doubled_cost_final"] > 1.0
    survives_exclusion = result["best_block_excluded_final"] > result["bh_final"]
    concentration_ok = (
        result["top_block_pct_of_pnl"] is None or abs(result["top_block_pct_of_pnl"]) < CONCENTRATION_CAP_PCT
    )
    gates = {
        "beats_cash": beats_cash, "beats_buy_and_hold": beats_bh, "beats_dca": beats_dca,
        "beats_momentum_control": beats_momentum, "beats_random_control": beats_random,
        "survives_doubled_cost": survives_doubled_cost, "survives_best_block_exclusion": survives_exclusion,
        "concentration_ok": concentration_ok, "has_holdout_blocks": has_holdout,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def main() -> None:
    all_results = {}
    for coin in ASSETS:
        all_results[coin] = run_asset(coin)

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = PATHS.results / "coinbase_premium_trend_regime" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# Coinbase-vs-Binance Price Premium TREND-FOLLOWING Regime Validation", ""]
    lines.append("## Primary rule")
    lines.append(
        f"> LONG-ONLY per-asset regime filter: 24h trailing mean (prior-only) of hourly "
        f"(Coinbase close / Binance close - 1) premium > 0 (sustained POSITIVE premium) "
        f"-> long spot, else cash. Entries/exits at next-bar open on regime flip. "
        f"{ROUND_TRIP_COST*100:.0f}bps round-trip cost per block."
    )
    lines.append("")
    lines.append("## Data sources")
    lines.append(
        "- Real Coinbase Exchange public hourly OHLCV "
        "(`data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz`, already cached from the prior "
        "contrarian study, no new fetch needed)."
    )
    lines.append("- Real Binance spot hourly OHLCV (`data/raw/{BTC,ETH}_1h.csv.gz`, already cached) for execution.")
    lines.append("")

    verdicts = {}
    summary_rows = []
    for coin, result in all_results.items():
        lines.append(f"### {coin}")
        lines.append(f"- Premium coverage: {result['premium_coverage_start']} -> {result['premium_coverage_end']} ({result['n_premium_hours']} aligned hours)")
        lines.append(f"- Regime on: {result['pct_time_on']:.1f}% of sample, {result['n_blocks']} blocks")
        lines.append(f"- Primary final (start=1.0): **{result['primary_final']:.4f}**")
        lines.append(f"- Cash final: **1.0000**")
        lines.append(f"- Buy-and-hold final: **{result['bh_final']:.4f}**")
        lines.append(f"- Daily DCA final: **{result['dca_final']:.4f}**")
        lines.append(f"- Momentum-control final: **{result['momentum_control_final']:.4f}**")
        lines.append(f"- Random-regime control final: **{result['random_control_final']:.4f}**")
        lines.append(f"- Doubled-cost final: **{result['doubled_cost_final']:.4f}**")
        lines.append(f"- Best-block-excluded final: **{result['best_block_excluded_final']:.4f}**")
        lines.append(f"- Top block % of PnL: {result['top_block_pct_of_pnl']}")
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
            "asset": coin, "n_blocks": result["n_blocks"], "primary_final": result["primary_final"],
            "bh_final": result["bh_final"], "dca_final": result["dca_final"],
            "momentum_control_final": result["momentum_control_final"],
            "random_control_final": result["random_control_final"],
            "top_block_pct_of_pnl": result["top_block_pct_of_pnl"], "verdict": verdict,
        })

    n_candidates = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append("## Overall verdict")
    lines.append(f"- {n_candidates}/{len(ASSETS)} assets are CANDIDATE (clear every gate)")
    lines.append(f"- Per-asset verdicts: {verdicts}")

    pd.DataFrame(summary_rows).to_csv(out_dir / "summary.csv", index=False)
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"Coinbase premium trend-regime validation written to {out_dir}")
    print(f"Verdicts: {verdicts}")


if __name__ == "__main__":
    main()
