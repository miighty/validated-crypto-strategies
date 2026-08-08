import pandas as pd

from crypto_regime_backtest.btc_drawdown_dca_validation import (
    PRIMARY_DELAY_HOURS,
    StrategySpec,
    build_daily_contribution_schedule,
    detect_drawdown_signals,
    simulate_drawdown_strategy,
)


def test_detect_drawdown_signals_waits_for_completed_close_and_next_open():
    index = pd.date_range("2024-01-01", periods=80, freq="h", tz="UTC")
    close = [100.0] * 72 + [69.0] + [70.0] * 7
    frame = pd.DataFrame(
        {
            "open": close,
            "high": [c + 1 for c in close],
            "low": [c - 1 for c in close],
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )
    signals = detect_drawdown_signals(frame, threshold=0.30, window_hours=72, delay_hours=1)
    assert len(signals) >= 1
    assert signals.iloc[0]["signal_time"] == index[72]
    assert signals.iloc[0]["entry_time"] == index[73]


def test_schedule_spends_identical_total_capital():
    index = pd.date_range("2024-01-01", periods=24 * 14, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1.0,
        },
        index=index,
    )
    schedule = build_daily_contribution_schedule(frame, initial_capital=1000.0, contribution_hour_utc=9)
    assert abs(float(schedule.sum()) - 1000.0) < 1e-9
    assert len(schedule) == 14


def test_drawdown_strategy_uses_next_open_and_cooldown():
    index = pd.date_range("2024-01-01", periods=120, freq="h", tz="UTC")
    close = [100.0] * 73 + [69.0] + [68.0] * 10 + [100.0] * 36
    frame = pd.DataFrame(
        {
            "open": close,
            "high": [c + 1 for c in close],
            "low": [c - 1 for c in close],
            "close": close,
            "volume": 1.0,
        },
        index=index,
    )
    schedule = build_daily_contribution_schedule(frame, initial_capital=1400.0, contribution_hour_utc=9)
    result = simulate_drawdown_strategy(
        frame,
        schedule,
        one_way_cost=0.0,
        spec=StrategySpec("test", threshold=0.30, window_hours=72, delay_hours=PRIMARY_DELAY_HOURS, cooldown_hours=24),
    )
    assert len(result.ledger) == 1
    assert result.ledger.iloc[0]["timestamp"] == index[74]
