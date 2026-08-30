from __future__ import annotations

"""Delta-neutral single-asset funding-carry harvest validation.

Mechanism (genuinely new in this repo): unlike the already-REJECTED
cross-sectional dollar-neutral funding-carry study (EXP-2026-08-29-FUNDCARRY-001,
long most-negative / short most-positive funding tercile across a 9-coin panel)
and the already-REJECTED single-asset *directional* funding panels
(funding_negative_panel_validation.py, funding_positive_panel_validation.py,
which buy unhedged spot on a funding extreme and are exposed to full price risk),
this study tests a **single-asset delta-neutral cash-and-carry harvest**:

    long spot + short perpetual, equal notional, on ONE asset at a time.

While positioned, the trade is (by construction, ignoring basis/liquidation
risk) insensitive to the asset's price direction: P&L accrues purely from the
8h funding print paid by longs to shorts. The entry/exit rule is a rolling
persistence filter (trailing mean of the last N completed funding prints)
with hysteresis (a higher entry threshold than exit threshold) to avoid
whipsaw. This is a genuinely new mechanism: it is timing-based capital
allocation into and out of a hedged carry position, not cross-sectional
ranking and not unhedged directional timing.

Honesty disclosures (reported prominently in the write-up, not just here):
  - No borrow/margin financing cost for the short perp leg is modeled (real
    desks pay/receive a small additional financing spread beyond funding).
  - No basis-risk/liquidation modeling; assumed continuously hedged 1:1.
  - Real data only: Binance real 8h funding print history
    (data/funding/{ASSET}_funding.csv.gz) and real spot 1h OHLCV
    (data/raw/{ASSET}_1h.csv.gz). No synthetic/proxy inputs.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv

UNIVERSE = ("BTC", "ETH", "SOL", "XRP")
SAMPLE_START = pd.Timestamp("2021-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")

# Preregistered primary rule (frozen before any result was inspected this run).
PRIMARY_LOOKBACK_PRINTS = 3          # trailing rolling mean over last 3 completed 8h prints (24h)
PRIMARY_ENTRY_THRESHOLD = 0.00030    # enter/stay-in hedge when rolling mean funding >= +3bps/8h
PRIMARY_EXIT_THRESHOLD = 0.00010     # exit hedge when rolling mean funding < +1bps/8h (hysteresis)
# Round-trip cost for a delta-neutral carry unwind: 2 legs (spot + perp) each way.
# one_way_cost = FEE_RATE + SLIPPAGE_RATE = 0.0015 (15bps) per the repo's shared cost model.
LEGS_PER_SIDE = 2
ENTRY_COST = LEGS_PER_SIDE * ONE_WAY_COST
EXIT_COST = LEGS_PER_SIDE * ONE_WAY_COST

SENSITIVITY_GRID = (
    (3, 0.00020, 0.00005),
    (3, 0.00030, 0.00010),
    (3, 0.00050, 0.00020),
    (9, 0.00030, 0.00010),
    (9, 0.00050, 0.00020),
)


@dataclass(frozen=True)
class StudyConfig:
    sample_start: str = "2021-01-01T00:00:00Z"
    validation_start: str = "2024-01-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    lookback_prints: int = PRIMARY_LOOKBACK_PRINTS
    entry_threshold: float = PRIMARY_ENTRY_THRESHOLD
    exit_threshold: float = PRIMARY_EXIT_THRESHOLD
    entry_cost: float = ENTRY_COST
    exit_cost: float = EXIT_COST
    initial_capital: float = STARTING_CAPITAL
    primary_rule: str = (
        "Single-asset delta-neutral cash-and-carry (long spot + short perp, equal "
        "notional). Enter/remain hedged while the trailing mean of the last 3 "
        "completed 8h funding prints >= +30bps/24h-equivalent (+3bps/8h mean); exit "
        "to fully unhedged cash-equivalent (flat, no position, no price exposure) "
        "when that trailing mean falls below +1bps/8h (hysteresis band). While "
        "hedged, capital compounds by the realized funding print each 8h; no price "
        "risk is modeled while hedged (idealized 1:1 hedge, no basis/liquidation "
        "risk, no separate margin financing spread)."
    )


@dataclass
class AssetSeries:
    funding: pd.DataFrame
    price: pd.DataFrame


def load_asset(paths: Paths, asset: str, start: pd.Timestamp) -> AssetSeries:
    funding = pd.read_csv(paths.funding / f"{asset}_funding.csv.gz")
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True, format="mixed")
    funding = funding.loc[funding["timestamp"] >= start].sort_values("timestamp").reset_index(drop=True)
    if funding.empty:
        raise RuntimeError(f"{asset} funding data does not cover the requested window")
    price = load_ohlcv(paths, asset, "1h").loc[start:].reset_index()
    if price.empty:
        raise RuntimeError(f"{asset} 1h price data does not cover the requested window")
    return AssetSeries(funding=funding, price=price)


def build_signal(funding: pd.DataFrame, lookback: int, entry_th: float, exit_th: float) -> pd.DataFrame:
    frame = funding.copy()
    frame["rolling_mean"] = frame["funding_rate"].rolling(lookback, min_periods=lookback).mean()
    frame = frame.dropna(subset=["rolling_mean"]).reset_index(drop=True)
    hedged = False
    state = []
    for value in frame["rolling_mean"]:
        if not hedged and value >= entry_th:
            hedged = True
        elif hedged and value < exit_th:
            hedged = False
        state.append(hedged)
    frame["hedged"] = state
    return frame


def simulate_carry(
    signal: pd.DataFrame,
    initial_capital: float,
    entry_cost: float,
    exit_cost: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate the timed delta-neutral carry harvest. Returns (equity, trade_log)."""
    equity_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    capital = initial_capital
    was_hedged = False
    entry_time = None
    entry_capital = None
    n_prints_in_trade = 0
    funding_collected_in_trade = 0.0
    for row in signal.itertuples(index=False):
        ts = pd.Timestamp(row.timestamp)
        is_hedged = bool(row.hedged)
        if is_hedged and not was_hedged:
            capital *= (1 - entry_cost)
            entry_time = ts
            entry_capital = capital
            n_prints_in_trade = 0
            funding_collected_in_trade = 0.0
        if is_hedged:
            funding = float(row.funding_rate)
            capital *= (1 + funding)
            n_prints_in_trade += 1
            funding_collected_in_trade += funding
        if was_hedged and not is_hedged:
            capital *= (1 - exit_cost)
            trade_rows.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "n_funding_prints": n_prints_in_trade,
                    "hold_hours": n_prints_in_trade * 8,
                    "capital_at_entry": entry_capital,
                    "capital_at_exit": capital,
                    "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                    "gross_funding_collected": funding_collected_in_trade,
                }
            )
        equity_rows.append({"timestamp": ts, "hedged": is_hedged, "capital": capital})
        was_hedged = is_hedged
    if was_hedged:
        capital *= (1 - exit_cost)
        trade_rows.append(
            {
                "entry_time": entry_time,
                "exit_time": pd.Timestamp(signal["timestamp"].iloc[-1]),
                "n_funding_prints": n_prints_in_trade,
                "hold_hours": n_prints_in_trade * 8,
                "capital_at_entry": entry_capital,
                "capital_at_exit": capital,
                "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                "gross_funding_collected": funding_collected_in_trade,
                "note": "forced_close_at_sample_end",
            }
        )
    equity = pd.DataFrame(equity_rows)
    trades = pd.DataFrame(trade_rows)
    return equity, trades


