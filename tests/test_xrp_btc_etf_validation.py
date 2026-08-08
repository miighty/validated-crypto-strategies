import pandas as pd

from crypto_regime_backtest.xrp_btc_etf_validation import StrategySpec, build_xrp_etf_signals


def test_build_xrp_etf_signals_uses_completed_24h_move_and_next_open_entry():
    timestamps = pd.date_range("2025-01-01", periods=30, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.40] * 24 + [0.56, 0.57, 0.58, 0.59, 0.60, 0.61],
        }
    )
    spec = StrategySpec(name="test", delta_threshold=0.10, level_threshold=0.55, hold_hours=72)
    signals = build_xrp_etf_signals(frame, spec)
    assert len(signals) == 6
    assert signals.iloc[0]["timestamp"] == timestamps[24]
    assert signals.iloc[0]["entry_time"] == timestamps[25]
    assert signals.iloc[0]["exit_time"] == timestamps[25] + pd.Timedelta(hours=72)
    assert (signals["delta_24h"] >= 0.10).all()


def test_build_xrp_etf_signals_respects_level_gate():
    timestamps = pd.date_range("2025-01-01", periods=30, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.40] * 24 + [0.50, 0.51, 0.52, 0.53, 0.54, 0.55],
        }
    )
    spec = StrategySpec(name="test", delta_threshold=0.10, level_threshold=0.55, hold_hours=72)
    signals = build_xrp_etf_signals(frame, spec)
    assert len(signals) == 1
    assert signals.iloc[0]["timestamp"] == timestamps[29]
    assert signals.iloc[0]["yes_price"] == 0.55
