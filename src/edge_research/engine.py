from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from .config import ExecutionConfig
from .indicators import market_regime

TRADE_COLUMNS = [
    "symbol",
    "direction",
    "signal_timestamp",
    "entry_timestamp",
    "entry_price",
    "entry_execution_price",
    "exit_timestamp",
    "exit_price",
    "exit_execution_price",
    "position_size",
    "allocated_notional",
    "gross_return",
    "fees",
    "slippage",
    "net_return",
    "net_pnl",
    "exit_reason",
    "holding_period_bars",
    "entry_regime",
    "reference_level",
]


@dataclass(frozen=True)
class ExitRules:
    maximum_holding_bars: int
    stop_atr_multiple: float | None = None
    exit_on_reference_failure: bool = False
    reference_buffer_atr: float = 0.0


@dataclass
class EngineResult:
    equity: pd.Series
    returns: pd.Series
    exposure: pd.Series
    trades: pd.DataFrame


def run_universe(
    frames: dict[str, pd.DataFrame],
    signals: dict[str, pd.DataFrame],
    execution: ExecutionConfig,
    exit_rules: ExitRules,
) -> EngineResult:
    if not frames:
        raise ValueError("At least one asset is required")
    per_asset_capital = execution.initial_capital / len(frames)
    results = {
        symbol: run_symbol_backtest(
            frame,
            symbol,
            signals[symbol],
            replace(execution, initial_capital=per_asset_capital),
            exit_rules,
        )
        for symbol, frame in frames.items()
    }
    equity = pd.concat({symbol: result.equity for symbol, result in results.items()}, axis=1)
    equity = equity.sort_index().ffill()
    for symbol in equity:
        equity[symbol] = equity[symbol].fillna(per_asset_capital)
    portfolio_equity = equity.sum(axis=1).rename("equity")
    returns = portfolio_equity.pct_change().fillna(
        portfolio_equity.iloc[0] / execution.initial_capital - 1
    )
    exposure_frame = pd.concat(
        {symbol: result.exposure for symbol, result in results.items()}, axis=1
    ).reindex(portfolio_equity.index)
    exposure = (
        exposure_frame.astype("boolean")
        .fillna(False)
        .astype(float)
        .mean(axis=1)
        .rename("exposure")
    )
    trades = pd.concat([result.trades for result in results.values()], ignore_index=True)
    if trades.empty:
        trades = pd.DataFrame(columns=TRADE_COLUMNS)
    else:
        trades = trades.sort_values(["entry_timestamp", "symbol"]).reset_index(drop=True)
    return EngineResult(portfolio_equity, returns, exposure, trades)