def simulate_always_on_carry(
    signal: pd.DataFrame, initial_capital: float, entry_cost: float, exit_cost: float
) -> pd.DataFrame:
    capital = initial_capital * (1 - entry_cost)
    rows = []
    for row in signal.itertuples(index=False):
        capital *= (1 + float(row.funding_rate))
        rows.append({"timestamp": pd.Timestamp(row.timestamp), "capital": capital})
    equity = pd.DataFrame(rows)
    if not equity.empty:
        equity.loc[equity.index[-1], "capital"] *= (1 - exit_cost)
    return equity


def simulate_buy_and_hold(price: pd.DataFrame, initial_capital: float, one_way_cost: float) -> pd.DataFrame:
    entry_price = float(price["open"].iloc[0]) * (1 + one_way_cost)
    units = initial_capital / entry_price
    frame = price[["timestamp", "close"]].copy()
    frame["capital"] = units * frame["close"]
    return frame[["timestamp", "capital"]]


def simulate_daily_dca(price: pd.DataFrame, initial_capital: float, one_way_cost: float) -> pd.DataFrame:
    hourly = price.copy()
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"], utc=True)
    contribution_slots = hourly.loc[hourly["timestamp"].dt.hour == 9].reset_index(drop=True)
    if contribution_slots.empty:
        raise RuntimeError("No 09:00 UTC contribution slots found for DCA benchmark")
    tranche = initial_capital / len(contribution_slots)
    units = 0.0
    cash = 0.0
    scheduled = set(contribution_slots["timestamp"])
    price_map = hourly.set_index("timestamp")[["open", "close"]]
    rows = []
    for ts, row in price_map.iterrows():
        if ts in scheduled:
            cash += tranche
            execution_price = float(row["open"]) * (1 + one_way_cost)
            units += cash / execution_price
            cash = 0.0
        rows.append({"timestamp": ts, "capital": units * float(row["close"]) + cash})
    return pd.DataFrame(rows)


