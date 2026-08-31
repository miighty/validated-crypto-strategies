from __future__ import annotations

"""Cross-exchange funding-rate divergence validation.

Mechanism (genuinely new in this repo): every prior funding study in this
repo used a SINGLE exchange's (Binance) funding print, either directionally
(funding_positive/negative_panel, REJECTED) or as a delta-neutral single-
exchange carry harvest (funding_carry_deltaneutral, REJECTED) or as a
cross-sectional dollar-neutral ranking across coins on one exchange
(funding_carry_cross_sectional, REJECTED). This study instead compares the
SAME asset's funding rate across TWO INDEPENDENT exchanges (Binance vs
Hyperliquid) at the same settlement window.

Economic rationale: persistent divergence between two venues' funding rates
reflects venue-specific positioning imbalances (one exchange's traders more
levered long/short than the other's). If a mean-reversion-in-the-spread
mechanism exists, a large divergence should predict the spread narrowing,
which is tradeable via a real, cash-settled cross-exchange basis position:
go long spot (or perp) on the exchange with the LOWER (more negative /
cheaper-to-be-long) funding rate and short the perp on the exchange with the
HIGHER (more expensive-to-be-long) funding rate, collecting the funding
differential while remaining price-neutral (long one venue's perp, short the
other's, equal notional -> net price exposure approximately zero if executed
simultaneously).

This is DISTINCT from the already-rejected delta-neutral single-exchange
carry study: that study hedges spot-vs-perp on ONE exchange and times entry
by the trailing level of funding. This study never touches spot at all -- it
is a purely cross-exchange perp-vs-perp basis trade, timed by the divergence
between two real, independently-published funding curves.

Real data only:
  - Binance USD-M real 8h funding history (data/funding/{ASSET}_funding.csv.gz,
    already cached in this repo, settlements at 00:00/08:00/16:00 UTC).
  - Hyperliquid real hourly funding history (data/hyperliquid_funding/
    {ASSET}_funding.csv.gz, newly fetched this run via the public
    `fundingHistory` info endpoint, https://api.hyperliquid.xyz/info).
    Hyperliquid pays/charges funding every hour (not every 8h); to compare
    apples-to-apples with Binance's 8h print, the Hyperliquid hourly rate is
    compounded over the matching 8h window ending at each Binance settlement
    timestamp: hl_8h = prod(1 + hl_hourly) - 1 over the preceding 8 hourly
    prints.
  - No proxy, synthetic, or simulated funding/price data anywhere in this
    module.

Honesty disclosures:
  - No cross-exchange margin/collateral-transfer friction is modeled beyond
    the repo's standard round-trip cost (each leg on each exchange pays the
    shared ONE_WAY_COST); real cross-exchange arb also requires capital
    pre-positioned on both venues and is subject to exchange-specific
    liquidation risk that is not modeled here.
  - Hyperliquid funding history via the public API only goes back to
    2023-05-12 (BTC/ETH/SOL) / 2023-06-18 (XRP) -- this materially truncates
    the sample versus Binance's longer history. The comparison window is the
    INTERSECTION of both exchanges' available history, reported explicitly.
  - Perp-vs-perp basis trade assumed to execute at zero price slippage
    between the two legs (idealized simultaneous fill); real execution would
    have basis-timing risk this backtest does not capture.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL

UNIVERSE = ("BTC", "ETH", "SOL", "XRP")

# Preregistered primary rule (frozen before any result was inspected this run).
PRIMARY_DIVERGENCE_THRESHOLD = 0.00050   # enter when |Binance_8h - Hyperliquid_8h| >= 5bps
PRIMARY_HOLD_PRINTS = 1                   # hold exactly 1 settlement (8h), then reassess
LEGS_PER_SIDE = 2                         # long one venue's perp + short the other's perp
ENTRY_COST = LEGS_PER_SIDE * ONE_WAY_COST
EXIT_COST = LEGS_PER_SIDE * ONE_WAY_COST

SENSITIVITY_GRID = (
    (0.00025, 1),
    (0.00050, 1),
    (0.00100, 1),
    (0.00050, 3),
    (0.00100, 3),
)

VALIDATION_SPLIT = 0.5  # first half / second half of the intersection window (walk-forward)


@dataclass(frozen=True)
class StudyConfig:
    divergence_threshold: float = PRIMARY_DIVERGENCE_THRESHOLD
    hold_prints: int = PRIMARY_HOLD_PRINTS
    entry_cost: float = ENTRY_COST
    exit_cost: float = EXIT_COST
    initial_capital: float = STARTING_CAPITAL
    primary_rule: str = (
        "Cross-exchange funding basis: at each real Binance 8h settlement, compute the "
        "matching real Hyperliquid 8h-compounded funding rate for the same asset. If "
        "|Binance_8h - Hyperliquid_8h| >= 5bps, enter a perp-vs-perp basis trade: long the "
        "perp on the exchange with the LOWER funding rate, short the perp on the exchange "
        "with the HIGHER funding rate, equal notional (net price-neutral by construction). "
        "Hold exactly 1 settlement (8h), collect the realized funding differential, exit, "
        "and reassess at the next settlement. No spot leg is used (distinct from the "
        "already-rejected single-exchange delta-neutral carry study)."
    )


def load_binance_funding(paths: Paths, asset: str) -> pd.DataFrame:
    frame = pd.read_csv(paths.funding / f"{asset}_funding.csv.gz")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
    frame = frame[["timestamp", "funding_rate"]].rename(columns={"funding_rate": "binance_8h"})
    frame = frame.sort_values("timestamp").drop_duplicates(subset="timestamp").reset_index(drop=True)
    return frame


def load_hyperliquid_funding(paths: Paths, asset: str) -> pd.DataFrame:
    hl_path = paths.data / "hyperliquid_funding" / f"{asset}_funding.csv.gz"
    frame = pd.read_csv(hl_path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
    frame = frame[["timestamp", "funding_rate"]].rename(columns={"funding_rate": "hl_hourly"})
    frame = frame.sort_values("timestamp").drop_duplicates(subset="timestamp").reset_index(drop=True)
    return frame


def compound_hl_to_8h(hl: pd.DataFrame, settlement_timestamps: pd.Series) -> pd.DataFrame:
    """For each Binance 8h settlement timestamp, compound the preceding 8 real
    Hyperliquid hourly funding prints (window: (ts - 8h, ts]) into one 8h-equivalent
    rate, requiring exactly 8 available hourly prints (no partial windows)."""
    hl_indexed = hl.set_index("timestamp")["hl_hourly"].sort_index()
    rows = []
    for ts in settlement_timestamps:
        window_start = ts - pd.Timedelta(hours=8)
        window = hl_indexed.loc[(hl_indexed.index > window_start) & (hl_indexed.index <= ts)]
        if len(window) != 8:
            rows.append({"timestamp": ts, "hl_8h": np.nan, "hl_prints": len(window)})
            continue
        compounded = float(np.prod(1.0 + window.to_numpy()) - 1.0)
        rows.append({"timestamp": ts, "hl_8h": compounded, "hl_prints": len(window)})
    return pd.DataFrame(rows)


def build_panel(paths: Paths, asset: str) -> pd.DataFrame:
    binance = load_binance_funding(paths, asset)
    hyperliquid = load_hyperliquid_funding(paths, asset)
    hl_range = (hyperliquid["timestamp"].min(), hyperliquid["timestamp"].max())
    settlements = binance.loc[
        (binance["timestamp"] > hl_range[0]) & (binance["timestamp"] <= hl_range[1])
    ].reset_index(drop=True)
    hl_8h = compound_hl_to_8h(hyperliquid, settlements["timestamp"])
    panel = settlements.merge(hl_8h, on="timestamp", how="left")
    panel = panel.dropna(subset=["hl_8h"]).reset_index(drop=True)
    panel["divergence"] = panel["binance_8h"] - panel["hl_8h"]
    panel["abs_divergence"] = panel["divergence"].abs()
    return panel


def simulate_basis_trade(panel: pd.DataFrame, config: StudyConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long the cheaper venue's perp, short the more expensive venue's perp,
    each settlement where |divergence| clears the threshold. Non-overlapping
    (enter at settlement i, hold to i+hold_prints, cannot re-enter mid-hold)."""
    capital = config.initial_capital
    equity_rows = [{"timestamp": panel["timestamp"].iloc[0] if not panel.empty else None, "capital": capital}]
    trade_rows = []
    i = 0
    n = len(panel)
    while i < n:
        row = panel.iloc[i]
        if row["abs_divergence"] >= config.divergence_threshold:
            end_idx = min(i + config.hold_prints, n) - 1
            window = panel.iloc[i : end_idx + 1]
            # Long the venue with the LOWER (cheaper) funding rate, short the higher one.
            long_binance = row["binance_8h"] < row["hl_8h"]
            capital *= (1 - config.entry_cost)
            entry_capital = capital
            gross_pnl_rate = 0.0
            for _, wrow in window.iterrows():
                # Receiving the short leg's funding, paying the long leg's funding.
                if long_binance:
                    period_pnl = wrow["hl_8h"] - wrow["binance_8h"]
                else:
                    period_pnl = wrow["binance_8h"] - wrow["hl_8h"]
                capital *= (1 + period_pnl)
                gross_pnl_rate += period_pnl
            capital *= (1 - config.exit_cost)
            trade_rows.append(
                {
                    "entry_time": row["timestamp"],
                    "exit_time": window["timestamp"].iloc[-1],
                    "n_prints": len(window),
                    "long_venue": "binance" if long_binance else "hyperliquid",
                    "entry_divergence": row["divergence"],
                    "gross_pnl_rate": gross_pnl_rate,
                    "capital_at_entry": entry_capital,
                    "capital_at_exit": capital,
                    "trade_return": (capital / entry_capital) - 1.0,
                }
            )
            equity_rows.append({"timestamp": window["timestamp"].iloc[-1], "capital": capital})
            i = end_idx + 1
        else:
            equity_rows.append({"timestamp": row["timestamp"], "capital": capital})
            i += 1
    equity = pd.DataFrame(equity_rows)
    trades = pd.DataFrame(trade_rows)
    return equity, trades


