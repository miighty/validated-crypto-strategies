import pandas as pd

from crypto_regime_backtest.btc_etf_validation import StrategySpec, build_btc_etf_signals


def test_build_btc_etf_signals_uses_completed_window_and_next_open_entry():
    timestamps = pd.date_range("2023-10-01", periods=30, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.50] * 24 + [0.601, 0.61, 0.62, 0.63, 0.64, 0.65],
        }
    )
    spec = StrategySpec(name="test", lookback_hours=24, delta_threshold=0.10, level_threshold=0.60, hold_hours=72)
    signals = build_btc_etf_signals(frame, spec)
    assert len(signals) == 6
    assert signals.iloc[0]["timestamp"] == timestamps[24]
    assert signals.iloc[0]["entry_time"] == timestamps[25]
    assert signals.iloc[0]["exit_time"] == timestamps[25] + pd.Timedelta(hours=72)
    assert (signals["delta_window"] >= 0.10).all()


def test_build_btc_etf_signals_respects_level_gate():
    timestamps = pd.date_range("2023-10-01", periods=30, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.50] * 24 + [0.55, 0.56, 0.57, 0.58, 0.59, 0.59],
        }
    )
    spec = StrategySpec(name="test", lookback_hours=24, delta_threshold=0.10, level_threshold=0.60, hold_hours=72)
    signals = build_btc_etf_signals(frame, spec)
    assert signals.empty
