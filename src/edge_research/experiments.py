from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ExecutionConfig, load_yaml, project_root
from .data import load_market_data
from .engine import EngineResult, ExitRules, run_universe
from .metrics import metrics_from_returns, return_by_year, summarize
from .reporting import write_report
from .strategies import (
    breakout_acceptance_signals,
    breakout_rejection_signals,
    immediate_breakout_signals,
    negative_candle_signals,
    random_entry_signals,
    rsi_mean_reversion_signals,
    simple_trend_signals,
)

SignalBuilder = Callable[[pd.DataFrame], pd.DataFrame]


def run_experiment(config_path: str | Path, symbols: list[str] | None = None) -> Path:
    config = load_yaml(config_path)
    frames, manifest = load_market_data(config["data_config"], symbols)
    if symbols:
        config["parent_experiment_id"] = config["experiment_id"]
        config["_manual_symbols"] = list(frames)
        config["experiment_id"] = manual_experiment_id(config["experiment_id"], list(frames))
    kind = config["experiment_type"]
    if kind == "rsi_mean_reversion":
        return run_rsi_experiment(config, frames, manifest)
    if kind == "breakout_acceptance_rejection":
        return run_breakout_experiment(config, frames, manifest)
    raise ValueError(f"Unknown experiment type: {kind}")


def manual_experiment_id(base_experiment_id: str, symbols: list[str]) -> str:
    symbol_suffix = "-".join(symbols)
    if len(symbol_suffix) > 72:
        digest = sha256(symbol_suffix.encode()).hexdigest()[:10].upper()
        symbol_suffix = f"{symbol_suffix[:48]}-{digest}"
    return f"{base_experiment_id}-MANUAL-{symbol_suffix}"


