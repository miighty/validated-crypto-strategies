import numpy as np
import pandas as pd

from crypto_regime_backtest.regimes import REGIME_ORDER, classify, regimes_known_at


def _frame(periods=180):
    index = pd.date_range("2023-01-01", periods=periods, freq="1D", tz="UTC")
    close = pd.Series(np.linspace(100, 200, periods), index=index)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def test_every_day_has_one_requested_regime_label():
    result = classify(_frame())
    assert result["regime"].notna().all()
    assert set(result["regime"]).issubset(set(REGIME_ORDER))


def test_daily_regime_is_not_available_until_next_day():
    daily = pd.DataFrame(
        {"regime": ["Bull Trend", "Bear Trend"]},
        index=pd.DatetimeIndex(["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]),
    )
    query = pd.DatetimeIndex(["2024-01-01T23:00:00Z", "2024-01-02T00:00:00Z"])
    known = regimes_known_at(query, daily)
    assert known.iloc[0] == "Unavailable"
    assert known.iloc[1] == "Bull Trend"
