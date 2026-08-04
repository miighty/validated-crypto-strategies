from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI aligned to the candle whose close supplies the last price change."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    result = 100 - 100 / (1 + relative_strength)
    result = result.mask((average_loss == 0) & (average_gain > 0), 100.0)
    result = result.mask((average_loss == 0) & (average_gain == 0), 50.0)
    return result


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(frame).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def prior_rolling_high(frame: pd.DataFrame, lookback: int) -> pd.Series:
    return frame["high"].rolling(lookback, min_periods=lookback).max().shift(1)


def market_regime(frame: pd.DataFrame) -> pd.Series:
    """Predefined coarse regime: 50-bar direction relative to a prior 200-bar mean."""
    sma200 = frame["close"].rolling(200, min_periods=200).mean().shift(1)
    direction = frame["close"].shift(1).pct_change(50)
    values = np.where(
        (frame["close"].shift(1) > sma200) & (direction > 0),
        "bull",
        np.where(
            (frame["close"].shift(1) < sma200) & (direction < 0), "bear", "sideways"
        ),
    )
    return pd.Series(values, index=frame.index, dtype="object")
