import pandas as pd

from crypto_regime_backtest.btc_wick_odds_validation import StrategySpec, build_btc_wick_signals


PRIMARY_SPEC = StrategySpec(
    name="test",
    wick_window_hours=3,
    drawdown_threshold=-0.10,
    support_delta_floor=-0.02,
    bounce_threshold=0.03,
    bounce_window_hours=3,
    hold_hours=4,
    cooldown_hours=2,
)


def test_build_btc_wick_signals_uses_prior_high_excluding_current_bar_and_next_open_entry():
    timestamps = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    btc = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100, 110, 120, 110, 108, 111, 112, 113, 114, 115],
            "high": [100, 110, 120, 111, 109, 112, 113, 114, 115, 116],
            "low": [99, 109, 119, 95, 107, 110, 111, 112, 113, 114],
            "close": [100, 110, 120, 96, 108, 112, 113, 114, 115, 116],
        }
    )
    support = pd.DataFrame(
        {
            "timestamp": timestamps,
            "support_mean": [0.5] * len(timestamps),
            "support_delta_24h": [0.0] * len(timestamps),
        }
    )

    signals = build_btc_wick_signals(btc, support, PRIMARY_SPEC)

    assert len(signals) == 1
    assert signals.iloc[0]["timestamp"] == timestamps[3]
    assert signals.iloc[0]["confirmation_time"] == timestamps[4]
    assert signals.iloc[0]["entry_time"] == timestamps[5]
    assert signals.iloc[0]["exit_time"] == timestamps[5] + pd.Timedelta(hours=int(4))
    assert abs(signals.iloc[0]["wick_drawdown"] - (95 / 120 - 1)) < 1e-12


def test_build_btc_wick_signals_respects_support_floor_and_requires_reclaim():
    timestamps = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    btc = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100, 110, 120, 110, 96, 97, 98, 99, 100, 101],
            "high": [100, 110, 120, 111, 97, 98, 99, 100, 101, 102],
            "low": [99, 109, 119, 95, 95, 95, 96, 97, 98, 99],
            "close": [100, 110, 120, 96, 96, 97, 98, 99, 100, 101],
        }
    )
    support_bad = pd.DataFrame(
        {
            "timestamp": timestamps,
            "support_mean": [0.5] * len(timestamps),
            "support_delta_24h": [0.0, 0.0, 0.0, -0.03, -0.03, -0.03, -0.03, -0.03, -0.03, -0.03],
        }
    )
    assert build_btc_wick_signals(btc, support_bad, PRIMARY_SPEC).empty

    support_ok = support_bad.copy()
    support_ok["support_delta_24h"] = 0.0
    assert build_btc_wick_signals(btc, support_ok, PRIMARY_SPEC).empty