def run_rsi_experiment(
    config: dict[str, Any], frames: dict[str, pd.DataFrame], manifest: dict[str, Any]
) -> Path:
    parameters = config["parameters"]
    execution = ExecutionConfig.from_mapping(config)
    stop_multiple = float(parameters["stop_atr_multiple"])
    matrix_rows = []
    base_result: EngineResult | None = None
    base_builder: SignalBuilder | None = None
    for threshold in parameters["entry_thresholds"]:
        for holding in parameters["holding_periods"]:
            builder = lambda frame, t=threshold: rsi_mean_reversion_signals(
                frame,
                float(t),
                int(parameters["rsi_period"]),
                float(parameters["exit_rsi"]),
            )
            result = _run(frames, builder, execution, ExitRules(int(holding), stop_multiple))
            row = _metric_row(f"RSI<{threshold}, hold={holding}", summarize(result))
            row.update({"threshold": threshold, "holding_bars": holding})
            matrix_rows.append(row)
            if float(threshold) == 30 and int(holding) == 4:
                base_result = result
                base_builder = builder
    if base_result is None or base_builder is None:
        raise ValueError("RSI configuration must include the frozen 30/4 base variant")

    periods = _research_periods(config)
    split_results = {
        name: _run(frames, base_builder, execution, ExitRules(4, stop_multiple), start, end)
        for name, start, end in periods
    }
    doubled = _run(
        frames,
        base_builder,
        replace(
            execution,
            fee_rate=execution.fee_rate * 2,
            slippage_rate=execution.slippage_rate * 2,
        ),
        ExitRules(4, stop_multiple),
    )
    delayed = _run(
        frames,
        base_builder,
        replace(execution, entry_delay_bars=execution.entry_delay_bars + 1),
        ExitRules(4, stop_multiple),
    )

    negative = _run(
        frames,
        lambda frame: negative_candle_signals(
            frame, float(parameters["negative_candle_atr"])
        ),
        execution,
        ExitRules(4, stop_multiple),
    )
    trend = _run(frames, simple_trend_signals, execution, ExitRules(500, stop_multiple))
    buy_hold = _buy_and_hold(frames, execution)
    random_rows, random_average = _random_baseline(
        frames,
        base_result,
        execution,
        holding_period=4,
        repetitions=int(parameters["random_repetitions"]),
        seed=int(parameters["random_seed"]),
    )

    full_metrics = summarize(base_result)
    double_metrics = summarize(doubled)
    delay_metrics = summarize(delayed)
    forward_metrics = summarize(split_results["Forward 2024–2026"])
    negative_metrics = summarize(negative)
    verdict, verdict_reason = _rsi_verdict(
        full_metrics, forward_metrics, double_metrics, delay_metrics, negative_metrics
    )

    main_results = pd.DataFrame(
        [
            _metric_row("Frozen base", full_metrics),
            _metric_row("Doubled costs", double_metrics),
            _metric_row("Entry delayed one extra bar", delay_metrics),
        ]
    )
    period_rows = [
        _metric_row(name, summarize(result)) for name, result in split_results.items()
    ]
    period_rows.extend(_year_rows(base_result))
    baselines = pd.DataFrame(
        [
            _metric_row("RSI frozen base", full_metrics),
            _metric_row("Large negative candle", negative_metrics),
            _metric_row("Simple 50-bar trend", summarize(trend)),
            _metric_row("Buy and hold", summarize(buy_hold)),
            random_average,
        ]
    )
    robustness = pd.DataFrame(
        [
            _robustness_row("Base costs", full_metrics, "Pass" if full_metrics["total_return"] > 0 else "Fail"),
            _robustness_row("Doubled costs", double_metrics, "Pass" if double_metrics["total_return"] > 0 else "Fail"),
            _robustness_row("One-extra-bar delay", delay_metrics, "Pass" if delay_metrics["total_return"] > 0 else "Fail"),
            _robustness_row("Forward 2024–2026", forward_metrics, "Pass" if forward_metrics["total_return"] > 0 else "Fail"),
            {
                "test": "Random baseline (20 fixed seeds)",
                "result": f"mean return {random_average['total_return']:.4f}; 5–95% in machine results",
                "status": "Comparison",
            },
        ]
    )
    asset_rows = _asset_rows(frames, base_builder, execution, ExitRules(4, stop_multiple))
    payload = _base_payload(config, manifest, frames)
    payload.update(
        {
            "strategy_name": "RSI Oversold Mean Reversion",
            "hypothesis": "Crypto assets rebound after RSI(14) closes below an oversold threshold.",
            "economic_reasoning": "The proposed payer is a short-horizon forced seller or panic seller whose urgent flow temporarily pushes price below a local equilibrium. The hostile alternative is that RSI merely relabels large negative candles and adds no after-cost information.",
            "rules": [
                "Compute Wilder RSI(14) from completed four-hour closes.",
                "Frozen base entry: RSI below 30; small predeclared matrix uses 25, 30, and 35.",
                "Enter long at the next candle open; the delayed test enters one further bar later.",
                "Exit at the next open after RSI closes above 50, after four held candles, or at a two-ATR intrabar stop.",
                "No overlapping position in the same asset; the portfolio allocates one equal subaccount per selected symbol.",
            ],
            "primary_metric": "Forward-window net total return after 5 bp fee and 5 bp slippage per side",
            "main_results": main_results,
            "results_by_asset": pd.DataFrame(asset_rows),
            "results_by_period": pd.DataFrame(period_rows),
            "baselines": baselines,
            "variants": pd.DataFrame(matrix_rows),
            "robustness": robustness,
            "largest_trades": _largest_trades(base_result.trades),
            "largest_trade_review": _trade_review_text(base_result.trades),
            "limitations": [
                "The 2016–2020 development window begins at each Binance symbol's actual listing date; SOL has no observations in that window.",
                "Four-hour candles cannot establish intrabar path ordering beyond the conservative stop convention.",
                "Fixed 5 bp slippage does not model stressed spread, depth, or market impact.",
                "The three-asset default universe is selected with hindsight and is too narrow for a general crypto claim.",
                "Random entries match per-symbol trade counts and time exits, but not every realized stop duration.",
            ],
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "next_experiment": "Test whether volatility compression improves breakout acceptance; do not tune another RSI threshold from the forward window.",
            "primary_result": f"Forward net return {forward_metrics.get('total_return', float('nan')):.2%}; full-sample net return {full_metrics.get('total_return', float('nan')):.2%}.",
            "machine_results": {
                "main": main_results,
                "splits": period_rows,
                "assets": asset_rows,
                "variants": matrix_rows,
                "baselines": baselines,
                "random_runs": random_rows,
                "verdict": verdict,
            },
        }
    )
    return write_report(payload, base_result)