def simulate_seeded_random_control(panel: pd.DataFrame, config: StudyConfig, n_trades: int, seed: int = 42) -> float:
    """Random-timing control: same number of non-overlapping trades, random entry
    settlements, random long-venue direction, same hold length and costs."""
    rng = np.random.default_rng(seed)
    n = len(panel)
    if n_trades == 0 or n == 0:
        return config.initial_capital
    capital = config.initial_capital
    max_start = max(n - config.hold_prints, 1)
    starts = sorted(rng.choice(max_start, size=min(n_trades, max_start), replace=False))
    for start in starts:
        end_idx = min(start + config.hold_prints, n) - 1
        window = panel.iloc[start : end_idx + 1]
        long_binance = bool(rng.integers(0, 2))
        capital *= (1 - config.entry_cost)
        for _, wrow in window.iterrows():
            period_pnl = (wrow["hl_8h"] - wrow["binance_8h"]) if long_binance else (wrow["binance_8h"] - wrow["hl_8h"])
            capital *= (1 + period_pnl)
        capital *= (1 - config.exit_cost)
    return capital


def sharpe_from_trade_returns(trade_returns: np.ndarray, trades_per_year: float) -> float:
    if len(trade_returns) < 2 or trade_returns.std(ddof=0) == 0:
        return 0.0
    return float((trade_returns.mean() / trade_returns.std(ddof=0)) * np.sqrt(trades_per_year))


