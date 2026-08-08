from __future__ import annotations

import pandas as pd

from crypto_regime_backtest.btc_alt_response_validation import (
    MIN_HOLDOUT_TRADES,
    SimulationResult,
    build_daily_contribution_schedule,
    classify_verdict,
    event_returns_from_signal,
)


def test_build_daily_contribution_schedule_uses_hour_slots() -> None:
    timestamps = pd.date_range("2025-01-01", periods=48, freq="1h", tz="UTC")
    frame = pd.DataFrame({"timestamp": timestamps})
    schedule = build_daily_contribution_schedule(frame, initial_capital=100.0, contribution_hour_utc=9)
    assert len(schedule) == 2
    assert [pd.Timestamp(timestamp).hour for timestamp in schedule.index] == [9, 9]
    assert schedule.sum() == 100.0


def test_event_returns_from_signal_prevents_overlap() -> None:
    timestamps = pd.date_range("2025-01-01", periods=8, freq="1h", tz="UTC")
    merged = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100, 101, 102, 103, 104, 105, 106, 107],
            "close": [100, 101, 102, 103, 104, 105, 106, 107],
        }
    )
    signal = pd.Series([False, True, True, False, True, False, False, False])
    returns = event_returns_from_signal(merged, signal, hold_hours=2, cooldown_hours=1)
    assert len(returns) == 1


def test_classify_verdict_rejects_sparse_holdout_even_with_positive_total() -> None:
    primary = SimulationResult(
        summary={"terminal_value": 12_000.0, "trade_count": MIN_HOLDOUT_TRADES + 5, "mean_trade_return": 0.03},
        ledger=pd.DataFrame({"net_trade_return": [0.03] * (MIN_HOLDOUT_TRADES + 5)}),
        equity=pd.DataFrame(),
        partition_summary=pd.DataFrame(
            [
                {"partition": "holdout_2025_onward", "trade_count": 5, "mean_trade_return": 0.02},
            ]
        ),
    )
    daily = SimulationResult(summary={"terminal_value": 11_000.0}, ledger=pd.DataFrame(), equity=pd.DataFrame(), partition_summary=pd.DataFrame())
    weekly = SimulationResult(summary={"terminal_value": 10_500.0}, ledger=pd.DataFrame(), equity=pd.DataFrame(), partition_summary=pd.DataFrame())
    hostile = [
        {"check": "btc_shock_without_lag_filter", "mean_trade_return": 0.01},
        {"check": "same_asset_momentum", "mean_trade_return": 0.01},
        {"check": "matched_random", "mean_trade_return": 0.0},
    ]
    assert classify_verdict(primary, daily, weekly, hostile) == "Rejected"