def run_breakout_experiment(
    config: dict[str, Any], frames: dict[str, pd.DataFrame], manifest: dict[str, Any]
) -> Path:
    parameters = config["parameters"]
    execution = ExecutionConfig.from_mapping(config)
    stop_multiple = float(parameters["stop_atr_multiple"])
    holding = int(parameters["holding_period"])
    periods = _research_periods(config)
    development = periods[0][1:]
    validation = periods[1][1:]

    matrix_rows = []
    candidates: list[tuple[float, int, int, float]] = []
    for lookback in parameters["lookbacks"]:
        for window in parameters["acceptance_windows"]:
            for buffer in parameters["atr_buffers"]:
                builder = _breakout_builder("Acceptance Long", int(lookback), int(window), float(buffer))
                dev_result = _run(frames, builder, execution, ExitRules(holding, stop_multiple, True, float(buffer)), *development)
                val_result = _run(frames, builder, execution, ExitRules(holding, stop_multiple, True, float(buffer)), *validation)
                dev_metrics = summarize(dev_result)
                val_metrics = summarize(val_result)
                score = _selection_score(dev_metrics, val_metrics)
                candidates.append((score, int(lookback), int(window), float(buffer)))
                matrix_rows.append(
                    {
                        "section": "Acceptance parameter matrix",
                        "lookback": lookback,
                        "window": window,
                        "atr_buffer": buffer,
                        "development_return": dev_metrics.get("total_return"),
                        "validation_return": val_metrics.get("total_return"),
                        "development_sharpe": dev_metrics.get("sharpe"),
                        "validation_sharpe": val_metrics.get("sharpe"),
                        "selection_score": score,
                    }
                )
    _, selected_lookback, selected_window, selected_buffer = max(candidates, key=lambda item: item[0])

    family_results: dict[str, EngineResult] = {}
    family_scores = []
    for family in ("Immediate Long", "Acceptance Long", "Rejection Short"):
        builder = _breakout_builder(family, selected_lookback, selected_window, selected_buffer)
        rules = ExitRules(holding, stop_multiple, True, selected_buffer)
        dev_result = _run(frames, builder, execution, rules, *development)
        val_result = _run(frames, builder, execution, rules, *validation)
        score = _selection_score(summarize(dev_result), summarize(val_result))
        family_results[family] = _run(frames, builder, execution, rules)
        family_scores.append((score, family, dev_result, val_result))
        matrix_rows.append(
            {
                "section": "Family comparison",
                "family": family,
                "lookback": selected_lookback,
                "window": selected_window,
                "atr_buffer": selected_buffer,
                "development_return": summarize(dev_result).get("total_return"),
                "validation_return": summarize(val_result).get("total_return"),
                "development_sharpe": summarize(dev_result).get("sharpe"),
                "validation_sharpe": summarize(val_result).get("sharpe"),
                "selection_score": score,
            }
        )
    _, selected_family, selected_dev, selected_val = max(family_scores, key=lambda item: item[0])
    selected_builder = _breakout_builder(
        selected_family, selected_lookback, selected_window, selected_buffer
    )
    selected_rules = ExitRules(holding, stop_multiple, True, selected_buffer)
    base_result = family_results[selected_family]

    # The forward window is opened only after the development/validation selection above.
    forward_name, forward_start, forward_end = periods[2]
    forward_result = _run(
        frames, selected_builder, execution, selected_rules, forward_start, forward_end
    )
    split_results = {
        periods[0][0]: selected_dev,
        periods[1][0]: selected_val,
        forward_name: forward_result,
    }
    doubled = _run(
        frames,
        selected_builder,
        replace(execution, fee_rate=execution.fee_rate * 2, slippage_rate=execution.slippage_rate * 2),
        selected_rules,
    )
    delayed = _run(
        frames,
        selected_builder,
        replace(execution, entry_delay_bars=execution.entry_delay_bars + 1),
        selected_rules,
    )
    volatility_sized = _run(
        frames,
        selected_builder,
        replace(execution, sizing="volatility_adjusted"),
        selected_rules,
    )

    asset_rows = _asset_rows(frames, selected_builder, execution, selected_rules)
    best_asset = max(asset_rows, key=lambda row: row.get("total_return") or -np.inf)["asset"]
    reduced_frames = {symbol: frame for symbol, frame in frames.items() if symbol != best_asset}
    without_best_asset = _run(reduced_frames, selected_builder, execution, selected_rules)
    yearly = return_by_year(base_result.returns)
    best_year = max(yearly, key=yearly.get)
    keep = base_result.returns.index.year != int(best_year)
    without_best_year = metrics_from_returns(
        base_result.returns.loc[keep],
        base_result.trades.loc[
            pd.to_datetime(base_result.trades["entry_timestamp"], utc=True).dt.year != int(best_year)
        ],
        base_result.exposure.loc[keep],
    )

    nearby_rows = []
    for lookback in parameters["nearby_lookbacks"]:
        builder = _breakout_builder(selected_family, int(lookback), selected_window, selected_buffer)
        result = _run(frames, builder, execution, selected_rules)
        nearby_rows.append(_metric_row(f"Nearby lookback {lookback}", summarize(result)))
    horizon_rows = []
    for horizon in parameters["horizon_sensitivity"]:
        result = _run(
            frames,
            selected_builder,
            execution,
            replace(selected_rules, maximum_holding_bars=int(horizon)),
        )
        horizon_rows.append(_metric_row(f"Exit horizon {horizon}", summarize(result)))

    random_rows, random_average = _random_baseline(
        frames, base_result, execution, holding, repetitions=20, seed=2718
    )
    buy_hold = _buy_and_hold(frames, execution)
    trend = _run(frames, simple_trend_signals, execution, ExitRules(500, stop_multiple))
    full_metrics = summarize(base_result)
    forward_metrics = summarize(forward_result)
    double_metrics = summarize(doubled)
    delay_metrics = summarize(delayed)
    vol_metrics = summarize(volatility_sized)
    immediate_metrics = summarize(family_results["Immediate Long"])
    verdict, verdict_reason = _breakout_verdict(
        full_metrics,
        summarize(selected_val),
        forward_metrics,
        double_metrics,
        delay_metrics,
        nearby_rows,
    )

    main_results = pd.DataFrame(
        [
            _metric_row(f"Selected: {selected_family}", full_metrics),
            _metric_row("Doubled costs", double_metrics),
            _metric_row("Entry delayed one extra bar", delay_metrics),
            _metric_row("Volatility-adjusted sizing", vol_metrics),
        ]
    )
    family_baselines = [
        _metric_row(name, summarize(result)) for name, result in family_results.items()
    ]
    baselines = pd.DataFrame(
        [
            *family_baselines,
            _metric_row("Simple 50-bar trend", summarize(trend)),
            _metric_row("Buy and hold", summarize(buy_hold)),
            random_average,
        ]
    )
    period_rows = [
        _metric_row(name, summarize(result)) for name, result in split_results.items()
    ]
    period_rows.extend(_year_rows(base_result))
    robustness_rows = [
        _robustness_row("Base costs", full_metrics, _pass_fail(full_metrics)),
        _robustness_row("Doubled costs", double_metrics, _pass_fail(double_metrics)),
        _robustness_row("One-extra-bar delay", delay_metrics, _pass_fail(delay_metrics)),
        _robustness_row("Forward 2024–2026", forward_metrics, _pass_fail(forward_metrics)),
        _robustness_row(f"Remove best asset ({best_asset})", summarize(without_best_asset), _pass_fail(summarize(without_best_asset))),
        _robustness_row(f"Remove best year ({best_year})", without_best_year, _pass_fail(without_best_year)),
        _robustness_row("Volatility-adjusted sizing", vol_metrics, _pass_fail(vol_metrics)),
        {
            "test": "Winner concentration",
            "result": f"largest={full_metrics.get('largest_winner_share_of_gross_profit')}; top5={full_metrics.get('top_five_winner_share_of_gross_profit')}",
            "status": "Pass" if (full_metrics.get("top_five_winner_share_of_gross_profit") or 1) < 0.5 else "Fail",
        },
        {
            "test": "Immediate breakout comparison",
            "result": f"selected {full_metrics.get('total_return'):.4f} vs immediate {immediate_metrics.get('total_return'):.4f}",
            "status": (
                "Selected baseline"
                if selected_family == "Immediate Long"
                else (
                    "Pass"
                    if full_metrics.get("total_return", -1)
                    > immediate_metrics.get("total_return", -1)
                    else "Fail"
                )
            ),
        },
    ]
    robustness_rows.extend(
        {
            "test": row["variant"],
            "result": f"return={row.get('total_return')}; Sharpe={row.get('sharpe')}",
            "status": "Pass" if (row.get("total_return") or -1) > 0 else "Fail",
        }
        for row in nearby_rows + horizon_rows
    )
    robustness_rows.extend(_regime_rows(base_result.trades))

    payload = _base_payload(config, manifest, frames)
    payload.update(
        {
            "strategy_name": "Breakout Acceptance and Rejection",
            "hypothesis": "A breakout that remains above prior resistance contains more persistent demand than an immediate breakout, while a rapid close back inside the range identifies trapped late buyers and a tradeable short.",
            "economic_reasoning": "Accepted breakouts may be paid by under-positioned trend followers and short optionality/inventory providers forced to chase. Rejection shorts may be paid by leveraged breakout buyers exiting after the old resistance level fails.",
            "rules": [
                f"Selected only from development and validation: {selected_family}, lookback {selected_lookback}, window {selected_window}, buffer {selected_buffer} ATR.",
                "The previous rolling high is shifted one candle and never includes the current candle.",
                "Immediate long enters after a close above the level; acceptance long requires a later close above it; rejection short requires a close back below within the declared window.",
                "Every entry fills at the next open. The delayed robustness case waits one additional candle.",
                f"Exit at a reference-level failure/reclaim, a {stop_multiple:g}-ATR stop, or after {holding} held candles.",
                "The 2024–2026 forward window is evaluated only after the candidate is selected by pre-2024 data.",
            ],
            "primary_metric": "Sealed 2024–2026 net total return after costs",
            "main_results": main_results,
            "results_by_asset": pd.DataFrame(asset_rows),
            "results_by_period": pd.DataFrame(period_rows),
            "baselines": baselines,
            "variants": pd.DataFrame(matrix_rows),
            "robustness": pd.DataFrame(robustness_rows),
            "largest_trades": _largest_trades(base_result.trades),
            "largest_trade_review": _trade_review_text(base_result.trades),
            "limitations": [
                "Development coverage is partial before Binance spot listings, and SOL has no 2016–2020 observations.",
                "Selection among a small declared family still creates multiple-testing risk; the forward window is the only untouched check.",
                "Four-hour OHLCV cannot resolve whether a level and stop were touched in an ambiguous intrabar order.",
                "Short spot execution, borrow availability, borrow cost, funding, and liquidation are not modelled; rejection shorts are research abstractions.",
                "Fixed slippage does not represent stressed breakout liquidity or market impact.",
            ],
            "verdict": verdict,
            "verdict_reason": verdict_reason,
            "next_experiment": "Add a predeclared volatility-compression filter to the selected acceptance rule and require incremental validation improvement over the unfiltered parent.",
            "primary_result": f"Selected {selected_family}; forward net return {forward_metrics.get('total_return', float('nan')):.2%}; full-sample net return {full_metrics.get('total_return', float('nan')):.2%}.",
            "machine_results": {
                "selection": {
                    "family": selected_family,
                    "lookback": selected_lookback,
                    "window": selected_window,
                    "atr_buffer": selected_buffer,
                },
                "main": main_results,
                "splits": period_rows,
                "assets": asset_rows,
                "variants": matrix_rows,
                "baselines": baselines,
                "robustness": robustness_rows,
                "random_runs": random_rows,
                "verdict": verdict,
            },
        }
    )
    return write_report(payload, base_result)


