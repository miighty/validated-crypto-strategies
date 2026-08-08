import pandas as pd

from crypto_regime_backtest.funding_negative_panel_validation import (
    AssetFrames,
    StrategySpec,
    build_signal_panel,
)


def test_build_signal_panel_selects_single_most_negative_asset_per_timestamp_and_applies_cooldown():
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
                    "funding_rate": [-0.0006, -0.0008],
                    "mark_price": [100.0, 100.0],
                    "source_symbol": ["BTCUSDT", "BTCUSDT"],
                }
            ),
        ),
        "ETH": AssetFrames(
            price=prices.copy(),
            funding=pd.DataFrame(
                {
                    "timestamp": [timestamps[9], timestamps[20]],
                    "funding_rate": [-0.0012, -0.0007],
                    "mark_price": [100.0, 100.0],
                    "source_symbol": ["ETHUSDT", "ETHUSDT"],
                }
            ),
        ),
    }
    spec = StrategySpec(name="test", funding_threshold=-0.0005, hold_hours=24, cooldown_hours=24)

    signals = build_signal_panel(market, spec)

    assert list(signals["asset"]) == ["ETH", "BTC"]
    assert list(signals["entry_time"]) == [timestamps[10], timestamps[60]]
    assert list(signals["exit_time"]) == [timestamps[34], timestamps[84]]
    assert signals.iloc[0]["funding_rate"] == -0.0012


def test_build_signal_panel_drops_signals_without_full_price_window():
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
                    "timestamp": [timestamps[-2]],
                    "funding_rate": [-0.0009],
                    "mark_price": [100.0],
                    "source_symbol": ["BTCUSDT"],
                }
            ),
        )
    }
    spec = StrategySpec(name="test", funding_threshold=-0.0005, hold_hours=8, cooldown_hours=24)

    signals = build_signal_panel(market, spec)

    assert signals.empty
