import pandas as pd

from edge_research.metrics import metrics_from_returns


def test_maximum_drawdown_and_equity_updates():
    index = pd.date_range("2024-01-01", periods=3, freq="4h", tz="UTC")
    returns = pd.Series([0.10, -0.20, 0.10], index=index)
    metrics = metrics_from_returns(returns)
    assert abs(metrics["total_return"] + 0.032) < 1e-12
    assert abs(metrics["maximum_drawdown"] - 0.20) < 1e-12
