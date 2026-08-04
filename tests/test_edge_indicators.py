import numpy as np
import pandas as pd

from edge_research.indicators import prior_rolling_high, rsi


def test_rsi_is_aligned_to_current_close_without_future_information():
    index = pd.date_range("2024-01-01", periods=7, freq="4h", tz="UTC")
    close = pd.Series([1.0, 2.0, 3.0, 2.0, 2.5, 4.0, 3.0], index=index)
    original = rsi(close, period=3)
    changed_future = close.copy()
    changed_future.iloc[-1] = 1000.0
    changed = rsi(changed_future, period=3)
    assert original.iloc[:6].equals(changed.iloc[:6])
    assert original.iloc[:3].isna().all()
    assert np.isfinite(original.iloc[3])


def test_prior_rolling_high_excludes_current_candle():
    index = pd.date_range("2024-01-01", periods=4, freq="4h", tz="UTC")
    frame = pd.DataFrame({"high": [1.0, 2.0, 10.0, 3.0]}, index=index)
    level = prior_rolling_high(frame, 2)
    assert level.iloc[2] == 2.0
    assert level.iloc[3] == 10.0
