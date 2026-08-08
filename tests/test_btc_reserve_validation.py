import pandas as pd

from crypto_regime_backtest.btc_reserve_validation import StrategySpec, build_btc_reserve_signals


def test_build_btc_reserve_signals_uses_completed_window_and_next_open_entry():
    timestamps = pd.date_range("2025-03-07", periods=60, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.25] * 48 + [0.31, 0.32, 0.33, 0.34, 0.35, 0.36, 0.37, 0.38, 0.39, 0.40, 0.41, 0.42],
        }
    )
    spec = StrategySpec(name="test", lookback_hours=48, delta_threshold=0.05, level_threshold=0.35, hold_hours=168)
    signals = build_btc_reserve_signals(frame, spec)
    assert len(signals) == 8
    assert signals.iloc[0]["timestamp"] == timestamps[52]
    assert signals.iloc[0]["entry_time"] == timestamps[53]
    assert signals.iloc[0]["exit_time"] == timestamps[53] + pd.Timedelta(hours=168)
    assert (signals["delta_window"] >= 0.05).all()


def test_build_btc_reserve_signals_respects_level_gate():
    timestamps = pd.date_range("2025-03-07", periods=60, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.25] * 48 + [0.29, 0.30, 0.31, 0.32, 0.33, 0.34, 0.34, 0.34, 0.34, 0.34, 0.34, 0.34],
        }
    )
    spec = StrategySpec(name="test", lookback_hours=48, delta_threshold=0.05, level_threshold=0.35, hold_hours=168)
    signals = build_btc_reserve_signals(frame, spec)
    assert signals.empty