def sharpe_from_period_returns(period_returns: np.ndarray, bars_per_year: float, rf_per_bar: float = 0.0) -> float:
    excess = period_returns - rf_per_bar
    if excess.std(ddof=0) == 0 or len(excess) < 2:
        return 0.0
    return float((excess.mean() / excess.std(ddof=0)) * np.sqrt(bars_per_year))


def sortino_from_period_returns(period_returns: np.ndarray, bars_per_year: float, rf_per_bar: float = 0.0) -> float:
    excess = period_returns - rf_per_bar
    downside = np.minimum(excess, 0.0)
    downside_dev = np.sqrt(np.mean(downside**2))
    if downside_dev == 0 or len(excess) < 2:
        return 0.0
    return float((excess.mean() / downside_dev) * np.sqrt(bars_per_year))


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


def summarize_capital_curve(name: str, asset: str, equity: pd.DataFrame, initial_capital: float, is_hedged_curve: bool) -> dict:
    if equity.empty:
        return {"strategy": name, "asset": asset, "final_capital": np.nan}
    final_capital = float(equity["capital"].iloc[-1])
    total_return = final_capital / initial_capital - 1.0
    if is_hedged_curve and "hedged" in equity.columns:
        period_returns = equity["capital"].pct_change().fillna(0.0).to_numpy()
    else:
        period_returns = equity["capital"].pct_change().dropna().to_numpy()
    bars_per_year = 365.25 * 3  # 8h bars
    sharpe = sharpe_from_period_returns(period_returns, bars_per_year)
    sortino = sortino_from_period_returns(period_returns, bars_per_year)
    mdd = max_drawdown(equity["capital"])
    return {
        "strategy": name,
        "asset": asset,
        "final_capital": final_capital,
        "total_return_pct": total_return * 100,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": mdd * 100,
    }


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    start = pd.Timestamp(config.sample_start)
    series = load_asset(paths, asset, start)
    signal = build_signal(series.funding, config.lookback_prints, config.entry_threshold, config.exit_threshold)
    signal["partition"] = signal["timestamp"].apply(partition_label)

    equity, trades = simulate_carry(signal, config.initial_capital, config.entry_cost, config.exit_cost)
    always_on = simulate_always_on_carry(signal, config.initial_capital, config.entry_cost, config.exit_cost)
    bh = simulate_buy_and_hold(series.price, config.initial_capital, ONE_WAY_COST)
    dca = simulate_daily_dca(series.price, config.initial_capital, ONE_WAY_COST)

    summary_rows = [
        {
            "strategy": "cash",
            "asset": asset,
            "final_capital": config.initial_capital,
            "total_return_pct": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown_pct": 0.0,
        },
        summarize_capital_curve("timed_delta_neutral_carry", asset, equity, config.initial_capital, True),
        summarize_capital_curve("always_on_delta_neutral_carry", asset, always_on, config.initial_capital, False),
        summarize_capital_curve("buy_and_hold", asset, bh, config.initial_capital, False),
        summarize_capital_curve("daily_dca", asset, dca, config.initial_capital, False),
    ]

    # doubled-cost hostile check
    doubled_equity, doubled_trades = simulate_carry(signal, config.initial_capital, config.entry_cost * 2, config.exit_cost * 2)
    doubled_final = float(doubled_equity["capital"].iloc[-1]) if not doubled_equity.empty else np.nan

    # best-trade exclusion hostile check
    if not trades.empty and len(trades) > 1:
        best_idx = trades["trade_return"].idxmax()
        excluded_capital = config.initial_capital
        for i, row in trades.iterrows():
            r = row["trade_return"] if i != best_idx else 0.0
            excluded_capital *= (1 + r)
        best_trade_pct_of_pnl = None
        total_pnl = float(equity["capital"].iloc[-1]) - config.initial_capital
        if total_pnl != 0:
            best_trade_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
            best_trade_pct_of_pnl = float(best_trade_pnl / total_pnl) * 100
    else:
        excluded_capital = float(equity["capital"].iloc[-1]) if not equity.empty else np.nan
        best_trade_pct_of_pnl = np.nan

    # partition breakdown for the primary strategy
    partition_rows = []
    for label in ("development_pre_2024", "validation_2024", "test_2025_onward"):
        part_signal = signal.loc[signal["partition"] == label]
        if part_signal.empty:
            partition_rows.append({"asset": asset, "partition": label, "n_prints": 0, "final_capital": np.nan})
            continue
        part_equity, part_trades = simulate_carry(part_signal.reset_index(drop=True), config.initial_capital, config.entry_cost, config.exit_cost)
        final = float(part_equity["capital"].iloc[-1]) if not part_equity.empty else np.nan
        partition_rows.append(
            {
                "asset": asset,
                "partition": label,
                "n_prints": len(part_signal),
                "n_trades": len(part_trades),
                "final_capital": final,
                "total_return_pct": (final / config.initial_capital - 1.0) * 100 if final == final else np.nan,
            }
        )

    time_hedged_pct = float(signal["hedged"].mean()) * 100

    return {
        "asset": asset,
        "summary_rows": summary_rows,
        "trades": trades,
        "n_trades": len(trades),
        "time_hedged_pct": time_hedged_pct,
        "doubled_cost_final": doubled_final,
        "best_trade_exclusion_final": excluded_capital,
        "best_trade_pct_of_pnl": best_trade_pct_of_pnl,
        "partition_rows": partition_rows,
        "equity": equity,
    }


