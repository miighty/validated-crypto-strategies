import pandas as pd
import pytest

from crypto_regime_backtest.data import validate_ohlcv


def test_rejects_duplicate_candles():
    timestamp = pd.Timestamp("2024-01-01", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": [timestamp, timestamp],
            "open": [1, 1],
            "high": [2, 2],
            "low": [0.5, 0.5],
            "close": [1.5, 1.5],
            "volume": [10, 10],
        }
    )
    with pytest.raises(ValueError, match="Duplicate"):
        validate_ohlcv(frame, "TEST", "1d")


def test_rejects_out_of_window_candle():
    frame = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-07-28", tz="UTC")],
            "open": [1],
            "high": [2],
            "low": [0.5],
            "close": [1.5],
            "volume": [10],
        }
    )
    with pytest.raises(ValueError, match="Unfinalized"):
        validate_ohlcv(frame, "TEST", "1d")
