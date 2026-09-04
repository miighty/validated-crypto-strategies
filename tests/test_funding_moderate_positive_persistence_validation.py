import pandas as pd

from crypto_regime_backtest.funding_moderate_positive_persistence_validation import (
    StrategySpec,
    build_signal_panel,
)
from crypto_regime_backtest.funding_negative_panel_validation import AssetFrames


def test_build_signal_panel_selects_single_best_asset_inside_bucket_and_applies_cooldown():
    timestamps = pd.date_range("2025-01-01", periods=120, freq="h", tz="UTC")
    prices = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": 100.0,
            "close": 100.0,
        }
    )
    market = {
        "BTC": AssetFrames(
            price=prices.copy(),
            funding=pd.DataFrame(
                {
                    "timestamp": [timestamps[9], timestamps[59]],
                    "funding_rate": [0.0002, 0.0004],
                    "mark_price": [100.0, 100.0],
                    "source_symbol": ["BTCUSDT", "BTCUSDT"],
                }
            ),
        ),
        "ETH": AssetFrames(
            price=prices.copy(),
            funding=pd.DataFrame(
                {
                    "timestamp": [timestamps[9], timestamps[20], timestamps[30]],
                    "funding_rate": [0.00049, 0.0008, 0.0003],
                    "mark_price": [100.0, 100.0, 100.0],
                    "source_symbol": ["ETHUSDT", "ETHUSDT", "ETHUSDT"],
                }
            ),
        ),
    }
    spec = StrategySpec(
        name="test",
        min_funding_threshold=0.0001,
        max_funding_threshold=0.0005,
        hold_hours=8,
        cooldown_hours=24,
    )

    signals = build_signal_panel(market, spec)

    assert list(signals["asset"]) == ["ETH", "BTC"]
    assert list(signals["entry_time"]) == [timestamps[10], timestamps[60]]
    assert list(signals["exit_time"]) == [timestamps[18], timestamps[68]]
    assert signals.iloc[0]["funding_rate"] == 0.00049


def test_build_signal_panel_excludes_rates_outside_bucket_and_missing_windows():
    timestamps = pd.date_range("2025-01-01", periods=24, freq="h", tz="UTC")
    prices = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": 100.0,
            "close": 100.0,
        }
    )
    market = {
        "BTC": AssetFrames(
            price=prices,
            funding=pd.DataFrame(
                {
                    "timestamp": [timestamps[3], timestamps[-2]],
                    "funding_rate": [0.00005, 0.0002],
                    "mark_price": [100.0, 100.0],
                    "source_symbol": ["BTCUSDT", "BTCUSDT"],
                }
            ),
        )
    }
    spec = StrategySpec(
        name="test",
        min_funding_threshold=0.0001,
        max_funding_threshold=0.0005,
        hold_hours=8,
        cooldown_hours=24,
    )

    signals = build_signal_panel(market, spec)

    assert signals.empty
