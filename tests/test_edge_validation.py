import pandas as pd

from crypto_regime_backtest.edge_validation import (
    EventSpec,
    build_non_overlapping_events,
    chronological_splits,
)


def test_events_are_next_open_and_non_overlapping():
    index = pd.date_range("2024-01-01", periods=20, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": range(100, 120), "high": range(101, 121), "low": range(99, 119), "close": range(100, 120), "volume": 1.0}, index=index)
    signal = pd.Series(0.0, index=index); signal.iloc[[3, 4, 12]] = 0.2
    spec = EventSpec("test", "test", 1, signal, 0.1, 4)
    trades = build_non_overlapping_events(frame, pd.Series("Range/Chop", index=index), spec)
    assert len(trades) == 2
    assert trades.iloc[0]["entry_time"] == index[4]
    assert trades.iloc[1]["entry_time"] == index[13]


def test_splits_are_chronological_and_disjoint():
    frame = pd.DataFrame({"entry_time": pd.date_range("2024-01-01", periods=10, freq="D"), "net_return": 0.01})
    splits = chronological_splits(frame)
    assert len(splits["train"]) == 6
    assert len(splits["validation"]) == 2
    assert len(splits["test"]) == 2
