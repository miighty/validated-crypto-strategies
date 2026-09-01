from __future__ import annotations

"""OI-confirmed daily breakout continuation (long-only, single-asset).

Genuinely new mechanism for this repo, combining real open-interest data
(first used long-side here; previously only used short-side in
crowded_perp_unwind_validation.py) with a structural price breakout on the
DAILY timeframe -- distinct from every prior breakout/trend study:
  - breakout_compression_validation.py: 4h timeframe, ATR/Bollinger-width
    compression filter, no OI, REJECTED.
  - sma_trend_following_validation.py: SMA(200) filter, no breakout
    structure, no OI, REJECTED (concentration artifact).
  - crowded_perp_unwind_validation.py: OI used SHORT-side (funding+OI
    extreme + downside break), fixed 48h hold, REJECTED (zero holdout
    trades).

Economic rationale: a price breakout above a recent range accompanied by
RISING open interest indicates genuinely fresh leveraged demand entering
the market (not short-covering or thin-liquidity noise), which should be
more likely to persist than an unconfirmed breakout. This is next_hypotheses
item #1's OI-confirmation analogue -- item #1 proposed an ATR/Bollinger-width
compression filter; this tests OI confirmation instead, a fundamentally
different (participation-based, not volatility-based) filter mechanism.

PRIMARY RULE (frozen before this run inspected any confirmed-breakout
results):
  1. Breakout: daily close > rolling 20-day high computed on the PRIOR 20
     completed daily closes (shift(1), no lookahead -- today's close is
     compared against days t-20..t-1, never including today).
  2. OI confirmation: most recent completed daily open-interest snapshot is
     >= +5% higher than the snapshot 5 days earlier (identical threshold to
     the already-tested crowded_perp_unwind study, so the OI-rise definition
     itself is not being re-tuned here).
  3. Joint signal: both (1) and (2) true on the same completed daily bar.
     Enter long at the NEXT daily bar's open.
  4. Exit (structural trailing stop, distinct from the short study's fixed
     hold): first daily close that falls below the rolling 10-day low
     computed on the PRIOR 10 completed closes (shift(1), no lookahead).
     Exit at the NEXT daily bar's open. Flat between exit and the next
     qualifying entry (non-overlapping trades).
  5. Costs: standard round-trip (2 x ONE_WAY_COST = 30bps) on entry/exit
     notional.

Baselines: cash, buy-and-hold, daily DCA, "unconfirmed breakout" control
(condition 1 alone -- same 20-day-high entry / 10-day-low exit, no OI
filter), and a seeded random-entry-timing control matching the primary
rule's trade count and mean holding period.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv
from .open_interest_data import load_oi

UNIVERSE = ("BTC", "ETH", "SOL", "XRP")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")

BREAKOUT_LOOKBACK_DAYS = 20
EXIT_LOOKBACK_DAYS = 10
OI_LOOKBACK_DAYS = 5
OI_RISE_THRESHOLD = 0.05  # +5% over 5 days, same as crowded_perp_unwind study
ROUND_TRIP_COST = 2 * ONE_WAY_COST
CONCENTRATION_CAP_PCT = 20.0

RANDOM_SEED = 20260901


@dataclass(frozen=True)
class StudyConfig:
    breakout_lookback_days: int = BREAKOUT_LOOKBACK_DAYS
    exit_lookback_days: int = EXIT_LOOKBACK_DAYS
    oi_lookback_days: int = OI_LOOKBACK_DAYS
    oi_rise_threshold: float = OI_RISE_THRESHOLD
    initial_capital: float = STARTING_CAPITAL
    primary_rule: str = (
        "LONG-ONLY: enter at next daily open when (a) close breaks above the "
        "trailing prior-only 20-day high AND (b) most recent completed daily "
        "open interest is >= +5% higher than 5 days earlier. Exit at next "
        "daily open on the first close below the trailing prior-only 10-day "
        "low. Flat otherwise, non-overlapping trades. 30bps round-trip cost."
    )


def build_oi_condition(oi: pd.DataFrame, lookback_days: int, threshold: float) -> pd.Series:
    frame = oi.copy().reset_index()
    frame = frame.dropna(subset=["sum_open_interest"])
    frame["oi_pct_change"] = frame["sum_open_interest"].pct_change(lookback_days)
    frame["condition"] = frame["oi_pct_change"] >= threshold
    return frame.set_index("timestamp")["condition"]


def build_daily_signal(price_1d: pd.DataFrame, oi_condition: pd.Series, config: StudyConfig) -> pd.DataFrame:
    frame = price_1d.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "timestamp"})
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    frame["rolling_high"] = frame["close"].shift(1).rolling(
        config.breakout_lookback_days, min_periods=config.breakout_lookback_days
    ).max()
    frame["rolling_low"] = frame["close"].shift(1).rolling(
        config.exit_lookback_days, min_periods=config.exit_lookback_days
    ).min()
    frame["breakout"] = frame["close"] > frame["rolling_high"]
    frame["exit_break"] = frame["close"] < frame["rolling_low"]

    oi_series = oi_condition.sort_index()
    oi_known_from = oi_series.copy()
    oi_known_from.index = oi_known_from.index + pd.Timedelta(days=1)
    oi_asof = oi_known_from.reindex(
        oi_known_from.index.union(frame["timestamp"])
    ).sort_index().ffill().reindex(frame["timestamp"]).to_numpy()
    frame["oi_rising"] = pd.Series(oi_asof, index=frame.index).fillna(False).astype(bool)

    frame["joint_signal"] = frame["breakout"] & frame["oi_rising"]
    return frame.set_index("timestamp")


def simulate_long_strategy(
    frame: pd.DataFrame,
    config: StudyConfig,
    entry_column: str = "joint_signal",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    capital = config.initial_capital
    equity_rows = []
    trade_rows = []
    in_position = False
    entry_index = None
    entry_price = None
    entry_time = None
    entry_capital = None

    timestamps = frame.index.to_list()
    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    entries = frame[entry_column].to_numpy()
    exit_breaks = frame["exit_break"].to_numpy()

    for i, ts in enumerate(timestamps):
        if in_position and bool(exit_breaks[i]) and i > entry_index:
            exit_price = opens[i]
            gross_return = (exit_price - entry_price) / entry_price
            capital *= (1 + gross_return)
            capital *= (1 - ONE_WAY_COST)
            trade_rows.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "gross_return": gross_return,
                    "capital_at_entry": entry_capital,
                    "capital_at_exit": capital,
                    "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                }
            )
            in_position = False
            entry_index = None
            entry_price = None
            entry_time = None
            entry_capital = None

        if not in_position and bool(entries[i]) and i + 1 < len(timestamps):
            entry_price = opens[i]
            capital *= (1 - ONE_WAY_COST)
            entry_capital = capital
            entry_index = i
            entry_time = ts
            in_position = True

        equity_rows.append({"timestamp": ts, "capital": capital, "in_position": in_position})

    if in_position:
        exit_price = closes[-1]
        gross_return = (exit_price - entry_price) / entry_price
        capital *= (1 + gross_return)
        capital *= (1 - ONE_WAY_COST)
        trade_rows.append(
            {
                "entry_time": entry_time,
                "exit_time": timestamps[-1],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_return": gross_return,
                "capital_at_entry": entry_capital,
                "capital_at_exit": capital,
                "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                "note": "forced_close_at_sample_end",
            }
        )
        equity_rows[-1]["capital"] = capital

    equity = pd.DataFrame(equity_rows).set_index("timestamp")
    trades = pd.DataFrame(trade_rows)
    return equity, trades


def simulate_buy_and_hold(price: pd.DataFrame, initial_capital: float) -> pd.Series:
    entry_price = float(price["open"].iloc[0]) * (1 + ONE_WAY_COST)
    units = initial_capital / entry_price
    return (units * price["close"]).rename("capital")


def simulate_daily_dca(price: pd.DataFrame, initial_capital: float) -> pd.Series:
    tranche = initial_capital / len(price)
    units = 0.0
    rows = []
    for _, row in price.iterrows():
        execution_price = float(row["open"]) * (1 + ONE_WAY_COST)
        units += tranche / execution_price
        rows.append(units * float(row["close"]))
    return pd.Series(rows, index=price.index, name="capital")


def simulate_random_control(
    frame: pd.DataFrame,
    config: StudyConfig,
    n_trades: int,
    mean_hold_days: int,
    seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Seeded random long-entry timing, matched trade count and mean hold length."""
    rng = np.random.default_rng(seed)
    n = len(frame)
    hold = max(1, int(round(mean_hold_days)))
    if n_trades == 0 or n < hold + 2:
        return pd.DataFrame(), pd.DataFrame()
    max_start = n - hold - 1
    if max_start <= 0:
        return pd.DataFrame(), pd.DataFrame()
    candidate_starts = rng.choice(
        np.arange(max_start), size=min(n_trades * 5, max_start), replace=False
    )
    candidate_starts.sort()
    chosen = []
    last_end = -10**9
    for s in candidate_starts:
        if s - last_end >= hold:
            chosen.append(s)
            last_end = s + hold
        if len(chosen) >= n_trades:
            break
    entries = np.zeros(n, dtype=bool)
    exit_breaks = np.zeros(n, dtype=bool)
    for s in chosen:
        entries[s] = True
        exit_idx = min(s + hold, n - 1)
        exit_breaks[exit_idx] = True
    fake_frame = frame.copy()
    fake_frame["joint_signal"] = entries
    fake_frame["exit_break"] = exit_breaks
    return simulate_long_strategy(fake_frame, config, entry_column="joint_signal")


