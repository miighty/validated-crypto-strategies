import pandas as pd

from crypto_regime_backtest.breakout_daily_20high_validation import StudyConfig as BreakoutConfig
from crypto_regime_backtest.breakout_orderbook_confirmation_validation import (
    DEPTH_Z_MIN_PERIODS,
    build_confirmed_breakout_frame,
)


def test_depth_zscore_uses_prior_days_only():
    price_idx = pd.date_range("2023-01-01", periods=40, freq="D", tz="UTC")
    closes = [100.0] * 38 + [101.0, 130.0]
    prior_imbalances = [0.1 + 0.01 * (i % 5) for i in range(39)]
    price = pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": 1.0,
        },
        index=price_idx,
    )
    depth = pd.DataFrame(
        {
            "imbalance": prior_imbalances + [5.0],
            "n_snapshots": 288,
        },
        index=price_idx,
    )

    frame = build_confirmed_breakout_frame(
        price_1d=price,
        depth=depth,
        breakout_config=BreakoutConfig(),
        depth_z_window=90,
        depth_z_min_periods=DEPTH_Z_MIN_PERIODS,
        depth_z_threshold=0.5,
    )

    prior = pd.Series(prior_imbalances, index=price_idx[:-1]).shift(1)
    expected = (
        prior_imbalances[-1] - prior.rolling(90, min_periods=DEPTH_Z_MIN_PERIODS).mean().iloc[-1]
    ) / prior.rolling(90, min_periods=DEPTH_Z_MIN_PERIODS).std(ddof=1).iloc[-1]
    assert abs(frame.loc[price_idx[-2], "depth_z"] - expected) < 1e-12
    assert frame.loc[price_idx[-1], "depth_z"] > 10.0
    assert bool(frame.loc[price_idx[-1], "depth_confirmed_breakout"])


def test_combined_signal_requires_both_breakout_and_positive_depth_confirmation():
    idx = pd.date_range("2023-01-01", periods=45, freq="D", tz="UTC")
    closes = [100.0] * 40 + [99.0, 99.0, 99.0, 99.0, 130.0]
    price = pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": 1.0,
        },
        index=idx,
    )
    depth = pd.DataFrame(
        {
            "imbalance": [0.2] * 44 + [-3.0],
            "n_snapshots": 288,
        },
        index=idx,
    )

    frame = build_confirmed_breakout_frame(
        price_1d=price,
        depth=depth,
        breakout_config=BreakoutConfig(),
        depth_z_window=90,
        depth_z_min_periods=DEPTH_Z_MIN_PERIODS,
        depth_z_threshold=0.5,
    )

    assert bool(frame.loc[idx[-1], "breakout"])
    assert frame.loc[idx[-1], "depth_z"] < 0.0
    assert not bool(frame.loc[idx[-1], "depth_confirmed_breakout"])
