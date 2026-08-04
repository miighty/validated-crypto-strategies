from itertools import pairwise

import pandas as pd

from edge_research.strategies import random_entry_signals


def test_random_baseline_is_reproducible_and_non_overlapping():
    index = pd.date_range("2024-01-01", periods=100, freq="4h", tz="UTC")
    close = pd.Series(range(100, 200), index=index, dtype=float)
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )
    first = random_entry_signals(frame, trade_count=8, holding_period=4, seed=42)
    second = random_entry_signals(frame, trade_count=8, holding_period=4, seed=42)
    other = random_entry_signals(frame, trade_count=8, holding_period=4, seed=43)
    assert first["entry"].equals(second["entry"])
    assert not first["entry"].equals(other["entry"])
    locations = [i for i, value in enumerate(first["entry"]) if value]
    assert len(locations) == 8
    assert all(right - left >= 5 for left, right in pairwise(locations))