def max_drawdown(capital: pd.Series) -> float:
    running_max = capital.cummax()
    drawdown = (capital - running_max) / running_max
    return float(drawdown.min())


def partition_label(ts: pd.Timestamp) -> str:
    if ts < VALIDATION_START:
        return "development_pre_2024"
    if ts < HOLDOUT_START:
        return "validation_2024"
    return "test_2025_onward"


def top_trade_pct_of_pnl(trades: pd.DataFrame, initial_capital: float, final_capital: float) -> float | None:
    if trades.empty:
        return None
    total_pnl = final_capital - initial_capital
    if total_pnl == 0:
        return None
    best_idx = trades["trade_return"].abs().idxmax()
    best_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
    return float(best_pnl / total_pnl) * 100


def simulate_doubled_cost(trades: pd.DataFrame, initial_capital: float) -> float:
    if trades.empty:
        return initial_capital
    extra_cost_factor = (1 - 2 * ONE_WAY_COST)
    capital = initial_capital
    for _, row in trades.iterrows():
        capital *= (1 + row["trade_return"]) * extra_cost_factor
    return capital


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    price_1d = load_ohlcv(paths, asset, "1d")
    oi = load_oi(paths, asset)
    oi_condition = build_oi_condition(oi, config.oi_lookback_days, config.oi_rise_threshold)

    oi_start = oi.index.min()
    price_window = price_1d.loc[price_1d.index >= oi_start]
    if price_window.empty:
        raise RuntimeError(f"{asset}: no price data after OI coverage start {oi_start}")

    frame = build_daily_signal(price_window, oi_condition, config)
    frame["partition"] = [partition_label(ts) for ts in frame.index]

    equity, trades = simulate_long_strategy(frame, config, entry_column="joint_signal")
    equity["capital"] = equity["capital"].astype(float)

    bh = simulate_buy_and_hold(price_window, config.initial_capital)
    dca = simulate_daily_dca(price_window, config.initial_capital)

    # unconfirmed breakout control: condition (1) alone, no OI filter
    unconfirmed_frame = frame.copy()
    unconfirmed_frame["unconfirmed_signal"] = unconfirmed_frame["breakout"]
    unconfirmed_equity, unconfirmed_trades = simulate_long_strategy(
        unconfirmed_frame, config, entry_column="unconfirmed_signal"
    )

    final_capital = float(equity["capital"].iloc[-1])
    doubled_final = simulate_doubled_cost(trades, config.initial_capital)

    if not trades.empty:
        best_idx = trades["trade_return"].abs().idxmax()
        excluded_capital = config.initial_capital
        for i, row in trades.iterrows():
            r = row["trade_return"] if i != best_idx else 0.0
            excluded_capital *= (1 + r)
    else:
        excluded_capital = final_capital
    top_trade_pct = top_trade_pct_of_pnl(trades, config.initial_capital, final_capital)

    mean_hold_days = 5.0
    if not trades.empty:
        holds = [(row["exit_time"] - row["entry_time"]).days for _, row in trades.iterrows()]
        mean_hold_days = float(np.mean(holds)) if holds else 5.0

    random_equity, random_trades = simulate_random_control(
        frame, config, len(trades), mean_hold_days
    )

    partition_rows = []
    for label in ("development_pre_2024", "validation_2024", "test_2025_onward"):
        part_trades = (
            trades[trades["entry_time"].apply(lambda t: partition_label(t) == label)]
            if not trades.empty
            else trades
        )
        partition_rows.append(
            {
                "asset": asset,
                "partition": label,
                "n_trades": len(part_trades),
                "mean_trade_return_pct": (
                    float(part_trades["trade_return"].mean() * 100) if len(part_trades) else np.nan
                ),
            }
        )

    return {
        "asset": asset,
        "frame": frame,
        "equity": equity,
        "trades": trades,
        "bh": bh,
        "dca": dca,
        "unconfirmed_equity": unconfirmed_equity,
        "unconfirmed_trades": unconfirmed_trades,
        "doubled_final": doubled_final,
        "excluded_capital": excluded_capital,
        "top_trade_pct": top_trade_pct,
        "random_equity": random_equity,
        "random_trades": random_trades,
        "partition_rows": partition_rows,
        "oi_start": oi_start,
        "mean_hold_days": mean_hold_days,
    }