def sortino_from_trade_returns(trade_returns: np.ndarray, trades_per_year: float) -> float:
    downside = np.minimum(trade_returns, 0.0)
    downside_dev = np.sqrt(np.mean(downside**2)) if len(trade_returns) else 0.0
    if downside_dev == 0 or len(trade_returns) < 2:
        return 0.0
    return float((trade_returns.mean() / downside_dev) * np.sqrt(trades_per_year))


def max_drawdown(capital: pd.Series) -> float:
    running_max = capital.cummax()
    drawdown = (capital - running_max) / running_max
    return float(drawdown.min())


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    panel = build_panel(paths, asset)
    if panel.empty:
        return {"asset": asset, "error": "no overlapping Binance/Hyperliquid funding history"}

    equity, trades = simulate_basis_trade(panel, config)
    final_capital = float(equity["capital"].iloc[-1])
    total_return_pct = (final_capital / config.initial_capital - 1.0) * 100

    n_settlements = len(panel)
    span_days = (panel["timestamp"].iloc[-1] - panel["timestamp"].iloc[0]).total_seconds() / 86400.0
    trades_per_year = (len(trades) / span_days * 365.25) if span_days > 0 and len(trades) > 0 else 0.0

    trade_returns = trades["trade_return"].to_numpy() if not trades.empty else np.array([])
    sharpe = sharpe_from_trade_returns(trade_returns, trades_per_year) if trades_per_year > 0 else 0.0
    sortino = sortino_from_trade_returns(trade_returns, trades_per_year) if trades_per_year > 0 else 0.0
    mdd = max_drawdown(equity["capital"])

    # Random-timing control (matched trade count/hold length/costs).
    random_final = simulate_seeded_random_control(panel, config, len(trades))

    # Doubled-cost hostile check.
    doubled_config = StudyConfig(
        divergence_threshold=config.divergence_threshold,
        hold_prints=config.hold_prints,
        entry_cost=config.entry_cost * 2,
        exit_cost=config.exit_cost * 2,
        initial_capital=config.initial_capital,
    )
    doubled_equity, _ = simulate_basis_trade(panel, doubled_config)
    doubled_final = float(doubled_equity["capital"].iloc[-1]) if not doubled_equity.empty else np.nan

    # Best-trade exclusion (concentration check).
    if not trades.empty:
        best_idx = trades["trade_return"].idxmax()
        excluded_capital = config.initial_capital
        for idx, row in trades.iterrows():
            r = row["trade_return"] if idx != best_idx else 0.0
            excluded_capital *= (1 + r)
        total_pnl = final_capital - config.initial_capital
        best_trade_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
        best_trade_pct_of_pnl = float(best_trade_pnl / total_pnl) * 100 if total_pnl != 0 else np.nan
    else:
        excluded_capital = final_capital
        best_trade_pct_of_pnl = np.nan

    # Walk-forward split (first half / second half of the intersection window).
    split_idx = int(len(panel) * VALIDATION_SPLIT)
    first_half = panel.iloc[:split_idx].reset_index(drop=True)
    second_half = panel.iloc[split_idx:].reset_index(drop=True)
    first_equity, first_trades = simulate_basis_trade(first_half, config) if not first_half.empty else (pd.DataFrame(), pd.DataFrame())
    second_equity, second_trades = simulate_basis_trade(second_half, config) if not second_half.empty else (pd.DataFrame(), pd.DataFrame())
    first_final = float(first_equity["capital"].iloc[-1]) if not first_equity.empty else np.nan
    second_final = float(second_equity["capital"].iloc[-1]) if not second_equity.empty else np.nan

    return {
        "asset": asset,
        "n_settlements": n_settlements,
        "span_start": panel["timestamp"].iloc[0],
        "span_end": panel["timestamp"].iloc[-1],
        "n_trades": len(trades),
        "final_capital": final_capital,
        "total_return_pct": total_return_pct,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": mdd * 100,
        "random_control_final": random_final,
        "doubled_cost_final": doubled_final,
        "best_trade_exclusion_final": excluded_capital,
        "best_trade_pct_of_pnl": best_trade_pct_of_pnl,
        "first_half_trades": len(first_trades),
        "first_half_final_pct": (first_final / config.initial_capital - 1.0) * 100 if first_final == first_final else np.nan,
        "second_half_trades": len(second_trades),
        "second_half_final_pct": (second_final / config.initial_capital - 1.0) * 100 if second_final == second_final else np.nan,
        "mean_abs_divergence_bps": float(panel["abs_divergence"].mean()) * 10000,
        "trades": trades,
        "equity": equity,
        "panel": panel,
    }