def _run(
    frames: dict[str, pd.DataFrame],
    builder: SignalBuilder,
    execution: ExecutionConfig,
    rules: ExitRules,
    start: str | None = None,
    end: str | None = None,
) -> EngineResult:
    signals = {symbol: builder(frame) for symbol, frame in frames.items()}
    selected_frames = {}
    selected_signals = {}
    for symbol, frame in frames.items():
        mask = pd.Series(True, index=frame.index)
        if start is not None:
            mask &= frame.index >= pd.Timestamp(start)
        if end is not None:
            mask &= frame.index < pd.Timestamp(end)
        subset = frame.loc[mask]
        if len(subset) >= 2:
            selected_frames[symbol] = subset
            selected_signals[symbol] = signals[symbol].reindex(subset.index)
    if not selected_frames:
        return _empty_result(execution.initial_capital)
    return run_universe(selected_frames, selected_signals, execution, rules)


def _empty_result(initial_capital: float) -> EngineResult:
    index = pd.DatetimeIndex([pd.Timestamp("1970-01-01", tz="UTC")])
    return EngineResult(
        pd.Series([initial_capital], index=index, name="equity"),
        pd.Series([0.0], index=index, name="returns"),
        pd.Series([False], index=index, name="exposure"),
        pd.DataFrame(),
    )