def run_symbol_backtest(
    frame: pd.DataFrame,
    symbol: str,
    signals: pd.DataFrame,
    execution: ExecutionConfig,
    exit_rules: ExitRules,
) -> EngineResult:
    if frame.empty:
        raise ValueError(f"{symbol}: empty backtest frame")
    if exit_rules.maximum_holding_bars < 1:
        raise ValueError("maximum_holding_bars must be positive")
    signal_frame = signals.reindex(frame.index).copy()
    if "entry" not in signal_frame:
        signal_frame["entry"] = 0
    if "exit" not in signal_frame:
        signal_frame["exit"] = False
    if "atr" not in signal_frame:
        signal_frame["atr"] = np.nan
    if "level" not in signal_frame:
        signal_frame["level"] = np.nan
    signal_frame["entry"] = signal_frame["entry"].fillna(0).astype(int).clip(-1, 1)
    signal_frame["exit"] = signal_frame["exit"].fillna(False).astype(bool)
    regimes = market_regime(frame)

    cash = float(execution.initial_capital)
    quantity = 0.0
    entry: dict[str, Any] | None = None
    stop_price: float | None = None
    reference_level: float | None = None
    occupied_at_close: list[bool] = []
    equity_values: list[float] = []
    exposure_values: list[bool] = []
    rows: list[dict[str, Any]] = []

    for i, (timestamp, bar) in enumerate(frame.iterrows()):
        raw_open = float(bar["open"])
        exposed_during_bar = quantity != 0
        closed_this_open = False

        if quantity != 0:
            reason = _scheduled_exit_reason(
                i, frame, signal_frame, quantity, entry, reference_level, exit_rules
            )
            if reason is not None:
                cash, trade = _close_trade(
                    cash,
                    quantity,
                    entry,
                    timestamp,
                    raw_open,
                    reason,
                    execution,
                    i,
                    reference_level,
                )
                rows.append(trade)
                quantity = 0.0
                entry = None
                stop_price = None
                reference_level = None
                closed_this_open = True

        signal_i = i - execution.entry_delay_bars
        if quantity == 0 and not closed_this_open and signal_i >= 0:
            direction = int(signal_frame["entry"].iloc[signal_i])
            signal_was_occupied = occupied_at_close[signal_i] if signal_i < len(occupied_at_close) else True
            if direction and not signal_was_occupied:
                signal_atr = float(signal_frame["atr"].iloc[signal_i])
                if not np.isfinite(signal_atr) or signal_atr <= 0:
                    direction = 0
            if direction:
                raw_entry_price = raw_open
                execution_price = raw_entry_price * (1 + direction * execution.slippage_rate)
                allocation = _allocation_fraction(
                    execution,
                    raw_entry_price,
                    signal_atr,
                    exit_rules.stop_atr_multiple,
                )
                allocated_notional = max(0.0, cash * allocation)
                size = allocated_notional / execution_price
                quantity = direction * size
                entry_fee = abs(quantity * execution_price) * execution.fee_rate
                cash -= quantity * execution_price + entry_fee
                level_value = float(signal_frame["level"].iloc[signal_i])
                reference_level = level_value if np.isfinite(level_value) else None
                stop_price = (
                    execution_price - direction * exit_rules.stop_atr_multiple * signal_atr
                    if exit_rules.stop_atr_multiple is not None
                    else None
                )
                entry = {
                    "symbol": symbol,
                    "direction": direction,
                    "signal_timestamp": frame.index[signal_i],
                    "entry_timestamp": timestamp,
                    "entry_index": i,
                    "raw_entry_price": raw_entry_price,
                    "entry_execution_price": execution_price,
                    "position_size": size,
                    "allocated_notional": allocated_notional,
                    "entry_fee": entry_fee,
                    "entry_regime": regimes.iloc[i],
                }
                exposed_during_bar = True

        if quantity != 0 and stop_price is not None and _stop_was_hit(bar, quantity, stop_price):
            raw_stop_exit = _stop_fill_reference(raw_open, quantity, stop_price)
            cash, trade = _close_trade(
                cash,
                quantity,
                entry,
                timestamp,
                raw_stop_exit,
                "atr_stop",
                execution,
                i,
                reference_level,
            )
            rows.append(trade)
            quantity = 0.0
            entry = None
            stop_price = None
            reference_level = None

        if i == len(frame) - 1 and quantity != 0:
            cash, trade = _close_trade(
                cash,
                quantity,
                entry,
                timestamp,
                float(bar["close"]),
                "end_of_data",
                execution,
                i,
                reference_level,
            )
            rows.append(trade)
            quantity = 0.0
            entry = None
            stop_price = None
            reference_level = None

        equity_close = cash + quantity * float(bar["close"])
        equity_values.append(equity_close)
        exposure_values.append(exposed_during_bar)
        occupied_at_close.append(quantity != 0)

    equity = pd.Series(equity_values, index=frame.index, name="equity", dtype=float)
    returns = equity.pct_change().fillna(equity.iloc[0] / execution.initial_capital - 1)
    trades = pd.DataFrame(rows, columns=TRADE_COLUMNS)
    exposure = pd.Series(exposure_values, index=frame.index, name="exposure", dtype=bool)
    return EngineResult(equity, returns, exposure, trades)