def classify_verdict(result: dict, initial_capital: float) -> tuple[str, dict]:
    primary_final = float(result["equity"]["capital"].iloc[-1])
    bh_final = float(result["bh"].iloc[-1])
    dca_final = float(result["dca"].iloc[-1])
    unconfirmed_final = (
        float(result["unconfirmed_equity"]["capital"].iloc[-1])
        if not result["unconfirmed_equity"].empty
        else initial_capital
    )
    random_final = (
        float(result["random_equity"]["capital"].iloc[-1])
        if not result["random_equity"].empty
        else initial_capital
    )
    doubled_final = result["doubled_final"]

    test_trades = [r for r in result["partition_rows"] if r["partition"] == "test_2025_onward"]
    has_holdout_trades = bool(test_trades and test_trades[0]["n_trades"] > 0)

    beats_cash = primary_final > initial_capital
    beats_bh = primary_final > bh_final
    beats_dca = primary_final > dca_final
    beats_unconfirmed = primary_final > unconfirmed_final
    beats_random = primary_final > random_final
    survives_doubled_cost = doubled_final > initial_capital
    survives_exclusion = result["excluded_capital"] > initial_capital
    concentration_ok = (
        result["top_trade_pct"] is None or abs(result["top_trade_pct"]) < CONCENTRATION_CAP_PCT
    )

    gates = {
        "beats_cash": beats_cash,
        "beats_bh": beats_bh,
        "beats_dca": beats_dca,
        "beats_unconfirmed_breakout_control": beats_unconfirmed,
        "beats_random_control": beats_random,
        "survives_doubled_cost": survives_doubled_cost,
        "survives_best_trade_exclusion": survives_exclusion,
        "concentration_ok": concentration_ok,
        "has_holdout_trades": has_holdout_trades,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_(no rows)_\n"
    formatted = frame.copy()
    for col in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[col]):
            formatted[col] = formatted[col].map(lambda v: f"{v:.4f}" if pd.notna(v) else "")
    header = "| " + " | ".join(str(c) for c in formatted.columns) + " |"
    sep = "| " + " | ".join("---" for _ in formatted.columns) + " |"
    body_lines = [
        "| " + " | ".join(str(v) for v in row) + " |" for row in formatted.itertuples(index=False)
    ]
    return "\n".join([header, sep, *body_lines])


