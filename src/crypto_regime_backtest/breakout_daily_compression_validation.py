from __future__ import annotations

"""Volatility-compression filter on the daily 20-day-high/10-day-low breakout
system -- addresses next_hypotheses.md item #1 (rank 1: "Volatility
compression followed by accepted breakout"), which was previously tested only
on the 4h ATR/Bollinger-width breakout system (breakout_compression_validation.py,
REJECTED) and never on the DAILY 20-day-high/10-day-low system that was itself
just run through the full validation ladder and REJECTED on statistical
significance (EXP-2026-09-01-BREAKOUT20HIGH-001, docs/BREAKOUT_DAILY_20HIGH_VALIDATION.md).

Genuinely new test for this repo: same underlying daily breakout mechanism as
the just-completed full-validation-ladder study, but with a PREREGISTERED
prior-only ATR%/close volatility-compression filter gating entries -- distinct
timeframe (daily vs the already-rejected 4h compression study) and distinct
parent system (20d-high/10d-low breakout vs the already-rejected 4h
"acceptance rule" breakout). Economic mechanism: dealers/short-vol
participants may be forced to chase a move that persists beyond a compressed
inventory range, so breakouts preceded by unusually LOW realized volatility
should have a cleaner, more persistent continuation than breakouts occurring
during already-elevated volatility (noise).

PRIMARY RULE (frozen before inspecting any filtered results -- the unfiltered
parent's numbers are already known from EXP-2026-09-01-BREAKOUT20HIGH-001 and
are treated as the baseline to beat, not tuned against):
  1. Compute ATR(14) on daily bars (Wilder's method), normalize by close:
     atr_pct = ATR14 / close.
  2. Compute the trailing 252-day percentile rank of atr_pct as of the PRIOR
     completed bar only (`atr_pct.shift(1).rolling(252).apply(percentileofscore
     of the current shifted value within the window)`), i.e. the compression
     reading at the moment of the breakout signal uses no information from the
     breakout bar itself or any future bar.
  3. Entry: identical to the parent system (daily close > prior-only rolling
     20-day high) AND compression percentile <= 30 (bottom-30% realized-vol
     regime at the moment of breakout). Enter at the NEXT daily bar's open.
  4. Exit: identical to the parent system (first close < prior-only rolling
     10-day low). Exit at the NEXT daily bar's open. Non-overlapping trades.
  5. Costs: standard round-trip (30bps).
  6. Universe: BTC/ETH/SOL/XRP, full available Binance spot daily history
     (matches the parent study exactly).

Baseline for THIS study: the unfiltered parent breakout system (identical
entry/exit logic, no compression gate) -- the falsification criterion from
next_hypotheses.md item #1 is "no improvement in validation net return or
false-breakout rate" versus acceptance-without-compression.

Reuses the parent module's simulate_long_strategy / simulate_buy_and_hold /
simulate_daily_dca / simulate_random_control / walk_forward_split /
monte_carlo_permutation / deflated_sharpe_ratio / partition_label functions
verbatim (identical cost model, identical no-lookahead discipline) so the two
studies are directly comparable.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .breakout_daily_20high_validation import (
    CONCENTRATION_CAP_PCT,
    HOLDOUT_START,
    MC_TRIALS,
    RANDOM_SEED,
    ROUND_TRIP_COST,
    VALIDATION_START,
    deflated_sharpe_ratio,
    monte_carlo_permutation,
    partition_label,
    simulate_buy_and_hold,
    simulate_daily_dca,
    simulate_doubled_cost,
    simulate_long_strategy,
    simulate_random_control,
    top_trade_pct_of_pnl,
    walk_forward_split,
)
from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv

UNIVERSE = ("BTC", "ETH", "SOL", "XRP")
BREAKOUT_LOOKBACK_DAYS = 20
EXIT_LOOKBACK_DAYS = 10
ATR_WINDOW = 14
COMPRESSION_LOOKBACK_DAYS = 252
COMPRESSION_PERCENTILE_MAX = 30.0  # bottom-30% realized-vol regime required to fire
N_STRATEGY_VARIANTS = 97  # program's true search-size proxy: 96 (parent study) + 1 (this study)


@dataclass(frozen=True)
class StudyConfig:
    breakout_lookback_days: int = BREAKOUT_LOOKBACK_DAYS
    exit_lookback_days: int = EXIT_LOOKBACK_DAYS
    atr_window: int = ATR_WINDOW
    compression_lookback_days: int = COMPRESSION_LOOKBACK_DAYS
    compression_percentile_max: float = COMPRESSION_PERCENTILE_MAX
    initial_capital: float = STARTING_CAPITAL
    delay_bars: int = 0
    primary_rule: str = (
        "LONG-ONLY: identical to the plain daily 20d-high/10d-low breakout "
        "system, but entry additionally requires the prior-only trailing "
        "252-day percentile rank of ATR(14)/close to be <= 30 (compressed "
        "volatility regime) at the signal bar. Exit unchanged (10d-low "
        "break). 30bps round-trip cost."
    )


def wilder_atr(frame: pd.DataFrame, window: int) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Wilder's smoothing (equivalent to an EMA with alpha = 1/window)
    return tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def rolling_percentile_of_last(window_values: np.ndarray) -> float:
    """Percentile rank (0-100) of the LAST value in window_values among all
    values in window_values (inclusive) -- used with a pre-shifted series so
    'last value' here is the prior-only reading."""
    last = window_values[-1]
    return float((window_values <= last).mean() * 100.0)


def build_daily_signal(price_1d: pd.DataFrame, config: StudyConfig) -> pd.DataFrame:
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

    atr = wilder_atr(frame, config.atr_window)
    atr_pct = (atr / frame["close"]).shift(1)  # prior-only: reading as of bar t-1
    frame["atr_pct_prior"] = atr_pct
    frame["compression_percentile"] = (
        atr_pct.rolling(config.compression_lookback_days, min_periods=config.compression_lookback_days)
        .apply(rolling_percentile_of_last, raw=True)
    )

    frame["breakout_raw"] = frame["close"] > frame["rolling_high"]
    frame["compressed"] = frame["compression_percentile"] <= config.compression_percentile_max
    frame["breakout"] = frame["breakout_raw"] & frame["compressed"].fillna(False)
    frame["exit_break"] = frame["close"] < frame["rolling_low"]
    return frame.set_index("timestamp")


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    price_1d = load_ohlcv(paths, asset, "1d")
    frame = build_daily_signal(price_1d, config)
    frame["partition"] = [partition_label(ts) for ts in frame.index]

    # Filtered (compression-gated) primary rule
    equity, trades = simulate_long_strategy(frame, config, entry_column="breakout")
    equity["capital"] = equity["capital"].astype(float)

    # Unfiltered control: identical exit logic, entry = raw breakout (no compression gate)
    control_equity, control_trades = simulate_long_strategy(frame, config, entry_column="breakout_raw")

    bh = simulate_buy_and_hold(price_1d, config.initial_capital)
    dca = simulate_daily_dca(price_1d, config.initial_capital)

    from dataclasses import replace
    delayed_config = replace(config, delay_bars=1)
    delayed_equity, delayed_trades = simulate_long_strategy(frame, delayed_config, entry_column="breakout")

    final_capital = float(equity["capital"].iloc[-1])
    control_final = float(control_equity["capital"].iloc[-1])
    delayed_final = float(delayed_equity["capital"].iloc[-1]) if not delayed_equity.empty else config.initial_capital
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

    random_equity, random_trades = simulate_random_control(frame, config, len(trades), mean_hold_days)

    wf = walk_forward_split(trades)
    mc = monte_carlo_permutation(trades["trade_return"].dropna().to_numpy(), MC_TRIALS) if not trades.empty else {}
    bars_per_year = 365.25 / mean_hold_days if mean_hold_days > 0 else 365.25
    dsr = (
        deflated_sharpe_ratio(trades["trade_return"].dropna().to_numpy(), bars_per_year, N_STRATEGY_VARIANTS)
        if not trades.empty
        else {}
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
        "control_equity": control_equity,
        "control_trades": control_trades,
        "control_final": control_final,
        "bh": bh,
        "dca": dca,
        "delayed_final": delayed_final,
        "delayed_n_trades": len(delayed_trades),
        "doubled_final": doubled_final,
        "excluded_capital": excluded_capital,
        "top_trade_pct": top_trade_pct,
        "random_equity": random_equity,
        "random_trades": random_trades,
        "partition_rows": partition_rows,
        "mean_hold_days": mean_hold_days,
        "walk_forward": wf,
        "monte_carlo": mc,
        "dsr": dsr,
    }


def classify_verdict(result: dict, initial_capital: float) -> tuple[str, dict]:
    primary_final = float(result["equity"]["capital"].iloc[-1])
    bh_final = float(result["bh"].iloc[-1])
    dca_final = float(result["dca"].iloc[-1])
    random_final = (
        float(result["random_equity"]["capital"].iloc[-1])
        if not result["random_equity"].empty
        else initial_capital
    )
    control_final = result["control_final"]
    doubled_final = result["doubled_final"]
    delayed_final = result["delayed_final"]

    test_trades = [r for r in result["partition_rows"] if r["partition"] == "test_2025_onward"]
    has_holdout_trades = bool(test_trades and test_trades[0]["n_trades"] > 0)

    beats_cash = primary_final > initial_capital
    beats_bh = primary_final > bh_final
    beats_dca = primary_final > dca_final
    beats_random = primary_final > random_final
    beats_unfiltered_control = primary_final > control_final  # THE primary economic claim under test
    survives_doubled_cost = doubled_final > initial_capital
    survives_exclusion = result["excluded_capital"] > initial_capital
    survives_delay = delayed_final > initial_capital
    concentration_ok = (
        result["top_trade_pct"] is None or abs(result["top_trade_pct"]) < CONCENTRATION_CAP_PCT
    )
    dsr_passes = bool(result["dsr"].get("passes_at_0.05")) if result["dsr"] else False
    mc_significant = bool(
        result["monte_carlo"].get("p_value") is not None and result["monte_carlo"]["p_value"] < 0.05
    )

    gates = {
        "beats_cash": beats_cash,
        "beats_bh": beats_bh,
        "beats_dca": beats_dca,
        "beats_random_control": beats_random,
        "beats_unfiltered_control": beats_unfiltered_control,
        "survives_doubled_cost": survives_doubled_cost,
        "survives_best_trade_exclusion": survives_exclusion,
        "survives_1bar_delay": survives_delay,
        "concentration_ok": concentration_ok,
        "has_holdout_trades": has_holdout_trades,
        "monte_carlo_significant": mc_significant,
        "deflated_sharpe_passes": dsr_passes,
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
    lines = ["# Daily 20-Day-High Breakout + ATR Compression Filter -- Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {config.primary_rule}")
    lines.append("")
    lines.append("## Data sources")
    lines.append("- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`). No synthetic data.")
    lines.append("")
    lines.append("## Per-asset results")
    verdicts = {}
    for asset, result in all_results.items():
        lines.append(f"### {asset}")
        lines.append(f"- Trades: **{len(result['trades'])}** (mean hold {result['mean_hold_days']:.1f}d)")
        primary_final = float(result["equity"]["capital"].iloc[-1])
        bh_final = float(result["bh"].iloc[-1])
        dca_final = float(result["dca"].iloc[-1])
        random_final = (
            float(result["random_equity"]["capital"].iloc[-1])
            if not result["random_equity"].empty
            else config.initial_capital
        )
        lines.append(f"- Compression-filtered primary final: **${primary_final:,.2f}** (start ${config.initial_capital:,.0f})")
        lines.append(f"- Unfiltered-breakout control final: **${result['control_final']:,.2f}** ({len(result['control_trades'])} trades)")
        lines.append(f"- Buy-and-hold final: **${bh_final:,.2f}**")
        lines.append(f"- Daily DCA final: **${dca_final:,.2f}**")
        lines.append(f"- Seeded random-timing control final: **${random_final:,.2f}** ({len(result['random_trades'])} trades)")
        lines.append(f"- Doubled-cost final: **${result['doubled_final']:,.2f}**")
        lines.append(f"- 1-bar delayed-execution final: **${result['delayed_final']:,.2f}** ({result['delayed_n_trades']} trades)")
        lines.append(f"- Best-trade-exclusion final: **${result['excluded_capital']:,.2f}**")
        lines.append(f"- Top single-trade % of total PnL: **{result['top_trade_pct']}**")
        lines.append(f"- Walk-forward split: {result['walk_forward']}")
        lines.append(f"- Monte Carlo bootstrap-null test: {result['monte_carlo']}")
        lines.append(f"- Deflated Sharpe (n_trials={N_STRATEGY_VARIANTS}): {result['dsr']}")
        verdict, gates = classify_verdict(result, config.initial_capital)
        verdicts[asset] = verdict
        lines.append(f"- Gates: {gates}")
        lines.append(f"- Verdict: **{verdict}**")
        lines.append("")
        lines.append("Partition breakdown:")
        lines.append(dataframe_to_markdown(pd.DataFrame(result["partition_rows"])))
        lines.append("")
    lines.append("## Overall verdict")
    n_candidate = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared every gate.")
    if n_candidate == 0:
        lines.append("\n**REJECTED** -- no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**CANDIDATE** -- every asset cleared every gate, including beating the unfiltered control, Monte Carlo, and Deflated Sharpe.")
    else:
        lines.append(f"\n**MIXED** -- {n_candidate}/{len(verdicts)} assets cleared every gate.")
    output.write_text("\n".join(lines))


def main() -> None:
    paths = Paths(root=Path(__file__).resolve().parents[2])
    config = StudyConfig()
    all_results = {}
    for asset in UNIVERSE:
        all_results[asset] = run_asset_study(paths, asset, config)

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = paths.results / "breakout_daily_compression" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    combined_trades = []
    for asset, result in all_results.items():
        t = result["trades"].copy()
        t["asset"] = asset
        combined_trades.append(t)
        verdict, gates = classify_verdict(result, config.initial_capital)
        with open(out_dir / f"{asset}_gates.json", "w") as f:
            json.dump({"verdict": verdict, "gates": gates}, f, indent=2, default=str)
    pd.concat(combined_trades, ignore_index=True).to_csv(out_dir / "trades.csv", index=False)

    write_report(out_dir / "REPORT.md", all_results, config)
    print(f"Report written to {out_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
