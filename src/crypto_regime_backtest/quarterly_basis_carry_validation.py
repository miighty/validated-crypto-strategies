"""EXP-2026-08-31-QBASIS-001: BTC/ETH quarterly futures cash-and-carry basis validation.

Hypothesis: Binance quarterly futures trade at a premium to spot (contango) that
mechanically converges to zero at contract expiry. A delta-neutral cash-and-carry
trade (long spot + short the current-quarter future, equal notional) captures this
annualized basis as a deterministic-at-expiry yield, net of round-trip costs -- a
genuinely new data source (Binance quarterly/dated futures term structure, never
used in this repo, distinct from perpetual funding) and new mechanism (basis
convergence at a fixed known date, not a persistence bet like the already-rejected
funding-carry studies).

Real data only: Binance public continuousKlines (CURRENT_QUARTER) + already-cached
Binance spot daily OHLCV. No proxy/synthetic basis.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv, sha256
from .funding_negative_panel_validation import dataframe_to_markdown

CONTINUOUS_ENDPOINT = "https://fapi.binance.com/fapi/v1/continuousKlines"
UNIVERSE = ("BTC", "ETH")  # Binance only lists dated/quarterly futures for BTC and ETH
SAMPLE_START = pd.Timestamp("2021-02-01T00:00:00Z")  # BTC quarterly futures launched ~2021-02-04
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-06-01T00:00:00Z")
PRIMARY_ANNUALIZED_THRESHOLD = 0.08  # 8% annualized basis to trigger a carry entry
COOLDOWN_DAYS = 1
RAW_COLS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
]


def _request_json(params: dict[str, object], attempts: int = 6) -> list:
    url = f"{CONTINUOUS_ENDPOINT}?{urllib.parse.urlencode(params)}"
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "crypto-regime-validation/0.1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(f"Binance continuousKlines request failed: {url}") from error
            time.sleep(min(2 ** attempt, 16))
    raise AssertionError("unreachable")


def fetch_quarterly_futures(pair: str, start: pd.Timestamp, end_exclusive: pd.Timestamp) -> pd.DataFrame:
    cursor = int(start.timestamp() * 1000)
    end_ms = int(end_exclusive.timestamp() * 1000)
    rows: list[list[object]] = []
    while cursor < end_ms:
        batch = _request_json({
            "pair": pair,
            "contractType": "CURRENT_QUARTER",
            "interval": "1d",
            "startTime": cursor,
            "endTime": end_ms - 1,
            "limit": 1000,
        })
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + 86_400_000
        if next_cursor <= cursor:
            raise RuntimeError(f"Pagination stalled for {pair} quarterly futures")
        cursor = next_cursor
        time.sleep(0.05)
    frame = pd.DataFrame(rows, columns=RAW_COLS)
    if frame.empty:
        raise RuntimeError(f"No quarterly futures candles returned for {pair}")
    frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return frame[["timestamp", "open", "high", "low", "close", "volume"]]


def quarterly_expiry_dates(start_year: int, end_year: int) -> list[pd.Timestamp]:
    """Binance quarterly contracts settle the last Friday of Mar/Jun/Sep/Dec, 08:00 UTC."""
    expiries = []
    for year in range(start_year, end_year + 1):
        for month in (3, 6, 9, 12):
            last_day = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(1)
            offset = (last_day.weekday() - 4) % 7  # 4 = Friday
            last_friday = last_day - pd.Timedelta(days=offset)
            expiries.append(pd.Timestamp(last_friday.date(), tz="UTC") + pd.Timedelta(hours=8))
    return sorted(expiries)


def days_to_next_expiry(ts: pd.Timestamp, expiries: list[pd.Timestamp]) -> float:
    for expiry in expiries:
        if expiry > ts:
            return (expiry - ts).total_seconds() / 86400.0
    raise RuntimeError(f"No expiry found after {ts}")


def load_basis_panel(paths: Paths, asset: str) -> pd.DataFrame:
    cache_dir = paths.data / "quarterly_futures"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{asset}_quarterly_1d.csv.gz"
    end_exclusive = pd.Timestamp("2026-07-28T00:00:00Z")
    if not cache_path.exists():
        futures = fetch_quarterly_futures(f"{asset}USDT", SAMPLE_START, end_exclusive)
        futures.to_csv(cache_path, index=False, compression="gzip", float_format="%.10g")
    else:
        futures = pd.read_csv(cache_path, parse_dates=["timestamp"])
        futures["timestamp"] = pd.to_datetime(futures["timestamp"], utc=True)

    spot = load_ohlcv(paths, asset, "1d").reset_index()
    spot["timestamp"] = pd.to_datetime(spot["timestamp"], utc=True)
    spot = spot.loc[spot["timestamp"] >= SAMPLE_START].reset_index(drop=True)

    merged = pd.merge(
        futures.rename(columns={"open": "fut_open", "close": "fut_close"})[["timestamp", "fut_open", "fut_close"]],
        spot.rename(columns={"open": "spot_open", "close": "spot_close"})[["timestamp", "spot_open", "spot_close"]],
        on="timestamp", how="inner",
    ).sort_values("timestamp").reset_index(drop=True)

    expiries = quarterly_expiry_dates(2021, 2027)
    merged["days_to_expiry"] = merged["timestamp"].apply(lambda ts: days_to_next_expiry(ts, expiries))
    merged["basis"] = merged["fut_close"] / merged["spot_close"] - 1.0
    merged["annualized_basis"] = merged["basis"] * (365.0 / merged["days_to_expiry"].clip(lower=1.0))
    merged["expiry"] = merged["timestamp"].apply(
        lambda ts: min(e for e in expiries if e > ts)
    )
    return merged


@dataclass(frozen=True)
class StudyConfig:
    sample_start: str = str(SAMPLE_START)
    validation_start: str = str(VALIDATION_START)
    holdout_start: str = str(HOLDOUT_START)
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    primary_annualized_threshold: float = PRIMARY_ANNUALIZED_THRESHOLD
    cooldown_days: int = COOLDOWN_DAYS
    primary_rule: str = (
        "At each real Binance daily close, if the current-quarter futures contract's annualized"
        " basis (log-linear extrapolation of (future_close/spot_close - 1) to a 365-day year) is"
        " >= 8%, enter a delta-neutral cash-and-carry trade (long spot + short the quarterly future,"
        " equal notional) at next day's open with the full accrued reserve; hold to contract expiry"
        " (basis converges to zero by settlement), realize the captured basis net of 4-leg round-trip"
        " costs (spot buy/sell + futures short/cover), then wait 1 day before re-evaluating."
    )


def build_signal_panel(panel: pd.DataFrame, threshold: float, cooldown_days: int) -> pd.DataFrame:
    triggers = panel.loc[panel["annualized_basis"] >= threshold].copy()
    if triggers.empty:
        return pd.DataFrame(columns=["signal_time", "entry_time", "exit_time", "entry_basis", "days_held"])
    triggers["entry_time"] = triggers["timestamp"] + pd.Timedelta(days=1)
    ts_index = set(panel["timestamp"])
    chosen = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for row in triggers.itertuples(index=False):
        entry_time = pd.Timestamp(row.entry_time)
        if entry_time < next_ok or entry_time not in ts_index:
            continue
        exit_time = pd.Timestamp(row.expiry).normalize() + pd.Timedelta(hours=0)
        # align exit to the nearest available daily bar at/after expiry
        candidates = panel.loc[panel["timestamp"] >= row.expiry, "timestamp"]
        if candidates.empty:
            continue
        exit_time = candidates.iloc[0]
        chosen.append({
            "signal_time": pd.Timestamp(row.timestamp),
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_basis": float(row.basis),
            "entry_annualized_basis": float(row.annualized_basis),
            "days_held": (exit_time - entry_time).total_seconds() / 86400.0,
        })
        next_ok = exit_time + pd.Timedelta(days=cooldown_days)
    return pd.DataFrame(chosen)


def simulate_carry(
    panel: pd.DataFrame, signals: pd.DataFrame, schedule: pd.Series, one_way_cost: float,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    """Delta-neutral: dollar return per trade = captured basis (locked at entry) minus 4-leg costs.

    Because the position is delta-neutral, price path between entry/exit doesn't matter --
    the basis realized at expiry is (approximately) the entry basis (futures converges to spot).
    We charge round-trip cost on both legs (spot + futures) = 4 * one_way_cost on notional.
    """
    cash = 0.0
    ledger_rows = []
    equity_rows = []
    scheduled = schedule.to_dict()
    signal_map = {pd.Timestamp(r.entry_time): r for r in signals.itertuples(index=False)}
    active_exit = None
    active_notional = 0.0
    active_entry_basis = 0.0
    for row in panel.itertuples(index=False):
        ts = pd.Timestamp(row.timestamp)
        cash += float(scheduled.get(ts, 0.0))
        if active_exit is not None and ts == active_exit:
            gross_carry = active_notional * active_entry_basis
            cost = active_notional * one_way_cost * 4
            pnl = gross_carry - cost
            cash += active_notional + pnl
            ledger_rows.append({
                "timestamp": ts, "kind": "carry_exit", "notional": active_notional,
                "entry_basis": active_entry_basis, "gross_carry": gross_carry, "cost": cost, "pnl": pnl,
            })
            active_exit = None
            active_notional = 0.0
            active_entry_basis = 0.0
        signal = signal_map.get(ts)
        if signal is not None and active_exit is None and cash > 0:
            active_notional = cash
            active_entry_basis = float(signal.entry_basis)
            active_exit = pd.Timestamp(signal.exit_time)
            ledger_rows.append({
                "timestamp": ts, "kind": "carry_entry", "notional": active_notional,
                "entry_basis": active_entry_basis, "planned_exit": active_exit,
            })
            cash = 0.0
        equity_rows.append({"timestamp": ts, "equity": cash + active_notional})
    ledger = pd.DataFrame(ledger_rows)
    equity = pd.DataFrame(equity_rows)
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else cash
    invested_total = float(schedule.sum())
    net_return = final_equity / invested_total - 1.0 if invested_total else 0.0
    exits = ledger.loc[ledger["kind"].eq("carry_exit")] if not ledger.empty else pd.DataFrame()
    return {
        "strategy": "quarterly_basis_carry",
        "final_equity": final_equity,
        "invested_total": invested_total,
        "net_return": net_return,
        "trade_count": int(len(exits)),
        "win_rate": float((exits["pnl"] > 0).mean()) if not exits.empty else float("nan"),
        "mean_trade_pnl": float(exits["pnl"].mean()) if not exits.empty else float("nan"),
        "total_pnl": float(exits["pnl"].sum()) if not exits.empty else 0.0,
        "top_trade_pnl_share": float(exits["pnl"].max() / exits["pnl"].sum()) if not exits.empty and exits["pnl"].sum() != 0 else float("nan"),
    }, ledger, equity


def simulate_dca(panel: pd.DataFrame, price_col: str, schedule: pd.Series, one_way_cost: float) -> dict[str, object]:
    cash = 0.0
    units = 0.0
    scheduled = schedule.to_dict()
    for row in panel.itertuples(index=False):
        ts = pd.Timestamp(row.timestamp)
        contribution = float(scheduled.get(ts, 0.0))
        if contribution:
            price = float(getattr(row, price_col)) * (1 + one_way_cost)
            units += contribution / price
            cash = 0.0
    final_price = float(panel[price_col.replace("open", "close") if "open" in price_col else price_col].iloc[-1])
    final_equity = units * final_price
    invested_total = float(schedule.sum())
    return {
        "strategy": f"dca_{price_col}",
        "final_equity": final_equity,
        "invested_total": invested_total,
        "net_return": final_equity / invested_total - 1.0 if invested_total else 0.0,
        "trade_count": int((schedule > 0).sum()),
    }


def simulate_cash(schedule: pd.Series) -> dict[str, object]:
    invested_total = float(schedule.sum())
    return {"strategy": "cash", "final_equity": invested_total, "invested_total": invested_total, "net_return": 0.0, "trade_count": 0}


def partition_metrics(panel: pd.DataFrame, signals: pd.DataFrame, schedule: pd.Series, one_way_cost: float) -> pd.DataFrame:
    rows = []
    bounds = [
        ("development", SAMPLE_START, VALIDATION_START),
        ("validation", VALIDATION_START, HOLDOUT_START),
        ("holdout", HOLDOUT_START, panel["timestamp"].max() + pd.Timedelta(days=1)),
    ]
    for name, start, end in bounds:
        sub_signals = signals.loc[(signals["entry_time"] >= start) & (signals["entry_time"] < end)] if not signals.empty else signals
        sub_panel = panel.loc[(panel["timestamp"] >= start) & (panel["timestamp"] < end)]
        sub_schedule = schedule.loc[(schedule.index >= start) & (schedule.index < end)]
        if sub_panel.empty:
            rows.append({"partition": name, "trade_count": 0})
            continue
        result, _, _ = simulate_carry(sub_panel.reset_index(drop=True), sub_signals, sub_schedule, one_way_cost)
        result["partition"] = name
        rows.append(result)
    return pd.DataFrame(rows)


def run_quarterly_basis_carry_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "quarterly_basis_carry" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    all_rows = []
    per_asset_ledgers = []
    per_asset_partitions = []
    manifest_assets = {}

    for asset in UNIVERSE:
        panel = load_basis_panel(paths, asset)
        panel = panel.loc[panel["timestamp"] >= SAMPLE_START].reset_index(drop=True)
        signals = build_signal_panel(panel, config.primary_annualized_threshold, config.cooldown_days)

        slots = panel.loc[panel["timestamp"].dt.hour == 0, "timestamp"]
        tranche = config.initial_capital / len(slots)
        schedule = pd.Series(tranche, index=slots, name="contribution_usd")

        primary, ledger, equity = simulate_carry(panel, signals, schedule, config.one_way_cost)
        doubled = simulate_carry(panel, signals, schedule, config.one_way_cost * 2)[0]
        doubled["strategy"] = "quarterly_basis_carry_doubled_cost"
        no_delay = simulate_carry(panel, signals, schedule, 0.0)[0]
        no_delay["strategy"] = "quarterly_basis_carry_zero_cost"

        # hostile: exclude the single best trade (by realized pnl) and re-simulate
        if not ledger.empty and (ledger["kind"] == "carry_exit").any():
            exits = ledger.loc[ledger["kind"].eq("carry_exit")].reset_index(drop=True)
            best_pos = int(exits["pnl"].idxmax())
            # signals are in the same chronological order as carry_exit rows (one signal per trade)
            trimmed_signals = signals.drop(signals.index[best_pos]) if best_pos < len(signals) else signals
            no_best, _, _ = simulate_carry(panel, trimmed_signals, schedule, config.one_way_cost)
        else:
            no_best = dict(primary)
        no_best["strategy"] = "quarterly_basis_carry_no_best_trade"

        cash_bench = simulate_cash(schedule)
        bh_close = simulate_dca(panel, "spot_close", schedule, config.one_way_cost)
        dca_open = simulate_dca(panel, "spot_open", schedule, config.one_way_cost)
        partitions = partition_metrics(panel, signals, schedule, config.one_way_cost)

        for r in (primary, doubled, no_delay, no_best, cash_bench, bh_close, dca_open):
            r = dict(r)
            r["asset"] = asset
            all_rows.append(r)
        ledger = ledger.assign(asset=asset)
        per_asset_ledgers.append(ledger)
        partitions = partitions.assign(asset=asset)
        per_asset_partitions.append(partitions)

        manifest_assets[asset] = {
            "quarterly_rows": int(len(panel)),
            "quarterly_sample_start": panel["timestamp"].min().isoformat(),
            "quarterly_sample_end": panel["timestamp"].max().isoformat(),
            "signal_count": int(len(signals)),
            "quarterly_futures_sha256": sha256(paths.data / "quarterly_futures" / f"{asset}_quarterly_1d.csv.gz"),
        }

    summary = pd.DataFrame(all_rows)
    trade_log = pd.concat(per_asset_ledgers, ignore_index=True) if per_asset_ledgers else pd.DataFrame()
    partition_frame = pd.concat(per_asset_partitions, ignore_index=True) if per_asset_partitions else pd.DataFrame()

    summary.to_csv(output / "strategy_summary.csv", index=False, float_format="%.10g")
    trade_log.to_csv(output / "trade_log.csv", index=False, float_format="%.10g")
    partition_frame.to_csv(output / "partition_summary.csv", index=False, float_format="%.10g")

    manifest = {"config": asdict(config), "assets": manifest_assets, "synthetic_data_used": False}
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")

    verdict_lines = classify_and_write_report(output, manifest, summary, partition_frame)
    print(f"Quarterly basis carry validation written to {output}", flush=True)
    print("\n".join(verdict_lines), flush=True)
    return summary


def classify_and_write_report(output: Path, manifest: dict, summary: pd.DataFrame, partitions: pd.DataFrame) -> list[str]:
    lines = ["# BTC/ETH Quarterly Futures Basis Cash-and-Carry Validation", "", f"Run artifact: `{output}`", ""]
    lines.append("## Primary rule")
    lines.append("")
    lines.append(f"> {manifest['config']['primary_rule']}")
    lines.append("")
    lines.append("## Result summary (per asset)")
    lines.append("")
    cols = ["asset", "strategy", "final_equity", "invested_total", "net_return", "trade_count", "win_rate", "top_trade_pnl_share"]
    present = [c for c in cols if c in summary.columns]
    lines.append(dataframe_to_markdown(summary[present]))
    lines.append("")
    lines.append("## Partition breakdown")
    lines.append("")
    part_cols = [c for c in ["asset", "partition", "trade_count", "net_return", "win_rate", "top_trade_pnl_share"] if c in partitions.columns]
    lines.append(dataframe_to_markdown(partitions[part_cols]))
    lines.append("")

    verdicts = []
    for asset in UNIVERSE:
        sub = summary.loc[summary["asset"].eq(asset)].set_index("strategy")
        primary_ret = float(sub.loc["quarterly_basis_carry", "net_return"])
        cash_ret = 0.0
        bh_ret = float(sub.loc["dca_spot_close", "net_return"])
        doubled_ret = float(sub.loc["quarterly_basis_carry_doubled_cost", "net_return"]) if "quarterly_basis_carry_doubled_cost" in sub.index else float("nan")
        holdout = partitions.loc[(partitions["asset"].eq(asset)) & (partitions["partition"].eq("holdout"))]
        holdout_trades = int(holdout["trade_count"].iloc[0]) if not holdout.empty else 0
        trade_count = int(sub.loc["quarterly_basis_carry", "trade_count"])
        top_share = sub.loc["quarterly_basis_carry", "top_trade_pnl_share"] if "top_trade_pnl_share" in sub.columns else float("nan")
        verdict = "REJECTED"
        reasons = []
        if trade_count == 0:
            reasons.append("zero signals generated at 8% annualized basis threshold")
        else:
            if primary_ret <= cash_ret:
                reasons.append(f"net_return {primary_ret:.4f} <= cash 0")
            if not np.isnan(doubled_ret) and doubled_ret <= cash_ret:
                reasons.append("fails doubled-cost check (loses to cash)")
            if holdout_trades == 0:
                reasons.append("zero trades in holdout partition (2025-06 onward)")
            if not reasons:
                verdict = "PROMISING BUT INCONCLUSIVE" if primary_ret > cash_ret and primary_ret <= bh_ret else "CANDIDATE"
        verdicts.append((asset, verdict, reasons, primary_ret, bh_ret, trade_count, holdout_trades, top_share))

    lines.append("## Verdict per asset")
    lines.append("")
    for asset, verdict, reasons, primary_ret, bh_ret, trade_count, holdout_trades, top_share in verdicts:
        lines.append(f"- **{asset}**: {verdict} -- carry net_return={primary_ret:.4f} vs spot B&H={bh_ret:.4f}, {trade_count} trades ({holdout_trades} in holdout), top-trade PnL share={top_share:.2f}" if not np.isnan(top_share) else
                      f"- **{asset}**: {verdict} -- carry net_return={primary_ret:.4f} vs spot B&H={bh_ret:.4f}, {trade_count} trades ({holdout_trades} in holdout)")
        for r in reasons:
            lines.append(f"  - {r}")
    lines.append("")
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
    return [f"{a}: {v}" for a, v, *_ in verdicts]
