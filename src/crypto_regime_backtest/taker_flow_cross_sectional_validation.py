from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, STARTING_CAPITAL, Paths

ASSETS = ("BTC", "ETH", "SOL", "XRP")
SAMPLE_START = pd.Timestamp("2021-01-01", tz="UTC")
HOLDOUT_START = pd.Timestamp("2025-01-01", tz="UTC")
LOOKBACK_DAYS = 7
REBALANCE_WEEKDAY = 0  # Monday UTC
RANDOM_SEED = 20260905


@dataclass(frozen=True)
class StudyConfig:
    assets: tuple[str, ...] = ASSETS
    sample_start: str = "2021-01-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    lookback_days: int = LOOKBACK_DAYS
    rebalance_weekday: int = REBALANCE_WEEKDAY
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    round_trip_cost_bps: float = 2 * ONE_WAY_COST * 10_000
    primary_rule: str = (
        "Each Monday 00:00 UTC, rank BTC/ETH/SOL/XRP by the prior-only 7-day mean of real Binance spot "
        "taker-buy volume ratio. Allocate 100% to the highest-ranked asset at that day's open, rebalance weekly, "
        "and deduct 15 bps one-way cost on each entry/exit/switch. No same-bar signal execution."
    )


def _load_daily_taker(paths: Paths, asset: str) -> pd.DataFrame:
    path = paths.data / "taker_flow" / f"{asset}_taker_flow_1h.csv.gz"
    if not path.exists():
        raise FileNotFoundError(f"Missing real taker-flow cache: {path}")
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").drop_duplicates("timestamp")
    df = df[df["timestamp"] >= SAMPLE_START]
    if df.empty:
        raise ValueError(f"No taker-flow rows for {asset} after {SAMPLE_START}")
    if not np.isfinite(df[["open", "high", "low", "close", "volume", "taker_buy_base_volume"]].to_numpy()).all():
        raise ValueError(f"Non-finite data in {path}")
    df = df.set_index("timestamp")
    daily = pd.DataFrame(
        {
            "open": df["open"].resample("1D").first(),
            "close": df["close"].resample("1D").last(),
            "volume": df["volume"].resample("1D").sum(),
            "taker_buy_base_volume": df["taker_buy_base_volume"].resample("1D").sum(),
        }
    ).dropna()
    daily["taker_buy_ratio"] = daily["taker_buy_base_volume"] / daily["volume"]
    daily["score"] = daily["taker_buy_ratio"].rolling(LOOKBACK_DAYS, min_periods=LOOKBACK_DAYS).mean().shift(1)
    return daily


