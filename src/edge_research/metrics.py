from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .engine import EngineResult

PERIODS_PER_YEAR_4H = 365.25 * 6


def summarize(
    result: EngineResult,
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
    periods_per_year: float = PERIODS_PER_YEAR_4H,
) -> dict[str, Any]:
    returns = _slice(result.returns, start, end)
    exposure = _slice(result.exposure, start, end)
    trades = result.trades.copy()
    if not trades.empty:
        entry_time = pd.to_datetime(trades["entry_timestamp"], utc=True)
        if start is not None:
            trades = trades.loc[entry_time >= pd.Timestamp(start)]
            entry_time = pd.to_datetime(trades["entry_timestamp"], utc=True)
        if end is not None:
            trades = trades.loc[entry_time < pd.Timestamp(end)]
    return metrics_from_returns(returns, trades, exposure, periods_per_year)


def metrics_from_returns(
    returns: pd.Series,
    trades: pd.DataFrame | None = None,
    exposure: pd.Series | None = None,
    periods_per_year: float = PERIODS_PER_YEAR_4H,
) -> dict[str, Any]:
    values = returns.replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if values.empty:
        return {"status": "unavailable", "periods": 0}
    total_return = float((1 + values).prod() - 1)
    elapsed_years = max(
        (values.index[-1] - values.index[0]).total_seconds() / (365.25 * 24 * 3600),
        len(values) / periods_per_year,
    )
    cagr = (
        float((1 + total_return) ** (1 / elapsed_years) - 1)
        if total_return > -1 and elapsed_years > 0
        else -1.0
    )
    annual_volatility = float(values.std(ddof=1) * math.sqrt(periods_per_year))
    sharpe = _ratio(values, periods_per_year, downside=False)
    sortino = _ratio(values, periods_per_year, downside=True)
    equity = (1 + values).cumprod()
    drawdown = equity / equity.cummax() - 1
    maximum_drawdown = abs(float(drawdown.min()))
    calmar = cagr / maximum_drawdown if maximum_drawdown > 0 else None
    trade_frame = trades if trades is not None else pd.DataFrame()
    trade_values = (
        pd.to_numeric(trade_frame.get("net_return"), errors="coerce").dropna()
        if not trade_frame.empty
        else pd.Series(dtype=float)
    )
    win_rate = float((trade_values > 0).mean()) if len(trade_values) else None
    gross_wins = float(trade_values[trade_values > 0].sum())
    gross_losses = abs(float(trade_values[trade_values < 0].sum()))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else None
    longest_losing_streak = _longest_losing_streak(trade_values)
    drawdown_duration = _maximum_drawdown_duration(drawdown)
    return {
        "status": "completed",
        "periods": len(values),
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": annual_volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "maximum_drawdown": maximum_drawdown,
        "calmar": calmar,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "average_trade": float(trade_values.mean()) if len(trade_values) else None,
        "median_trade": float(trade_values.median()) if len(trade_values) else None,
        "number_of_trades": len(trade_values),
        "average_holding_period_bars": (
            float(pd.to_numeric(trade_frame["holding_period_bars"]).mean())
            if not trade_frame.empty
            else None
        ),
        "exposure": float(exposure.astype(float).mean()) if exposure is not None else None,
        "longest_losing_streak": longest_losing_streak,
        "maximum_drawdown_duration_bars": drawdown_duration,
        "largest_winner_share_of_gross_profit": _largest_winner_share(trade_values),
        "top_five_winner_share_of_gross_profit": _top_winner_share(trade_values, 5),
    }


def return_by_year(returns: pd.Series) -> dict[str, float]:
    grouped = returns.groupby(returns.index.year)
    return {str(year): float((1 + values).prod() - 1) for year, values in grouped}


def return_by_symbol(trades: pd.DataFrame) -> dict[str, dict[str, float | int | None]]:
    if trades.empty:
        return {}
    output: dict[str, dict[str, float | int | None]] = {}
    for symbol, group in trades.groupby("symbol"):
        trade_returns = pd.to_numeric(group["net_return"], errors="coerce").dropna()
        output[str(symbol)] = {
            "compounded_trade_return": float((1 + trade_returns).prod() - 1),
            "net_pnl": float(pd.to_numeric(group["net_pnl"], errors="coerce").sum()),
            "trades": len(trade_returns),
            "win_rate": float((trade_returns > 0).mean()) if len(trade_returns) else None,
        }
    return output


def equity_drawdown(returns: pd.Series, initial_capital: float = 10_000.0) -> pd.DataFrame:
    equity = initial_capital * (1 + returns.fillna(0)).cumprod()
    drawdown = equity / equity.cummax() - 1
    return pd.DataFrame({"equity": equity, "drawdown": drawdown})


def _slice(series: pd.Series, start: pd.Timestamp | str | None, end: pd.Timestamp | str | None) -> pd.Series:
    result = series
    if start is not None:
        result = result.loc[result.index >= pd.Timestamp(start)]
    if end is not None:
        result = result.loc[result.index < pd.Timestamp(end)]
    return result


def _ratio(values: pd.Series, periods_per_year: float, downside: bool) -> float | None:
    denominator_values = values[values < 0] if downside else values
    deviation = float(denominator_values.std(ddof=1))
    if not np.isfinite(deviation) or deviation <= 0:
        return None
    return float(math.sqrt(periods_per_year) * values.mean() / deviation)


def _longest_losing_streak(values: pd.Series) -> int:
    longest = current = 0
    for is_loss in (values < 0):
        current = current + 1 if is_loss else 0
        longest = max(longest, current)
    return longest


def _maximum_drawdown_duration(drawdown: pd.Series) -> int:
    longest = current = 0
    for underwater in (drawdown < 0):
        current = current + 1 if underwater else 0
        longest = max(longest, current)
    return longest


def _largest_winner_share(values: pd.Series) -> float | None:
    winners = values[values > 0]
    if winners.empty:
        return None
    return float(winners.max() / winners.sum())


def _top_winner_share(values: pd.Series, count: int) -> float | None:
    winners = values[values > 0]
    if winners.empty:
        return None
    return float(winners.nlargest(count).sum() / winners.sum())