def write_report(output: Path, all_results: dict, config: StudyConfig) -> None:
    lines = ["# OI-Confirmed Daily Breakout Continuation (Long-Only) Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {config.primary_rule}")
    lines.append("")
    lines.append("## Data sources")
    lines.append("- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`).")
    lines.append(
        "- Real Binance USD-M futures open interest (already cached this program, "
        "`data/open_interest/*_oi_daily.csv.gz`, fetched from the public "
        "`data.binance.vision` daily-metrics archive). No synthetic/proxy OI used."
    )
    lines.append("")
    lines.append("## Per-asset results")
    for asset, result in all_results.items():
        lines.append(f"### {asset}")
        lines.append(f"- OI data starts: **{result['oi_start'].date()}** (real archive coverage limit)")
        lines.append(f"- Trades: **{len(result['trades'])}** (mean hold {result['mean_hold_days']:.1f}d)")
        primary_final = float(result["equity"]["capital"].iloc[-1])
        bh_final = float(result["bh"].iloc[-1])
        dca_final = float(result["dca"].iloc[-1])
        unconfirmed_final = (
            float(result["unconfirmed_equity"]["capital"].iloc[-1])
            if not result["unconfirmed_equity"].empty
            else config.initial_capital
        )
        random_final = (
            float(result["random_equity"]["capital"].iloc[-1])
            if not result["random_equity"].empty
            else config.initial_capital
        )
        lines.append(f"- Primary final capital: **${primary_final:,.2f}** (start ${config.initial_capital:,.0f})")
        lines.append(f"- Buy-and-hold final: **${bh_final:,.2f}**")
        lines.append(f"- Daily DCA final: **${dca_final:,.2f}**")
        lines.append(
            f"- Unconfirmed-breakout control (no OI filter) final: **${unconfirmed_final:,.2f}** "
            f"({len(result['unconfirmed_trades'])} trades)"
        )
        lines.append(f"- Seeded random-timing control final: **${random_final:,.2f}** ({len(result['random_trades'])} trades)")
        lines.append(f"- Doubled-cost final: **${result['doubled_final']:,.2f}**")
        lines.append(f"- Best-trade-exclusion final: **${result['excluded_capital']:,.2f}**")
        lines.append(f"- Top single-trade % of total PnL: **{result['top_trade_pct']}**")
        verdict, gates = classify_verdict(result, config.initial_capital)
        lines.append(f"- Gates: {gates}")
        lines.append(f"- Verdict: **{verdict}**")
        lines.append("")
        lines.append("Partition breakdown:")
        lines.append(dataframe_to_markdown(pd.DataFrame(result["partition_rows"])))
        lines.append("")
    lines.append("## Overall verdict")
    verdicts = {asset: classify_verdict(result, config.initial_capital)[0] for asset, result in all_results.items()}
    n_candidate = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared every gate.")
    if n_candidate == 0:
        lines.append("\n**REJECTED** -- no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**PROMISING** -- every asset cleared every gate; still subject to further robustness scrutiny.")
    else:
        lines.append("\n**PROMISING BUT INCONCLUSIVE** -- mixed results across assets.")
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


