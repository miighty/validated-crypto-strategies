import pandas as pd

from crypto_regime_backtest.breakout_compression_validation import (
    breakout_acceptance_with_compression_signals,
    rolling_percentile_rank,
)


def test_rolling_percentile_rank_reports_last_value_rank_in_window():
    series = pd.Series([1.0, 2.0, 3.0, 2.0, 1.0])
    rank = rolling_percentile_rank(series, 3)
    assert pd.isna(rank.iloc[1])
    assert rank.iloc[2] == 1.0
    assert rank.iloc[3] == 2 / 3
    assert rank.iloc[4] == 1 / 3


def test_breakout_compression_uses_prior_bar_only_for_filter():
    index = pd.date_range("2024-01-01", periods=48, freq="4h", tz="UTC")
    base = [100.0] * 46 + [120.0, 121.0]
    pre_ranges = list(range(34, 0, -1)) + [1.0] * 12
    highs = [100.0 + width / 2 for width in pre_ranges] + [130.0, 121.5]
    lows = [100.0 - width / 2 for width in pre_ranges] + [80.0, 119.5]
    frame = pd.DataFrame(
        {
            "open": base,
            "high": highs,
            "low": lows,
            "close": base,
            "volume": 1.0,
        },
        index=index,
    )
    signals = breakout_acceptance_with_compression_signals(
        frame,
        lookback=5,
        acceptance_window=2,
        atr_buffer=0.0,
        compression_lookback=20,
        compression_threshold=0.5,
    )
    triggered = signals.index[signals["entry"] == 1]
    assert list(triggered) == [index[47]]
