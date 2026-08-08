from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from crypto_regime_backtest.config import Paths, project_root
from crypto_regime_backtest.data import load_ohlcv
from edge_research.config import ExecutionConfig
from edge_research.engine import EngineResult, ExitRules, run_universe
from edge_research.indicators import atr, prior_rolling_high
from edge_research.metrics import equity_drawdown, metrics_from_returns, summarize
from edge_research.strategies import breakout_acceptance_signals, immediate_breakout_signals

SAMPLE_START = pd.Timestamp("2018-01-01T00:00:00Z")
DEVELOPMENT_END = pd.Timestamp("2020-01-01T00:00:00Z")
VALIDATION_END = pd.Timestamp("2024-01-01T00:00:00Z")
CONTRIBUTION_HOUR_UTC = 0
STRATEGY_UNIVERSE = ("BTC", "ETH", "SOL")
BENCHMARK_ASSETS = ("BTC", "ETH", "SOL", "XRP")
LOOKBACK = 50
ACCEPTANCE_WINDOW = 2
ATR_BUFFER = 0.1
STOP_ATR_MULTIPLE = 2.0
HOLDING_BARS = 24
COMPRESSION_LOOKBACK = 252
COMPRESSION_THRESHOLDS = (0.20, 0.30, 0.40, 0.50)
ENTRY_DELAY_BARS = 1
FEE_RATE = 0.0005
SLIPPAGE_RATE = 0.0005
INITIAL_CAPITAL = 10_000.0


@dataclass(frozen=True)
class StudyConfig:
    sample_start: str = "2018-01-01T00:00:00Z"
    development_end: str = "2020-01-01T00:00:00Z"
    validation_end: str = "2024-01-01T00:00:00Z"
    contribution_hour_utc: int = CONTRIBUTION_HOUR_UTC
    strategy_universe: tuple[str, ...] = STRATEGY_UNIVERSE
    benchmark_assets: tuple[str, ...] = BENCHMARK_ASSETS
    lookback: int = LOOKBACK
    acceptance_window: int = ACCEPTANCE_WINDOW
    atr_buffer: float = ATR_BUFFER
    stop_atr_multiple: float = STOP_ATR_MULTIPLE
    holding_bars: int = HOLDING_BARS
    compression_lookback: int = COMPRESSION_LOOKBACK
    compression_thresholds: tuple[float, ...] = COMPRESSION_THRESHOLDS
    entry_delay_bars: int = ENTRY_DELAY_BARS
    fee_rate: float = FEE_RATE
    slippage_rate: float = SLIPPAGE_RATE
    initial_capital: float = INITIAL_CAPITAL


@dataclass(frozen=True)
class Partition:
    name: str
    start: pd.Timestamp
    end_exclusive: pd.Timestamp | None


PARTITIONS = (
    Partition("development_2018_2019", SAMPLE_START, DEVELOPMENT_END),
    Partition("validation_2020_2023", DEVELOPMENT_END, VALIDATION_END),
    Partition("forward_2024_2026", VALIDATION_END, None),
)


