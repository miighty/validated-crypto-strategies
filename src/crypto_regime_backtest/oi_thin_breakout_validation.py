from __future__ import annotations

"""OI-THIN breakout continuation (long-only, single-asset) -- follow-up to
the REJECTED OI-rising confirmation study (oi_breakout_confirmation_validation.py,
EXP-2026-09-01-OIBREAKOUT-001).

That study's registry note explicitly recommended: "if OI is revisited
long-side, try the opposite construction (OI falling into a breakout, i.e.
thin positioning with room to add)." This module implements exactly that
follow-up -- genuinely new filter direction, same breakout/exit structure,
same universe, same costs, so this is an apples-to-apples mechanism swap,
not a re-tune of the rejected threshold.

PRIMARY RULE (frozen before this run inspected any thin-OI-confirmed
breakout results):
  1. Breakout: daily close > rolling 20-day high computed on the PRIOR 20
     completed daily closes (shift(1), no lookahead) -- identical to the
     rejected study.
  2. OI-thin confirmation: most recent completed daily open-interest
     snapshot is <= -5% lower than the snapshot 5 days earlier (mirror-image
     threshold of the rejected study's +5% rise trigger -- same magnitude,
     opposite sign, not re-tuned).
  3. Joint signal: both (1) and (2) true on the same completed daily bar.
     Enter long at the NEXT daily bar's open.
  4. Exit: first daily close that falls below the rolling 10-day low
     computed on the PRIOR 10 completed closes (shift(1), no lookahead),
     identical exit rule to the rejected study. Exit at the NEXT daily
     bar's open. Flat between exit and next qualifying entry
     (non-overlapping trades).
  5. Costs: standard round-trip (2 x ONE_WAY_COST = 30bps).

Baselines: cash, buy-and-hold, daily DCA, unconfirmed-breakout control
(condition 1 alone), the OI-RISING confirmed variant from the rejected
study (for direct comparison), and a seeded random-entry-timing control
matching the primary rule's trade count and mean holding period.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Paths
from .data import load_ohlcv
from .open_interest_data import load_oi
from .oi_breakout_confirmation_validation import (
    UNIVERSE,
    StudyConfig,
    build_daily_signal,
    classify_verdict,
    dataframe_to_markdown,
    max_drawdown,
    partition_label,
    simulate_buy_and_hold,
    simulate_daily_dca,
    simulate_doubled_cost,
    simulate_long_strategy,
    simulate_random_control,
    top_trade_pct_of_pnl,
)

OI_FALL_THRESHOLD = -0.05  # mirror image of the rejected study's +5% rise trigger


def build_oi_thin_condition(oi: pd.DataFrame, lookback_days: int, threshold: float) -> pd.Series:
    """threshold is negative; condition is pct_change <= threshold (OI falling)."""
    frame = oi.copy().reset_index()
    frame = frame.dropna(subset=["sum_open_interest"])
    frame["oi_pct_change"] = frame["sum_open_interest"].pct_change(lookback_days)
    frame["condition"] = frame["oi_pct_change"] <= threshold
    return frame.set_index("timestamp")["condition"]


def build_daily_signal_thin(price_1d: pd.DataFrame, oi_condition: pd.Series, config: StudyConfig) -> pd.DataFrame:
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
    frame["oi_thin"] = pd.Series(oi_asof, index=frame.index).fillna(False).astype(bool)

    frame["joint_signal"] = frame["breakout"] & frame["oi_thin"]
    return frame.set_index("timestamp")


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    price_1d = load_ohlcv(paths, asset, "1d")
    oi = load_oi(paths, asset)
    oi_thin_condition = build_oi_thin_condition(oi, config.oi_lookback_days, OI_FALL_THRESHOLD)
    oi_rise_condition_import = __import__(
        "crypto_regime_backtest.oi_breakout_confirmation_validation", fromlist=["build_oi_condition"]
    ).build_oi_condition(oi, config.oi_lookback_days, config.oi_rise_threshold)

    oi_start = oi.index.min()
    price_window = price_1d.loc[price_1d.index >= oi_start]
    if price_window.empty:
        raise RuntimeError(f"{asset}: no price data after OI coverage start {oi_start}")

    frame = build_daily_signal_thin(price_window, oi_thin_condition, config)
    frame["partition"] = [partition_label(ts) for ts in frame.index]

    equity, trades = simulate_long_strategy(frame, config, entry_column="joint_signal")
    equity["capital"] = equity["capital"].astype(float)

    bh = simulate_buy_and_hold(price_window, config.initial_capital)
    dca = simulate_daily_dca(price_window, config.initial_capital)

    # unconfirmed breakout control: breakout alone, no OI filter
    unconfirmed_frame = frame.copy()
    unconfirmed_frame["unconfirmed_signal"] = unconfirmed_frame["breakout"]
    unconfirmed_equity, unconfirmed_trades = simulate_long_strategy(
        unconfirmed_frame, config, entry_column="unconfirmed_signal"
    )

    # OI-rising control: the already-rejected study's variant, for direct comparison
    rising_frame = build_daily_signal(price_window, oi_rise_condition_import, config)
    rising_frame["rising_signal"] = rising_frame["joint_signal"]
    rising_equity, rising_trades = simulate_long_strategy(
        rising_frame, config, entry_column="rising_signal"
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
        "rising_equity": rising_equity,
        "rising_trades": rising_trades,
        "doubled_final": doubled_final,
        "excluded_capital": excluded_capital,
        "top_trade_pct": top_trade_pct,
        "random_equity": random_equity,
        "random_trades": random_trades,
        "partition_rows": partition_rows,
        "oi_start": oi_start,
        "mean_hold_days": mean_hold_days,
    }


def classify_verdict_thin(result: dict, initial_capital: float) -> tuple[str, dict]:
    primary_final = float(result["equity"]["capital"].iloc[-1])
    bh_final = float(result["bh"].iloc[-1])
    dca_final = float(result["dca"].iloc[-1])
    unconfirmed_final = (
        float(result["unconfirmed_equity"]["capital"].iloc[-1])
        if not result["unconfirmed_equity"].empty
        else initial_capital
    )
    rising_final = (
        float(result["rising_equity"]["capital"].iloc[-1])
        if not result["rising_equity"].empty
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

    gates = {
        "beats_cash": primary_final > initial_capital,
        "beats_bh": primary_final > bh_final,
        "beats_dca": primary_final > dca_final,
        "beats_unconfirmed_breakout_control": primary_final > unconfirmed_final,
        "beats_oi_rising_variant": primary_final > rising_final,
        "beats_random_control": primary_final > random_final,
        "survives_doubled_cost": doubled_final > initial_capital,
        "survives_best_trade_exclusion": result["excluded_capital"] > initial_capital,
        "concentration_ok": (
            result["top_trade_pct"] is None or abs(result["top_trade_pct"]) < 20.0
        ),
        "has_holdout_trades": has_holdout_trades,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def write_report(output: Path, all_results: dict, config: StudyConfig) -> None:
    lines = ["# OI-Thin (Falling) Daily Breakout Continuation (Long-Only) Validation", ""]
    lines.append("## Primary rule")
    lines.append(
        "> LONG-ONLY: enter at next daily open when (a) close breaks above the trailing "
        "prior-only 20-day high AND (b) most recent completed daily open interest is "
        "<= -5% lower than 5 days earlier (mirror image of the rejected OI-rising study's "
        "+5% trigger). Exit at next daily open on the first close below the trailing "
        "prior-only 10-day low. Flat otherwise, non-overlapping trades. 30bps round-trip cost."
    )
    lines.append("")
    lines.append("## Data sources")
    lines.append("- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`).")
    lines.append(
        "- Real Binance USD-M futures open interest (already cached this program, "
        "`data/open_interest/*_oi_daily.csv.gz`, fetched from the public "
        "`data.binance.vision` daily-metrics archive). No synthetic/proxy OI used."
    )
    lines.append("")
    lines.append("## Genealogy")
    lines.append(
        "This is the explicit recommended follow-up from EXP-2026-09-01-OIBREAKOUT-001 "
        "(rejected: OI-RISING confirmation lost 2.7x-4.0x to the unconfirmed breakout "
        "control on all 4 assets). Same breakout/exit structure, same magnitude threshold "
        "(5%), opposite sign (OI falling = thin positioning, room to add) -- not a re-tune."
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
        rising_final = (
            float(result["rising_equity"]["capital"].iloc[-1])
            if not result["rising_equity"].empty
            else config.initial_capital
        )
        random_final = (
            float(result["random_equity"]["capital"].iloc[-1])
            if not result["random_equity"].empty
            else config.initial_capital
        )
        lines.append(f"- Primary (OI-thin) final capital: **${primary_final:,.2f}** (start ${config.initial_capital:,.0f})")
        lines.append(f"- Buy-and-hold final: **${bh_final:,.2f}**")
        lines.append(f"- Daily DCA final: **${dca_final:,.2f}**")
        lines.append(
            f"- Unconfirmed-breakout control (no OI filter) final: **${unconfirmed_final:,.2f}** "
            f"({len(result['unconfirmed_trades'])} trades)"
        )
        lines.append(
            f"- OI-RISING variant (rejected study, direct comparison) final: **${rising_final:,.2f}** "
            f"({len(result['rising_trades'])} trades)"
        )
        lines.append(f"- Seeded random-timing control final: **${random_final:,.2f}** ({len(result['random_trades'])} trades)")
        lines.append(f"- Doubled-cost final: **${result['doubled_final']:,.2f}**")
        lines.append(f"- Best-trade-exclusion final: **${result['excluded_capital']:,.2f}**")
        lines.append(f"- Top single-trade % of total PnL: **{result['top_trade_pct']}**")
        verdict, gates = classify_verdict_thin(result, config.initial_capital)
        lines.append(f"- Gates: {gates}")
        lines.append(f"- Verdict: **{verdict}**")
        lines.append("")
        lines.append("Partition breakdown:")
        lines.append(dataframe_to_markdown(pd.DataFrame(result["partition_rows"])))
        lines.append("")
    lines.append("## Overall verdict")
    verdicts = {asset: classify_verdict_thin(result, config.initial_capital)[0] for asset, result in all_results.items()}
    n_candidate = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared every gate.")
    if n_candidate == 0:
        lines.append("\n**REJECTED** -- no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**PROMISING** -- every asset cleared every gate; still subject to further robustness scrutiny.")
    else:
        lines.append("\n**PROMISING BUT INCONCLUSIVE** -- mixed results across assets.")
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


def run_oi_thin_breakout_validation(paths: Paths) -> dict:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "oi_thin_breakout" / "runs" / run_id
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
        "oi_fall_threshold": OI_FALL_THRESHOLD,
        "universe": UNIVERSE,
        "verdicts": {asset: classify_verdict_thin(r, config.initial_capital)[0] for asset, r in all_results.items()},
        "gates": {asset: classify_verdict_thin(r, config.initial_capital)[1] for asset, r in all_results.items()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")

    print(f"Report written to {output / 'REPORT.md'}")
    return {"output": output, "all_results": all_results, "config": config}


if __name__ == "__main__":
    from .config import project_root

    run_oi_thin_breakout_validation(Paths(project_root()))