def run_sensitivity(paths: Paths, config: StudyConfig) -> pd.DataFrame:
    rows = []
    for asset in UNIVERSE:
        panel = build_panel(paths, asset)
        if panel.empty:
            continue
        for threshold, hold in SENSITIVITY_GRID:
            variant_config = StudyConfig(
                divergence_threshold=threshold,
                hold_prints=hold,
                entry_cost=config.entry_cost,
                exit_cost=config.exit_cost,
                initial_capital=config.initial_capital,
            )
            equity, trades = simulate_basis_trade(panel, variant_config)
            final = float(equity["capital"].iloc[-1]) if not equity.empty else np.nan
            rows.append(
                {
                    "asset": asset,
                    "divergence_threshold_bps": threshold * 10000,
                    "hold_prints": hold,
                    "n_trades": len(trades),
                    "final_capital": final,
                    "total_return_pct": (final / config.initial_capital - 1.0) * 100 if final == final else np.nan,
                }
            )
    return pd.DataFrame(rows)


def classify_verdict(result: dict, initial_capital: float) -> str:
    if "error" in result:
        return "BLOCKED"
    beats_cash = result["final_capital"] > initial_capital
    beats_random = result["final_capital"] > result["random_control_final"]
    survives_doubled_cost = result["doubled_cost_final"] > initial_capital
    survives_exclusion = result["best_trade_exclusion_final"] > initial_capital
    concentration_ok = (
        np.isnan(result["best_trade_pct_of_pnl"]) or abs(result["best_trade_pct_of_pnl"]) < 100
    )
    both_halves_positive = (
        result["first_half_final_pct"] > 0 and result["second_half_final_pct"] > 0
        if not (np.isnan(result["first_half_final_pct"]) or np.isnan(result["second_half_final_pct"]))
        else False
    )
    sufficient_trades = result["n_trades"] >= 20
    if (
        beats_cash
        and beats_random
        and survives_doubled_cost
        and survives_exclusion
        and concentration_ok
        and sufficient_trades
    ):
        return "CANDIDATE" if both_halves_positive else "PROMISING_BUT_INCONCLUSIVE"
    return "REJECTED"


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