def run_breakout_compression_validation(paths: Paths) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "breakout_compression" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    strategy_frames = {
        coin: load_ohlcv(paths, coin, "4h").loc[lambda frame: frame.index >= pd.Timestamp(config.sample_start)].copy()
        for coin in config.strategy_universe
    }
    benchmark_frames = {
        coin: load_ohlcv(paths, coin, "4h").loc[lambda frame: frame.index >= pd.Timestamp(config.sample_start)].copy()
        for coin in config.benchmark_assets
    }
    if any(frame.empty for frame in strategy_frames.values()):
        raise RuntimeError("At least one strategy-universe asset lacks 4h coverage in the requested window")

    execution = ExecutionConfig(
        initial_capital=config.initial_capital,
        fee_rate=config.fee_rate,
        slippage_rate=config.slippage_rate,
        entry_delay_bars=config.entry_delay_bars,
    )
    rules = ExitRules(config.holding_bars, config.stop_atr_multiple, True, config.atr_buffer)

    matrix_rows: list[dict[str, Any]] = []
    candidates: list[tuple[float, float]] = []
    for threshold in config.compression_thresholds:
        builder = lambda frame, t=threshold: breakout_acceptance_with_compression_signals(
            frame,
            config.lookback,
            config.acceptance_window,
            config.atr_buffer,
            config.compression_lookback,
            float(t),
        )
        dev_result = run_strategy(strategy_frames, builder, execution, rules, SAMPLE_START, DEVELOPMENT_END)
        val_result = run_strategy(strategy_frames, builder, execution, rules, DEVELOPMENT_END, VALIDATION_END)
        dev_metrics = summarize(dev_result)
        val_metrics = summarize(val_result)
        score = selection_score(dev_metrics, val_metrics)
        candidates.append((score, float(threshold)))
        matrix_rows.append(
            {
                "compression_threshold": float(threshold),
                "development_return": dev_metrics.get("total_return"),
                "validation_return": val_metrics.get("total_return"),
                "development_sharpe": dev_metrics.get("sharpe"),
                "validation_sharpe": val_metrics.get("sharpe"),
                "development_trades": dev_metrics.get("number_of_trades"),
                "validation_trades": val_metrics.get("number_of_trades"),
                "selection_score": score,
            }
        )
    _, selected_threshold = max(candidates, key=lambda item: item[0])

    selected_builder = lambda frame: breakout_acceptance_with_compression_signals(
        frame,
        config.lookback,
        config.acceptance_window,
        config.atr_buffer,
        config.compression_lookback,
        selected_threshold,
    )
    parent_builder = lambda frame: breakout_acceptance_signals(
        frame,
        config.lookback,
        config.acceptance_window,
        config.atr_buffer,
    )
    immediate_builder = lambda frame: immediate_breakout_signals(frame, config.lookback)

    selected_result = run_strategy(strategy_frames, selected_builder, execution, rules)
    parent_result = run_strategy(strategy_frames, parent_builder, execution, rules)
    immediate_result = run_strategy(strategy_frames, immediate_builder, execution, rules)

    partition_rows = []
    for partition in PARTITIONS:
        selected_partition = run_strategy(
            strategy_frames, selected_builder, execution, rules, partition.start, partition.end_exclusive
        )
        parent_partition = run_strategy(
            strategy_frames, parent_builder, execution, rules, partition.start, partition.end_exclusive
        )
        selected_metrics = summarize(selected_partition)
        parent_metrics = summarize(parent_partition)
        partition_rows.append(
            {
                "partition": partition.name,
                "selected_total_return": selected_metrics.get("total_return"),
                "selected_sharpe": selected_metrics.get("sharpe"),
                "selected_trades": selected_metrics.get("number_of_trades"),
                "parent_total_return": parent_metrics.get("total_return"),
                "parent_sharpe": parent_metrics.get("sharpe"),
                "parent_trades": parent_metrics.get("number_of_trades"),
                "increment_vs_parent": none_safe(selected_metrics.get("total_return"))
                - none_safe(parent_metrics.get("total_return")),
            }
        )

    doubled = run_strategy(
        strategy_frames,
        selected_builder,
        ExecutionConfig(
            initial_capital=config.initial_capital,
            fee_rate=config.fee_rate * 2,
            slippage_rate=config.slippage_rate * 2,
            entry_delay_bars=config.entry_delay_bars,
        ),
        rules,
    )
    delayed = run_strategy(
        strategy_frames,
        selected_builder,
        ExecutionConfig(
            initial_capital=config.initial_capital,
            fee_rate=config.fee_rate,
            slippage_rate=config.slippage_rate,
            entry_delay_bars=config.entry_delay_bars + 1,
        ),
        rules,
    )
    asset_rows = asset_breakdown(strategy_frames, selected_builder, execution, rules)
    best_asset = max(asset_rows, key=lambda row: row.get("total_return") if row.get("total_return") is not None else -np.inf)["asset"]
    reduced_frames = {coin: frame for coin, frame in strategy_frames.items() if coin != best_asset}
    without_best_asset = run_strategy(reduced_frames, selected_builder, execution, rules)

    sensitivity_rows = []
    for threshold in config.compression_thresholds:
        builder = lambda frame, t=threshold: breakout_acceptance_with_compression_signals(
            frame,
            config.lookback,
            config.acceptance_window,
            config.atr_buffer,
            config.compression_lookback,
            float(t),
        )
        full_result = run_strategy(strategy_frames, builder, execution, rules)
        forward_result = run_strategy(strategy_frames, builder, execution, rules, VALIDATION_END, None)
        sensitivity_rows.append(
            {
                "compression_threshold": float(threshold),
                "full_total_return": summarize(full_result).get("total_return"),
                "full_sharpe": summarize(full_result).get("sharpe"),
                "forward_total_return": summarize(forward_result).get("total_return"),
                "forward_sharpe": summarize(forward_result).get("sharpe"),
                "full_trades": summarize(full_result).get("number_of_trades"),
                "forward_trades": summarize(forward_result).get("number_of_trades"),
            }
        )

    basket_buy_hold = simulate_buy_hold_basket(strategy_frames, config.initial_capital, config.fee_rate + config.slippage_rate)
    basket_daily_dca = simulate_dca_basket(
        strategy_frames,
        config.initial_capital,
        config.fee_rate + config.slippage_rate,
        contribution_hour_utc=config.contribution_hour_utc,
        weekly=False,
    )
    basket_weekly_dca = simulate_dca_basket(
        strategy_frames,
        config.initial_capital,
        config.fee_rate + config.slippage_rate,
        contribution_hour_utc=config.contribution_hour_utc,
        weekly=True,
    )

    benchmark_rows = []
    benchmark_equities = []
    for coin in config.benchmark_assets:
        frame = benchmark_frames[coin]
        buy_hold_summary, buy_hold_equity = simulate_buy_hold_asset(
            frame, config.initial_capital, config.fee_rate + config.slippage_rate, f"buy_hold_{coin}"
        )
        daily_summary, daily_equity = simulate_dca_asset(
            frame,
            config.initial_capital,
            config.fee_rate + config.slippage_rate,
            contribution_hour_utc=config.contribution_hour_utc,
            weekly=False,
            name=f"daily_dca_{coin}",
            units_label=f"{coin.lower()}_units",
        )
        weekly_summary, weekly_equity = simulate_dca_asset(
            frame,
            config.initial_capital,
            config.fee_rate + config.slippage_rate,
            contribution_hour_utc=config.contribution_hour_utc,
            weekly=True,
            name=f"weekly_dca_{coin}",
            units_label=f"{coin.lower()}_units",
        )
        benchmark_rows.extend([buy_hold_summary, daily_summary, weekly_summary])
        benchmark_equities.extend([buy_hold_equity, daily_equity, weekly_equity])

    main_rows = [
        metric_row("Compression-selected acceptance", summarize(selected_result)),
        metric_row("Unfiltered acceptance parent", summarize(parent_result)),
        metric_row("Immediate breakout baseline", summarize(immediate_result)),
        metric_row("Doubled costs", summarize(doubled)),
        metric_row("Entry delayed one extra bar", summarize(delayed)),
    ]
    strategy_summary = pd.DataFrame(main_rows)
    partition_summary = pd.DataFrame(partition_rows)
    selection_grid = pd.DataFrame(matrix_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    benchmark_summary = pd.DataFrame(
        [
            basket_buy_hold[0],
            basket_daily_dca[0],
            basket_weekly_dca[0],
            *benchmark_rows,
        ]
    )

    selected_metrics = summarize(selected_result)
    parent_metrics = summarize(parent_result)
    immediate_metrics = summarize(immediate_result)
    doubled_metrics = summarize(doubled)
    delayed_metrics = summarize(delayed)
    without_best_asset_metrics = summarize(without_best_asset)
    forward_selected = summarize(run_strategy(strategy_frames, selected_builder, execution, rules, VALIDATION_END, None))
    forward_parent = summarize(run_strategy(strategy_frames, parent_builder, execution, rules, VALIDATION_END, None))
    validation_selected = summarize(run_strategy(strategy_frames, selected_builder, execution, rules, DEVELOPMENT_END, VALIDATION_END))
    validation_parent = summarize(run_strategy(strategy_frames, parent_builder, execution, rules, DEVELOPMENT_END, VALIDATION_END))

    hostile_rows = [
        {
            "check": "Validation improvement vs unfiltered parent",
            "selected_total_return": validation_selected.get("total_return"),
            "benchmark_total_return": validation_parent.get("total_return"),
            "difference": none_safe(validation_selected.get("total_return")) - none_safe(validation_parent.get("total_return")),
            "status": "Pass" if none_safe(validation_selected.get("total_return")) > none_safe(validation_parent.get("total_return")) else "Fail",
        },
        {
            "check": "Forward improvement vs unfiltered parent",
            "selected_total_return": forward_selected.get("total_return"),
            "benchmark_total_return": forward_parent.get("total_return"),
            "difference": none_safe(forward_selected.get("total_return")) - none_safe(forward_parent.get("total_return")),
            "status": "Pass" if none_safe(forward_selected.get("total_return")) > none_safe(forward_parent.get("total_return")) else "Fail",
        },
        {
            "check": "Full sample vs immediate breakout",
            "selected_total_return": selected_metrics.get("total_return"),
            "benchmark_total_return": immediate_metrics.get("total_return"),
            "difference": none_safe(selected_metrics.get("total_return")) - none_safe(immediate_metrics.get("total_return")),
            "status": "Pass" if none_safe(selected_metrics.get("total_return")) > none_safe(immediate_metrics.get("total_return")) else "Fail",
        },
        {
            "check": "Doubled costs remain positive",
            "selected_total_return": doubled_metrics.get("total_return"),
            "benchmark_total_return": 0.0,
            "difference": none_safe(doubled_metrics.get("total_return")),
            "status": "Pass" if none_safe(doubled_metrics.get("total_return")) > 0 else "Fail",
        },
        {
            "check": "One-extra-bar delay remains positive",
            "selected_total_return": delayed_metrics.get("total_return"),
            "benchmark_total_return": 0.0,
            "difference": none_safe(delayed_metrics.get("total_return")),
            "status": "Pass" if none_safe(delayed_metrics.get("total_return")) > 0 else "Fail",
        },
        {
            "check": f"Remove best asset ({best_asset})",
            "selected_total_return": without_best_asset_metrics.get("total_return"),
            "benchmark_total_return": 0.0,
            "difference": none_safe(without_best_asset_metrics.get("total_return")),
            "status": "Pass" if none_safe(without_best_asset_metrics.get("total_return")) > 0 else "Fail",
        },
        {
            "check": "Vs basket daily DCA",
            "selected_total_return": selected_metrics.get("total_return"),
            "benchmark_total_return": basket_daily_dca[0]["total_return"],
            "difference": none_safe(selected_metrics.get("total_return")) - none_safe(basket_daily_dca[0]["total_return"]),
            "status": "Pass" if none_safe(selected_metrics.get("total_return")) > none_safe(basket_daily_dca[0]["total_return"]) else "Fail",
        },
        {
            "check": "Vs basket weekly DCA",
            "selected_total_return": selected_metrics.get("total_return"),
            "benchmark_total_return": basket_weekly_dca[0]["total_return"],
            "difference": none_safe(selected_metrics.get("total_return")) - none_safe(basket_weekly_dca[0]["total_return"]),
            "status": "Pass" if none_safe(selected_metrics.get("total_return")) > none_safe(basket_weekly_dca[0]["total_return"]) else "Fail",
        },
    ]
    hostile = pd.DataFrame(hostile_rows)
    verdict, verdict_reason = classify_verdict(
        validation_selected,
        validation_parent,
        forward_selected,
        selected_metrics,
        basket_daily_dca[0],
        basket_weekly_dca[0],
    )

    trades = selected_result.trades.copy()
    equity = strategy_equity_frame(selected_result, "compression_selected")
    parent_equity = strategy_equity_frame(parent_result, "acceptance_parent")
    immediate_equity = strategy_equity_frame(immediate_result, "immediate_breakout")
    all_equity = pd.concat(
        [
            equity,
            parent_equity,
            immediate_equity,
            basket_buy_hold[1],
            basket_daily_dca[1],
            basket_weekly_dca[1],
            *benchmark_equities,
        ],
        ignore_index=True,
    )

    strategy_summary.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    partition_summary.to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    selection_grid.to_csv(output / "selection_grid.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    benchmark_summary.to_csv(output / "benchmark_summary.csv", index=False, float_format="%.17g")
    pd.DataFrame(asset_rows).to_csv(output / "asset_breakdown.csv", index=False, float_format="%.17g")
    trades.to_csv(output / "trades.csv", index=False, float_format="%.17g")
    all_equity.to_csv(output / "equity_curve.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "strategy_universe": list(config.strategy_universe),
        "benchmark_assets": list(config.benchmark_assets),
        "selected_threshold": selected_threshold,
        "sample_start": min(frame.index.min() for frame in strategy_frames.values()).isoformat(),
        "sample_end": max(frame.index.max() for frame in strategy_frames.values()).isoformat(),
        "provenance": load_provenance(paths, set(config.strategy_universe) | set(config.benchmark_assets), "4h"),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(
        output,
        manifest,
        strategy_summary,
        partition_summary,
        benchmark_summary,
        hostile,
        verdict,
        verdict_reason,
    )
    write_findings_doc(output, selected_threshold, partition_summary, hostile, benchmark_summary, verdict)
    print(f"Breakout-compression validation written to {output}", flush=True)
    return strategy_summary


def rolling_percentile_rank(series: pd.Series, window: int) -> pd.Series:
    def last_rank(values: np.ndarray) -> float:
        finite = values[np.isfinite(values)]
        if len(finite) != len(values) or len(values) == 0:
            return np.nan
        return float(np.mean(values <= values[-1]))

    return series.rolling(window, min_periods=window).apply(last_rank, raw=True)


def breakout_acceptance_with_compression_signals(
    frame: pd.DataFrame,
    lookback: int,
    acceptance_window: int,
    atr_buffer: float,
    compression_lookback: int,
    compression_threshold: float,
) -> pd.DataFrame:
    level_series = prior_rolling_high(frame, lookback)
    atr_value = atr(frame, 14)
    normalized_atr = atr_value / frame["close"].replace(0, np.nan)
    compression_rank = rolling_percentile_rank(normalized_atr.shift(1), compression_lookback)
    compression_ok = compression_rank <= compression_threshold
    entries = np.zeros(len(frame), dtype=int)
    accepted_levels = np.full(len(frame), np.nan)
    candidate_level: float | None = None
    candidate_index: int | None = None
    for i in range(len(frame)):
        level = float(level_series.iloc[i])
        current_atr = float(atr_value.iloc[i])
        if candidate_level is not None and candidate_index is not None:
            age = i - candidate_index
            if (
                1 <= age <= acceptance_window
                and np.isfinite(current_atr)
                and float(frame["close"].iloc[i]) > candidate_level + atr_buffer * current_atr
            ):
                entries[i] = 1
                accepted_levels[i] = candidate_level
                candidate_level = None
                candidate_index = None
                continue
            if age >= acceptance_window:
                candidate_level = None
                candidate_index = None
        if (
            candidate_level is None
            and np.isfinite(level)
            and bool(compression_ok.iloc[i])
            and float(frame["close"].iloc[i]) > level
        ):
            candidate_level = level
            candidate_index = i
    return pd.DataFrame(
        {"entry": entries, "exit": False, "atr": atr_value, "level": accepted_levels},
        index=frame.index,
    )


def run_strategy(
    frames: dict[str, pd.DataFrame],
    builder,
    execution: ExecutionConfig,
    rules: ExitRules,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> EngineResult:
    signals = {coin: builder(frame) for coin, frame in frames.items()}
    selected_frames: dict[str, pd.DataFrame] = {}
    selected_signals: dict[str, pd.DataFrame] = {}
    for coin, frame in frames.items():
        mask = pd.Series(True, index=frame.index)
        if start is not None:
            mask &= frame.index >= start
        if end is not None:
            mask &= frame.index < end
        subset = frame.loc[mask]
        if len(subset) >= 2:
            selected_frames[coin] = subset
            selected_signals[coin] = signals[coin].reindex(subset.index)
    if not selected_frames:
        raise RuntimeError("No frames available for the requested run window")
    return run_universe(selected_frames, selected_signals, execution, rules)


def selection_score(development: dict[str, Any], validation: dict[str, Any]) -> float:
    returns = [development.get("total_return", -1), validation.get("total_return", -1)]
    sharpes = [development.get("sharpe"), validation.get("sharpe")]
    if all(value is not None and value > 0 for value in returns):
        usable = [value for value in sharpes if value is not None]
        return float(np.nanmean(usable)) if usable else -1.0
    return -10.0 + float(sum(value if value is not None else -1 for value in returns))


def metric_row(label: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant": label,
        "total_return": metrics.get("total_return"),
        "cagr": metrics.get("cagr"),
        "sharpe": metrics.get("sharpe"),
        "sortino": metrics.get("sortino"),
        "maximum_drawdown": metrics.get("maximum_drawdown"),
        "trades": metrics.get("number_of_trades"),
        "win_rate": metrics.get("win_rate"),
        "profit_factor": metrics.get("profit_factor"),
        "exposure": metrics.get("exposure"),
    }


def asset_breakdown(
    frames: dict[str, pd.DataFrame], builder, execution: ExecutionConfig, rules: ExitRules
) -> list[dict[str, Any]]:
    rows = []
    for asset, frame in frames.items():
        result = run_strategy({asset: frame}, builder, execution, rules)
        metrics = summarize(result)
        rows.append({"asset": asset, **metric_row(asset, metrics)})
    return rows


def simulate_buy_hold_asset(
    frame: pd.DataFrame,
    initial_capital: float,
    one_way_cost: float,
    name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    first = frame.iloc[0]
    units = initial_capital / (float(first["open"]) * (1 + one_way_cost))
    equity = pd.DataFrame(
        {
            "timestamp": frame.index,
            "equity": units * frame["close"].astype(float).to_numpy(),
            "strategy": name,
        }
    )
    summary = benchmark_summary_from_equity(name, equity, units)
    summary["benchmark_type"] = "buy_hold"
    return summary, equity


def simulate_dca_asset(
    frame: pd.DataFrame,
    initial_capital: float,
    one_way_cost: float,
    contribution_hour_utc: int,
    weekly: bool,
    name: str,
    units_label: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    slots = frame.index[(frame.index.hour == contribution_hour_utc)]
    if len(slots) == 0:
        raise RuntimeError("No contribution slots available for DCA benchmark")
    tranche = initial_capital / len(slots)
    scheduled = {timestamp: tranche for timestamp in slots}
    cash = 0.0
    units = 0.0
    records = []
    for timestamp, row in frame.iterrows():
        contribution = float(scheduled.get(timestamp, 0.0))
        if contribution:
            cash += contribution
        buy_now = contribution > 0 and not weekly
        buy_now = buy_now or (
            weekly and timestamp.hour == contribution_hour_utc and timestamp.dayofweek == 0 and cash > 0
        )
        if buy_now:
            gross_spend = cash if weekly else contribution
            price = float(row["open"])
            exec_price = price * (1 + one_way_cost)
            bought = gross_spend / exec_price
            cash -= gross_spend
            units += bought
        records.append(
            {
                "timestamp": timestamp,
                "equity": cash + units * float(row["close"]),
                units_label: units,
                "cash": cash,
                "strategy": name,
            }
        )
    equity = pd.DataFrame(records)
    summary = benchmark_summary_from_equity(name, equity[["timestamp", "equity", "strategy"]], units)
    summary["benchmark_type"] = "weekly_dca" if weekly else "daily_dca"
    return summary, equity[["timestamp", "equity", "strategy"]]


def simulate_buy_hold_basket(
    frames: dict[str, pd.DataFrame], initial_capital: float, one_way_cost: float
) -> tuple[dict[str, Any], pd.DataFrame]:
    equities = []
    for frame in frames.values():
        _, equity = simulate_buy_hold_asset(frame, initial_capital / len(frames), one_way_cost, "basket_buy_hold_component")
        equities.append(equity.set_index("timestamp")["equity"])
    basket = pd.concat(equities, axis=1).sort_index().ffill().sum(axis=1)
    equity = pd.DataFrame({"timestamp": basket.index, "equity": basket.to_numpy(), "strategy": "basket_buy_hold_btc_eth_sol"})
    summary = benchmark_summary_from_equity("basket_buy_hold_btc_eth_sol", equity, np.nan)
    summary["benchmark_type"] = "basket_buy_hold"
    return summary, equity


def simulate_dca_basket(
    frames: dict[str, pd.DataFrame],
    initial_capital: float,
    one_way_cost: float,
    contribution_hour_utc: int,
    weekly: bool,
) -> tuple[dict[str, Any], pd.DataFrame]:
    equities = []
    for asset, frame in frames.items():
        _, equity = simulate_dca_asset(
            frame,
            initial_capital / len(frames),
            one_way_cost,
            contribution_hour_utc,
            weekly,
            f"basket_component_{asset}",
            f"{asset.lower()}_units",
        )
        equities.append(equity.set_index("timestamp")["equity"])
    basket = pd.concat(equities, axis=1).sort_index().ffill().sum(axis=1)
    strategy = "basket_weekly_dca_btc_eth_sol" if weekly else "basket_daily_dca_btc_eth_sol"
    equity = pd.DataFrame({"timestamp": basket.index, "equity": basket.to_numpy(), "strategy": strategy})
    summary = benchmark_summary_from_equity(strategy, equity, np.nan)
    summary["benchmark_type"] = "basket_weekly_dca" if weekly else "basket_daily_dca"
    return summary, equity


def benchmark_summary_from_equity(name: str, equity: pd.DataFrame, final_units: float) -> dict[str, Any]:
    series = equity.set_index("timestamp")["equity"].astype(float)
    total_return = float(series.iloc[-1] / INITIAL_CAPITAL - 1)
    elapsed_years = max(
        (series.index[-1] - series.index[0]).total_seconds() / (365.25 * 24 * 3600),
        1 / (365.25 * 6),
    )
    cagr = float((series.iloc[-1] / INITIAL_CAPITAL) ** (1 / elapsed_years) - 1) if series.iloc[-1] > 0 else -1.0
    drawdown = series / series.cummax().replace(0, np.nan) - 1
    returns = series.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    sharpe = metrics_from_returns(
        returns,
        pd.DataFrame(),
        pd.Series(False, index=series.index),
    ).get("sharpe")
    return {
        "strategy": name,
        "final_usd": float(series.iloc[-1]),
        "final_units": None if pd.isna(final_units) else float(final_units),
        "total_return": total_return,
        "cagr": cagr,
        "maximum_drawdown": abs(float(drawdown.min())) if len(drawdown) else None,
        "sharpe": sharpe,
    }


def strategy_equity_frame(result: EngineResult, strategy: str) -> pd.DataFrame:
    values = equity_drawdown(result.returns, float(result.equity.iloc[0]) if len(result.equity) else INITIAL_CAPITAL)
    return pd.DataFrame(
        {
            "timestamp": values.index,
            "equity": values["equity"].to_numpy(),
            "drawdown": values["drawdown"].to_numpy(),
            "strategy": strategy,
        }
    )


def none_safe(value: float | None) -> float:
    return float(value) if value is not None and np.isfinite(value) else float("nan")


def classify_verdict(
    validation_selected: dict[str, Any],
    validation_parent: dict[str, Any],
    forward_selected: dict[str, Any],
    full_selected: dict[str, Any],
    basket_daily_dca: dict[str, Any],
    basket_weekly_dca: dict[str, Any],
) -> tuple[str, str]:
    if none_safe(validation_selected.get("total_return")) <= none_safe(validation_parent.get("total_return")):
        return (
            "REJECTED",
            "The compression filter failed its primary preregistered gate: it did not improve validation return versus the unfiltered acceptance parent.",
        )
    if none_safe(forward_selected.get("total_return")) <= 0:
        return "REJECTED", "The selected compression rule lost money in the untouched 2024–2026 forward window."
    if none_safe(full_selected.get("total_return")) <= none_safe(basket_daily_dca.get("total_return")):
        return "INCONCLUSIVE", "The timing rule is profitable but does not clear the same-universe daily DCA baseline."
    if none_safe(full_selected.get("total_return")) <= none_safe(basket_weekly_dca.get("total_return")):
        return "INCONCLUSIVE", "The timing rule is profitable but does not clear the same-universe weekly DCA baseline."
    return "RESEARCH CANDIDATE", "The compression filter improved on the parent in validation and remained positive after the main hostile checks, but this is still historical research rather than deployment evidence."


def load_provenance(paths: Paths, coins: set[str], timeframe: str) -> list[dict[str, Any]]:
    provenance_path = paths.data / "provenance.csv"
    if not provenance_path.exists():
        return []
    frame = pd.read_csv(provenance_path)
    subset = frame[(frame["coin"].isin(sorted(coins))) & (frame["timeframe"].eq(timeframe))].copy()
    return subset.to_dict(orient="records")


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "(no rows)"
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            if pd.isna(value):
                values.append("")
            elif isinstance(value, float):
                values.append(f"{value:.6g}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(
    output: Path,
    manifest: dict[str, Any],
    strategy_summary: pd.DataFrame,
    partition_summary: pd.DataFrame,
    benchmark_summary: pd.DataFrame,
    hostile: pd.DataFrame,
    verdict: str,
    verdict_reason: str,
) -> None:
    selected_threshold = manifest["selected_threshold"]
    text = [
        "# Breakout Compression Validation",
        "",
        f"**Verdict:** **{verdict}**",
        "",
        "## Frozen hypothesis",
        "",
        "Accepted breakouts that emerge from prior volatility compression may carry more persistent demand than the unfiltered acceptance parent.",
        "",
        "## Exact rule",
        "",
        f"- Base parent: 50-bar acceptance long, 2-bar acceptance window, 0.1 ATR breakout buffer, 24-bar max hold, 2 ATR stop.",
        f"- Compression gate: ATR(14)/close percentile rank over the prior {COMPRESSION_LOOKBACK} completed 4h bars must be at or below the selected threshold.",
        "- Compression is measured on `shift(1)` data, so the breakout bar itself never contributes to the filter.",
        f"- Selected threshold from development+validation only: **{selected_threshold:.2f}**.",
        "- Entries still occur at the next 4h open; no overlapping positions within an asset.",
        "",
        "## Strategy summary",
        "",
        dataframe_to_markdown(strategy_summary),
        "",
        "## Partition summary",
        "",
        dataframe_to_markdown(partition_summary),
        "",
        "## Benchmark summary",
        "",
        dataframe_to_markdown(benchmark_summary),
        "",
        "## Hostile checks",
        "",
        dataframe_to_markdown(hostile),
        "",
        "## Verdict",
        "",
        f"**{verdict}** — {verdict_reason}",
        "",
        "Artifacts: `strategy_summary.csv`, `partition_summary.csv`, `selection_grid.csv`, `sensitivity_checks.csv`, `hostile_checks.csv`, `benchmark_summary.csv`, `trades.csv`, `equity_curve.csv`, `config.json`.",
    ]
    (output / "REPORT.md").write_text("\n".join(text) + "\n")


def write_findings_doc(
    output: Path,
    selected_threshold: float,
    partition_summary: pd.DataFrame,
    hostile: pd.DataFrame,
    benchmark_summary: pd.DataFrame,
    verdict: str,
) -> None:
    validation = partition_summary.loc[partition_summary["partition"].eq("validation_2020_2023")].iloc[0]
    forward = partition_summary.loc[partition_summary["partition"].eq("forward_2024_2026")].iloc[0]
    basket_daily = benchmark_summary.loc[
        benchmark_summary["strategy"].eq("basket_daily_dca_btc_eth_sol")
    ].iloc[0]
    basket_weekly = benchmark_summary.loc[
        benchmark_summary["strategy"].eq("basket_weekly_dca_btc_eth_sol")
    ].iloc[0]
    doc = Path(project_root()) / "docs" / "BREAKOUT_COMPRESSION_VALIDATION.md"
    content = [
        "# Breakout Compression Validation",
        "",
        f"Run artifact: `{output.relative_to(project_root()) / 'REPORT.md'}`",
        "",
        "## Key findings",
        "",
        f"- **Primary test:** accepted 4h breakout longs on BTC/ETH/SOL with a prior-only ATR compression filter; selected threshold = **{selected_threshold:.2f}**.",
        f"- **Validation gate vs parent:** selected return **{validation['selected_total_return']:.2%}** vs unfiltered parent **{validation['parent_total_return']:.2%}**.",
        f"- **Forward 2024–2026:** selected return **{forward['selected_total_return']:.2%}** vs parent **{forward['parent_total_return']:.2%}**.",
        f"- **Same-universe DCA benchmarks:** basket daily DCA **{basket_daily['total_return']:.2%}**, basket weekly DCA **{basket_weekly['total_return']:.2%}**.",
        "",
        "## Honest conclusion",
        "",
        f"**{verdict}**. The decisive hostile checks are in `hostile_checks.csv`; no proxy or synthetic inputs were used.",
        "",
        "## Files",
        "",
        f"- `{output.relative_to(project_root()) / 'REPORT.md'}`",
        f"- `{output.relative_to(project_root()) / 'strategy_summary.csv'}`",
        f"- `{output.relative_to(project_root()) / 'partition_summary.csv'}`",
        f"- `{output.relative_to(project_root()) / 'benchmark_summary.csv'}`",
        f"- `{output.relative_to(project_root()) / 'hostile_checks.csv'}`",
    ]
    doc.write_text("\n".join(content) + "\n")
