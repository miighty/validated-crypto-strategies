from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr, prior_rolling_high, rsi


def rsi_mean_reversion_signals(
    frame: pd.DataFrame, threshold: float, period: int = 14, exit_rsi: float = 50
) -> pd.DataFrame:
    rsi_value = rsi(frame["close"], period)
    return pd.DataFrame(
        {
            "entry": (rsi_value < threshold).astype(int),
            "exit": rsi_value > exit_rsi,
            "atr": atr(frame, 14),
            "level": np.nan,
        },
        index=frame.index,
    )


def negative_candle_signals(frame: pd.DataFrame, atr_multiple: float = 1.0) -> pd.DataFrame:
    atr_value = atr(frame, 14)
    fall = frame["close"].diff() < -atr_multiple * atr_value
    return pd.DataFrame(
        {"entry": fall.astype(int), "exit": False, "atr": atr_value, "level": np.nan},
        index=frame.index,
    )


def simple_trend_signals(frame: pd.DataFrame) -> pd.DataFrame:
    average = frame["close"].rolling(50, min_periods=50).mean()
    entry = (frame["close"] > average) & (frame["close"].shift(1) <= average.shift(1))
    exit_signal = frame["close"] < average
    return pd.DataFrame(
        {
            "entry": entry.astype(int),
            "exit": exit_signal,
            "atr": atr(frame, 14),
            "level": np.nan,
        },
        index=frame.index,
    )


def random_entry_signals(
    frame: pd.DataFrame, trade_count: int, holding_period: int, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    atr_value = atr(frame, 14)
    candidates = np.flatnonzero(atr_value.notna().to_numpy())
    rng.shuffle(candidates)
    selected: list[int] = []
    minimum_spacing = holding_period + 1
    for candidate in candidates:
        if candidate >= len(frame) - holding_period - 1:
            continue
        if all(abs(candidate - prior) >= minimum_spacing for prior in selected):
            selected.append(int(candidate))
            if len(selected) >= trade_count:
                break
    selected.sort()
    entry = pd.Series(0, index=frame.index, dtype=int)
    if selected:
        entry.iloc[selected] = 1
    return pd.DataFrame(
        {"entry": entry, "exit": False, "atr": atr_value, "level": np.nan},
        index=frame.index,
    )


def immediate_breakout_signals(frame: pd.DataFrame, lookback: int) -> pd.DataFrame:
    level = prior_rolling_high(frame, lookback)
    atr_value = atr(frame, 14)
    entry = frame["close"] > level
    return pd.DataFrame(
        {"entry": entry.astype(int), "exit": False, "atr": atr_value, "level": level},
        index=frame.index,
    )


def breakout_acceptance_signals(
    frame: pd.DataFrame,
    lookback: int,
    acceptance_window: int,
    atr_buffer: float,
) -> pd.DataFrame:
    level_series = prior_rolling_high(frame, lookback)
    atr_value = atr(frame, 14)
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
                and float(frame["close"].iloc[i])
                > candidate_level + atr_buffer * current_atr
            ):
                entries[i] = 1
                accepted_levels[i] = candidate_level
                candidate_level = None
                candidate_index = None
                continue
            if age >= acceptance_window:
                candidate_level = None
                candidate_index = None
        if candidate_level is None and np.isfinite(level) and frame["close"].iloc[i] > level:
            candidate_level = level
            candidate_index = i
    return pd.DataFrame(
        {
            "entry": entries,
            "exit": False,
            "atr": atr_value,
            "level": accepted_levels,
        },
        index=frame.index,
    )


def breakout_rejection_signals(
    frame: pd.DataFrame,
    lookback: int,
    rejection_window: int,
    atr_buffer: float,
) -> pd.DataFrame:
    level_series = prior_rolling_high(frame, lookback)
    atr_value = atr(frame, 14)
    entries = np.zeros(len(frame), dtype=int)
    rejected_levels = np.full(len(frame), np.nan)
    candidate_level: float | None = None
    candidate_index: int | None = None
    for i in range(len(frame)):
        level = float(level_series.iloc[i])
        current_atr = float(atr_value.iloc[i])
        if candidate_level is not None and candidate_index is not None:
            age = i - candidate_index
            if (
                age <= rejection_window
                and np.isfinite(current_atr)
                and float(frame["close"].iloc[i])
                < candidate_level - atr_buffer * current_atr
            ):
                entries[i] = -1
                rejected_levels[i] = candidate_level
                candidate_level = None
                candidate_index = None
                continue
            if age >= rejection_window:
                candidate_level = None
                candidate_index = None
        if candidate_level is None and np.isfinite(level) and frame["high"].iloc[i] > level:
            candidate_level = level
            candidate_index = i
            if np.isfinite(current_atr) and frame["close"].iloc[i] < level - atr_buffer * current_atr:
                entries[i] = -1
                rejected_levels[i] = level
                candidate_level = None
                candidate_index = None
    return pd.DataFrame(
        {
            "entry": entries,
            "exit": False,
            "atr": atr_value,
            "level": rejected_levels,
        },
        index=frame.index,
    )