def _buy_and_hold(
    frames: dict[str, pd.DataFrame], execution: ExecutionConfig
) -> EngineResult:
    signals = {}
    for symbol, frame in frames.items():
        value = pd.DataFrame(
            {"entry": 0, "exit": False, "atr": frame["open"] * 0.01, "level": np.nan},
            index=frame.index,
        )
        value.iloc[0, value.columns.get_loc("entry")] = 1
        signals[symbol] = value
    maximum = max(len(frame) for frame in frames.values()) + 1
    return run_universe(frames, signals, execution, ExitRules(maximum, None))


def _random_baseline(
    frames: dict[str, pd.DataFrame],
    reference: EngineResult,
    execution: ExecutionConfig,
    holding_period: int,
    repetitions: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    counts = reference.trades.groupby("symbol").size().to_dict() if not reference.trades.empty else {}
    rows = []
    for repetition in range(repetitions):
        signals = {
            symbol: random_entry_signals(
                frame,
                int(counts.get(symbol, 0)),
                holding_period,
                seed + repetition * 1009 + symbol_index,
            )
            for symbol_index, (symbol, frame) in enumerate(frames.items())
        }
        result = run_universe(frames, signals, execution, ExitRules(holding_period, None))
        row = _metric_row(f"Random seed {seed + repetition * 1009}", summarize(result))
        rows.append(row)
    returns = np.array([row["total_return"] for row in rows], dtype=float)
    sharpes = np.array([row["sharpe"] for row in rows], dtype=float)
    average = {
        "variant": f"Random baseline mean ({repetitions} seeds)",
        "total_return": float(np.nanmean(returns)),
        "sharpe": float(np.nanmean(sharpes)),
        "maximum_drawdown": float(np.nanmean([row["maximum_drawdown"] for row in rows])),
        "trades": round(np.nanmean([row["trades"] for row in rows])),
        "return_5th_percentile": float(np.nanpercentile(returns, 5)),
        "return_95th_percentile": float(np.nanpercentile(returns, 95)),
    }
    return rows, average


def _asset_rows(
    frames: dict[str, pd.DataFrame],
    builder: SignalBuilder,
    execution: ExecutionConfig,
    rules: ExitRules,
) -> list[dict[str, Any]]:
    rows = []
    for symbol, frame in frames.items():
        metrics = summarize(_run({symbol: frame}, builder, execution, rules))
        row = _metric_row(symbol, metrics)
        row["asset"] = row.pop("variant")
        rows.append(row)
    return rows


def _breakout_builder(
    family: str, lookback: int, window: int, buffer: float
) -> SignalBuilder:
    if family == "Immediate Long":
        return lambda frame: immediate_breakout_signals(frame, lookback)
    if family == "Acceptance Long":
        return lambda frame: breakout_acceptance_signals(frame, lookback, window, buffer)
    if family == "Rejection Short":
        return lambda frame: breakout_rejection_signals(frame, lookback, window, buffer)
    raise ValueError(family)


def _research_periods(config: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    splits = config["splits"]
    return [
        ("Development 2016–2020", splits["development_start"], splits["development_end"]),
        ("Validation 2020–2024", splits["development_end"], splits["validation_end"]),
        ("Forward 2024–2026", splits["validation_end"], None),
    ]


def _selection_score(development: dict[str, Any], validation: dict[str, Any]) -> float:
    returns = [development.get("total_return", -1), validation.get("total_return", -1)]
    sharpes = [development.get("sharpe"), validation.get("sharpe")]
    if all(value is not None and value > 0 for value in returns):
        return float(np.nanmean([value for value in sharpes if value is not None]))
    return -10.0 + float(sum(value if value is not None else -1 for value in returns))


def _metric_row(label: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "variant": label,
        "total_return": metrics.get("total_return"),
        "cagr": metrics.get("cagr"),
        "sharpe": metrics.get("sharpe"),
        "sortino": metrics.get("sortino"),
        "maximum_drawdown": metrics.get("maximum_drawdown"),
        "win_rate": metrics.get("win_rate"),
        "profit_factor": metrics.get("profit_factor"),
        "trades": metrics.get("number_of_trades", 0),
        "exposure": metrics.get("exposure"),
    }


def _year_rows(result: EngineResult) -> list[dict[str, Any]]:
    rows = []
    entry_times = (
        pd.to_datetime(result.trades["entry_timestamp"], utc=True)
        if not result.trades.empty
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    for year, values in result.returns.groupby(result.returns.index.year):
        trades = result.trades.loc[entry_times.dt.year == year] if not result.trades.empty else result.trades
        exposure = result.exposure.reindex(values.index)
        rows.append(_metric_row(str(year), metrics_from_returns(values, trades, exposure)))
    return rows


def _regime_rows(trades: pd.DataFrame) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    rows = []
    for regime, group in trades.groupby("entry_regime"):
        values = pd.to_numeric(group["net_return"], errors="coerce").dropna()
        rows.append(
            {
                "test": f"Entry regime: {regime}",
                "result": f"trades={len(values)}; compounded trade return={(1 + values).prod() - 1:.4f}",
                "status": "Descriptive",
            }
        )
    return rows


def _robustness_row(test: str, metrics: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "test": test,
        "result": f"return={metrics.get('total_return')}; Sharpe={metrics.get('sharpe')}; maxDD={metrics.get('maximum_drawdown')}",
        "status": status,
    }


def _pass_fail(metrics: dict[str, Any]) -> str:
    return "Pass" if (metrics.get("total_return") or -1) > 0 else "Fail"


def _largest_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    columns = [
        "symbol",
        "direction",
        "signal_timestamp",
        "entry_timestamp",
        "entry_price",
        "exit_timestamp",
        "exit_price",
        "net_return",
        "exit_reason",
    ]
    winners = trades.nlargest(5, "net_return")
    losers = trades.nsmallest(5, "net_return")
    return pd.concat([winners, losers]).drop_duplicates().loc[:, columns]


def _trade_review_text(trades: pd.DataFrame) -> str:
    if trades.empty:
        return "No trades were available to review; the hypothesis is underpowered."
    finite = np.isfinite(
        trades[["entry_price", "exit_price", "position_size", "net_return"]].to_numpy(dtype=float)
    ).all()
    ordered = (
        pd.to_datetime(trades["exit_timestamp"], utc=True)
        >= pd.to_datetime(trades["entry_timestamp"], utc=True)
    ).all()
    return (
        f"Manual ledger review: finite prices and sizes={'yes' if finite else 'no'}; "
        f"exit timestamps do not precede entries={'yes' if ordered else 'no'}. "
        "The listed extremes remain subject to candle-level path ambiguity and are not removed as outliers."
    )


def _rsi_verdict(
    full: dict[str, Any],
    forward: dict[str, Any],
    doubled: dict[str, Any],
    delayed: dict[str, Any],
    negative: dict[str, Any],
) -> tuple[str, str]:
    failures = []
    for label, metric in (
        ("full sample", full),
        ("forward window", forward),
        ("doubled costs", doubled),
        ("one-extra-bar delay", delayed),
    ):
        if (metric.get("total_return") or -1) <= 0:
            failures.append(label)
    if failures:
        return "REJECTED", "Net profitability failed in: " + ", ".join(failures) + "."
    if full.get("total_return", -1) <= negative.get("total_return", -1):
        return "INCONCLUSIVE", "RSI did not beat the materially simpler large-negative-candle baseline."
    return "RESEARCH CANDIDATE", "The frozen rule survived core checks, but the narrow universe and candle-level execution model do not justify paper trading."


def _breakout_verdict(
    full: dict[str, Any],
    validation: dict[str, Any],
    forward: dict[str, Any],
    doubled: dict[str, Any],
    delayed: dict[str, Any],
    nearby: list[dict[str, Any]],
) -> tuple[str, str]:
    core = {
        "full sample": full,
        "validation": validation,
        "forward window": forward,
        "doubled costs": doubled,
    }
    failures = [name for name, metric in core.items() if (metric.get("total_return") or -1) <= 0]
    if failures:
        return "REJECTED", "The selected pre-2024 candidate failed net profitability in: " + ", ".join(failures) + "."
    positive_nearby = sum((row.get("total_return") or -1) > 0 for row in nearby)
    if (delayed.get("total_return") or -1) <= 0 or positive_nearby < max(2, len(nearby) // 2):
        return "INCONCLUSIVE", "The result is profitable but fragile to entry timing or nearby lookbacks."
    if (full.get("number_of_trades") or 0) < 100 or (full.get("maximum_drawdown") or 1) > 0.4:
        return "INCONCLUSIVE", "Evidence is positive, but trade count or drawdown is insufficient for a stronger label."
    return (
        "RESEARCH CANDIDATE",
        "The strategy survived the core Python historical checks and is ready for Pine/TradingView review, but is not approved for paper or live trading.",
    )


def _base_payload(
    config: dict[str, Any], manifest: dict[str, Any], frames: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    datasets = [item for item in manifest["datasets"] if item["symbol"] in frames]
    quality = pd.DataFrame(datasets)[
        [
            "symbol",
            "rows",
            "first_timestamp",
            "last_timestamp",
            "end_exclusive",
            "missing_candles",
            "duplicates_removed",
        ]
    ]
    config_path = Path(config["_config_path"]).relative_to(project_root())
    dataset_ends = {item["end_exclusive"] for item in datasets}
    if len(dataset_ends) == 1:
        end_description = f"through {next(iter(dataset_ends))} (exclusive)"
    else:
        end_description = "with per-symbol exclusive ends: " + ", ".join(
            f"{item['symbol']}={item['end_exclusive']}" for item in datasets
        )
    return {
        "experiment_id": config["experiment_id"],
        "config_path": str(config_path),
        "report_directory": config.get("report_directory", "reports"),
        "data_description": (
            f"Finalized Binance spot {manifest['timeframe']} OHLCV, requested from "
            f"{manifest['start_requested']} {end_description}. "
            "Actual coverage starts at each symbol's exchange listing and gaps are not filled."
        ),
        "data_quality": quality,
        "cost_description": (
            f"Initial portfolio ${config['initial_capital']:,.0f}; fee {config['fee_rate'] * 10_000:.1f} bp "
            f"and slippage {config['slippage_rate'] * 10_000:.1f} bp per side. "
            f"Sizing={config['sizing']}; default entry delay={config['entry_delay_bars']} bar."
        ),
        "pine_script": config.get("tradingview", {}).get("pine_script", ""),
        "tradingview_status": _tradingview_status(config["experiment_id"]),
        "reproduce_command": "edge-research run --config "
        f"{config_path}"
        + (
            " --symbols " + " ".join(config["_manual_symbols"])
            if config.get("_manual_symbols")
            else ""
        ),
    }


def _tradingview_status(experiment_id: str) -> str:
    path = project_root() / "reports" / "tradingview" / f"{experiment_id}.json"
    if not path.exists():
        return (
            "DEFERRED — no supplementary TradingView record was requested for this "
            "manual run. Python remains the validation authority."
        )
    record = json.loads(path.read_text())
    sections = [f"**{record['status']}**."]
    if record.get("compile_result"):
        sections[0] += f" {record['compile_result']}"

    tester_results = record.get("strategy_tester_results", {})
    if tester_results:
        rows = [
            "| TradingView symbol | Window | Return | Max drawdown | Trades | Profit factor |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for symbol, result in tester_results.items():
            rows.append(
                f"| `{symbol}` | {result['window']} | {result['total_return_percent']:.2f}% | "
                f"{result['maximum_drawdown_percent']:.2f}% | {result['total_trades']} | "
                f"{result['profit_factor']:.3f} |"
            )
        sections.append("\n".join(rows))

    if record.get("reconciliation_note"):
        sections.append(record["reconciliation_note"])
    limitation = record.get("limitation") or record.get("blocker")
    if limitation:
        sections.append(f"Deferred platform note: {limitation}")
    sections.append("Python remains the validation authority; this platform record is supplementary.")
    sections.append("No script or idea was published." if not record.get("published") else "Published.")
    return "\n\n".join(sections)
