import pandas as pd

from crypto_regime_backtest.fed_hawkish_btc_validation import StrategySpec, build_signal_panel


def test_build_signal_panel_uses_completed_24h_fall_and_next_open_entry():
    timestamps = pd.date_range("2024-01-01", periods=30, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "slug": ["fed-rate-cut-by-march-20"] * 30,
            "yes_price": [0.60] * 24 + [0.48, 0.47, 0.46, 0.45, 0.44, 0.43],
            "trade_count": [1] * 30,
            "traded_notional": [10.0] * 30,
        }
    )
    price_index = pd.date_range("2024-01-01", periods=200, freq="h", tz="UTC")
    spec = StrategySpec(
        name="test",
        lookback_hours=24,
        delta_threshold=0.12,
        level_threshold=0.45,
        hold_hours=72,
        cooldown_hours=0,
    )

    signals = build_signal_panel(frame, price_index, spec)

    assert len(signals) == 1
    assert signals.iloc[0]["signal_time"] == timestamps[27]
    assert signals.iloc[0]["entry_time"] == timestamps[28]
    assert signals.iloc[0]["exit_time"] == timestamps[28] + pd.Timedelta(hours=72)
    assert abs(signals.iloc[0]["odds_delta"] + 0.15) < 1e-12


def test_build_signal_panel_applies_global_cooldown_across_market_slugs():
    timestamps = pd.date_range("2024-01-01", periods=40, freq="h", tz="UTC")
    frame = pd.concat(
        [
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "slug": ["fed-rate-cut-by-march-20"] * 40,
                    "yes_price": [0.60] * 24 + [0.44] * 16,
                    "trade_count": [1] * 40,
                    "traded_notional": [10.0] * 40,
                }
            ),
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "slug": ["fed-rate-cut-by-may-1"] * 40,
                    "yes_price": [0.62] * 24 + [0.43] * 16,
                    "trade_count": [1] * 40,
                    "traded_notional": [10.0] * 40,
                }
            ),
        ],
        ignore_index=True,
    )
    price_index = pd.date_range("2024-01-01", periods=240, freq="h", tz="UTC")
    spec = StrategySpec(name="test", lookback_hours=24, delta_threshold=0.12, level_threshold=0.45, hold_hours=72, cooldown_hours=24)

    signals = build_signal_panel(frame, price_index, spec)

    assert len(signals) == 1
    assert signals.iloc[0]["slug"] == "fed-rate-cut-by-march-20"
