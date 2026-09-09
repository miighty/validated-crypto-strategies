from __future__ import annotations

import pandas as pd

from crypto_regime_backtest import move_riskoff_overlay_validation as move


def test_build_state_uses_prior_only_zscore_and_hysteresis() -> None:
    dates = pd.date_range("2020-01-01", periods=270, freq="D", tz="UTC")
    values = [100.0] * 252 + [200.0, 210.0, 120.0, 110.0, 100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0, 91.0, 90.0, 89.0, 88.0, 87.0]
    df = pd.DataFrame({"date": dates, "move": values})

    state = move.build_state(df)

    first_signal_day = pd.Timestamp("2020-09-09", tz="UTC")
    assert state.loc[first_signal_day, "mean_prior"] == 100.0
    assert bool(state.loc[first_signal_day, "risk_on_signal_close"]) is False
    assert bool(state.loc[first_signal_day, "risk_on_actionable"]) is True
    assert bool(state.loc[pd.Timestamp("2020-09-10", tz="UTC"), "risk_on_actionable"]) is False


def test_simulate_enters_and_exits_on_allowed_state() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    spot = pd.DataFrame({"open": [100.0, 110.0, 120.0, 130.0], "close": [110.0, 120.0, 130.0, 140.0]}, index=idx)
    allowed = pd.Series([True, True, False, True], index=idx)

    eq, trades = move.simulate(spot, allowed, 0.0)

    assert len(trades) == 2
    assert trades.iloc[0]["entry_time"] == idx[0]
    assert trades.iloc[0]["exit_time"] == idx[2]
    assert eq["equity"].iloc[-1] > 10_000.0