def run_sensitivity(paths: Paths, config: StudyConfig) -> pd.DataFrame:
    rows = []
    start = pd.Timestamp(config.sample_start)
    for asset in UNIVERSE:
        series = load_asset(paths, asset, start)
        for lookback, entry_th, exit_th in SENSITIVITY_GRID:
            signal = build_signal(series.funding, lookback, entry_th, exit_th)
            equity, trades = simulate_carry(signal, config.initial_capital, config.entry_cost, config.exit_cost)
            final = float(equity["capital"].iloc[-1]) if not equity.empty else np.nan
            rows.append(
                {
                    "asset": asset,
                    "lookback_prints": lookback,
                    "entry_threshold": entry_th,
                    "exit_threshold": exit_th,
                    "n_trades": len(trades),
                    "final_capital": final,
                    "total_return_pct": (final / config.initial_capital - 1.0) * 100 if final == final else np.nan,
                }
            )
    return pd.DataFrame(rows)


def classify_verdict(asset_result: dict, initial_capital: float) -> str:
    summary = {row["strategy"]: row for row in asset_result["summary_rows"]}
    primary_final = summary["timed_delta_neutral_carry"]["final_capital"]
    bh_final = summary["buy_and_hold"]["final_capital"]
    dca_final = summary["daily_dca"]["final_capital"]
    always_on_final = summary["always_on_delta_neutral_carry"]["final_capital"]
    beats_cash = primary_final > initial_capital
    beats_always_on = primary_final > always_on_final
    survives_doubled_cost = asset_result["doubled_cost_final"] > initial_capital
    survives_exclusion = asset_result["best_trade_exclusion_final"] > initial_capital
    concentration_ok = (
        asset_result["best_trade_pct_of_pnl"] is None
        or np.isnan(asset_result["best_trade_pct_of_pnl"])
        or abs(asset_result["best_trade_pct_of_pnl"]) < 100
    )
    if beats_cash and beats_always_on and survives_doubled_cost and survives_exclusion and concentration_ok:
        return "CANDIDATE"
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


