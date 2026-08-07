import numpy as np
import pandas as pd

from edge_research.cross_asset_strategy import strategy_metrics


def test_strategy_metrics_compound_only_realized_event_returns():
    returns = pd.Series([0.10, -0.05], index=pd.DatetimeIndex(["2024-01-01", "2024-02-01"]))
    result = strategy_metrics(returns, initial_capital=10_000)
    assert result["events"] == 2
    assert np.isclose(result["ending_equity"], 10_450)
    assert np.isclose(result["net_profit"], 450)
    assert np.isclose(result["maximum_drawdown"], -0.05)


def test_empty_strategy_is_not_reported_as_profit():
    result = strategy_metrics(pd.Series(dtype=float), initial_capital=10_000)
    assert result["events"] == 0
    assert result["total_return"] is None
    assert result["net_profit"] == 0
