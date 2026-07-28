import pandas as pd

from crypto_regime_backtest.backtest import execute_positions


def test_signal_executes_on_next_bar_open_and_cost_is_charged():
    index = pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0, 100.0, 110.0, 121.0],
            "high": [101, 111, 122, 122],
            "low": [99, 99, 109, 120],
            "close": [100, 110, 121, 121],
            "volume": 1.0,
        },
        index=index,
    )
    desired = pd.Series([1.0, 1.0, 0.0, 0.0], index=index)
    regimes = pd.Series("Bull Trend", index=index)
    result = execute_positions(frame, desired, regimes, 365.25, one_way_cost=0.0015)
    assert result.position.tolist() == [0.0, 1.0, 1.0, 0.0]
    assert result.returns.iloc[0] == 0.0
    assert abs(result.returns.iloc[1] - (0.10 - 0.0015)) < 1e-12
    assert abs(result.returns.iloc[2] - 0.10) < 1e-12
    assert abs(result.returns.iloc[3] + 0.0015) < 1e-12


def test_flip_pays_two_one_way_costs():
    index = pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100.0] * 4,
            "high": [101.0] * 4,
            "low": [99.0] * 4,
            "close": [100.0] * 4,
            "volume": 1.0,
        },
        index=index,
    )
    desired = pd.Series([1.0, -1.0, -1.0, 0.0], index=index)
    regimes = pd.Series("Range/Chop", index=index)
    result = execute_positions(frame, desired, regimes, 365.25, one_way_cost=0.0015)
    assert result.returns.iloc[2] == -0.003
