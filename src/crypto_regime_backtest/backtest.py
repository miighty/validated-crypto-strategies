from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, STARTING_CAPITAL


@dataclass
class BacktestResult:
    returns: pd.Series
    equity: pd.Series
    position: pd.Series
    trades: pd.DataFrame
    metrics: list[dict[str, object]]


def execute_positions(
    frame: pd.DataFrame,
    desired: pd.Series,
    regimes: pd.Series,
    periods_per_year: float,
    one_way_cost: float = ONE_WAY_COST,
) -> BacktestResult:
    desired = desired.reindex(frame.index).fillna(0.0).clip(-1, 1)
    # Signal at close t can first become a position at open t+1.
    position = desired.shift(1).fillna(0.0)
    forward_open_return = frame["open"].shift(-1) / frame["open"] - 1
    turnover = (position - position.shift(1).fillna(0.0)).abs()
    returns = position * forward_open_return.fillna(0.0) - turnover * one_way_cost
    equity = STARTING_CAPITAL * (1 + returns).cumprod()
    trades = trade_log(frame, position, returns, regimes, one_way_cost)
    metric_rows = metric_table(returns, regimes.reindex(returns.index), trades, periods_per_year)
    return BacktestResult(returns, equity, position, trades, metric_rows)


def execute_return_stream(
    returns: pd.Series,
    regimes: pd.Series,
    periods_per_year: float,
    trades: pd.DataFrame | None = None,
) -> BacktestResult:
    clean = returns.fillna(0.0).sort_index()
    equity = STARTING_CAPITAL * (1 + clean).cumprod()
    empty_trades = (
        trades
        if trades is not None
        else pd.DataFrame(
            columns=[
                "entry_time",
                "exit_time",
                "side",
                "entry_price",
                "exit_price",
                "return",
                "pnl",
                "fees_paid",
                "entry_regime",
                "bars",
            ]
        )
    )
    metrics = metric_table(clean, regimes.reindex(clean.index), empty_trades, periods_per_year)
    return BacktestResult(
        clean, equity, pd.Series(index=clean.index, dtype=float), empty_trades, metrics
    )


def trade_log(
    frame: pd.DataFrame,
    position: pd.Series,
    returns: pd.Series,
    regimes: pd.Series,
    one_way_cost: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    current_start: int | None = None
    current_side = 0.0
    index = frame.index
    for i, side in enumerate(position.to_numpy()):
        if side != current_side:
            if current_start is not None and current_side != 0:
                segment = returns.iloc[current_start:i]
                trade_return = float((1 + segment).prod() - 1)
                rows.append(
                    {
                        "entry_time": index[current_start],
                        "exit_time": index[i] if i < len(index) else index[-1],
                        "side": "long" if current_side > 0 else "short",
                        "entry_price": float(frame["open"].iloc[current_start]),
                        "exit_price": float(frame["open"].iloc[i])
                        if i < len(index)
                        else float(frame["close"].iloc[-1]),
                        "return": trade_return,
                        "pnl": STARTING_CAPITAL * trade_return,
                        "fees_paid": STARTING_CAPITAL * one_way_cost * (1 + abs(side)),
                        "entry_regime": regimes.reindex(index).iloc[current_start],
                        "bars": i - current_start,
                    }
                )
            current_start = i if side != 0 else None
            current_side = side
    if current_start is not None and current_side != 0:
        segment = returns.iloc[current_start:]
        trade_return = float((1 + segment).prod() - 1)
        rows.append(
            {
                "entry_time": index[current_start],
                "exit_time": index[-1],
                "side": "long" if current_side > 0 else "short",
                "entry_price": float(frame["open"].iloc[current_start]),
                "exit_price": float(frame["close"].iloc[-1]),
                "return": trade_return,
                "pnl": STARTING_CAPITAL * trade_return,
                "fees_paid": STARTING_CAPITAL * one_way_cost,
                "entry_regime": regimes.reindex(index).iloc[current_start],
                "bars": len(index) - current_start,
            }
        )
    return pd.DataFrame(rows)


def metric_table(
    returns: pd.Series,
    regimes: pd.Series,
    trades: pd.DataFrame,
    periods_per_year: float,
) -> list[dict[str, object]]:
    rows = [_metrics(returns, trades, periods_per_year, "Overall")]
    for regime in sorted(regimes.dropna().unique()):
        subset = returns[regimes == regime]
        regime_trades = trades[trades["entry_regime"] == regime] if not trades.empty else trades
        rows.append(_metrics(subset, regime_trades, periods_per_year, str(regime)))
    return rows


def _metrics(
    returns: pd.Series, trades: pd.DataFrame, periods_per_year: float, regime: str
) -> dict[str, object]:
    values = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return {"regime": regime, "status": "unavailable", "periods": 0}
    total_return = float((1 + values).prod() - 1)
    years = len(values) / periods_per_year
    annualized = (
        float((1 + total_return) ** (1 / years) - 1) if years > 0 and total_return > -1 else -1.0
    )
    standard_deviation = float(values.std(ddof=1))
    sharpe = (
        float(math.sqrt(periods_per_year) * values.mean() / standard_deviation)
        if standard_deviation > 0
        else None
    )
    curve = (1 + values).cumprod()
    drawdown = curve / curve.cummax() - 1
    maximum_drawdown = abs(float(drawdown.min()))
    calmar = annualized / maximum_drawdown if maximum_drawdown > 0 else None
    valid_trades = trades.dropna(subset=["pnl"]) if not trades.empty else trades
    if valid_trades.empty:
        win_rate = None
        profit_factor = None
        average_duration = None
        total_trades = len(trades)
    else:
        wins = valid_trades.loc[valid_trades["pnl"] > 0, "pnl"].sum()
        losses = -valid_trades.loc[valid_trades["pnl"] < 0, "pnl"].sum()
        win_rate = float((valid_trades["pnl"] > 0).mean())
        profit_factor = float(wins / losses) if losses > 0 else None
        average_duration = float(valid_trades["bars"].mean())
        total_trades = len(valid_trades)
    return {
        "regime": regime,
        "status": "completed_historical_backtest",
        "periods": len(values),
        "total_return": total_return,
        "annualized_return": annualized,
        "sharpe": sharpe,
        "max_drawdown": maximum_drawdown,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_trades,
        "average_trade_duration_bars": average_duration,
        "calmar": calmar,
    }