def write_report(output: Path, manifest: dict, all_results: dict, sensitivity: pd.DataFrame) -> None:
    lines = ["# Delta-Neutral Single-Asset Funding-Carry Harvest Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {manifest['config']['primary_rule']}")
    lines.append("")
    lines.append("## Honesty disclosures")
    lines.append("- No margin/borrow financing spread modeled for the short-perp leg beyond the funding print itself.")
    lines.append("- Assumed a continuously maintained 1:1 hedge with no basis or liquidation risk while positioned.")
    lines.append("- Real data only: Binance real 8h funding history + real 1h spot OHLCV, already cached in this repo.")
    lines.append("")
    lines.append("## Per-asset results")
    lines.append("")
    for asset, result in all_results.items():
        lines.append(f"### {asset}")
        summary_df = pd.DataFrame(result["summary_rows"])
        lines.append(dataframe_to_markdown(summary_df))
        lines.append("")
        lines.append(
            f"- Trades: **{result['n_trades']}**, time hedged: **{result['time_hedged_pct']:.1f}%**"
        )
        lines.append(f"- Doubled-cost final capital: **${result['doubled_cost_final']:.2f}**")
        lines.append(
            f"- Best-trade-exclusion final capital: **${result['best_trade_exclusion_final']:.2f}**"
            f" (best trade = {result['best_trade_pct_of_pnl']}% of total PnL)"
            if result["best_trade_pct_of_pnl"] is not None and not (isinstance(result["best_trade_pct_of_pnl"], float) and np.isnan(result["best_trade_pct_of_pnl"]))
            else f"- Best-trade-exclusion final capital: **${result['best_trade_exclusion_final']:.2f}**"
        )
        lines.append(f"- Verdict: **{result['verdict']}**")
        lines.append("")
        lines.append("Partition breakdown:")
        lines.append(dataframe_to_markdown(pd.DataFrame(result["partition_rows"])))
        lines.append("")
    lines.append("## Sensitivity grid (final capital, $10,000 start)")
    lines.append(dataframe_to_markdown(sensitivity))
    lines.append("")
    lines.append("## Overall verdict")
    verdicts = [result["verdict"] for result in all_results.values()]
    n_candidate = sum(1 for v in verdicts if v == "CANDIDATE")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared all gates (beat cash, beat always-on carry, "
                  f"survive doubled cost, survive best-trade exclusion, concentration < 100% of PnL).")
    if n_candidate == 0:
        lines.append("\n**REJECTED** — no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**PROMISING** — every asset cleared every gate; still subject to Sharpe-rubric and "
                      "multiple-testing scrutiny before any deployment claim.")
    else:
        lines.append("\n**PROMISING BUT INCONCLUSIVE** — mixed results across assets.")
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


def run_funding_carry_deltaneutral_validation(paths: Paths) -> dict:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "funding_carry_deltaneutral" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)

    config = StudyConfig()
    all_results = {}
    for asset in UNIVERSE:
        result = run_asset_study(paths, asset, config)
        result["verdict"] = classify_verdict(result, config.initial_capital)
        all_results[asset] = result

    sensitivity = run_sensitivity(paths, config)

    summary_frame = pd.concat(
        [pd.DataFrame(r["summary_rows"]) for r in all_results.values()], ignore_index=True
    )
    partition_frame = pd.concat(
        [pd.DataFrame(r["partition_rows"]) for r in all_results.values()], ignore_index=True
    )
    trades_frame = pd.concat(
        [r["trades"].assign(asset=asset) for asset, r in all_results.items() if not r["trades"].empty],
        ignore_index=True,
    ) if any(not r["trades"].empty for r in all_results.values()) else pd.DataFrame()

    summary_frame.to_csv(output / "strategy_summary.csv", index=False, float_format="%.10g")
    partition_frame.to_csv(output / "partition_summary.csv", index=False, float_format="%.10g")
    trades_frame.to_csv(output / "trade_log.csv", index=False, float_format="%.10g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.10g")

    manifest = {
        "config": asdict(config),
        "assets": list(UNIVERSE),
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, all_results, sensitivity)
    print(f"Delta-neutral funding-carry validation written to {output}", flush=True)
    return {"output": str(output), "verdicts": {a: r["verdict"] for a, r in all_results.items()}}
