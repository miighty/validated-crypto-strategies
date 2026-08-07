import numpy as np
import pandas as pd

from edge_research.cross_asset import (
    classify_liquidation_events,
    expanding_wild_events,
    incremental_liquidation_value,
    residual_opening_gap,
    rolling_beta,
)


def test_wild_threshold_uses_prior_observations_only():
    index = pd.date_range("2024-01-01", periods=6, freq="D", tz="UTC")
    returns = pd.Series([0.01, -0.02, 0.03, 0.01, 0.20, 0.01], index=index)
    result = expanding_wild_events(returns, quantile=0.75, minimum_prior_observations=4)
    assert result.loc[index[4], "threshold"] == 0.0225
    assert bool(result.loc[index[4], "is_wild"])
    assert result.loc[index[5], "threshold"] > result.loc[index[4], "threshold"]


def test_rolling_beta_is_lagged_and_residual_gap_removes_expected_btc_move():
    index = pd.date_range("2024-01-01", periods=8, freq="D", tz="UTC")
    btc = pd.Series([-0.02, 0.01, 0.03, -0.01, 0.02, -0.03, 0.01, 0.04], index=index)
    assets = pd.DataFrame({"COIN": 2 * btc, "MSTR": 3 * btc}, index=index)
    betas = rolling_beta(assets, btc, lookback=5, minimum_observations=4)
    assert np.isclose(betas.loc[index[5], "COIN"], 2.0)
    assert np.isclose(betas.loc[index[5], "MSTR"], 3.0)
    gaps = pd.DataFrame({"COIN": [0.08], "MSTR": [0.11]}, index=[index[7]])
    residual = residual_opening_gap(gaps, btc, betas)
    assert np.isclose(residual.loc[index[7], "COIN"], 0.0)
    assert np.isclose(residual.loc[index[7], "MSTR"], -0.01)


def test_liquidation_events_separate_long_short_and_two_sided_cascades():
    index = pd.date_range("2024-01-01", periods=8, freq="h", tz="UTC")
    long = pd.Series([0, 0, 60, 60, 0, 0, 50, 50], index=index)
    short = pd.Series([0, 0, 0, 0, 70, 70, 50, 50], index=index)
    result = classify_liquidation_events(
        long, short, absolute_event_usd=100, normalized_quantile=0.99, rolling_hours=2
    )
    assert result.loc[index[3], "event_type"] == "long_cascade"
    assert result.loc[index[5], "event_type"] == "short_squeeze"
    assert result.loc[index[7], "event_type"] == "two_sided"


def test_liquidations_must_add_information_beyond_btc_and_factors():
    rng = np.random.default_rng(7)
    index = pd.date_range("2024-01-01", periods=400, freq="D", tz="UTC")
    btc = pd.Series(rng.normal(0, 0.03, len(index)), index=index)
    vol = btc.rolling(10, min_periods=1).std().fillna(0)
    qqq = pd.Series(rng.normal(0, 0.01, len(index)), index=index)
    size = pd.Series(rng.normal(0, 1, len(index)), index=index)
    imbalance = pd.Series(rng.normal(0, 1, len(index)), index=index)
    equity = 1.5 * btc + 0.4 * qqq + 0.03 * size - 0.02 * imbalance
    result = incremental_liquidation_value(
        equity, btc, vol, pd.DataFrame({"QQQ": qqq}), size, imbalance
    )
    assert result["incremental_r_squared"] > 0.10
    augmented = result["augmented"]
    assert np.isclose(augmented.coefficients["liquidation_size"], 0.03, atol=1e-10)
    assert np.isclose(augmented.coefficients["liquidation_imbalance"], -0.02, atol=1e-10)

