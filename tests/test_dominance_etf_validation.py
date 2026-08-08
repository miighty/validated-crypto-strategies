import pandas as pd
import pytest

from crypto_regime_backtest.dominance_etf_validation import (
    dominance_signals,
    forward_events,
    validate_availability,
)


def test_dominance_cross_above_29_percent_is_not_029_percent():
    index = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    frame = pd.DataFrame({"available_at": index, "btc_dominance": [0.28, 0.291, 0.30]})
    assert dominance_signals(frame)["cross_above_29pct"].tolist() == [False, True, False]


def test_future_return_starts_after_signal_and_does_not_overlap():
    index = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    signals = pd.Series([False, True, True, False, True, False, False, False], index=index)
    returns = pd.Series(.01, index=index)
    events = forward_events(signals, returns, 2, -1, pd.Series("Bull Trend", index=index))
    assert events["entry_time"].tolist() == [index[2], index[5]]


def test_rejects_availability_before_observation():
    frame = pd.DataFrame({"timestamp": [pd.Timestamp("2024-01-02", tz="UTC")], "available_at": [pd.Timestamp("2024-01-01", tz="UTC")]})
    with pytest.raises(ValueError, match="availability"):
        validate_availability(frame, "timestamp", "available_at", "dominance")
