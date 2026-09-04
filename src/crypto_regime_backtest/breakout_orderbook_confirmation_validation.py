from __future__ import annotations

"""Daily 20d-high breakout + order-book depth confirmation.

Genuinely new for this repo: combines the already-studied daily breakout parent
system with the repo's newly cached real Binance futures order-book depth state
as a confirmation filter, rather than using depth imbalance as a standalone
signal.

Primary rule (frozen before inspecting strategy results in this module):
1. Compute the plain daily breakout signal exactly as in
   breakout_daily_20high_validation.py: close > prior-only rolling 20d high,
   next-day-open entry; exit on close < prior-only rolling 10d low,
   next-day-open exit.
2. Compute daily order-book imbalance z-score from the cached real Binance
   bookDepth archive using ONLY prior days in the rolling baseline:
   z_t = (imbalance_t - mean(imbalance_{t-90:t-1})) / std(...).
3. Enter only when breakout_t is true AND z_t >= +0.5 on the SAME completed
   day. This is a modest positive-confirmation threshold chosen ex ante from
   signal-count viability (not from returns): a stricter 1.5 threshold leaves
   too few combined signals in the 2023+ archive window for a meaningful test.
4. Compare directly against the unfiltered breakout control on the IDENTICAL
   2023-01-01+ overlapping window, plus buy-and-hold, DCA, and a seeded
   random-timing control.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .breakout_daily_20high_validation import (
    CONCENTRATION_CAP_PCT,
    N_STRATEGY_VARIANTS,
    StudyConfig as BreakoutConfig,
    build_daily_signal,
    classify_verdict as classify_parent_verdict,
    dataframe_to_markdown,
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
from .data import load_ohlcv, sha256

UNIVERSE = ("BTC", "ETH", "SOL", "XRP")
DEPTH_START = pd.Timestamp("2023-01-01T00:00:00Z")
DEPTH_Z_WINDOW = 90
DEPTH_Z_MIN_PERIODS = 30
DEPTH_Z_THRESHOLD = 0.5
RANDOM_SEED = 20260904
ASSET_SEED_OFFSET = {"BTC": 1, "ETH": 2, "SOL": 3, "XRP": 4}


@dataclass(frozen=True)
class StudyConfig:
    depth_z_window: int = DEPTH_Z_WINDOW
    depth_z_min_periods: int = DEPTH_Z_MIN_PERIODS
    depth_z_threshold: float = DEPTH_Z_THRESHOLD
    depth_start: str = DEPTH_START.isoformat()
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    breakout_lookback_days: int = 20
    exit_lookback_days: int = 10
    primary_rule: str = (
        "Enter at next daily open when close breaks above the prior-only 20-day high AND the same day's "
        "real Binance futures order-book depth imbalance z-score is >= +0.5 vs its own prior-only trailing "
        "90-day history. Exit at next daily open on the first close below the prior-only 10-day low. "
        "Non-overlapping, 30bps round-trip cost."
    )


def load_depth(paths: Paths, asset: str) -> pd.DataFrame:
    frame = pd.read_csv(
        paths.data / "orderbook_depth" / f"{asset}_depth_imbalance_1d.csv.gz",
        parse_dates=["timestamp"],
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.set_index("timestamp").sort_index()
    if frame.index.duplicated().any():
        raise ValueError(f"Duplicate order-book timestamps for {asset}")
    if not frame.index.is_monotonic_increasing:
        raise ValueError(f"Unsorted order-book timestamps for {asset}")
    return frame.loc[frame.index >= DEPTH_START].copy()


def build_confirmed_breakout_frame(
    price_1d: pd.DataFrame,
    depth: pd.DataFrame,
    breakout_config: BreakoutConfig,
    depth_z_window: int,
    depth_z_min_periods: int,
    depth_z_threshold: float,
) -> pd.DataFrame:
    breakout = build_daily_signal(price_1d, breakout_config)
    breakout = breakout.loc[breakout.index >= DEPTH_START].copy()
    prior = depth["imbalance"].shift(1)
    roll_mean = prior.rolling(depth_z_window, min_periods=depth_z_min_periods).mean()
    roll_std = prior.rolling(depth_z_window, min_periods=depth_z_min_periods).std(ddof=1)
    depth = depth.copy()
    depth["depth_z"] = (depth["imbalance"] - roll_mean) / roll_std
    merged = breakout.join(depth[["imbalance", "depth_z", "n_snapshots"]], how="inner")
    merged["depth_confirmed_breakout"] = merged["breakout"] & (merged["depth_z"] >= depth_z_threshold)
    merged["partition"] = [partition_label(ts) for ts in merged.index]
    return merged


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict[str, Any]:
    price_1d = load_ohlcv(paths, asset, "1d")
    depth = load_depth(paths, asset)
    breakout_config = BreakoutConfig(initial_capital=config.initial_capital)
    frame = build_confirmed_breakout_frame(
        price_1d=price_1d,
        depth=depth,
        breakout_config=breakout_config,
        depth_z_window=config.depth_z_window,
        depth_z_min_periods=config.depth_z_min_periods,
        depth_z_threshold=config.depth_z_threshold,
    )

    filtered_equity, filtered_trades = simulate_long_strategy(
        frame, breakout_config, entry_column="depth_confirmed_breakout"
    )
    control_equity, control_trades = simulate_long_strategy(frame, breakout_config, entry_column="breakout")
    delayed_equity, delayed_trades = simulate_long_strategy(
        frame, BreakoutConfig(initial_capital=config.initial_capital, delay_bars=1), entry_column="depth_confirmed_breakout"
    )
    bh = simulate_buy_and_hold(frame, config.initial_capital)
    dca = simulate_daily_dca(frame, config.initial_capital)

    filtered_final = float(filtered_equity["capital"].iloc[-1])
    control_final = float(control_equity["capital"].iloc[-1])
    delayed_final = float(delayed_equity["capital"].iloc[-1])
    doubled_final = simulate_doubled_cost(filtered_trades, config.initial_capital)
    top_trade_pct = top_trade_pct_of_pnl(filtered_trades, config.initial_capital, filtered_final)

    if not filtered_trades.empty:
        best_idx = filtered_trades["trade_return"].abs().idxmax()
        excluded_capital = config.initial_capital
        for i, row in filtered_trades.iterrows():
            rr = row["trade_return"] if i != best_idx else 0.0
            excluded_capital *= 1 + rr
    else:
        excluded_capital = filtered_final

    mean_hold_days = 5.0
    if not filtered_trades.empty:
        holds = [(row["exit_time"] - row["entry_time"]).days for _, row in filtered_trades.iterrows()]
        if holds:
            mean_hold_days = float(np.mean(holds))
    random_equity, random_trades = simulate_random_control(
        frame,
        breakout_config,
        len(filtered_trades),
        int(round(mean_hold_days)),
        seed=RANDOM_SEED + ASSET_SEED_OFFSET[asset],
    )
    random_final = (
        float(random_equity["capital"].iloc[-1]) if not random_equity.empty else config.initial_capital
    )

    wf = walk_forward_split(filtered_trades)
    mc = (
        monte_carlo_permutation(filtered_trades["trade_return"].dropna().to_numpy(), 2000, seed=RANDOM_SEED)
        if not filtered_trades.empty
        else {}
    )
    bars_per_year = 365.25 / mean_hold_days if mean_hold_days > 0 else 365.25
    dsr = (
        deflated_sharpe_ratio(
            filtered_trades["trade_return"].dropna().to_numpy(),
            bars_per_year,
            N_STRATEGY_VARIANTS + 1,
        )
        if not filtered_trades.empty
        else {}
    )

    partition_rows = []
    for label in ("development_pre_2024", "validation_2024", "test_2025_onward"):
        part_trades = (
            filtered_trades[filtered_trades["entry_time"].apply(lambda t: partition_label(t) == label)]
            if not filtered_trades.empty
            else filtered_trades
        )
        partition_rows.append(
            {
                "asset": asset,
                "partition": label,
                "n_trades": len(part_trades),
                "mean_trade_return_pct": float(part_trades["trade_return"].mean() * 100) if len(part_trades) else np.nan,
            }
        )

    gates = {
        "beats_unfiltered_breakout_control": filtered_final > control_final,
        "beats_buy_and_hold": filtered_final > float(bh.iloc[-1]),
        "beats_daily_dca": filtered_final > float(dca.iloc[-1]),
        "beats_random_timing_control": filtered_final > random_final,
        "survives_doubled_cost": doubled_final > config.initial_capital,
        "survives_best_trade_exclusion": excluded_capital > config.initial_capital,
        "survives_1bar_delay": delayed_final > config.initial_capital,
        "concentration_ok": top_trade_pct is None or abs(top_trade_pct) < CONCENTRATION_CAP_PCT,
        "has_holdout_trades": any(r["partition"] == "test_2025_onward" and r["n_trades"] > 0 for r in partition_rows),
        "monte_carlo_significant": bool(mc.get("p_value") is not None and mc["p_value"] < 0.05),
        "deflated_sharpe_passes": bool(dsr.get("passes_at_0.05")) if dsr else False,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"

    parent_verdict, parent_gates = classify_parent_verdict(
        {
            "equity": control_equity,
            "bh": bh,
            "dca": dca,
            "random_equity": random_equity,
            "doubled_final": simulate_doubled_cost(control_trades, config.initial_capital),
            "delayed_final": float(
                simulate_long_strategy(
                    frame,
                    BreakoutConfig(initial_capital=config.initial_capital, delay_bars=1),
                    entry_column="breakout",
                )[0]["capital"].iloc[-1]
            ),
            "excluded_capital": control_final,
            "top_trade_pct": top_trade_pct_of_pnl(control_trades, config.initial_capital, control_final),
            "partition_rows": [
                {
                    "partition": label,
                    "n_trades": int(
                        len(control_trades[control_trades["entry_time"].apply(lambda t: partition_label(t) == label)])
                    ) if not control_trades.empty else 0,
                }
                for label in ("development_pre_2024", "validation_2024", "test_2025_onward")
            ],
            "monte_carlo": {},
            "dsr": {},
        },
        config.initial_capital,
    )

    return {
        "asset": asset,
        "frame": frame,
        "filtered_equity": filtered_equity,
        "filtered_trades": filtered_trades,
        "control_equity": control_equity,
        "control_trades": control_trades,
        "bh": bh,
        "dca": dca,
        "random_equity": random_equity,
        "random_trades": random_trades,
        "filtered_final": filtered_final,
        "control_final": control_final,
        "random_final": random_final,
        "doubled_final": doubled_final,
        "delayed_final": delayed_final,
        "delayed_n_trades": len(delayed_trades),
        "excluded_capital": excluded_capital,
        "top_trade_pct": top_trade_pct,
        "partition_rows": partition_rows,
        "mean_hold_days": mean_hold_days,
        "combined_signal_count": int(frame["depth_confirmed_breakout"].sum()),
        "unfiltered_signal_count": int(frame["breakout"].sum()),
        "walk_forward": wf,
        "monte_carlo": mc,
        "dsr": dsr,
        "gates": gates,
        "verdict": verdict,
        "parent_control_verdict": parent_verdict,
        "parent_control_gates": parent_gates,
    }


def write_report(output: Path, all_results: dict[str, dict[str, Any]], config: StudyConfig) -> None:
    lines = ["# Order-Book Depth-Confirmed Daily Breakout Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {config.primary_rule}")
    lines.append("")
    lines.append("## Data sources")
    lines.append("- Real Binance spot daily OHLCV: `data/raw/*_1d.csv.gz`")
    lines.append("- Real Binance USD-M public order-book depth archive aggregated to daily imbalance: `data/orderbook_depth/*_depth_imbalance_1d.csv.gz`")
    lines.append("")
    lines.append("## Per-asset results")
    verdicts = {}
    summary_rows = []
    for asset, result in all_results.items():
        verdicts[asset] = result["verdict"]
        summary_rows.append(
            {
                "asset": asset,
                "trades": len(result["filtered_trades"]),
                "filtered_final": result["filtered_final"],
                "unfiltered_control_final": result["control_final"],
                "buy_hold_final": float(result["bh"].iloc[-1]),
                "dca_final": float(result["dca"].iloc[-1]),
                "random_final": result["random_final"],
                "top_trade_pct": result["top_trade_pct"],
                "verdict": result["verdict"],
            }
        )
        lines.append(f"### {asset}")
        lines.append(f"- Combined breakout+depth signals: **{result['combined_signal_count']}** raw / **{len(result['filtered_trades'])}** executed trades")
        lines.append(f"- Filtered final capital: **${result['filtered_final']:,.2f}**")
        lines.append(f"- Unfiltered breakout control final: **${result['control_final']:,.2f}**")
        lines.append(f"- Buy-and-hold final: **${float(result['bh'].iloc[-1]):,.2f}**")
        lines.append(f"- Daily DCA final: **${float(result['dca'].iloc[-1]):,.2f}**")
        lines.append(f"- Random-timing control final: **${result['random_final']:,.2f}** ({len(result['random_trades'])} trades)")
        lines.append(f"- Doubled-cost final: **${result['doubled_final']:,.2f}**")
        lines.append(f"- 1-bar delayed final: **${result['delayed_final']:,.2f}** ({result['delayed_n_trades']} trades)")
        lines.append(f"- Best-trade-exclusion final: **${result['excluded_capital']:,.2f}**")
        lines.append(f"- Top single-trade % of total PnL: **{result['top_trade_pct']}**")
        lines.append(f"- Walk-forward: {result['walk_forward']}")
        lines.append(f"- Monte Carlo: {result['monte_carlo']}")
        lines.append(f"- Deflated Sharpe: {result['dsr']}")
        lines.append(f"- Gates: {result['gates']}")
        lines.append(f"- Verdict: **{result['verdict']}**")
        lines.append("")
        lines.append("Partition breakdown:")
        lines.append(dataframe_to_markdown(pd.DataFrame(result["partition_rows"])))
        lines.append("")
    lines.append("## Summary table")
    lines.append(dataframe_to_markdown(pd.DataFrame(summary_rows)))
    lines.append("")
    n_candidate = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append("## Overall verdict")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared every gate.")
    lines.append("**REJECTED** -- no asset cleared every gate." if n_candidate == 0 else "**MIXED/CANDIDATE**")
    output.write_text("\n".join(lines))


def run_breakout_orderbook_confirmation_validation(paths: Paths) -> Path:
    paths.create()
    config = StudyConfig()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "breakout_orderbook_confirmation" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    all_results: dict[str, dict[str, Any]] = {}
    for asset in UNIVERSE:
        all_results[asset] = run_asset_study(paths, asset, config)
        all_results[asset]["filtered_trades"].to_csv(output / f"{asset}_filtered_trades.csv", index=False)
        all_results[asset]["control_trades"].to_csv(output / f"{asset}_control_trades.csv", index=False)
        all_results[asset]["frame"].reset_index().to_csv(output / f"{asset}_signal_frame.csv", index=False)
        with (output / f"{asset}_gates.json").open("w") as handle:
            json.dump(
                {"verdict": all_results[asset]["verdict"], "gates": all_results[asset]["gates"]},
                handle,
                indent=2,
                default=str,
            )

    summary = pd.DataFrame(
        [
            {
                "asset": asset,
                "trades": len(res["filtered_trades"]),
                "filtered_final": res["filtered_final"],
                "control_final": res["control_final"],
                "buy_hold_final": float(res["bh"].iloc[-1]),
                "dca_final": float(res["dca"].iloc[-1]),
                "random_final": res["random_final"],
                "doubled_final": res["doubled_final"],
                "delayed_final": res["delayed_final"],
                "top_trade_pct": res["top_trade_pct"],
                "verdict": res["verdict"],
            }
            for asset, res in all_results.items()
        ]
    )
    summary.to_csv(output / "summary.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "data": {
            asset: {
                "price_path": f"data/raw/{asset}_1d.csv.gz",
                "depth_path": f"data/orderbook_depth/{asset}_depth_imbalance_1d.csv.gz",
                "price_sha256": sha256(paths.raw / f"{asset}_1d.csv.gz"),
                "depth_sha256": sha256(paths.data / "orderbook_depth" / f"{asset}_depth_imbalance_1d.csv.gz"),
            }
            for asset in UNIVERSE
        },
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output / "REPORT.md", all_results, config)
    return output / "REPORT.md"


def main() -> None:
    paths = Paths(root=Path(__file__).resolve().parents[2])
    report = run_breakout_orderbook_confirmation_validation(paths)
    print(f"Report written to {report}")


if __name__ == "__main__":
    main()