def _scheduled_exit_reason(
    i: int,
    frame: pd.DataFrame,
    signals: pd.DataFrame,
    quantity: float,
    entry: dict[str, Any] | None,
    reference_level: float | None,
    rules: ExitRules,
) -> str | None:
    if entry is None:
        return None
    if i - int(entry["entry_index"]) >= rules.maximum_holding_bars:
        return "time_exit"
    prior_i = i - 1
    if prior_i >= 0 and bool(signals["exit"].iloc[prior_i]):
        return "signal_exit"
    if rules.exit_on_reference_failure and reference_level is not None and prior_i >= 0:
        prior_close = float(frame["close"].iloc[prior_i])
        prior_atr = float(signals["atr"].iloc[prior_i])
        buffer = rules.reference_buffer_atr * prior_atr if np.isfinite(prior_atr) else 0.0
        if quantity > 0 and prior_close < reference_level - buffer:
            return "reference_failure"
        if quantity < 0 and prior_close > reference_level + buffer:
            return "reference_reclaim"
    return None


def _allocation_fraction(
    execution: ExecutionConfig,
    entry_price: float,
    signal_atr: float,
    stop_atr_multiple: float | None,
) -> float:
    if execution.sizing == "fixed_fraction":
        return min(execution.allocation_fraction, execution.max_allocation)
    multiple = stop_atr_multiple if stop_atr_multiple is not None else 1.0
    risk_per_dollar = multiple * signal_atr / entry_price
    if risk_per_dollar <= 0:
        return 0.0
    return min(execution.risk_fraction / risk_per_dollar, execution.max_allocation)


def _stop_was_hit(bar: pd.Series, quantity: float, stop_price: float) -> bool:
    return bool(bar["low"] <= stop_price) if quantity > 0 else bool(bar["high"] >= stop_price)


def _stop_fill_reference(raw_open: float, quantity: float, stop_price: float) -> float:
    if quantity > 0:
        return min(raw_open, stop_price)
    return max(raw_open, stop_price)


def _close_trade(
    cash: float,
    quantity: float,
    entry: dict[str, Any] | None,
    timestamp: pd.Timestamp,
    raw_exit_price: float,
    reason: str,
    execution: ExecutionConfig,
    exit_index: int,
    reference_level: float | None,
) -> tuple[float, dict[str, Any]]:
    if entry is None:
        raise RuntimeError("Cannot close a position without entry state")
    direction = 1 if quantity > 0 else -1
    exit_execution_price = raw_exit_price * (1 - direction * execution.slippage_rate)
    exit_fee = abs(quantity * exit_execution_price) * execution.fee_rate
    cash += quantity * exit_execution_price - exit_fee
    size = abs(quantity)
    gross_pnl = direction * size * (raw_exit_price - float(entry["raw_entry_price"]))
    slippage = size * (
        abs(float(entry["entry_execution_price"]) - float(entry["raw_entry_price"]))
        + abs(exit_execution_price - raw_exit_price)
    )
    fees = float(entry["entry_fee"]) + exit_fee
    net_pnl = gross_pnl - slippage - fees
    allocated_notional = float(entry["allocated_notional"])
    row = {
        "symbol": entry["symbol"],
        "direction": "long" if direction > 0 else "short",
        "signal_timestamp": entry["signal_timestamp"],
        "entry_timestamp": entry["entry_timestamp"],
        "entry_price": float(entry["raw_entry_price"]),
        "entry_execution_price": float(entry["entry_execution_price"]),
        "exit_timestamp": timestamp,
        "exit_price": raw_exit_price,
        "exit_execution_price": exit_execution_price,
        "position_size": size,
        "allocated_notional": allocated_notional,
        "gross_return": gross_pnl / allocated_notional if allocated_notional else np.nan,
        "fees": fees,
        "slippage": slippage,
        "net_return": net_pnl / allocated_notional if allocated_notional else np.nan,
        "net_pnl": net_pnl,
        "exit_reason": reason,
        "holding_period_bars": exit_index - int(entry["entry_index"]),
        "entry_regime": entry["entry_regime"],
        "reference_level": reference_level,
    }
    return cash, row
