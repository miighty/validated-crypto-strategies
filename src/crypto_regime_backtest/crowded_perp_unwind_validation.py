from __future__ import annotations

"""Crowded perpetual unwind (funding + open-interest joint extreme, short-only).

Genuinely new mechanism/data for this repo (next_hypotheses.md item #5):
extreme positive funding (crowded levered longs) *combined with* rising open
interest (fresh leverage being added, not just stale positioning) identifies
longs vulnerable to a forced-selling unwind. Distinct from every prior
funding study in this repo:
  - funding_positive_panel_validation.py: LONG on positive funding alone
    (contrarian-momentum long, no OI, REJECTED).
  - funding_carry_deltaneutral_validation.py: delta-neutral (long spot + short
    perp), no directional price bet, no OI (REJECTED).
  - funding_carry_cross_sectional / funding_crossexchange_divergence: L/S
    ranking or cross-venue basis, no OI, no single-asset short (REJECTED).
This study is the first SHORT-ONLY directional study in this repo, and the
first to use real Binance USD-M futures open-interest history (newly fetched
this run via data.binance.vision's public daily-metrics archive:
open_interest_data.py). No proxy/synthetic OI or funding was used; if a
symbol/date is missing from the public archive it is skipped and reported,
never fabricated.

PRIMARY RULE (frozen before this run inspected any joint-extreme results):
  1. Funding extreme: trailing mean of the last 3 completed 8h funding prints
     >= +5bps/8h (0.0005) -- same threshold as the already-rejected single-
     asset funding_positive_panel study, so the only new variables under test
     are the OI filter, the downside-break confirmation, and the short
     direction, not a new funding threshold.
  2. OI rising ("levered build-up"): most recent completed daily open-interest
     snapshot is >= +5% higher than the snapshot 5 days earlier.
  3. Joint extreme: both (1) and (2) true as of a given completed hourly bar
     (funding evaluated on completed prints; OI evaluated on the most recent
     completed daily snapshot strictly before that hour, no lookahead).
  4. Confirmation ("first downside break"): from the first hour the joint
     extreme becomes true, wait for the first hourly candle whose CLOSE is
     below the trailing rolling 24h LOW computed on the prior 24 completed
     bars (shifted, prior-only -- no lookahead). Enter short at the NEXT
     hourly bar's open.
  5. Exit: fixed 48h hold, then flat. A 24h cooldown after any exit before a
     new entry can trigger, to dedupe one crowded episode into one trade.
  6. Real economic accrual while short: funding is RECEIVED by the short
     position on each completed 8h print during the hold (this is a real
     cash flow, included for honesty -- ignoring it would understate the
     strategy's true economics since it is currently betting during a
     POSITIVE-funding regime, which is a tailwind for a short).
  7. Costs: standard round-trip (2 x ONE_WAY_COST = 30bps) charged on
     entry/exit notional, spot-execution-price proxy for a perp short.

Baselines: cash, buy-and-hold, daily DCA, "funding-only" unhedged short
control (condition 1 alone, no OI join, no downside-break confirmation,
same fixed hold), and a seeded random-entry-timing control matching the
primary rule's trade count and holding period.
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

FUNDING_LOOKBACK_PRINTS = 3
FUNDING_THRESHOLD = 0.0005       # +5bps/8h trailing mean
OI_LOOKBACK_DAYS = 5
OI_RISE_THRESHOLD = 0.05         # +5% over 5 days
DOWNSIDE_BREAK_LOOKBACK_HOURS = 24
HOLD_HOURS = 48
COOLDOWN_HOURS = 24
ROUND_TRIP_COST = 2 * ONE_WAY_COST

RANDOM_SEED = 20260901


@dataclass(frozen=True)
class StudyConfig:
    funding_lookback_prints: int = FUNDING_LOOKBACK_PRINTS
    funding_threshold: float = FUNDING_THRESHOLD
    oi_lookback_days: int = OI_LOOKBACK_DAYS
    oi_rise_threshold: float = OI_RISE_THRESHOLD
    downside_break_lookback_hours: int = DOWNSIDE_BREAK_LOOKBACK_HOURS
    hold_hours: int = HOLD_HOURS
    cooldown_hours: int = COOLDOWN_HOURS
    initial_capital: float = STARTING_CAPITAL
    primary_rule: str = (
        "SHORT-ONLY: enter short at next hourly open when (a) trailing mean "
        "of last 3 completed 8h funding prints >= +5bps/8h AND (b) most "
        "recent completed daily open interest is >= +5% higher than 5 days "
        "earlier AND (c) the hourly close breaks below the trailing prior-"
        "only 24h low for the first time since the joint condition became "
        "true. Hold 48h fixed, then flat, 24h cooldown before re-entry. "
        "Funding received each completed 8h print while short. 30bps "
        "round-trip cost."
    )


def load_funding(paths: Paths, asset: str) -> pd.DataFrame:
    funding = pd.read_csv(paths.funding / f"{asset}_funding.csv.gz")
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True, format="mixed")
    return funding.sort_values("timestamp").reset_index(drop=True)


def build_funding_condition(funding: pd.DataFrame, lookback: int, threshold: float) -> pd.Series:
    frame = funding.copy()
    frame["rolling_mean"] = frame["funding_rate"].rolling(lookback, min_periods=lookback).mean()
    frame["condition"] = frame["rolling_mean"] >= threshold
    return frame.set_index("timestamp")["condition"]


def build_oi_condition(oi: pd.DataFrame, lookback_days: int, threshold: float) -> pd.Series:
    frame = oi.copy().reset_index()
    frame = frame.dropna(subset=["sum_open_interest"])
    frame["oi_pct_change"] = frame["sum_open_interest"].pct_change(lookback_days)
    frame["condition"] = frame["oi_pct_change"] >= threshold
    return frame.set_index("timestamp")["condition"]


def hourly_joint_signal(
    price_1h: pd.DataFrame,
    funding_condition: pd.Series,
    oi_condition: pd.Series,
    config: StudyConfig,
) -> pd.DataFrame:
    """Build the hourly frame with joint funding+OI extreme and downside-break entries."""
    frame = price_1h.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "timestamp"})
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    # funding condition: as-of the most recent completed funding print strictly before this hour
    funding_series = funding_condition.sort_index()
    funding_asof = funding_series.reindex(
        funding_series.index.union(frame["timestamp"])
    ).sort_index().ffill().reindex(frame["timestamp"]).to_numpy()
    frame["funding_extreme"] = pd.Series(funding_asof, index=frame.index).fillna(False).astype(bool)

    # OI condition: as-of the most recent completed daily snapshot strictly before this hour
    oi_series = oi_condition.sort_index()
    # shift OI timestamps forward by 1 day so a daily snapshot at 00:00 UTC on day D
    # is only "known" starting some time after D's close; conservatively treat the
    # daily snapshot (last 5-min print of day D) as available from day D+1 00:00 UTC.
    oi_known_from = oi_series.copy()
    oi_known_from.index = oi_known_from.index + pd.Timedelta(days=1)
    oi_asof = oi_known_from.reindex(
        oi_known_from.index.union(frame["timestamp"])
    ).sort_index().ffill().reindex(frame["timestamp"]).to_numpy()
    frame["oi_rising"] = pd.Series(oi_asof, index=frame.index).fillna(False).astype(bool)

    frame["joint_extreme"] = frame["funding_extreme"] & frame["oi_rising"]

    # prior-only rolling 24h low (shifted so current bar is excluded -- no lookahead)
    frame["rolling_low_24h"] = frame["low"].shift(1).rolling(
        config.downside_break_lookback_hours, min_periods=config.downside_break_lookback_hours
    ).min()
    frame["downside_break"] = frame["close"] < frame["rolling_low_24h"]

    # entry: first downside break since joint_extreme most recently became true
    # (armed = joint_extreme currently true and no downside break consumed yet
    #  since it turned true this episode)
    armed = False
    consumed = False
    entries = []
    for joint, breakdown in zip(frame["joint_extreme"], frame["downside_break"]):
        if joint and not armed:
            armed = True
            consumed = False
        if not joint:
            armed = False
            consumed = False
        entry = bool(armed and breakdown and not consumed)
        if entry:
            consumed = True
        entries.append(entry)
    frame["entry_trigger"] = entries
    return frame.set_index("timestamp")


def simulate_short_strategy(
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    config: StudyConfig,
    trigger_column: str = "entry_trigger",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate the short-only strategy with funding accrual while positioned."""
    funding_lookup = funding.set_index("timestamp")["funding_rate"]
    capital = config.initial_capital
    equity_rows = []
    trade_rows = []
    in_position = False
    entry_index = None
    entry_price = None
    entry_time = None
    entry_capital = None
    last_exit_index = -10**9
    funding_collected = 0.0

    timestamps = frame.index.to_list()
    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    triggers = frame[trigger_column].to_numpy()

    for i, ts in enumerate(timestamps):
        if in_position:
            hold_hours = i - entry_index
            if hold_hours >= config.hold_hours:
                exit_price = opens[i]
                gross_return = (entry_price - exit_price) / entry_price  # short: profit when price falls
                capital *= (1 + gross_return)
                capital *= (1 - ONE_WAY_COST)  # exit cost
                trade_rows.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": ts,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "gross_return": gross_return,
                        "funding_collected": funding_collected,
                        "capital_at_entry": entry_capital,
                        "capital_at_exit": capital,
                        "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                    }
                )
                in_position = False
                last_exit_index = i
                entry_index = None
                entry_price = None
                entry_time = None
                entry_capital = None
                funding_collected = 0.0
            else:
                # accrue funding if an 8h print falls at/around this hour
                if ts in funding_lookup.index:
                    rate = float(funding_lookup.loc[ts])
                    capital *= (1 + rate)  # short receives positive funding
                    funding_collected += rate

        if (
            not in_position
            and bool(triggers[i])
            and (i - last_exit_index) >= config.cooldown_hours
        ):
            entry_price = opens[i]
            capital *= (1 - ONE_WAY_COST)  # entry cost
            entry_capital = capital
            entry_index = i
            entry_time = ts
            in_position = True
            funding_collected = 0.0

        equity_rows.append({"timestamp": ts, "capital": capital, "in_position": in_position})

    if in_position:
        exit_price = closes[-1]
        gross_return = (entry_price - exit_price) / entry_price
        capital *= (1 + gross_return)
        capital *= (1 - ONE_WAY_COST)
        trade_rows.append(
            {
                "entry_time": entry_time,
                "exit_time": timestamps[-1],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_return": gross_return,
                "funding_collected": funding_collected,
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
    hourly = price.copy()
    contribution_mask = hourly.index.hour == 9
    slots = hourly.loc[contribution_mask]
    if slots.empty:
        raise RuntimeError("No 09:00 UTC contribution slots found for DCA benchmark")
    tranche = initial_capital / len(slots)
    units = 0.0
    cash = 0.0
    scheduled = set(slots.index)
    rows = []
    for ts, row in hourly.iterrows():
        if ts in scheduled:
            cash += tranche
            execution_price = float(row["open"]) * (1 + ONE_WAY_COST)
            units += cash / execution_price
            cash = 0.0
        rows.append(units * float(row["close"]) + cash)
    return pd.Series(rows, index=hourly.index, name="capital")


def simulate_random_control(
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    config: StudyConfig,
    n_trades: int,
    seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Seeded random short-entry timing, matched trade count and hold length."""
    rng = np.random.default_rng(seed)
    n = len(frame)
    if n_trades == 0 or n < config.hold_hours + config.cooldown_hours + 1:
        return pd.DataFrame(), pd.DataFrame()
    max_start = n - config.hold_hours - 1
    candidate_starts = rng.choice(np.arange(max_start), size=min(n_trades * 5, max_start), replace=False)
    candidate_starts.sort()
    chosen = []
    last_end = -10**9
    for s in candidate_starts:
        if s - last_end >= config.cooldown_hours:
            chosen.append(s)
            last_end = s + config.hold_hours
        if len(chosen) >= n_trades:
            break
    trigger = np.zeros(n, dtype=bool)
    trigger[chosen] = True
    fake_frame = frame.copy()
    fake_frame["entry_trigger"] = trigger
    return simulate_short_strategy(fake_frame, funding, config, trigger_column="entry_trigger")


def sharpe_from_period_returns(period_returns: np.ndarray, bars_per_year: float, rf_per_bar: float = 0.0) -> float:
    excess = period_returns - rf_per_bar
    if len(excess) < 2 or excess.std(ddof=0) == 0:
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


def top_trade_pct_of_pnl(trades: pd.DataFrame, initial_capital: float, final_capital: float) -> float | None:
    if trades.empty or len(trades) < 1:
        return None
    total_pnl = final_capital - initial_capital
    if total_pnl == 0:
        return None
    best_idx = trades["trade_return"].abs().idxmax()
    best_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
    return float(best_pnl / total_pnl) * 100


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    price_1h = load_ohlcv(paths, asset, "1h")
    funding = load_funding(paths, asset)
    oi = load_oi(paths, asset)

    funding_condition = build_funding_condition(funding, config.funding_lookback_prints, config.funding_threshold)
    oi_condition = build_oi_condition(oi, config.oi_lookback_days, config.oi_rise_threshold)

    # restrict to the window where OI data actually exists (real-data-only, no fabrication before OI coverage starts)
    oi_start = oi.index.min()
    price_window = price_1h.loc[price_1h.index >= oi_start]
    if price_window.empty:
        raise RuntimeError(f"{asset}: no price data after OI coverage start {oi_start}")

    frame = hourly_joint_signal(price_window, funding_condition, oi_condition, config)
    frame["partition"] = [partition_label(ts) for ts in frame.index]

    equity, trades = simulate_short_strategy(frame, funding, config)
    equity["capital"] = equity["capital"].astype(float)

    bh = simulate_buy_and_hold(price_window, config.initial_capital)
    dca = simulate_daily_dca(price_window, config.initial_capital)

    # funding-only control: condition (1) alone, no OI, no downside-break confirmation
    funding_only_trigger = frame["funding_extreme"].to_numpy()
    fo_armed = False
    fo_consumed = False
    fo_entries = []
    for cond in funding_only_trigger:
        if cond and not fo_armed:
            fo_armed = True
            fo_consumed = False
        if not cond:
            fo_armed = False
        entry = bool(fo_armed and not fo_consumed)
        if entry:
            fo_consumed = True
        fo_entries.append(entry)
    funding_only_frame = frame.copy()
    funding_only_frame["entry_trigger"] = fo_entries
    funding_only_equity, funding_only_trades = simulate_short_strategy(funding_only_frame, funding, config)

    # doubled cost hostile check
    class DoubledConfig:
        pass
    doubled_equity, _ = simulate_short_strategy_doubled_cost(frame, funding, config)

    # best-trade exclusion
    final_capital = float(equity["capital"].iloc[-1])
    if not trades.empty:
        best_idx = trades["trade_return"].abs().idxmax()
        excluded_capital = config.initial_capital
        for i, row in trades.iterrows():
            r = row["trade_return"] if i != best_idx else 0.0
            excluded_capital *= (1 + r)
    else:
        excluded_capital = final_capital
    top_trade_pct = top_trade_pct_of_pnl(trades, config.initial_capital, final_capital)

    # random control matched to trade count
    random_equity, random_trades = simulate_random_control(frame, funding, config, len(trades))

    # partition breakdown
    partition_rows = []
    for label in ("development_pre_2024", "validation_2024", "test_2025_onward"):
        part_trades = trades[
            trades["entry_time"].apply(lambda t: partition_label(t) == label)
        ] if not trades.empty else trades
        partition_rows.append(
            {
                "asset": asset,
                "partition": label,
                "n_trades": len(part_trades),
                "mean_trade_return_pct": float(part_trades["trade_return"].mean() * 100) if len(part_trades) else np.nan,
            }
        )

    return {
        "asset": asset,
        "frame": frame,
        "equity": equity,
        "trades": trades,
        "bh": bh,
        "dca": dca,
        "funding_only_equity": funding_only_equity,
        "funding_only_trades": funding_only_trades,
        "doubled_equity": doubled_equity,
        "excluded_capital": excluded_capital,
        "top_trade_pct": top_trade_pct,
        "random_equity": random_equity,
        "random_trades": random_trades,
        "partition_rows": partition_rows,
        "oi_start": oi_start,
    }


def simulate_short_strategy_doubled_cost(frame: pd.DataFrame, funding: pd.DataFrame, config: StudyConfig):
    # reuse simulate_short_strategy but monkeypatch cost by scaling entry/exit prices
    # simplest: run simulate_short_strategy but multiply ONE_WAY_COST effect manually
    doubled_frame = frame.copy()
    equity, trades = simulate_short_strategy(doubled_frame, funding, config)
    if trades.empty:
        return equity, trades
    # apply an extra round of costs post-hoc: multiply each trade's net multiplier by (1 - 2*ONE_WAY_COST)
    extra_cost_factor = (1 - 2 * ONE_WAY_COST)
    capital = config.initial_capital
    rows = []
    for _, row in trades.iterrows():
        r = row["trade_return"]
        capital *= (1 + r) * extra_cost_factor
        rows.append(capital)
    doubled_final = pd.DataFrame({"capital": rows})
    return doubled_final, trades


def classify_verdict(result: dict, initial_capital: float) -> str:
    primary_final = float(result["equity"]["capital"].iloc[-1])
    bh_final = float(result["bh"].iloc[-1])
    dca_final = float(result["dca"].iloc[-1])
    fo_final = float(result["funding_only_equity"]["capital"].iloc[-1]) if not result["funding_only_equity"].empty else initial_capital
    random_final = float(result["random_equity"]["capital"].iloc[-1]) if not result["random_equity"].empty else initial_capital
    doubled_final = float(result["doubled_equity"]["capital"].iloc[-1]) if not result["doubled_equity"].empty else initial_capital

    test_trades = [
        r for r in result["partition_rows"] if r["partition"] == "test_2025_onward"
    ]
    has_holdout_trades = bool(test_trades and test_trades[0]["n_trades"] > 0)

    beats_cash = primary_final > initial_capital
    beats_bh = primary_final > bh_final
    beats_dca = primary_final > dca_final
    beats_funding_only = primary_final > fo_final
    beats_random = primary_final > random_final
    survives_doubled_cost = doubled_final > initial_capital
    survives_exclusion = result["excluded_capital"] > initial_capital
    concentration_ok = (
        result["top_trade_pct"] is None or abs(result["top_trade_pct"]) < 20
    )

    gates = {
        "beats_cash": beats_cash,
        "beats_bh": beats_bh,
        "beats_dca": beats_dca,
        "beats_funding_only_control": beats_funding_only,
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
    lines = ["# Crowded Perpetual Unwind (Funding + Open-Interest Joint Extreme, Short-Only) Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {config.primary_rule}")
    lines.append("")
    lines.append("## Data sources")
    lines.append("- Real Binance USD-M perpetual funding history (already cached, `data/funding/*.csv.gz`).")
    lines.append("- Real Binance spot 1h OHLCV (already cached, `data/raw/*_1h.csv.gz`) as execution/price proxy for the perp.")
    lines.append(
        "- Real Binance USD-M futures open interest, newly fetched this run from the public "
        "`data.binance.vision` daily-metrics archive (`data/open_interest/*_oi_daily.csv.gz`). "
        "No synthetic/proxy OI used; missing archive days are skipped, never fabricated."
    )
    lines.append("")
    lines.append("## Per-asset results")
    for asset, result in all_results.items():
        lines.append(f"### {asset}")
        lines.append(f"- OI data starts: **{result['oi_start'].date()}** (real archive coverage limit)")
        lines.append(f"- Trades: **{len(result['trades'])}**")
        primary_final = float(result["equity"]["capital"].iloc[-1])
        bh_final = float(result["bh"].iloc[-1])
        dca_final = float(result["dca"].iloc[-1])
        fo_final = float(result["funding_only_equity"]["capital"].iloc[-1]) if not result["funding_only_equity"].empty else config.initial_capital
        random_final = float(result["random_equity"]["capital"].iloc[-1]) if not result["random_equity"].empty else config.initial_capital
        doubled_final = float(result["doubled_equity"]["capital"].iloc[-1]) if not result["doubled_equity"].empty else config.initial_capital
        lines.append(f"- Primary final capital: **${primary_final:,.2f}** (start ${config.initial_capital:,.0f})")
        lines.append(f"- Buy-and-hold final: **${bh_final:,.2f}**")
        lines.append(f"- Daily DCA final: **${dca_final:,.2f}**")
        lines.append(f"- Funding-only control (no OI/no downside-break) final: **${fo_final:,.2f}** ({len(result['funding_only_trades'])} trades)")
        lines.append(f"- Seeded random-timing control final: **${random_final:,.2f}** ({len(result['random_trades'])} trades)")
        lines.append(f"- Doubled-cost final: **${doubled_final:,.2f}**")
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


def run_crowded_perp_unwind_validation(paths: Paths) -> dict:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "crowded_perp_unwind" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)

    config = StudyConfig()
    all_results = {}
    for asset in UNIVERSE:
        result = run_asset_study(paths, asset, config)
        all_results[asset] = result
        print(f"{asset}: {len(result['trades'])} trades, final capital "
              f"${float(result['equity']['capital'].iloc[-1]):,.2f}")

    write_report(output, all_results, config)

    trades_frame = pd.concat(
        [r["trades"].assign(asset=asset) for asset, r in all_results.items() if not r["trades"].empty],
        ignore_index=True,
    ) if any(not r["trades"].empty for r in all_results.values()) else pd.DataFrame()
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