def write_report(output: Path, config: StudyConfig, all_results: dict, sensitivity: pd.DataFrame) -> None:
    lines = ["# Cross-Exchange (Binance vs Hyperliquid) Funding Divergence Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {config.primary_rule}")
    lines.append("")
    lines.append("## Honesty disclosures")
    lines.append("- Hyperliquid public funding history only reaches back to 2023-05-12 (BTC/ETH/SOL) / "
                  "2023-06-18 (XRP); the comparison window is the intersection of both exchanges' real "
                  "history, reported per asset below -- this is a much shorter sample than the repo's "
                  "other funding studies.")
    lines.append("- No cross-exchange collateral-transfer friction or exchange-specific liquidation risk "
                  "modeled beyond the shared round-trip cost model.")
    lines.append("- Real data only: Binance real 8h funding (already cached) + Hyperliquid real hourly "
                  "funding (fetched this run via the public `fundingHistory` endpoint, compounded to 8h "
                  "windows aligned to Binance settlements). No synthetic/proxy funding data.")
    lines.append("")
    lines.append("## Per-asset results")
    lines.append("")
    summary_rows = []
    for asset, result in all_results.items():
        lines.append(f"### {asset}")
        if "error" in result:
            lines.append(f"- **BLOCKED**: {result['error']}")
            lines.append("")
            continue
        lines.append(f"- Overlap window: **{result['span_start']}** -> **{result['span_end']}** "
                      f"({result['n_settlements']} matched settlements)")
        lines.append(f"- Mean |divergence|: **{result['mean_abs_divergence_bps']:.2f} bps**")
        lines.append(f"- Trades: **{result['n_trades']}**")
        lines.append(f"- Final capital: **${result['final_capital']:.2f}** ({result['total_return_pct']:.2f}%), "
                      f"Sharpe **{result['sharpe']:.2f}**, Sortino **{result['sortino']:.2f}**, "
                      f"max drawdown **{result['max_drawdown_pct']:.2f}%**")
        lines.append(f"- Random-timing control final: **${result['random_control_final']:.2f}**")
        lines.append(f"- Doubled-cost final: **${result['doubled_cost_final']:.2f}**")
        lines.append(f"- Best-trade-exclusion final: **${result['best_trade_exclusion_final']:.2f}** "
                      f"(best trade = {result['best_trade_pct_of_pnl']:.1f}% of total PnL)")
        lines.append(f"- Walk-forward: first half **{result['first_half_final_pct']:.2f}%** "
                      f"({result['first_half_trades']} trades), second half "
                      f"**{result['second_half_final_pct']:.2f}%** ({result['second_half_trades']} trades)")
        lines.append(f"- Verdict: **{result['verdict']}**")
        lines.append("")
        summary_rows.append(
            {
                "asset": asset,
                "n_trades": result["n_trades"],
                "final_capital": result["final_capital"],
                "total_return_pct": result["total_return_pct"],
                "sharpe": result["sharpe"],
                "verdict": result["verdict"],
            }
        )
    lines.append("## Summary table")
    lines.append(dataframe_to_markdown(pd.DataFrame(summary_rows)))
    lines.append("")
    lines.append("## Sensitivity grid (final capital, $10,000 start)")
    lines.append(dataframe_to_markdown(sensitivity))
    lines.append("")
    lines.append("## Overall verdict")
    verdicts = [r.get("verdict", "BLOCKED") for r in all_results.values()]
    n_candidate = sum(1 for v in verdicts if v == "CANDIDATE")
    n_promising = sum(1 for v in verdicts if v == "PROMISING_BUT_INCONCLUSIVE")
    lines.append(f"{n_candidate}/{len(verdicts)} assets fully cleared all gates (beat cash, beat random-timing "
                  f"control, survive doubled cost, survive best-trade exclusion, concentration < 100% of PnL, "
                  f"positive in both walk-forward halves, >= 20 trades).")
    if n_candidate == 0 and n_promising == 0:
        lines.append("\n**REJECTED** -- no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**PROMISING** -- every asset cleared every gate; still subject to Sharpe-rubric and "
                      "multiple-testing scrutiny (Deflated Sharpe, cross-sectional MC where applicable) before "
                      "any deployment claim.")
    else:
        lines.append("\n**PROMISING BUT INCONCLUSIVE / MIXED** -- see per-asset verdicts above.")
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


