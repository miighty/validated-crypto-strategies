import numpy as np
import pandas as pd

from edge_research.cross_asset_studies import (
    adjust_splits,
    btc_event_returns,
    calculate_daily_returns,
    combine_daily_panels,
    intraday_to_daily,
)


def test_intraday_features_use_declared_entry_and_close_windows():
    index = pd.date_range("2024-01-02 14:30", periods=390, freq="min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.arange(390) + 100.0,
            "high": np.arange(390) + 101.0,
            "low": np.arange(390) + 99.0,
            "close": np.arange(390) + 100.0,
            "volume": np.ones(390),
        },
        index=index,
    )
    daily = intraday_to_daily(frame)
    assert np.isclose(daily.iloc[0]["entry"], 107.0)
    assert np.isclose(daily.iloc[0]["trade_entry"], 112.0)
    assert np.isclose(daily.iloc[0]["close"], 487.0)
    assert daily.iloc[0]["minutes"] == 390


def test_btc_event_return_stops_at_last_completed_0925_bar():
    index = pd.date_range("2024-01-05 20:00", "2024-01-08 14:30", freq="5min", tz="UTC")
    prices = pd.Series(100.0, index=index)
    prices.loc[pd.Timestamp("2024-01-05 20:55", tz="UTC")] = 100.0
    prices.loc[pd.Timestamp("2024-01-08 14:20", tz="UTC")] = 110.0
    prices.loc[pd.Timestamp("2024-01-08 14:25", tz="UTC")] = 999.0
    frame = pd.DataFrame({"close": prices})
    sessions = pd.DatetimeIndex(["2024-01-05", "2024-01-08"])
    events = btc_event_returns(frame, sessions)
    assert np.isclose(events.iloc[0]["btc_event_return"], 0.10)
    assert bool(events.iloc[0]["is_weekend"])


def test_split_adjustment_removes_false_overnight_loss():
    index = pd.DatetimeIndex(["2024-08-07", "2024-08-08", "2024-08-09"])
    daily = pd.DataFrame(
        {
            "open": [1300.0, 130.0, 132.0],
            "entry": [1310.0, 131.0, 133.0],
            "trade_entry": [1310.0, 131.0, 133.0],
            "close": [1300.0, 132.0, 134.0],
            "minutes": [390, 390, 390],
        },
        index=index,
    )
    adjusted = calculate_daily_returns(adjust_splits(daily))
    assert bool(adjusted.loc[index[1], "split_event"])
    assert np.isclose(adjusted.loc[index[1], "gap"], 131 / 130 - 1)
    assert np.isclose(adjusted.loc[index[2], "previous_close"], 132.0)


def test_combined_download_windows_recalculate_boundary_return():
    first = pd.DataFrame(
        {
            "session": pd.DatetimeIndex(["2023-12-29"]),
            "symbol": ["COIN"],
            "open": [170.0],
            "entry": [171.0],
            "trade_entry": [171.5],
            "close": [172.0],
            "minutes": [390],
        }
    ).set_index(["session", "symbol"])
    second = pd.DataFrame(
        {
            "session": pd.DatetimeIndex(["2024-01-02"]),
            "symbol": ["COIN"],
            "open": [174.0],
            "entry": [175.0],
            "trade_entry": [175.5],
            "close": [176.0],
            "minutes": [390],
        }
    ).set_index(["session", "symbol"])
    combined = combine_daily_panels(first, second)
    assert np.isclose(combined.loc[(pd.Timestamp("2024-01-02"), "COIN"), "gap"], 175 / 172 - 1)
