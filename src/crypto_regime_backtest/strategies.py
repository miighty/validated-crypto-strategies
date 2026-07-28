from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import feature_frame


def trend_following(frame: pd.DataFrame) -> pd.Series:
    data = feature_frame(frame)
    cross_up = (
        (data["close"] > data["ema20"])
        & (data["close"].shift(1) <= data["ema20"].shift(1))
        & (data["ema50"] > data["ema50"].shift(1))
    )
    cross_down = (
        (data["close"] < data["ema20"])
        & (data["close"].shift(1) >= data["ema20"].shift(1))
        & (data["ema50"] < data["ema50"].shift(1))
    )
    return _trailing_state(data, cross_up, cross_down, 2.0)


def breakout(frame: pd.DataFrame) -> pd.Series:
    data = feature_frame(frame)
    prior_high = data["high"].rolling(20).max().shift(1)
    prior_low = data["low"].rolling(20).min().shift(1)
    volume_confirmed = data["volume"] > 1.5 * data["volume_mean20"].shift(1)
    long_entry = (data["close"] > prior_high) & volume_confirmed
    short_entry = (data["close"] < prior_low) & volume_confirmed
    return _trailing_state(data, long_entry, short_entry, 2.0)


def mean_reversion(frame: pd.DataFrame) -> pd.Series:
    data = feature_frame(frame)
    state = 0
    entry = np.nan
    output = []
    for row in data.itertuples():
        if state == 0:
            if row.close <= row.bb_lower and row.rsi14 < 30:
                state, entry = 1, row.close
            elif row.close >= row.bb_upper and row.rsi14 > 70:
                state, entry = -1, row.close
        elif (
            state == 1
            and (row.close >= row.bb_middle or row.close < entry - 1.5 * row.atr14)
            or state == -1
            and (row.close <= row.bb_middle or row.close > entry + 1.5 * row.atr14)
        ):
            state, entry = 0, np.nan
        output.append(state)
    return pd.Series(output, index=data.index, dtype=float)


def contrarian(frame: pd.DataFrame) -> pd.Series:
    data = feature_frame(frame)
    state = 0
    entry = np.nan
    output = []
    for row in data.itertuples():
        volume_spike = row.volume > 2 * row.volume_mean20 if pd.notna(row.volume_mean20) else False
        if state == 0:
            if row.rsi14 < 20 and volume_spike:
                state, entry = 1, row.close
            elif row.rsi14 > 80 and volume_spike:
                state, entry = -1, row.close
        elif (
            state == 1
            and ((40 <= row.rsi14 <= 60) or row.close < entry - 3 * row.atr14)
            or state == -1
            and ((40 <= row.rsi14 <= 60) or row.close > entry + 3 * row.atr14)
        ):
            state, entry = 0, np.nan
        output.append(state)
    return pd.Series(output, index=data.index, dtype=float)


def grid(frame: pd.DataFrame) -> pd.Series:
    # At each UTC day boundary, center 20 two-percent levels on the prior finalized close.
    day = frame.index.floor("D")
    prior_daily_close = frame["close"].groupby(day).last().shift(1)
    anchors = pd.Series(day, index=frame.index).map(prior_daily_close)
    distance = (anchors - frame["close"]) / (anchors * 0.02)
    return distance.round().clip(-10, 10).div(10).fillna(0.0)


def momentum_positions(daily_frames: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    closes = pd.concat({coin: frame["close"] for coin, frame in daily_frames.items()}, axis=1)
    scores = closes.pct_change(20, fill_method=None)
    week = pd.Series(scores.index.strftime("%G-%V"), index=scores.index)
    rebalance = ~week.duplicated()
    ranks = scores.rank(axis=1, method="first")
    count = scores.notna().sum(axis=1)
    targets = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    for column in targets:
        targets.loc[rebalance & (ranks[column] > count - 3), column] = 1.0
        targets.loc[rebalance & (ranks[column] <= 3), column] = -1.0
    targets = targets.replace(0, np.nan).ffill().fillna(0.0)
    # Six equal-weight legs make portfolio gross exposure one.
    targets /= 6.0
    return {coin: targets[coin].dropna() for coin in targets}


def statistical_arbitrage(first: pd.DataFrame, second: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    prices = pd.concat(
        [first["close"].rename("first"), second["close"].rename("second")], axis=1
    ).dropna()
    log_ratio = np.log(prices["first"]) - np.log(prices["second"])
    mean = log_ratio.rolling(30 * 6).mean()
    standard_deviation = log_ratio.rolling(30 * 6).std(ddof=0)
    zscore = (log_ratio - mean) / standard_deviation.replace(0, np.nan)
    state = 0
    states = []
    for z in zscore:
        if pd.isna(z):
            state = 0
        elif state == 0 and z > 2:
            state = -1
        elif state == 0 and z < -2:
            state = 1
        elif state == 1 and (z >= 0 or z < -3.5) or state == -1 and (z <= 0 or z > 3.5):
            state = 0
        states.append(state)
    state_series = pd.Series(states, index=prices.index, dtype=float)
    return 0.5 * state_series, -0.5 * state_series


def _trailing_state(
    data: pd.DataFrame, long_entry: pd.Series, short_entry: pd.Series, atr_multiple: float
) -> pd.Series:
    state = 0
    extreme = np.nan
    output = []
    for i, row in enumerate(data.itertuples()):
        if state == 0:
            if bool(long_entry.iloc[i]):
                state, extreme = 1, row.high
            elif bool(short_entry.iloc[i]):
                state, extreme = -1, row.low
        elif state == 1:
            extreme = max(extreme, row.high)
            if row.close < extreme - atr_multiple * row.atr14 or bool(short_entry.iloc[i]):
                state = -1 if bool(short_entry.iloc[i]) else 0
                extreme = row.low if state == -1 else np.nan
        elif state == -1:
            extreme = min(extreme, row.low)
            if row.close > extreme + atr_multiple * row.atr14 or bool(long_entry.iloc[i]):
                state = 1 if bool(long_entry.iloc[i]) else 0
                extreme = row.high if state == 1 else np.nan
        output.append(state)
    return pd.Series(output, index=data.index, dtype=float)
