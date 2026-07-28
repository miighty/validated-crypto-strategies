from __future__ import annotations

import numpy as np
import pandas as pd


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


def atr(frame: pd.DataFrame, length: int = 14) -> pd.Series:
    return true_range(frame).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + relative_strength)


def adx(frame: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    up = frame["high"].diff()
    down = -frame["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index)
    smoothed_atr = atr(frame, length)
    plus_di = (
        100 * plus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / smoothed_atr
    )
    minus_di = (
        100 * minus_dm.ewm(alpha=1 / length, adjust=False, min_periods=length).mean() / smoothed_atr
    )
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_value = dx.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return pd.DataFrame({"adx": adx_value, "plus_di": plus_di, "minus_di": minus_di})


def bollinger(close: pd.Series, length: int = 20, deviations: float = 2.0) -> pd.DataFrame:
    middle = close.rolling(length).mean()
    standard_deviation = close.rolling(length).std(ddof=0)
    upper = middle + deviations * standard_deviation
    lower = middle - deviations * standard_deviation
    width = (upper - lower) / middle.replace(0, np.nan)
    return pd.DataFrame(
        {"bb_lower": lower, "bb_middle": middle, "bb_upper": upper, "bb_width": width}
    )


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["atr14"] = atr(out)
    out["rsi14"] = rsi(out["close"])
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    out["sma50"] = out["close"].rolling(50).mean()
    out["volume_mean20"] = out["volume"].rolling(20).mean()
    out = out.join(bollinger(out["close"]))
    out = out.join(adx(out))
    return out