def run_oi_breakout_confirmation_validation(paths: Paths) -> dict:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "oi_breakout_confirmation" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)

    config = StudyConfig()
    all_results = {}
    for asset in UNIVERSE:
        result = run_asset_study(paths, asset, config)
        all_results[asset] = result
        print(
            f"{asset}: {len(result['trades'])} trades, final capital "
            f"${float(result['equity']['capital'].iloc[-1]):,.2f}"
        )

    write_report(output, all_results, config)

    trades_frame = (
        pd.concat(
            [r["trades"].assign(asset=asset) for asset, r in all_results.items() if not r["trades"].empty],
            ignore_index=True,
        )
        if any(not r["trades"].empty for r in all_results.values())
        else pd.DataFrame()
    )
    trades_frame.to_csv(output / "trades.csv", index=False)

    partition_frame = pd.concat([pd.DataFrame(r["partition_rows"]) for r in all_results.values()], ignore_index=True)
    partition_frame.to_csv(output / "partition_summary.csv", index=False)

    manifest = {
        "config": config.__dict__,
        "universe": UNIVERSE,
        "verdicts": {asset: classify_verdict(r, config.initial_capital)[0] for asset, r in all_results.items()},
        "gates": {asset: classify_verdict(r, config.initial_capital)[1] for asset, r in all_results.items()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")

    print(f"Report written to {output / 'REPORT.md'}")
    return {"output": output, "all_results": all_results, "config": config}


if __name__ == "__main__":
    from .config import project_root

    run_oi_breakout_confirmation_validation(Paths(project_root()))