def run_funding_crossexchange_divergence_validation(paths: Paths) -> dict:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "funding_crossexchange_divergence" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)

    config = StudyConfig()
    all_results = {}
    for asset in UNIVERSE:
        result = run_asset_study(paths, asset, config)
        result["verdict"] = classify_verdict(result, config.initial_capital)
        all_results[asset] = result

    sensitivity = run_sensitivity(paths, config)

    summary_rows = []
    trades_frames = []
    for asset, result in all_results.items():
        if "error" in result:
            continue
        summary_rows.append(
            {
                "asset": asset,
                "n_settlements": result["n_settlements"],
                "n_trades": result["n_trades"],
                "final_capital": result["final_capital"],
                "total_return_pct": result["total_return_pct"],
                "sharpe": result["sharpe"],
                "sortino": result["sortino"],
                "max_drawdown_pct": result["max_drawdown_pct"],
                "random_control_final": result["random_control_final"],
                "doubled_cost_final": result["doubled_cost_final"],
                "best_trade_exclusion_final": result["best_trade_exclusion_final"],
                "best_trade_pct_of_pnl": result["best_trade_pct_of_pnl"],
                "verdict": result["verdict"],
            }
        )
        if not result["trades"].empty:
            trades_frames.append(result["trades"].assign(asset=asset))

    summary_frame = pd.DataFrame(summary_rows)
    trades_frame = pd.concat(trades_frames, ignore_index=True) if trades_frames else pd.DataFrame()

    summary_frame.to_csv(output / "strategy_summary.csv", index=False, float_format="%.10g")
    trades_frame.to_csv(output / "trade_log.csv", index=False, float_format="%.10g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.10g")

    manifest = {
        "run_id": run_id,
        "config": {
            "divergence_threshold": config.divergence_threshold,
            "hold_prints": config.hold_prints,
            "entry_cost": config.entry_cost,
            "exit_cost": config.exit_cost,
            "initial_capital": config.initial_capital,
            "primary_rule": config.primary_rule,
        },
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2))

    write_report(output, config, all_results, sensitivity)

    return {"output": output, "all_results": all_results, "summary_frame": summary_frame}