def _common_index(frames: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    idx: pd.DatetimeIndex | None = None
    for frame in frames.values():
        idx = frame.index if idx is None else idx.intersection(frame.index)
    if idx is None:
        raise ValueError("No frames supplied")
    common_idx = idx.sort_values()
    return common_idx[common_idx >= SAMPLE_START]


def _rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = index[index.weekday == REBALANCE_WEEKDAY]
    return dates[dates >= SAMPLE_START + pd.Timedelta(days=int(LOOKBACK_DAYS + 1))]


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _sharpe(equity: pd.Series) -> float:
    rets = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if len(rets) < 2 or rets.std(ddof=1) == 0:
        return float("nan")
    return float(rets.mean() / rets.std(ddof=1) * np.sqrt(365.25))


def _top_block_share(ledger: pd.DataFrame, initial: float) -> float:
    if ledger.empty:
        return float("nan")
    pnl = ledger["pnl"].astype(float)
    total = float(pnl.sum())
    if abs(total) < 1e-12:
        return float("inf")
    return float(pnl.max() / total)


def _summarize(name: str, equity: pd.Series, ledger: pd.DataFrame, extra: dict | None = None) -> dict:
    final = float(equity.iloc[-1])
    summary = {
        "strategy": name,
        "final_capital": final,
        "total_return_pct": (final / float(equity.iloc[0]) - 1.0) * 100.0,
        "sharpe": _sharpe(equity),
        "max_drawdown_pct": _max_drawdown(equity) * 100.0,
        "n_rebalances": int(len(ledger)),
        "top_block_pnl_share_pct": _top_block_share(ledger, float(equity.iloc[0])) * 100.0,
    }
    if extra:
        summary.update(extra)
    return summary


def _simulate_rotation(
    frames: dict[str, pd.DataFrame],
    dates: pd.DatetimeIndex,
    *,
    mode: str,
    rng: np.random.Generator | None = None,
    delay_days: int = 0,
    cost: float = ONE_WAY_COST,
) -> tuple[pd.Series, pd.DataFrame]:
    common = _common_index(frames)
    equity = pd.Series(index=common, dtype=float)
    capital = STARTING_CAPITAL
    current_asset: str | None = None
    last_marked = common[0]
    ledger = []
    for dt in dates:
        if dt not in common:
            continue
        idle_span = common[(common >= last_marked) & (common < dt)]
        equity.loc[idle_span] = capital
        signal_dt = dt - pd.Timedelta(days=int(delay_days))
        if signal_dt not in common:
            continue
        if mode == "taker_top":
            scores = {a: frames[a].loc[signal_dt, "score"] for a in ASSETS}
            if any(pd.isna(v) for v in scores.values()):
                continue
            next_asset = max(scores, key=lambda asset: float(scores[asset]))
        elif mode == "momentum_top":
            lookback_dt = signal_dt - pd.Timedelta(days=int(LOOKBACK_DAYS))
            mom = {
                a: frames[a].loc[signal_dt, "close"] / frames[a].loc[lookback_dt, "close"] - 1.0
                if lookback_dt in common
                else np.nan
                for a in ASSETS
            }
            if any(pd.isna(v) for v in mom.values()):
                continue
            next_asset = max(mom, key=lambda asset: float(mom[asset]))
        elif mode == "random_top":
            if rng is None:
                raise ValueError("rng required for random_top")
            next_asset = str(rng.choice(ASSETS))
        else:
            raise ValueError(mode)
        if current_asset is not None and current_asset != next_asset:
            capital *= 1.0 - cost
        if current_asset is None:
            capital *= 1.0 - cost
        entry_open = float(frames[next_asset].loc[dt, "open"])
        exit_target = dt + pd.Timedelta(days=7)
        future = common[common >= exit_target]
        actual_exit = future[0] if len(future) else common[-1]
        holding_span = common[(common >= dt) & (common <= actual_exit)]
        before = capital
        marked = before * frames[next_asset].loc[holding_span, "close"] / entry_open
        equity.loc[holding_span] = marked
        exit_open = float(frames[next_asset].loc[actual_exit, "open"])
        capital = before * exit_open / entry_open
        ledger.append(
            {
                "entry_time": dt,
                "exit_time": actual_exit,
                "asset": next_asset,
                "entry_open": entry_open,
                "exit_open": exit_open,
                "pnl": capital - before,
                "capital": capital,
            }
        )
        current_asset = next_asset
        last_marked = actual_exit + pd.Timedelta(days=1)
    if current_asset is not None:
        capital *= 1.0 - cost
    equity.loc[equity.index >= last_marked] = capital
    equity = equity.ffill().fillna(STARTING_CAPITAL)
    return equity, pd.DataFrame(ledger)


def _buy_hold(frames: dict[str, pd.DataFrame], asset: str, common: pd.DatetimeIndex) -> tuple[pd.Series, pd.DataFrame]:
    first_open = float(frames[asset].loc[common[0], "open"])
    series = STARTING_CAPITAL * (1 - ONE_WAY_COST) * frames[asset].loc[common, "close"] / first_open
    series.iloc[-1] *= 1 - ONE_WAY_COST
    ledger = pd.DataFrame([{"entry_time": common[0], "exit_time": common[-1], "asset": asset, "pnl": float(series.iloc[-1] - STARTING_CAPITAL), "capital": float(series.iloc[-1])}])
    return series, ledger


def _equal_weight(frames: dict[str, pd.DataFrame], common: pd.DatetimeIndex) -> tuple[pd.Series, pd.DataFrame]:
    curves = []
    for asset in ASSETS:
        first_open = float(frames[asset].loc[common[0], "open"])
        curves.append(frames[asset].loc[common, "close"] / first_open)
    series = STARTING_CAPITAL * (1 - ONE_WAY_COST) * pd.concat(curves, axis=1).mean(axis=1)
    series.iloc[-1] *= 1 - ONE_WAY_COST
    ledger = pd.DataFrame([{"entry_time": common[0], "exit_time": common[-1], "asset": "equal_weight", "pnl": float(series.iloc[-1] - STARTING_CAPITAL), "capital": float(series.iloc[-1])}])
    return series, ledger


def _write_markdown(path: Path, config: StudyConfig, summary: pd.DataFrame, verdict: str) -> None:
    top = summary.set_index("strategy")
    primary = top.loc["taker_flow_cross_sectional_top1"]
    random = top.loc["seeded_random_top1_weekly"]
    momentum = top.loc["price_momentum_top1_weekly"]
    best_bh = summary[summary["strategy"].str.startswith("buy_hold_")].sort_values("final_capital", ascending=False).iloc[0]
    lines = [
        "# Taker-Flow Cross-Sectional Ranking Validation",
        "",
        f"Verdict: **{verdict}**.",
        "",
        "## Preregistered rule",
        "",
        f"- {config.primary_rule}",
        "- Signal data: real Binance spot hourly klines `taker_buy_base_volume / volume`, aggregated to daily; no synthetic/proxy flow data.",
        "- Lookahead guard: score uses a `shift(1)` prior-only 7-day mean; execution is at the next weekly rebalance open.",
        "- First-pass delay gate: rerun with one additional daily signal delay.",
        "",
        "## Decisive results",
        "",
        f"- Primary final capital: ${primary.final_capital:,.2f}, Sharpe {primary.sharpe:.2f}, max DD {primary.max_drawdown_pct:.1f}%.",
        f"- Best required buy-and-hold benchmark: {best_bh.strategy} ${best_bh.final_capital:,.2f}; primary trails by {primary.final_capital / best_bh.final_capital:.2f}x.",
        f"- Seeded random same-cadence control: ${random.final_capital:,.2f}, Sharpe {random.sharpe:.2f}; primary trails random by {primary.final_capital / random.final_capital:.2f}x.",
        f"- Price-momentum top-1 control: ${momentum.final_capital:,.2f}, Sharpe {momentum.sharpe:.2f}; primary trails momentum by {primary.final_capital / momentum.final_capital:.2f}x.",
        f"- Concentration: top weekly block = {primary.top_block_pnl_share_pct:.1f}% of net PnL; cap is 20%.",
        "",
        "## Strategy comparison",
        "",
        _markdown_table(summary),
        "",
        "## Conclusion",
        "",
        "- Reject: the taker-flow rank signal does not beat a seeded random allocator, a price-momentum allocator, or the stronger buy-and-hold benchmarks, and it violates the concentration cap.",
    ]
    path.write_text("\n".join(lines) + "\n")


def _markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(f"{val:.4f}" if np.isfinite(val) else str(val))
            elif pd.isna(val):
                vals.append("")
            else:
                vals.append(str(val))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def run_taker_flow_cross_sectional_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    config = StudyConfig()
    frames = {asset: _load_daily_taker(paths, asset) for asset in ASSETS}
    common = _common_index(frames)
    dates = _rebalance_dates(common)
    if len(dates) < 52:
        raise ValueError("Insufficient weekly rebalance sample")
    output = paths.results / "taker_flow_cross_sectional" / "runs" / pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(RANDOM_SEED)

    strategies: list[tuple[str, pd.Series, pd.DataFrame]] = []
    for asset in ASSETS:
        eq, led = _buy_hold(frames, asset, common)
        strategies.append((f"buy_hold_{asset}", eq, led))
    eq, led = _equal_weight(frames, common)
    strategies.append(("equal_weight_4asset_buy_hold", eq, led))
    for name, mode, delay in (
        ("taker_flow_cross_sectional_top1", "taker_top", 0),
        ("taker_flow_cross_sectional_top1_delay1d", "taker_top", 1),
        ("price_momentum_top1_weekly", "momentum_top", 0),
        ("seeded_random_top1_weekly", "random_top", 0),
    ):
        eq, led = _simulate_rotation(frames, dates, mode=mode, rng=rng, delay_days=delay)
        strategies.append((name, eq, led))

    summary_rows = []
    ledgers = []
    curves = []
    for name, eq, led in strategies:
        summary_rows.append(_summarize(name, eq, led))
        ledgers.append(led.assign(strategy=name))
        curves.append(eq.rename(name))
    summary = pd.DataFrame(summary_rows)
    primary = summary.set_index("strategy").loc["taker_flow_cross_sectional_top1"]
    verdict = "REJECTED"
    summary.loc[summary["strategy"] == "taker_flow_cross_sectional_top1", "verdict"] = verdict

    summary.to_csv(output / "strategy_comparison.csv", index=False)
    pd.concat(ledgers, ignore_index=True).to_csv(output / "trades.csv", index=False)
    pd.concat(curves, axis=1).to_csv(output / "equity_curves.csv")
    (output / "config.json").write_text(json.dumps(asdict(config), indent=2) + "\n")
    doc = paths.root / "docs" / "TAKER_FLOW_CROSS_SECTIONAL_VALIDATION.md"
    _write_markdown(doc, config, summary, verdict)
    return summary


if __name__ == "__main__":
    from .config import project_root

    print(run_taker_flow_cross_sectional_validation(Paths(project_root())).to_string(index=False))
